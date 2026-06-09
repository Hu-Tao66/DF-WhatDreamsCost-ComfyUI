import json
import logging
import math
from uuid import uuid4

import torch

import comfy.model_management
from comfy_api.latest import io

from .ltx_director import (
    GuideData,
    _build_combined_audio,
    _encode_relay,
    _load_image_tensor,
)
from .ltx_auto_director import (
    MAX_AUTO_SEGMENTS,
    _empty_audio_latent,
    _normalize_lengths,
    _parse_prompts,
    _process_image_tensor,
    _strengths_for_count,
    _transitions_for_count,
    _to_float,
    _to_int,
    _to_str,
)

log = logging.getLogger(__name__)

PARSE_MODE_ALIASES = {
    "auto": "auto",
    "\u81ea\u52a8": "auto",
    "json": "json",
    "JSON": "json",
    "\u7ed3\u6784\u5316 JSON": "json",
    "numbered_text": "numbered_text",
    "\u7f16\u53f7\u6587\u672c": "numbered_text",
}

RESIZE_METHOD_ALIASES = {
    "maintain aspect ratio": "maintain aspect ratio",
    "\u4fdd\u6301\u6bd4\u4f8b": "maintain aspect ratio",
    "stretch to fit": "stretch to fit",
    "\u62c9\u4f38\u586b\u6ee1": "stretch to fit",
    "pad": "pad",
    "\u7559\u767d\u586b\u5145": "pad",
    "crop": "crop",
    "\u88c1\u526a\u586b\u6ee1": "crop",
}

GRID_LAYOUT_ALIASES = {
    "auto": "auto",
    "\u81ea\u52a8": "auto",
    "\u81ea\u52a8\u68c0\u6d4b": "auto",
    "2x3": "2x3",
    "2 x 3": "2x3",
    "2\u5217 x 3\u884c": "2x3",
    "2\u5217x3\u884c": "2x3",
    "2 columns x 3 rows": "2x3",
    "3x2": "3x2",
    "3 x 2": "3x2",
    "3\u5217 x 2\u884c": "3x2",
    "3\u5217x2\u884c": "3x2",
    "3 columns x 2 rows": "3x2",
}

GRID_MODE_OPTIONS = ["2x2 \u56db\u5bab\u683c", "3x2 \u516d\u5bab\u683c", "3x3 \u4e5d\u5bab\u683c"]
SHOT_ASPECT_OPTIONS = ["\u81ea\u52a8 / \u4fdd\u6301\u5355\u683c\u6bd4\u4f8b", "16:9 \u6a2a\u5c4f", "9:16 \u7ad6\u5c4f", "1:1 \u65b9\u56fe"]

GRID_MODE_ALIASES = {
    "2x2": (2, 2),
    "2x2 \u56db\u5bab\u683c": (2, 2),
    "\u56db\u5bab\u683c": (2, 2),
    "4": (2, 2),
    "3x2": (3, 2),
    "2x3": (3, 2),
    "3x2 \u516d\u5bab\u683c": (3, 2),
    "2x3 \u516d\u5bab\u683c": (3, 2),
    "\u516d\u5bab\u683c": (3, 2),
    "6": (3, 2),
    "3x3": (3, 3),
    "3x3 \u4e5d\u5bab\u683c": (3, 3),
    "\u4e5d\u5bab\u683c": (3, 3),
    "9": (3, 3),
}

SHOT_ASPECT_ALIASES = {
    "": None,
    "auto": None,
    "\u81ea\u52a8": None,
    "\u81ea\u52a8 / \u4fdd\u6301\u5355\u683c\u6bd4\u4f8b": None,
    "keep": None,
    "16:9": 16 / 9,
    "16:9 \u6a2a\u5c4f": 16 / 9,
    "\u6a2a\u5c4f": 16 / 9,
    "9:16": 9 / 16,
    "9:16 \u7ad6\u5c4f": 9 / 16,
    "\u7ad6\u5c4f": 9 / 16,
    "1:1": 1.0,
    "1:1 \u65b9\u56fe": 1.0,
    "\u65b9\u56fe": 1.0,
}

DEFAULT_BORDER_SAFE_CROP_PX = 8
MAX_BORDER_SAFE_CROP_PX = 48
DEFAULT_BORDER_SENSITIVITY = 0.10
GRID_MAX_SEGMENTS = 9


def _normalize_choice(value, aliases, default):
    return aliases.get(_to_str(value).strip(), default)


def _grid_dimensions(grid_mode):
    return GRID_MODE_ALIASES.get(_to_str(grid_mode).strip(), (3, 2))


def _shot_aspect_ratio(shot_aspect):
    return SHOT_ASPECT_ALIASES.get(_to_str(shot_aspect).strip(), None)


def _safe_crop_strength(value):
    return max(0.0, min(5.0, _to_float(value, 1.0)))


def _fallback_prompt(index: int) -> str:
    return f"\u7b2c {index + 1} \u4e2a\u5206\u955c\u4fdd\u6301\u7535\u5f71\u611f\u8fde\u7eed\u8fd0\u52a8\u3002"


def _to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = _to_str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "on", "\u662f", "\u5f00", "\u542f\u7528"}:
        return True
    if text in {"false", "0", "no", "n", "off", "\u5426", "\u5173", "\u7981\u7528"}:
        return False
    return default


def _repair_border_settings(border_sensitivity, border_crop_px):
    sensitivity = _to_float(border_sensitivity, DEFAULT_BORDER_SENSITIVITY)
    crop_px = _to_int(border_crop_px, DEFAULT_BORDER_SAFE_CROP_PX)

    if not math.isfinite(float(sensitivity)) or sensitivity < 0.01 or sensitivity > 0.45:
        if sensitivity > 1 and crop_px == DEFAULT_BORDER_SAFE_CROP_PX:
            crop_px = _to_int(sensitivity, DEFAULT_BORDER_SAFE_CROP_PX)
        sensitivity = DEFAULT_BORDER_SENSITIVITY

    return max(0.01, min(0.45, float(sensitivity))), max(0, int(crop_px))


def _image_segment_count(timeline):
    return len([
        seg for seg in timeline.get("segments", [])
        if seg.get("type", "image") == "image"
    ])


def _axis_border_mask(storyboard_images, axis, sensitivity):
    image = storyboard_images[0].detach().float().clamp(0.0, 1.0)
    max_channel = image.max(dim=-1).values
    min_channel = image.min(dim=-1).values
    luminance = (
        image[..., 0] * 0.2126
        + image[..., 1] * 0.7152
        + image[..., 2] * 0.0722
    )
    saturation = max_channel - min_channel
    if axis == "x":
        luminance_projection = luminance.mean(dim=0)
        saturation_projection = saturation.mean(dim=0)
    else:
        luminance_projection = luminance.mean(dim=1)
        saturation_projection = saturation.mean(dim=1)

    sensitivity = max(0.01, min(0.45, float(sensitivity)))
    bright_threshold = max(0.60, 1.0 - max(sensitivity, 0.16) * 2.2)
    saturation_threshold = min(0.40, 0.28 + sensitivity * 0.4)
    border_like = (
        ((luminance_projection >= bright_threshold) | (luminance_projection <= sensitivity))
        & (saturation_projection <= saturation_threshold)
    )
    return border_like.cpu().tolist()


def _safe_border_crop_px(cell_size, border_crop_px):
    cell_size = max(1.0, float(cell_size))
    try:
        requested_value = float(border_crop_px)
        requested = int(round(requested_value)) if math.isfinite(requested_value) else 0
    except (TypeError, ValueError):
        requested = 0
    requested = max(0, requested)
    automatic = max(DEFAULT_BORDER_SAFE_CROP_PX, int(round(cell_size * 0.022)))
    safe_crop = max(requested, automatic)
    max_safe = max(0, min(MAX_BORDER_SAFE_CROP_PX, int(cell_size // 5)))
    return min(safe_crop, max_safe)


def _mask_runs(mask, start, end):
    runs = []
    index = max(0, int(start))
    end = min(len(mask), int(end))
    while index < end:
        while index < end and not mask[index]:
            index += 1
        run_start = index
        while index < end and mask[index]:
            index += 1
        if index > run_start:
            runs.append((run_start, index))
    return runs


def _axis_boundary_band(mask, expected, axis_len, cell_size):
    expected = max(0, min(int(axis_len), int(round(expected))))
    search_radius = max(2, min(64, int(cell_size) // 8 if cell_size else 2))
    max_band_width = max(2, min(64, int(cell_size) // 6 if cell_size else 2))

    if expected <= 0:
        runs = _mask_runs(mask, 0, min(axis_len, search_radius + 1))
        if runs and runs[0][0] <= 2:
            return 0, min(runs[0][1], max_band_width)
        return 0, 0

    if expected >= axis_len:
        runs = _mask_runs(mask, max(0, axis_len - search_radius - 1), axis_len)
        if runs and axis_len - runs[-1][1] <= 2:
            return max(axis_len - max_band_width, runs[-1][0]), axis_len
        return axis_len, axis_len

    start = max(0, expected - search_radius)
    end = min(axis_len, expected + search_radius + 1)
    runs = [run for run in _mask_runs(mask, start, end) if run[1] - run[0] <= max_band_width]
    if not runs:
        return expected, expected

    def distance_to_expected(run):
        if run[0] <= expected < run[1]:
            return 0
        return min(abs(expected - run[0]), abs(expected - (run[1] - 1)))

    best = min(runs, key=distance_to_expected)
    if distance_to_expected(best) > search_radius:
        return expected, expected
    return best


def _axis_boundary_score(mask, expected, axis_len, cell_size):
    start, end = _axis_boundary_band(mask, expected, axis_len, cell_size)
    if end <= start:
        return 0.0
    width = max(1, end - start)
    center = (start + end - 1) / 2.0
    distance = abs(float(expected) - center)
    radius = max(1.0, min(64.0, float(cell_size) / 8.0 if cell_size else 1.0))
    return max(0.0, 1.0 - distance / radius) + min(width, 12) / 12.0


def _layout_score(storyboard_images, cols, rows, sensitivity):
    _, height, width, _ = storyboard_images.shape
    x_mask = _axis_border_mask(storyboard_images, "x", sensitivity)
    y_mask = _axis_border_mask(storyboard_images, "y", sensitivity)
    score = 0.0
    for index in range(1, int(cols)):
        expected = round(index * int(width) / int(cols))
        score += _axis_boundary_score(x_mask, expected, int(width), int(width) / int(cols))
    for index in range(1, int(rows)):
        expected = round(index * int(height) / int(rows))
        score += _axis_boundary_score(y_mask, expected, int(height), int(height) / int(rows))
    return score


def _resolve_grid_layout(storyboard_images, grid_layout, border_sensitivity):
    grid_layout = _normalize_choice(grid_layout, GRID_LAYOUT_ALIASES, "auto")
    if grid_layout == "2x3":
        return 2, 3
    if grid_layout == "3x2":
        return 3, 2

    if storyboard_images is None or int(storyboard_images.shape[0]) != 1:
        return 3, 2

    score_2x3 = _layout_score(storyboard_images, 2, 3, border_sensitivity)
    score_3x2 = _layout_score(storyboard_images, 3, 2, border_sensitivity)
    if score_2x3 > score_3x2 + 0.25:
        return 2, 3
    return 3, 2


def _axis_intervals(storyboard_images, parts, axis, sensitivity, border_crop_px):
    axis_len = int(storyboard_images.shape[2] if axis == "x" else storyboard_images.shape[1])
    parts = max(1, int(parts))
    if parts == 1:
        return [(0, axis_len)]

    mask = _axis_border_mask(storyboard_images, axis, sensitivity)
    cell_size = max(1, axis_len / parts)
    bands = [
        _axis_boundary_band(mask, round(index * axis_len / parts), axis_len, cell_size)
        for index in range(parts + 1)
    ]

    intervals = []
    safe_crop = _safe_border_crop_px(cell_size, border_crop_px)
    for index in range(parts):
        fallback_start = int(round(index * axis_len / parts))
        fallback_end = int(round((index + 1) * axis_len / parts))
        left_band = bands[index]
        right_band = bands[index + 1]
        start = int(left_band[1])
        end = int(right_band[0])

        if end <= start:
            start, end = fallback_start, fallback_end

        start = max(0, min(axis_len - 1, start))
        end = max(start + 1, min(axis_len, end))
        if fallback_end - fallback_start > safe_crop * 2:
            start = max(start, fallback_start + safe_crop)
            end = min(end, fallback_end - safe_crop)
            # Detected divider bands often have a small glow/antialias halo just inside
            # the content cells. Step inward from internal dividers instead of cropping
            # exactly at the detected band edge.
            if index > 0 and left_band[1] > left_band[0]:
                start = max(start, min(axis_len - 1, int(left_band[1]) + safe_crop))
            if index + 1 < parts and right_band[1] > right_band[0]:
                end = min(end, max(0, int(right_band[0]) - safe_crop))
            if end <= start:
                start = max(0, min(axis_len - 1, fallback_start + safe_crop))
                end = max(start + 1, min(axis_len, fallback_end - safe_crop))
        intervals.append((start, end))

    return intervals


def _center_crop_to(tensor, target_h, target_w):
    height = int(tensor.shape[1])
    width = int(tensor.shape[2])
    y0 = max(0, (height - target_h) // 2)
    x0 = max(0, (width - target_w) // 2)
    return tensor[:, y0:y0 + target_h, x0:x0 + target_w, :]


def _resize_crop_to(tensor, target_h, target_w):
    target_h = max(1, int(target_h))
    target_w = max(1, int(target_w))
    if int(tensor.shape[1]) == target_h and int(tensor.shape[2]) == target_w:
        return tensor
    image = tensor.permute(0, 3, 1, 2)
    image = torch.nn.functional.interpolate(
        image,
        size=(target_h, target_w),
        mode="bilinear",
        align_corners=False,
    )
    return image.permute(0, 2, 3, 1).clamp(0.0, 1.0)


def _crop_to_aspect_ratio(tensor, target_ratio):
    if not target_ratio or target_ratio <= 0:
        return tensor

    height = int(tensor.shape[1])
    width = int(tensor.shape[2])
    if height <= 1 or width <= 1:
        return tensor

    current_ratio = width / height
    if current_ratio > target_ratio:
        target_w = max(1, int(round(height * target_ratio)))
        return _center_crop_to(tensor, height, min(width, target_w))
    if current_ratio < target_ratio:
        target_h = max(1, int(round(width / target_ratio)))
        return _center_crop_to(tensor, min(height, target_h), width)
    return tensor


def _target_cell_size(source_width, source_height, cols, rows, target_ratio=None):
    cell_h = max(1, int(round(int(source_height) / max(1, int(rows)))))
    cell_w = max(1, int(round(int(source_width) / max(1, int(cols)))))
    if not target_ratio or target_ratio <= 0:
        return cell_h, cell_w

    current_ratio = cell_w / cell_h
    if current_ratio > target_ratio:
        cell_w = max(1, int(round(cell_h * target_ratio)))
    elif current_ratio < target_ratio:
        cell_h = max(1, int(round(cell_w / target_ratio)))
    return cell_h, cell_w


def _border_like_ratio(edge, sensitivity):
    edge = edge.detach().float().clamp(0.0, 1.0)
    max_channel = edge.max(dim=-1).values
    min_channel = edge.min(dim=-1).values
    luminance = (
        edge[..., 0] * 0.2126
        + edge[..., 1] * 0.7152
        + edge[..., 2] * 0.0722
    )
    saturation = max_channel - min_channel
    bright_threshold = max(0.60, 1.0 - max(float(sensitivity), 0.16) * 2.2)
    saturation_threshold = min(0.40, 0.28 + float(sensitivity) * 0.4)
    border_like = (luminance >= bright_threshold) & (saturation <= saturation_threshold)
    return float(border_like.float().mean().item())


def _trim_border_like_edges(crop, sensitivity, border_crop_px):
    height = int(crop.shape[1])
    width = int(crop.shape[2])
    if height <= 4 or width <= 4:
        return crop

    safe_crop = _safe_border_crop_px(min(height, width), border_crop_px)
    max_trim = max(8, int(min(height, width) * 0.05), safe_crop + 8)
    max_trim = min(max_trim, max(0, min(height, width) // 6), 48)
    if max_trim <= 0:
        return crop

    threshold = 0.42
    left = 0
    while left < max_trim and left < width - 2:
        if _border_like_ratio(crop[:, :, left:left + 1, :], sensitivity) < threshold:
            break
        left += 1

    right = 0
    while right < max_trim and right < width - left - 2:
        if _border_like_ratio(crop[:, :, width - right - 1:width - right, :], sensitivity) < threshold:
            break
        right += 1

    top = 0
    while top < max_trim and top < height - 2:
        if _border_like_ratio(crop[:, top:top + 1, :, :], sensitivity) < threshold:
            break
        top += 1

    bottom = 0
    while bottom < max_trim and bottom < height - top - 2:
        if _border_like_ratio(crop[:, height - bottom - 1:height - bottom, :, :], sensitivity) < threshold:
            break
        bottom += 1

    x0 = left
    x1 = width - right
    y0 = top
    y1 = height - bottom
    if x1 - x0 < 8 or y1 - y0 < 8:
        return crop
    return crop[:, y0:y1, x0:x1, :]


def _split_single_six_grid_image(
    storyboard_images,
    count,
    cols=3,
    rows=2,
    auto_crop_borders=False,
    border_sensitivity=0.10,
    border_crop_px=8,
    grid_layout="auto",
    target_ratio=None,
    max_segments=MAX_AUTO_SEGMENTS,
):
    if storyboard_images is None or count <= 1:
        return storyboard_images
    if int(storyboard_images.shape[0]) != 1:
        return storyboard_images

    _, height, width, _ = storyboard_images.shape
    border_sensitivity, border_crop_px = _repair_border_settings(border_sensitivity, border_crop_px)
    normalized_layout = _normalize_choice(grid_layout, GRID_LAYOUT_ALIASES, None)
    if normalized_layout in {"auto", "2x3", "3x2"}:
        cols, rows = _resolve_grid_layout(storyboard_images, normalized_layout, border_sensitivity)
    else:
        cols, rows = max(1, int(cols)), max(1, int(rows))
    crops = []

    if auto_crop_borders:
        x_intervals = _axis_intervals(storyboard_images, cols, "x", border_sensitivity, border_crop_px)
        y_intervals = _axis_intervals(storyboard_images, rows, "y", border_sensitivity, border_crop_px)
    else:
        cell_w = max(1, int(width) // cols)
        cell_h = max(1, int(height) // rows)
        x_intervals = [(col * cell_w, col * cell_w + cell_w) for col in range(cols)]
        y_intervals = [(row * cell_h, row * cell_h + cell_h) for row in range(rows)]

    max_segments = max(1, int(max_segments))
    for idx in range(min(max_segments, count, cols * rows)):
        col = idx % cols
        row = idx // cols
        x0, x1 = x_intervals[col]
        y0, y1 = y_intervals[row]
        crop = storyboard_images[:, y0:y1, x0:x1, :]
        if auto_crop_borders:
            crop = _trim_border_like_edges(crop, border_sensitivity, border_crop_px)
        crop = _crop_to_aspect_ratio(crop, target_ratio)
        crops.append(crop)

    if not crops:
        return storyboard_images

    if auto_crop_borders:
        min_h = min(int(crop.shape[1]) for crop in crops)
        min_w = min(int(crop.shape[2]) for crop in crops)
        if target_ratio and target_ratio > 0:
            if min_w / max(1, min_h) > target_ratio:
                min_w = max(1, int(round(min_h * target_ratio)))
            else:
                min_h = max(1, int(round(min_w / target_ratio)))
        crops = [_center_crop_to(crop, min_h, min_w) for crop in crops]
        target_h, target_w = _target_cell_size(width, height, cols, rows, target_ratio)
        crops = [_resize_crop_to(crop, target_h, target_w) for crop in crops]

    return torch.cat(crops, dim=0)


def _build_default_timeline(storyboard_images, llm_response, duration_frames, frame_rate,
                            segment_lengths, guide_strength, transition_smoothness, parse_mode,
                            grid_count=MAX_AUTO_SEGMENTS):
    batch_count = int(storyboard_images.shape[0]) if storyboard_images is not None else 0
    prompts, json_lengths = _parse_prompts(llm_response, parse_mode)
    grid_count = max(1, min(GRID_MAX_SEGMENTS, int(grid_count)))
    if batch_count == 1:
        count = min(grid_count, len(prompts) or grid_count)
    else:
        count = max(1, min(grid_count, batch_count or grid_count))
    prompts = (prompts + [_fallback_prompt(i) for i in range(count)])[:count]
    lengths = _normalize_lengths(segment_lengths, json_lengths, duration_frames, count, frame_rate)
    strengths = _strengths_for_count(guide_strength, count)
    transitions = _transitions_for_count(transition_smoothness, count)

    cursor = 0
    segments = []
    for idx in range(count):
        segments.append({
            "id": uuid4().hex[:12],
            "start": int(cursor),
            "length": int(lengths[idx]),
            "prompt": prompts[idx],
            "type": "image",
            "source": "storyboard_images",
            "batch_index": idx,
            "guideStrength": float(strengths[idx]),
            "transitionSmoothness": float(transitions[idx]),
        })
        cursor += int(lengths[idx])

    return {"segments": segments, "audioSegments": []}


def _decode_timeline(timeline_data):
    try:
        data = json.loads(timeline_data) if timeline_data else {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if not isinstance(data.get("segments"), list):
        data["segments"] = []
    if not isinstance(data.get("audioSegments"), list):
        data["audioSegments"] = []
    return data


def _parsed_prompt_for_segment(seg, index, parsed_prompts):
    batch_index = seg.get("batch_index")
    try:
        batch_index = int(batch_index)
    except (TypeError, ValueError):
        batch_index = index

    if 0 <= batch_index < len(parsed_prompts):
        return parsed_prompts[batch_index]
    if index < len(parsed_prompts):
        return parsed_prompts[index]
    return ""


def _prompt_for_segment(seg, index, parsed_prompts):
    parsed_prompt = _parsed_prompt_for_segment(seg, index, parsed_prompts)
    if parsed_prompt and seg.get("source") == "storyboard_images":
        return parsed_prompt

    prompt = _to_str(seg.get("prompt")).strip()
    if prompt:
        return prompt

    if parsed_prompt:
        return parsed_prompt
    return _fallback_prompt(index)


def _contiguous_prompts_and_lengths(segments, parsed_prompts, duration_frames):
    sorted_segments = sorted(segments, key=lambda seg: float(seg.get("start", 0)))
    prompts = []
    lengths = []
    transitions = []
    current_cursor = 0
    pending_gap = 0

    for idx, seg in enumerate(sorted_segments):
        start = max(0, int(float(seg.get("start", 0))))
        length = max(1, int(float(seg.get("length", 1))))
        if start >= duration_frames:
            break

        if start > current_cursor:
            gap_length = min(start, duration_frames) - current_cursor
            if lengths:
                lengths[-1] += gap_length
            else:
                pending_gap += gap_length

        clipped_end = min(start + length, duration_frames)
        clipped_length = max(1, clipped_end - start)
        prompts.append(_prompt_for_segment(seg, idx, parsed_prompts))
        lengths.append(clipped_length + pending_gap)
        transitions.append(max(0.0, min(1.0, _to_float(seg.get("transitionSmoothness"), 0.0))))
        pending_gap = 0
        current_cursor = start + length

    clamped_cursor = min(current_cursor, duration_frames)
    if lengths and clamped_cursor < duration_frames:
        lengths[-1] += duration_frames - clamped_cursor

    if not prompts:
        prompts = [_fallback_prompt(0)]
        lengths = [duration_frames]
        transitions = [0.0]

    return (
        " | ".join(prompts),
        ",".join(str(int(v)) for v in lengths),
        ",".join(f"{float(v):.2f}" for v in transitions),
    )


def _load_segment_image(seg, storyboard_images, fallback_index, custom_width, custom_height,
                        resize_method, divisible_by, img_compression):
    tensor = None

    if storyboard_images is not None:
        batch_index = seg.get("batch_index")
        try:
            batch_index = int(batch_index)
        except (TypeError, ValueError):
            batch_index = fallback_index

        if 0 <= batch_index < int(storyboard_images.shape[0]):
            tensor = storyboard_images[batch_index:batch_index + 1]

    if tensor is None:
        tensor = _load_image_tensor(seg)

    return _process_image_tensor(
        tensor,
        custom_width,
        custom_height,
        resize_method,
        divisible_by,
        img_compression,
    )


def _build_guide_data(timeline, storyboard_images, duration_frames, frame_rate, guide_strength,
                      custom_width, custom_height, resize_method, divisible_by, img_compression):
    guide_data = {"images": [], "insert_frames": [], "strengths": [], "frame_rate": frame_rate}
    derived_w, derived_h = custom_width, custom_height
    image_segments = [
        seg for seg in timeline.get("segments", [])
        if seg.get("type", "image") == "image"
        and int(float(seg.get("start", 0))) < duration_frames
    ]
    image_segments.sort(key=lambda seg: float(seg.get("start", 0)))
    strengths = _strengths_for_count(guide_strength, max(MAX_AUTO_SEGMENTS, len(image_segments)))

    for idx, seg in enumerate(image_segments):
        has_batch = storyboard_images is not None and (
            seg.get("source") == "storyboard_images" or seg.get("batch_index") is not None
        )
        has_file = seg.get("imageFile") or seg.get("imageB64")
        if not has_batch and not has_file:
            continue

        tensor = _load_segment_image(
            seg,
            storyboard_images,
            idx,
            custom_width,
            custom_height,
            resize_method,
            divisible_by,
            img_compression,
        )
        if idx == 0:
            derived_h = int(tensor.shape[1])
            derived_w = int(tensor.shape[2])

        strength = seg.get("guideStrength")
        if strength is None:
            strength = strengths[idx] if idx < len(strengths) else 1.0

        guide_data["images"].append(tensor)
        guide_data["insert_frames"].append(int(float(seg.get("start", 0))))
        guide_data["strengths"].append(float(strength))

    if not guide_data["images"]:
        w = derived_w if derived_w > 0 else 768
        h = derived_h if derived_h > 0 else 512
        w = max(32, (int(w) // 32) * 32)
        h = max(32, (int(h) // 32) * 32)
        guide_data["images"].append(torch.zeros((1, h, w, 3), dtype=torch.float32))
        guide_data["insert_frames"].append(0)
        guide_data["strengths"].append(0.0)
        derived_w, derived_h = w, h

    return guide_data, derived_w, derived_h


class LTXGridDirector(io.ComfyNode):
    """DF grid director with 2x2/3x2/3x3 storyboard splitting."""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="DF-LTXGridDirector",
            display_name="DF-LTX \u5bab\u683c\u5bfc\u6f14\u53f0",
            category="DF-WhatDreamsCost",
            description=(
                "DF \u901a\u7528\u5bab\u683c\u5bfc\u6f14\u53f0\uff1a\u5728 CS \u65b0\u7248\u5bab\u683c\u5bfc\u6f14\u53f0\u57fa\u7840\u4e0a\u4fdd\u6301 DF \u547d\u540d\uff0c"
                "\u652f\u6301 2x2 \u56db\u5bab\u683c\u30013x2 \u516d\u5bab\u683c\u548c 3x3 \u4e5d\u5bab\u683c\uff0c\u5e76\u4f7f\u7528 DF \u7684\u767d\u8fb9\u6846\u68c0\u6d4b\u88c1\u526a\u3002"
            ),
            inputs=[
                io.Model.Input("model", display_name="\u6a21\u578b"),
                io.Clip.Input("clip", display_name="\u6587\u672c\u7f16\u7801\u5668"),
                io.Image.Input("storyboard_images", display_name="\u5bab\u683c\u56fe\u50cf", optional=True),
                io.Combo.Input("grid_mode", display_name="\u5bab\u683c\u6a21\u5f0f", options=GRID_MODE_OPTIONS, default="3x2 \u516d\u5bab\u683c", optional=True),
                io.Combo.Input("shot_aspect", display_name="\u5206\u955c\u6bd4\u4f8b", options=SHOT_ASPECT_OPTIONS, default="\u81ea\u52a8 / \u4fdd\u6301\u5355\u683c\u6bd4\u4f8b", optional=True),
                io.Float.Input("border_crop", display_name="\u767d\u8fb9\u88c1\u526a\u5f3a\u5ea6", default=1.0, min=0.0, max=5.0, step=0.05, optional=True),
                io.String.Input("llm_response", display_name="GPT \u5206\u955c\u6587\u672c", multiline=True, default=""),
                io.Vae.Input("audio_vae", display_name="\u97f3\u9891 VAE", optional=True),
                io.Latent.Input("optional_latent", display_name="\u53ef\u9009\u6f5c\u7a7a\u95f4", optional=True),
                io.String.Input("global_prompt", display_name="\u5168\u5c40\u63d0\u793a\u8bcd", multiline=True, default=""),
                io.Int.Input("duration_frames", display_name="\u603b\u5e27\u6570", default=120, min=1, max=10000, step=1),
                io.Float.Input("duration_seconds", display_name="\u603b\u79d2\u6570", default=5.0, min=0.1, max=1000.0, step=0.01),
                io.String.Input("timeline_data", display_name="\u65f6\u95f4\u7ebf\u6570\u636e", default=""),
                io.Boolean.Input("use_custom_audio", display_name="\u4f7f\u7528\u81ea\u5b9a\u4e49\u97f3\u9891", default=False, optional=True),
                io.String.Input("local_prompts", display_name="\u5206\u955c\u63d0\u793a\u8bcd", multiline=True, default=""),
                io.String.Input("segment_lengths", display_name="\u6bcf\u6bb5\u5e27\u6570", default=""),
                io.String.Input("epsilon", display_name="\u5206\u6bb5\u8fb9\u754c\u9510\u5ea6", default="0.001"),
                io.Float.Input("frame_rate", display_name="\u5e27\u7387", default=24, min=1, max=240, step=1, optional=True),
                io.String.Input("display_mode", display_name="\u65f6\u95f4\u663e\u793a", default="\u79d2", optional=True),
                io.String.Input("guide_strength", display_name="\u56fe\u50cf\u5f15\u5bfc\u5f3a\u5ea6", default="1.0"),
                io.String.Input("transition_smoothness", display_name="\u8fc7\u6e21\u5e73\u6ed1\u5ea6", default="", optional=True),
                io.Combo.Input("parse_mode", display_name="\u6587\u672c\u89e3\u6790\u65b9\u5f0f", options=["\u81ea\u52a8", "JSON", "\u7f16\u53f7\u6587\u672c"], default="\u81ea\u52a8", optional=True),
                io.Int.Input("custom_width", display_name="\u8f93\u51fa\u5bbd\u5ea6", default=0, min=0, max=8192, step=1, optional=True),
                io.Int.Input("custom_height", display_name="\u8f93\u51fa\u9ad8\u5ea6", default=0, min=0, max=8192, step=1, optional=True),
                io.Combo.Input(
                    "resize_method",
                    display_name="\u56fe\u50cf\u9002\u914d\u65b9\u5f0f",
                    options=["\u4fdd\u6301\u6bd4\u4f8b", "\u62c9\u4f38\u586b\u6ee1", "\u7559\u767d\u586b\u5145", "\u88c1\u526a\u586b\u6ee1"],
                    default="\u4fdd\u6301\u6bd4\u4f8b",
                    optional=True,
                ),
                io.Int.Input("divisible_by", display_name="\u5c3a\u5bf8\u6574\u9664", default=32, min=1, max=256, step=1, optional=True),
                io.Int.Input("img_compression", display_name="\u56fe\u50cf\u538b\u7f29", default=18, min=0, max=100, step=1, optional=True),
            ],
            outputs=[
                io.Model.Output(display_name="\u6a21\u578b"),
                io.Conditioning.Output(display_name="\u6b63\u5411\u6761\u4ef6"),
                io.Latent.Output(display_name="\u89c6\u9891\u6f5c\u7a7a\u95f4"),
                io.Latent.Output(display_name="\u97f3\u9891\u6f5c\u7a7a\u95f4"),
                GuideData.Output(display_name="\u5f15\u5bfc\u6570\u636e"),
                io.Float.Output(display_name="\u5e27\u7387"),
                io.Audio.Output(display_name="\u5408\u6210\u97f3\u9891"),
            ],
        )

    @classmethod
    def execute(cls, model, clip, global_prompt, duration_frames, duration_seconds,
                timeline_data, local_prompts, segment_lengths, guide_strength="1.0",
                transition_smoothness="", epsilon=1e-3, frame_rate=24,
                display_mode="seconds", custom_width=0, custom_height=0,
                resize_method="maintain aspect ratio", divisible_by=32, img_compression=18,
                storyboard_images=None, llm_response="", audio_vae=None, optional_latent=None,
                use_custom_audio=False, parse_mode="auto", grid_mode="3x2 \u516d\u5bab\u683c",
                shot_aspect="\u81ea\u52a8 / \u4fdd\u6301\u5355\u683c\u6bd4\u4f8b", border_crop=1.0) -> io.NodeOutput:
        llm_response = _to_str(llm_response)
        global_prompt = _to_str(global_prompt)
        segment_lengths = _to_str(segment_lengths)
        guide_strength = _to_str(guide_strength)
        transition_smoothness = _to_str(transition_smoothness)
        duration_frames = max(1, _to_int(duration_frames, 120))
        frame_rate = _to_float(frame_rate, 24.0)
        epsilon = _to_float(epsilon, 0.001)
        custom_width = max(0, _to_int(custom_width, 0))
        custom_height = max(0, _to_int(custom_height, 0))
        divisible_by = max(1, _to_int(divisible_by, 32))
        img_compression = max(0, _to_int(img_compression, 18))
        parse_mode = _normalize_choice(parse_mode, PARSE_MODE_ALIASES, "auto")
        resize_method = _normalize_choice(resize_method, RESIZE_METHOD_ALIASES, "maintain aspect ratio")
        grid_cols, grid_rows = _grid_dimensions(grid_mode)
        target_ratio = _shot_aspect_ratio(shot_aspect)
        border_crop_strength = _safe_crop_strength(border_crop)
        grid_count = min(GRID_MAX_SEGMENTS, grid_cols * grid_rows)

        parsed_prompts, _ = _parse_prompts(llm_response, parse_mode)
        timeline = _decode_timeline(timeline_data)

        if not timeline["segments"] and storyboard_images is not None:
            timeline = _build_default_timeline(
                storyboard_images,
                llm_response,
                duration_frames,
                frame_rate,
                segment_lengths,
                guide_strength,
                transition_smoothness,
                parse_mode,
                grid_count=grid_count,
            )

        timeline_json = json.dumps(timeline, ensure_ascii=False)
        local_prompts, segment_lengths_out, transition_smoothness_out = _contiguous_prompts_and_lengths(
            timeline["segments"],
            parsed_prompts,
            duration_frames,
        )

        border_crop_px = 0
        if storyboard_images is not None and int(storyboard_images.shape[0]) == 1:
            _, source_h, source_w, _ = storyboard_images.shape
            cell_size = min(int(source_w) / max(1, grid_cols), int(source_h) / max(1, grid_rows))
            border_crop_px = int(round(cell_size * 0.015 * border_crop_strength))

        storyboard_images_for_guides = _split_single_six_grid_image(
            storyboard_images,
            _image_segment_count(timeline),
            cols=grid_cols,
            rows=grid_rows,
            auto_crop_borders=border_crop_strength > 0,
            border_sensitivity=DEFAULT_BORDER_SENSITIVITY,
            border_crop_px=border_crop_px,
            grid_layout=None,
            target_ratio=target_ratio,
            max_segments=GRID_MAX_SEGMENTS,
        )

        guide_data, derived_w, derived_h = _build_guide_data(
            timeline,
            storyboard_images_for_guides,
            duration_frames,
            frame_rate,
            guide_strength,
            custom_width,
            custom_height,
            resize_method,
            divisible_by,
            img_compression,
        )

        ltxv_length = duration_frames + 1
        if optional_latent is None:
            latent_w = max(32, (int(derived_w) // 32) * 32)
            latent_h = max(32, (int(derived_h) // 32) * 32)
            latent_t = ((ltxv_length - 1) // 8) + 1
            samples = torch.zeros(
                [1, 128, latent_t, latent_h // 32, latent_w // 32],
                device=comfy.model_management.intermediate_device(),
            )
            latent = {"samples": samples}
        else:
            latent = optional_latent

        patched, conditioning = _encode_relay(
            model,
            clip,
            latent,
            global_prompt,
            local_prompts,
            segment_lengths_out,
            epsilon,
            transition_smoothness_out,
        )

        audio_out = _build_combined_audio(timeline_json, ltxv_length, frame_rate)
        audio_latent = {}
        if audio_vae is not None:
            if use_custom_audio:
                try:
                    waveform = audio_out["waveform"]
                    if waveform.ndim == 2:
                        waveform = waveform.unsqueeze(0)
                    if hasattr(audio_vae, "first_stage_model"):
                        latent_samples = audio_vae.encode(waveform.movedim(1, -1))
                    else:
                        latent_samples = audio_vae.encode({
                            "waveform": waveform,
                            "sample_rate": audio_out["sample_rate"],
                        })
                    mask = torch.full(
                        (1, latent_samples.shape[-2], latent_samples.shape[-1]),
                        0.0,
                        dtype=torch.float32,
                        device=comfy.model_management.intermediate_device(),
                    )
                    audio_latent = {
                        "samples": latent_samples,
                        "type": "audio",
                        "noise_mask": mask.reshape((-1, 1, mask.shape[-2], mask.shape[-1])),
                    }
                except Exception as exc:
                    log.error("[LTX Grid Director] Failed to encode custom audio: %s", exc)
                    raise exc
            else:
                audio_latent = _empty_audio_latent(audio_vae, ltxv_length, frame_rate)

        return io.NodeOutput(patched, conditioning, latent, audio_latent, guide_data, frame_rate, audio_out)


class LTXSixGridDirector(io.ComfyNode):
    """DF six-grid director with automatic border-aware storyboard splitting."""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="DF-LTXSixGridDirector",
            display_name="DF-LTX \u516d\u5bab\u683c\u5bfc\u6f14\u53f0",
            category="DF-WhatDreamsCost",
            description=(
                "DF \u72ec\u7acb\u516d\u5bab\u683c\u5bfc\u6f14\u53f0\uff1a\u4ece 3x2 \u516d\u5bab\u683c\u56fe\u81ea\u52a8\u62c6\u5206\u5206\u955c\uff0c"
                "\u5e76\u5728\u62c6\u5206\u65f6\u81ea\u52a8\u907f\u5f00\u767d\u8fb9\u6846\u548c\u5206\u9694\u7ebf\u3002"
            ),
            inputs=[
                io.Model.Input("model", display_name="\u6a21\u578b"),
                io.Clip.Input("clip", display_name="\u6587\u672c\u7f16\u7801\u5668"),
                io.Image.Input("storyboard_images", display_name="\u516d\u5bab\u683c\u62c6\u5206\u56fe", optional=True),
                io.String.Input("llm_response", display_name="GPT \u5206\u955c\u6587\u672c", multiline=True, default=""),
                io.Vae.Input("audio_vae", display_name="\u97f3\u9891 VAE", optional=True),
                io.Latent.Input("optional_latent", display_name="\u53ef\u9009\u6f5c\u7a7a\u95f4", optional=True),
                io.String.Input("global_prompt", display_name="\u5168\u5c40\u63d0\u793a\u8bcd", multiline=True, default=""),
                io.Int.Input("duration_frames", display_name="\u603b\u5e27\u6570", default=120, min=1, max=10000, step=1),
                io.Float.Input("duration_seconds", display_name="\u603b\u79d2\u6570", default=5.0, min=0.1, max=1000.0, step=0.01),
                io.String.Input("timeline_data", display_name="\u65f6\u95f4\u7ebf\u6570\u636e", default=""),
                io.Boolean.Input("use_custom_audio", display_name="\u4f7f\u7528\u81ea\u5b9a\u4e49\u97f3\u9891", default=False, optional=True),
                io.String.Input("local_prompts", display_name="\u5206\u955c\u63d0\u793a\u8bcd", multiline=True, default=""),
                io.String.Input("segment_lengths", display_name="\u6bcf\u6bb5\u5e27\u6570", default=""),
                io.String.Input("epsilon", display_name="\u5206\u6bb5\u8fb9\u754c\u9510\u5ea6", default="0.001"),
                io.Float.Input("frame_rate", display_name="\u5e27\u7387", default=24, min=1, max=240, step=1, optional=True),
                io.String.Input("display_mode", display_name="\u65f6\u95f4\u663e\u793a", default="\u79d2", optional=True),
                io.String.Input("guide_strength", display_name="\u56fe\u50cf\u5f15\u5bfc\u5f3a\u5ea6", default="1.0"),
                io.String.Input("transition_smoothness", display_name="\u8fc7\u6e21\u5e73\u6ed1\u5ea6", default="", optional=True),
                io.Combo.Input("parse_mode", display_name="\u6587\u672c\u89e3\u6790\u65b9\u5f0f", options=["\u81ea\u52a8", "JSON", "\u7f16\u53f7\u6587\u672c"], default="\u81ea\u52a8", optional=True),
                io.Int.Input("custom_width", display_name="\u8f93\u51fa\u5bbd\u5ea6", default=0, min=0, max=8192, step=1, optional=True),
                io.Int.Input("custom_height", display_name="\u8f93\u51fa\u9ad8\u5ea6", default=0, min=0, max=8192, step=1, optional=True),
                io.Combo.Input(
                    "grid_layout",
                    display_name="\u516d\u5bab\u683c\u5e03\u5c40",
                    options=["\u81ea\u52a8\u68c0\u6d4b", "2\u5217 x 3\u884c", "3\u5217 x 2\u884c"],
                    default="\u81ea\u52a8\u68c0\u6d4b",
                    optional=True,
                ),
                io.Boolean.Input("auto_crop_borders", display_name="\u81ea\u52a8\u88c1\u6389\u516d\u5bab\u683c\u8fb9\u6846", default=True, optional=True),
                io.Float.Input("border_sensitivity", display_name="\u8fb9\u6846\u68c0\u6d4b\u7075\u654f\u5ea6", default=0.10, min=0.01, max=0.45, step=0.01, optional=True),
                io.Int.Input("border_crop_px", display_name="\u5206\u9694\u7ebf\u5b89\u5168\u88c1\u526a\u50cf\u7d20", default=8, min=0, max=128, step=1, optional=True),
                io.Combo.Input(
                    "resize_method",
                    display_name="\u56fe\u50cf\u9002\u914d\u65b9\u5f0f",
                    options=["\u4fdd\u6301\u6bd4\u4f8b", "\u62c9\u4f38\u586b\u6ee1", "\u7559\u767d\u586b\u5145", "\u88c1\u526a\u586b\u6ee1"],
                    default="\u4fdd\u6301\u6bd4\u4f8b",
                    optional=True,
                ),
                io.Int.Input("divisible_by", display_name="\u5c3a\u5bf8\u6574\u9664", default=32, min=1, max=256, step=1, optional=True),
                io.Int.Input("img_compression", display_name="\u56fe\u50cf\u538b\u7f29", default=18, min=0, max=100, step=1, optional=True),
            ],
            outputs=[
                io.Model.Output(display_name="\u6a21\u578b"),
                io.Conditioning.Output(display_name="\u6b63\u5411\u6761\u4ef6"),
                io.Latent.Output(display_name="\u89c6\u9891\u6f5c\u7a7a\u95f4"),
                io.Latent.Output(display_name="\u97f3\u9891\u6f5c\u7a7a\u95f4"),
                GuideData.Output(display_name="\u5f15\u5bfc\u6570\u636e"),
                io.Float.Output(display_name="\u5e27\u7387"),
                io.Audio.Output(display_name="\u5408\u6210\u97f3\u9891"),
            ],
        )

    @classmethod
    def execute(cls, model, clip, global_prompt, duration_frames, duration_seconds,
                timeline_data, local_prompts, segment_lengths, guide_strength="1.0",
                transition_smoothness="", epsilon=1e-3, frame_rate=24,
                display_mode="seconds", custom_width=0, custom_height=0,
                grid_layout="auto", auto_crop_borders=True, border_sensitivity=0.10, border_crop_px=8,
                resize_method="maintain aspect ratio", divisible_by=32, img_compression=18,
                storyboard_images=None, llm_response="", audio_vae=None, optional_latent=None,
                use_custom_audio=False, parse_mode="auto") -> io.NodeOutput:
        llm_response = _to_str(llm_response)
        global_prompt = _to_str(global_prompt)
        segment_lengths = _to_str(segment_lengths)
        guide_strength = _to_str(guide_strength)
        transition_smoothness = _to_str(transition_smoothness)
        duration_frames = max(1, _to_int(duration_frames, 120))
        frame_rate = _to_float(frame_rate, 24.0)
        epsilon = _to_float(epsilon, 0.001)
        custom_width = max(0, _to_int(custom_width, 0))
        custom_height = max(0, _to_int(custom_height, 0))
        grid_layout = _normalize_choice(grid_layout, GRID_LAYOUT_ALIASES, "auto")
        auto_crop_borders = _to_bool(auto_crop_borders, True)
        border_sensitivity, border_crop_px = _repair_border_settings(border_sensitivity, border_crop_px)
        divisible_by = max(1, _to_int(divisible_by, 32))
        img_compression = max(0, _to_int(img_compression, 18))
        parse_mode = _normalize_choice(parse_mode, PARSE_MODE_ALIASES, "auto")
        resize_method = _normalize_choice(resize_method, RESIZE_METHOD_ALIASES, "maintain aspect ratio")

        parsed_prompts, _ = _parse_prompts(llm_response, parse_mode)
        timeline = _decode_timeline(timeline_data)

        if not timeline["segments"] and storyboard_images is not None:
            timeline = _build_default_timeline(
                storyboard_images,
                llm_response,
                duration_frames,
                frame_rate,
                segment_lengths,
                guide_strength,
                transition_smoothness,
                parse_mode,
            )

        timeline_json = json.dumps(timeline, ensure_ascii=False)
        local_prompts, segment_lengths_out, transition_smoothness_out = _contiguous_prompts_and_lengths(
            timeline["segments"],
            parsed_prompts,
            duration_frames,
        )
        storyboard_images_for_guides = _split_single_six_grid_image(
            storyboard_images,
            _image_segment_count(timeline),
            auto_crop_borders=auto_crop_borders,
            border_sensitivity=border_sensitivity,
            border_crop_px=border_crop_px,
            grid_layout=grid_layout,
        )

        guide_data, derived_w, derived_h = _build_guide_data(
            timeline,
            storyboard_images_for_guides,
            duration_frames,
            frame_rate,
            guide_strength,
            custom_width,
            custom_height,
            resize_method,
            divisible_by,
            img_compression,
        )

        ltxv_length = duration_frames + 1
        if optional_latent is None:
            latent_w = max(32, (int(derived_w) // 32) * 32)
            latent_h = max(32, (int(derived_h) // 32) * 32)
            latent_t = ((ltxv_length - 1) // 8) + 1
            samples = torch.zeros(
                [1, 128, latent_t, latent_h // 32, latent_w // 32],
                device=comfy.model_management.intermediate_device(),
            )
            latent = {"samples": samples}
        else:
            latent = optional_latent

        patched, conditioning = _encode_relay(
            model,
            clip,
            latent,
            global_prompt,
            local_prompts,
            segment_lengths_out,
            epsilon,
            transition_smoothness_out,
        )

        audio_out = _build_combined_audio(timeline_json, ltxv_length, frame_rate)
        audio_latent = {}
        if audio_vae is not None:
            if use_custom_audio:
                try:
                    waveform = audio_out["waveform"]
                    if waveform.ndim == 2:
                        waveform = waveform.unsqueeze(0)
                    if hasattr(audio_vae, "first_stage_model"):
                        latent_samples = audio_vae.encode(waveform.movedim(1, -1))
                    else:
                        latent_samples = audio_vae.encode({
                            "waveform": waveform,
                            "sample_rate": audio_out["sample_rate"],
                        })
                    mask = torch.full(
                        (1, latent_samples.shape[-2], latent_samples.shape[-1]),
                        0.0,
                        dtype=torch.float32,
                        device=comfy.model_management.intermediate_device(),
                    )
                    audio_latent = {
                        "samples": latent_samples,
                        "type": "audio",
                        "noise_mask": mask.reshape((-1, 1, mask.shape[-2], mask.shape[-1])),
                    }
                except Exception as exc:
                    log.error("[LTX Six Grid Director] Failed to encode custom audio: %s", exc)
                    raise exc
            else:
                audio_latent = _empty_audio_latent(audio_vae, ltxv_length, frame_rate)

        return io.NodeOutput(patched, conditioning, latent, audio_latent, guide_data, frame_rate, audio_out)


NODE_CLASS_MAPPINGS = {
    "DF-LTXGridDirector": LTXGridDirector,
    "DF-LTXSixGridDirector": LTXSixGridDirector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DF-LTXGridDirector": "DF-LTX \u5bab\u683c\u5bfc\u6f14\u53f0",
    "DF-LTXSixGridDirector": "DF-LTX \u516d\u5bab\u683c\u5bfc\u6f14\u53f0",
}
