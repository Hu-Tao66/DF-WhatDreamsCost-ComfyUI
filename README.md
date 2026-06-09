# DF-WhatDreamsCost-ComfyUI

## 来源说明

`DF-WhatDreamsCost-ComfyUI` 是基于 [yg496/CS-WhatDreamsCost-ComfyUI](https://github.com/yg496/CS-WhatDreamsCost-ComfyUI) 的二次 fork。CS 插件本身基于 [WhatDreamsCost/WhatDreamsCost-ComfyUI](https://github.com/WhatDreamsCost/WhatDreamsCost-ComfyUI)。本仓库保留上游作者署名和原有功能基础，只在独立 `DF-` 命名空间中注册节点，方便和原版、CS 版同时安装。

导演台交互增强参考了 [yusu-02/Yusu-WhatDreamsCost-ComfyUI](https://github.com/yusu-02/Yusu-WhatDreamsCost-ComfyUI) 中值得借鉴的时间线宽度处理和过渡控制思路，并在 DF 命名空间内重新实现，避免和 CS/Yusu 节点冲突。

## 相比 CS 版新增了什么

这个 DF fork 的主要目标是解决六宫格分镜图带白边、灰白边框或分隔线时，拆分后的单张分镜仍然残留边线的问题。

新增和调整内容：

- 跟进 CS 新版 `CS-LTXGridDirector`，新增独立 `DF-LTXGridDirector` / `DF-LTX 宫格导演台`。
- `DF-LTXGridDirector` 支持 `2x2 四宫格`、`3x2 六宫格`、`3x3 九宫格`，并支持 `16:9`、`9:16`、`1:1` 分镜比例裁剪。
- 新宫格导演台没有照搬 CS 的简单内缩裁剪，而是继续使用 DF 的白边/灰白边框检测裁剪，尽量只去掉边框和分隔线。
- 在 `DF-LTXSixGridDirector` 中增加六宫格白边/灰白分隔线自动裁剪。
- 支持 `3列 x 2行` 和 `2列 x 3行` 六宫格布局，也可以自动检测布局。
- 增加 `自动裁掉六宫格边框`、`边框检测灵敏度`、`分隔线安全裁剪像素` 参数。
- 裁掉边框后会把分镜恢复到原单格尺寸，例如 864x1024 的 3x2 六宫格会拆成 6 张 288x512。
- 前端时间线预览也同步使用裁白边后的裁剪区域，避免预览和实际执行不一致。
- `DF-LTXAutoDirector` 也加入同一套逻辑：如果输入是一张合成六宫格图，会先自动裁白边并拆成 6 张；如果输入已经是批量分镜图，则保持 CS 原逻辑。
- 所有公开节点保持 CS 原节点名称结构，只把 `CS-` 前缀改为 `DF-`，避免和 CS 插件冲突。
- `DF-LoadVideoUI` 的后端接口使用独立 `/df_video_ui_*` 路由，避免和 CS 版同时安装时路由冲突。
- 导演台增加每段 `Transition / 过渡` 控制，并修复总秒数/总帧数手动输入后的图片、音频时间线对齐。

除了上面这些差异，其它节点功能基本保持 CS 版逻辑。

## 节点命名

本 fork 按“CS 原名称换 DF 前缀”的规则注册节点。旧的 WhatDreamsCost 原始节点名不会被覆盖，CS 版节点名也不会被覆盖。

| CS 版节点 | DF fork 节点 |
| --- | --- |
| `CS-LTXDirector` | `DF-LTXDirector` |
| `CS-LTXAutoDirector` | `DF-LTXAutoDirector` |
| `CS-LTXGridDirector` | `DF-LTXGridDirector` |
| `CS-LTXSixGridDirector` | `DF-LTXSixGridDirector` |
| `CS-LTXDirectorGuide` | `DF-LTXDirectorGuide` |
| `CS-LTXKeyframer` | `DF-LTXKeyframer` |
| `CS-LTXSequencer` | `DF-LTXSequencer` |
| `CS-MultiImageLoader` | `DF-MultiImageLoader` |
| `CS-SpeechLengthCalculator` | `DF-SpeechLengthCalculator` |
| `CS-LoadAudioUI` | `DF-LoadAudioUI` |
| `CS-LoadVideoUI` | `DF-LoadVideoUI` |

如果你从 CS 工作流迁移到 DF，需要把节点类型从 `CS-...` 替换成对应的 `DF-...`。新版通用宫格节点是 `DF-LTXGridDirector`，旧六宫格兼容节点仍然是 `DF-LTXSixGridDirector`。

## ▶️ YouTube Tutorial Videos

<table>
  <tr>
    <td>
      <p align="center">LTX Director Trailer</p>
      <a href="https://www.youtube.com/watch?v=fZgtkRcu4_k">
        <img src="https://img.youtube.com/vi/fZgtkRcu4_k/0.jpg" alt="LTX Director Trailer" width="400">
      </a>
    </td>
    <td>
      <p align="center">LTX Director Tutorial</p>
      <a href="https://www.youtube.com/watch?v=vM60pJJqqEI">
        <img src="https://img.youtube.com/vi/vM60pJJqqEI/0.jpg" alt="LTX Director Tutorial" width="400">
      </a>
    </td>
  </tr>
</table>

## 安装

1. 进入 `ComfyUI/custom_nodes` 目录。
2. 克隆本仓库：

```bash
git clone https://github.com/Hu-Tao66/DF-WhatDreamsCost-ComfyUI.git
```

3. 重启 ComfyUI。
4. 在 ComfyUI 节点菜单里搜索 `DF-`。

如果后续提交到 ComfyUI Manager，也可以通过 Manager 安装。

**注意**

需要同时保持 ComfyUI-LTXVideo 和 ComfyUI-KJNodes 为较新版本。LTX 相关节点依赖这些插件的接口。

# 更新记录

**v1.4.9**
  * **CS updated Grid Director ported into DF**
    - Adds `DF-LTXGridDirector`, mirroring the upstream CS grid director naming structure with the `DF-` prefix.
    - Supports 2x2, 3x2, and 3x3 storyboard grids, including nine-grid auto-fill in the DF timeline UI.
    - Adds shot aspect options for automatic/keep, 16:9, 9:16, and 1:1 crops.
    - Keeps DF's border-aware white/gray divider crop instead of reverting to CS's simple fixed inset.
    - Preserves DF timeline/audio improvements, including transition control, manual duration alignment, and editable audio segments.
    - Reference: [yg496/CS-WhatDreamsCost-ComfyUI](https://github.com/yg496/CS-WhatDreamsCost-ComfyUI) latest `CS-LTXGridDirector` update.

**DF fork**
  * **Based on CS-WhatDreamsCost-ComfyUI, with border-aware six-grid splitting**
    - Keeps the CS node set and renames public nodes from `CS-...` to `DF-...`.
    - Adds white/gray border and divider-line cropping to `DF-LTXSixGridDirector`.
    - Adds the same single six-grid auto-split and border-crop path to `DF-LTXAutoDirector`.
    - Supports automatic layout detection, `3列 x 2行`, and `2列 x 3行`.
    - Restores cropped shots to the original cell size after border removal.
    - Uses independent `DF-LoadVideoUI` backend routes so this fork can coexist with the CS plugin.

**v1.4.8**
  * **Six-grid white-divider halo crop fix**
    - Tightens the crop around detected internal divider bands so white lines and antialias glow are removed more reliably.
    - Applies the same crop-boundary fix to both backend execution and the front-end director preview.
    - Fixes front-end preview crop rectangles being scaled twice, which made the director timeline draw the wrong area.
    - Repairs older workflows whose widget values shifted after new six-grid settings were added, such as `8.00 / NaN / 32` appearing in the crop settings.
    - Refreshes six-grid previews whenever layout or border-crop settings change, without rebuilding the user's edited timeline.
    - Makes the final edge trim target white/light-gray borders only, so dark image content is no longer treated as a border.

**v1.4.7**
  * **Audio editing controls added to the DF director timeline**
    - Adds a toolbar and right-click action to split an audio segment at the playhead.
    - Adds selected-clip duration editing in seconds for image/text/audio segments.
    - Adds selected-audio `trim in` editing in seconds while preserving the source-audio length limit.
    - Adds a quick action to fit the selected image/text segment to the overlapping audio clip.
    - Keeps the existing `DF-LoadAudioUI` trim node and director audio-track output path unchanged.

**v1.4.6**
  * **Manual duration alignment fix**
    - Manual `duration_seconds` / `duration_frames` edits now keep the user-entered total duration instead of being overwritten by timeline auto-sync.
    - Image/text segments are proportionally realigned to the new total duration, so six-grid storyboard blocks still fill the timeline.
    - Audio segments are realigned with the new duration while staying capped by the available source audio length.
    - Dragging image/text/audio segments still auto-syncs the total duration in both directions.

**v1.4.5**
  * **Yusu director improvements merged into the DF timeline**
    - Adds per-segment `Transition` control to `DF-LTXDirector` and `DF-LTXSixGridDirector`.
    - Passes `transition_smoothness` into Prompt Relay so shot boundaries can be softened without changing global `epsilon`.
    - Lets `DF-LTXAutoDirector` accept one transition value for all shots or comma-separated per-shot values.
    - Grows the timeline output duration when image/text/audio segments extend past the current duration.
    - Applies the Yusu-style DOM widget width guard and removes the duplicated `DF-LTXDirectorGuide` frontend tail.
    - Reference: [yusu-02/Yusu-WhatDreamsCost-ComfyUI](https://github.com/yusu-02/Yusu-WhatDreamsCost-ComfyUI).

**v1.4.4**
  * **Six-grid source refresh fix**
    - The six-grid director now rebuilds the six storyboard timeline blocks only when the upstream six-grid image source changes.
    - Connected `llm_response` text still syncs into the current six blocks, but text changes alone no longer clear the timeline cache.
    - During execution, storyboard-image segments prefer the current connected `llm_response` prompts, preventing a new six-grid image from accidentally using prompts from the previous run.

**v1.4.3**
  * **Lean six-grid preview rendering**
    - Six-grid storyboard thumbnails are now drawn directly from one shared source image during canvas rendering.
    - The node no longer creates six cropped base64 preview images for automatic storyboard segments.
    - Old storyboard `imageB64` payloads are stripped when timelines are loaded and re-saved.

**v1.4.2**
  * **RunningHub timeline performance fix**
    - Six-grid previews are now stored as lightweight front-end cache instead of being written into `timeline_data`.
    - Drag and resize operations no longer deep-copy base64 image/audio payloads.
    - Six-grid preview crops are downscaled and JPEG-compressed for smoother timeline interaction.

**v1.4.1**
  * **RunningHub frontend sync fix**
    - The six-grid director now reads connected LLM text from upstream text display nodes, such as `showAnything`, instead of relying only on the local `llm_response` widget.
    - The timeline polls the connected text source and syncs updated shot prompts into the front-end editor automatically.

**v1.4.0 DF fork**
  * **New node: DF-LTX Six-Grid Director / DF-LTX 六宫格导演台**
    - Adds an automatic six-grid storyboard workflow on top of the original LTX Director timeline.
    - Accepts a single 3x2 storyboard image or a batch of six images, then builds six editable timeline shots.
    - Connects LLM/GPT/Qwen shot text into the timeline so prompts can be reviewed and manually edited before generation.
    - Registers all public nodes under `DF-...` IDs to avoid overwriting the original WhatDreamsCost nodes on shared platforms.
    - Refreshes six-grid previews when the upstream storyboard image changes.
    - Adds a guide latent size alignment fix in `DF-LTXDirectorGuide` for more stable LTX guide insertion.

**v1.3.9**
  * **Fixed recent updates not showing in the manager**

It took like 5 tries but I finally got it working 🤦‍♂️

**v1.3.3**
  * **LTX Director Hotfix 2**
    - Fixed duration_seconds input issue.
    - Made both duration widgets visible at all times now
    - Implemented audio latent fix to improve compatibility


**v1.3.2**
  * **LTX Director Hotfix**
    - Fixed epsilon input overlapping custom_width input
    - Fixed invisible widgets in nodes 2.0 when toggling widget visibility through settings menu

If anyone finds anymore bugs or has idea for improvements please let me know! 


**v1.3.1**
  * **LTX Director Example Workflow Fix**
    - Minor fix to the example workflow (i forgot to set the clip loader type to ltxv lol)
    
 **v1.3.0**
  * **New nodes: LTX Director and LTX Director Guide**
    - A complete timeline editor that can do almost everything. It's my most ambitious node so far and the successor to LTX Sequencer/Multi Image Loader.

 **v1.2.9**
  * **Fixed every known issue with Multi Image Loader and added text output to Speech Length Calculator**
  
    - Removed the completely useless drag and drop animations (now it's snappy and no longer finicky)
    - Fixed the node resizing on nodes 2.0 
    - Updated grid logic to fit images better
    - Added ablity to right click images to copy/open/save images
    - Fixed the "invisible hitbox" underneath node issue (actually this time).

  Also added a text output to the Speech Length Calculator node (can't believe i didn't do this initially)

<details>
  <summary>Click to view older Updates</summary>

 **v1.2.8**
  * **Updated Load Video UI and Color Conversion**
    * Added crop mode, a simple interface to crop videos. It also include various aspect ratio presets.
    * Updated color conversion to ensure colors are as accurate as possible. Will first check metadata for colorspace, and if metadata is missing then it will guess the colorspace based on video dimensions.
    * Updated display mode toggle UI to be more understandable 

 **v1.2.7**
  * **New Node: Load Video UI**

Custom Node to Trim, Resize, and Preview Videos in Realtime
  
   **v1.2.6**
  * **Updated Speech Length Calculator UI**

Also added duration output to the Load Audio UI node

 **v1.2.5**
  * **Updated Load Audio UI Node**
    * Added Duration Setting
    * Made the whole selection bar draggable
    * Fixed Trimmed UI to show centiseconds
    
 **v1.2.4**
 * **New Node: Load Audio UI**

Overhaul of the load audio node. Features a simple interface to easily trim audio. Also allows dragging and dropping files (fixes the original node that doesn't allow dropping in videos). Also compatible with nodes 2.0.

 **v1.2.3**
  * **Workflow Update + Minor Bug Fix** 
    * Added new workflow that is compatible with the latest ComfyUI version (as of 4/27/26). The new workflow also included an option to include custom audio, and has minor improvements of the previous workflows.
    * Fixed minor bug with Multi Image Loader that blocked mouse input in a small area under the node 🤷‍♂️

**v1.2.0**
  * **New Node: Speech Length Calculator** 
  
  Automatically output in realtime how long a video should be based on the dialouge. 

**v1.1.0**
  * Added resize_method to the Multi Image Loader node for more resize options
  * Added insert_mode which allows you to enter in seconds instead of frames on the LTX Sequencer node
  * Updated workflows with more notes
  * Re-added tiny vae to workflows
  * Fixed various bugs
  * more things i can't rememeber
  
**This update will change the node layouts, so be sure to update your workflows or else they won't work properly.**

❗❗❗ **New Tutorial on using these nodes available: https://www.youtube.com/watch?v=aXDIr8eNovI**  ❗❗❗
</details>

# ⚙️ Custom Nodes

## DF-LTX Six-Grid Director / DF-LTX 六宫格导演台

`DF-LTX 六宫格导演台` 是这个分支的核心新增节点。它保留了原版 LTX Director 的时间线编辑能力，同时把六宫格分镜图、LLM/GPT/Qwen 分镜文本、LTX 引导图生成流程接到一起，让“六宫格图像 -> 六段分镜 -> 可编辑时间线 -> LTX 生成”尽量自动化。

它适合这样的工作流：先由上游节点生成一张 3x2 六宫格分镜图，再让反推模型或 GPT 输出 6 段分镜描述，导演台节点会自动把六宫格拆成 6 个分镜块，并把对应文本写入时间线。运行前你仍然可以在前端手动修改每段分镜的提示词、时长和引导强度。

**ComfyUI 节点名称：**

| Name | Meaning |
| --- | --- |
| `DF-LTX 六宫格导演台` | ComfyUI 里看到的节点显示名。 |
| `DF-LTXSixGridDirector` | 新的节点内部 ID。 |
| `DF-...` | 这个分支的所有公开节点都使用 `DF-` 前缀，避免覆盖原作者插件。 |

**基础流程：**

1. 用上游节点生成或加载一张 3x2 六宫格分镜图。
2. 把六宫格图片接到 `六宫格拆分图` / `storyboard_images`。
3. 把 LLM/GPT/Qwen 输出的分镜文本接到 `GPT 分镜文本` / `llm_response`。
4. 把 LTX 模型和 CLIP 接到 `模型` / `model` 与 `文本编码器` / `clip`。
5. 如果工作流需要音频潜空间，可以额外接入 Audio VAE。
6. 打开节点前端时间线，检查 6 个图像分镜块，并按需要调整每段时长和提示词。
7. 把 `引导数据` / `guide_data` 接到 `DF-LTXDirectorGuide`，把 `视频潜空间` / `video_latent` 接入 LTX 采样链路。

**六宫格读取顺序：**

六宫格按标准 3x2 顺序读取，从左到右、从上到下：

```text
1  2  3
4  5  6
```

也就是说，第 1 段是左上角，第 3 段是右上角，第 4 段是左下角，第 6 段是右下角。

**推荐的分镜文本格式：**

推荐让 GPT/Qwen 输出 JSON，因为它能同时保存分镜序号、提示词和每段帧数，最适合全自动工作流：

```json
[
  {"shot": 1, "prompt": "Wide shot, character enters the room...", "frames": 20},
  {"shot": 2, "prompt": "Medium shot, character reports to the boss...", "frames": 20},
  {"shot": 3, "prompt": "Close-up, boss listens and thinks...", "frames": 20}
]
```

节点也会尝试解析编号文本或普通文本，但如果你希望工作流稳定自动运行，JSON 是最稳的格式。

**前端可手动编辑：**

自动填充之后，6 个分镜块不是锁死的。你仍然可以在导演台里手动调整：

- 拖动或缩放分镜块，修改每段起止时间；
- 选中分镜后，在文本框里修改该段提示词；
- 修改每段图像引导强度；
- 继续手动添加图像、文本或音频片段；
- 使用原版 LTX Director 的自定义音频和时间线播放控制。

这些手动修改会写入 `时间线数据` / `timeline_data`。对于普通手动片段，真正运行时会使用当前前端时间线里的最终内容；对于来自六宫格的自动分镜片段，如果当前连接的 `llm_response` 已经生成了新的 6 段文本，节点会优先使用当前文本，避免沿用上一轮缓存的提示词。

**自动刷新规则：**

六宫格导演台只会在 `六宫格拆分图` / `storyboard_images` 的上游图片来源发生变化时，自动清除上一轮六宫格时间线缓存并重新创建 6 个分镜块。

如果只是 `GPT 分镜文本` / `llm_response` 发生变化，节点会把新文本同步到当前 6 个分镜块里，但不会因为文本变化而清除整条时间线。修改 `总帧数`、`总秒数` 或 `帧率` 也不会触发清缓存。

**LTX 引导尺寸修复：**

有些 LTX 工作流里，引导图经过 VAE 编码后会得到和主视频 latent 不一致的空间尺寸，例如 `Expected size 33 but got size 17`。这个分支在 `DF-LTXDirectorGuide` 中加入了尺寸对齐步骤，会在插入 keyframe 前把 guide latent 自动对齐到当前视频 latent 的尺寸，减少这类报错。


## DF-LTX Director
<img width="1481" height="833" alt="Clipboard Image (2)" src="https://github.com/user-attachments/assets/08f3fe53-9393-4f5d-9de5-58b229fbed47" />

A Complete Timeline Editor For LTX 2.3. This is the sucessor of my previous nodes, and has loads of features in it. It was originally based off of [Kijai's Prompt Relay node](https://github.com/kijai/ComfyUI-PromptRelay) and my LTX Sequencer/Multi Image Loader nodes.

**Main Features:**
- **Fully Functional Timeline Editor:** I spent hours studying various video editors and ended up with this design. If anyone has ideas for improvements let me know! I will adding documentation on all the functions soon.
- **Prompt Relay integrated:** This unlocks the ability to have granular control over video generation. For more information on Prompt Relay go here, https://gordonchen19.github.io/Prompt-Relay/
- **First, Middle, Last Frame Support:** This has by far the easiest method of creating first/last frames videos. It supports any number of keyframes, and will be the successor of my previous nodes.
- **Custom Audio Support:** Import, trim, and combine your own audio clips in this node. Enabling custom audio is as simple as clicking 1 button. It is also compatible with every other feature in the node, include first/last frames, t2v, i2v, and prompt relay.
- **Image to Video:** Part of the goal of this node was to make it easier to do everything, including Image to Video. It has built in resize functionality, and of course all the benifits of the prompt relay and custom audio integration.
- **Text to Video:** Use text segments to create T2V videos. Compatible with all other features of the node.

Download workflows here: https://github.com/your-name/DF-WhatDreamsCost-ComfyUI/tree/main/example_workflows

**Tutorial videos and documentation coming soon**


## DF-Multi Image Loader
<img width="1280" height="720" alt="Multi_Image_Loader_Wide_Gif" src="https://github.com/user-attachments/assets/99b6afd8-5197-4e6c-81da-a7bd156c42c7" />

An Image loader that features a built in gallery, allowing your to easily rearrange images and output them seperately or batched together. It also combines the image resize node and LTXVPreprocess node to reduce clutter in LTX workflows.

## DF-LTX Sequencer
![LTX_Sequencer_GIF](https://github.com/user-attachments/assets/88f27155-f50e-4cb2-b937-ab173e6bdf0b)

An overhaul of the LTXVAddGuideMulti node. It allows you to quickly create FFLF (First Frame Last Frame) videos, shot sequences, supports any number of middle frames.

Connect the `DF-MultiImageLoader` node's `multi_output` to automatically update the node's widgets.

It also has a sync feature that syncs all LTX Sequencer nodes together in realtime, removing the need to edit every single node manually every time you want to make a change to something. 


## DF-LTX Keyframer
<img width="1082" height="608" alt="LTX Keyframer Wide" src="https://github.com/user-attachments/assets/850ba4a2-dbca-4e5a-a580-1c271e9f0c41" />

An overhaul of the LTXVImgToVideoInplaceKJ node. It allows you to quickly create FFLF (First Frame Last Frame) videos and shot sequences. Also upports any number of middle frames.

Connect the `DF-MultiImageLoader` node's `multi_output` to automatically update the node's widgets.

It also has a sync feature that syncs all LTX Keyframer nodes together in realtime, removing the need to edit every single node manually every time you want to make a change to something. 

**I would recommend using the LTX Sequencer Node over this node, after further testing it seems superior in at pretty much everything. I'll leave it in just in case more people want to test it**

## DF-Speech Length Calculator
<img width="1280" height="720" alt="Speech Length Calculator v2 Gif" src="https://github.com/user-attachments/assets/04b9a1cf-20e4-4b7b-a9c6-4a5a0825995b" />
<br>
<br>
This node calculates in realtime how long a video should be based on the dialogue. Any words in quotations will be considered as speech. The node updates in realtime without having to run the workflow, and outputs the length depending on how fast the speech is.

If you connect another string/text node to the text_input, it will still update in the length in realtime.

I kept having to play the guessing game on my own generations so I made this node to make it easier :man_shrugging:

## DF-Load Video UI  
<table width="100%">
  <tr>
    <td width="50%" align="center">
      <p>Simple Controls</p>
      <img src="https://github.com/user-attachments/assets/fb76ff03-a6ff-4837-bd63-7e429f5f3d37" width="100%" />
    </td>
    <td width="50%" align="center">
      <p>New Crop Mode!</p>
      <img src="https://github.com/user-attachments/assets/28cfb4ca-e42a-44da-9afb-f20cb01b9722" width="100%" />
    </td>
  </tr>
</table>

<br>
<br>
An upgraded Load Video node. It has the following features:

* Simple interface to quickly trim videos and preview them in realtime.
* Ability to load any length of video into the node (the default load video node was limited to 100MB files)
* Easily switch between showing seconds and frames with a toggle button. This will change the widgets as well as the interface.
* Multiple options for resizing the video (maintain aspect ratio, crop, stretch to fit, pad)
* Allows dragging and dropping files into the node
* Progress bar
* Optimized to use less RAM (still very limited due to ComfyUI limitations, but at least a little more efficient)

Please note that due to ComfyUI limitations (and the fact that this node doesn't use any addtional libraries), this node will not work well for outputting large videos. You can trim any length of video without a problem, but if the output is still large it will end up using a lot of RAM. I have implemented various optimizations though to make it use less memory.

## DF-Load Audio UI  
<img width="1280" height="720" alt="Load_Audio_UI_V2" src="https://github.com/user-attachments/assets/e3dc5c8d-d0b9-4336-8196-944204719239" />
<br>
<br>
An upgraded Load Audio node. Features a simple interface to easily trim audio. Also allows dragging and dropping files (fixes the original node that doesn't allow dropping in videos). Also compatible with nodes 2.0.

# 💡 Workflows
Download workflows here: https://github.com/your-name/DF-WhatDreamsCost-ComfyUI/tree/main/example_workflows

# ❗ Known Issues

Fixed everything so far. If there are any other issue or bugs you find please let me know!

# 💡 Additional Info

Feel free to suggest improvements, and if you run into any bugs let me know!

For those asking, I mainly used gemini to create these nodes.
