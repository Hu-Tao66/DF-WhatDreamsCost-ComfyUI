from .ltx_keyframer import LTXKeyframer
from .multi_image_loader import MultiImageLoader
from .ltx_sequencer import LTXSequencer
from .speech_length_calculator import SpeechLengthCalculator
from .load_audio_ui import LoadAudioUI
from .load_video_ui import LoadVideoUI
from .ltx_director import LTXDirector
from .ltx_auto_director import LTXAutoDirector
from .ltx_sixgrid_director import LTXSixGridDirector
from .ltx_director_guide import LTXDirectorGuide
from comfy_api.latest import ComfyExtension, io
from typing_extensions import override


class DFWhatDreamsCostExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            LTXKeyframer,
            LTXSequencer,
            LTXDirector,
            LTXAutoDirector,
            LTXSixGridDirector,
            LTXDirectorGuide,
        ]


async def comfy_entrypoint() -> DFWhatDreamsCostExtension:
    return DFWhatDreamsCostExtension()


NODE_CLASS_MAPPINGS = {
    "DF-LTXKeyframer": LTXKeyframer,
    "DF-MultiImageLoader": MultiImageLoader,
    "DF-LTXSequencer": LTXSequencer,
    "DF-SpeechLengthCalculator": SpeechLengthCalculator,
    "DF-LoadAudioUI": LoadAudioUI,
    "DF-LoadVideoUI": LoadVideoUI,
    "DF-LTXDirector": LTXDirector,
    "DF-LTXAutoDirector": LTXAutoDirector,
    "DF-LTXSixGridDirector": LTXSixGridDirector,
    "DF-LTXDirectorGuide": LTXDirectorGuide,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DF-LTXKeyframer": "DF LTX Keyframer",
    "DF-MultiImageLoader": "DF Multi Image Loader",
    "DF-LTXSequencer": "DF LTX Sequencer",
    "DF-SpeechLengthCalculator": "DF Speech Length Calculator",
    "DF-LoadAudioUI": "DF Load Audio UI",
    "DF-LoadVideoUI": "DF Load Video UI",
    "DF-LTXDirector": "DF LTX Director",
    "DF-LTXAutoDirector": "DF LTX Auto Director",
    "DF-LTXSixGridDirector": "DF-LTX \u516d\u5bab\u683c\u5bfc\u6f14\u53f0",
    "DF-LTXDirectorGuide": "DF LTX Director Guide",
}

WEB_DIRECTORY = "./df_js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
