# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

import configparser
import enum
import gradio as gr
from gu_funclib import *
import importlib.util
import inspect
import os
import sys

"""
import copy
import cv2
import gc
import imagesize
import json
import pandas as pd
from PIL import Image
import random
import shutil
"""


# #########################################################################
# #########################################################################
# #########################################################################
# #############################  CONSTANTS  ###############################
# #########################################################################
# #########################################################################
# #########################################################################

# #############################  COMMON  ##################################
ALLOWED_IMG_EXT = [".png", ".jpg", ".jpeg", ".bmp", ".dds", ".eps", ".bmp", ".tga", ".tif", ".tiff", ".webp"]
ALLOWED_MOD_EXT = [".bin", ".ckpt", ".pt", ".pth", ".safetensors", ".sft"]
#ALLOWED_VID_EXT = [".mp4"]
DIR_SUN = os.getcwd()
DIR_CORE = os.path.join(DIR_SUN, "core")
DIR_TEMP = os.path.join(DIR_SUN, "tmp")
DIR_TOOLS = os.path.join(DIR_SUN, "tools")
DUR_ERR = 10
DUR_INFO = 5
INI_TOOLS = os.path.join(DIR_TOOLS, "tools.ini")
LOGLINES = 3
LSP = "       "
STUB_ARCHIVE = os.path.join(DIR_CORE, "arch_ready.jpg")
SND_VOLUME = 0.25 # sound volume (0.0 .. 1.0)

# #############################  CAPTIONS  ################################
CAP_ADVANCED = "Advanced parameters"
CAP_LOG = "Task execution"
CAP_RES_DWNL = "Ready file"
CAP_RES_PREV = "Result preview"
CAP_RESULT = "Result"
CAP_SRC_ARCH = "Archive"
CAP_SRC_AUDIO = "Sound"
CAP_SRC_FOLDER = "Folder"
CAP_SRC_IMG = "Image"
CAP_SRC_SELECTOR = "Source"
CAP_SRC_VID = "Video"
CAP_SUBMIT = "Run"

# ##########################  DROPBOX LISTS ###############################
CH_ARCHIVE = "Archive"
CH_FOLDER = "Folder"
CH_SINGLE = "Single"

# ##########################  ERROR MESSAGES  #############################
ERR_GETOUTPUT = "Error: result not received!"
ERR_IMGFILE = "Error in image file!"
ERR_NO_SRCARCHIVE = "Error: source archive not set!"
ERR_NO_SRCAUDIO = "Error: source audio not set!"
ERR_NO_SRCFILE = "Error: source file not set!"
ERR_NO_SRCFOLDER = "Error: source folder not set!"
ERR_NO_SRCIMAGE = "Error: source image not set!"
ERR_NO_SRCVIDEO = "Error: source video not set!"
ERR_RETRIEVE = "Error: result not returned!"
ERR_SRCFOLDER = "Check the source folder!"
ERR_SUNFOLDER = "Cannot use the Script-U-Need root folder!"
ERR_FOLDER_404 = "Folder not found!"

# ##########################  INFO MESSAGES  #############################
INFO_COMFYFOLDER = "for StabilityMatrix specify folder ...StabilityMatrix\\Data / for standalone - folder ...ComfyUI"

# #########################################################################
# #########################################################################
# #########################################################################
# ###########################  DATA TYPES  ################################
# #########################################################################
# #########################################################################
# #########################################################################

class TParamType(enum.Enum): # tool input and output param type
    markdown = 0
    text = 1
    number = 2
    slider = 3
    check = 4
    checkgroup = 5
    radio = 6
    dropbox = 7
    image = 8
    imageedit = 9
    video = 10
    audio = 11
    folder = 12
    archive = 13
    #preset = 14
    textfile = 15
    jsonfile = 16
    group = 17
    #button
    #colorpicker
    #model3d

ALLOWED_SINGLE_INPUTS = [
    TParamType.text, TParamType.image, TParamType.imageedit, TParamType.video, TParamType.audio, TParamType.textfile, TParamType.jsonfile
]
ALLOWED_TOOL_OUT = [
    TParamType.text, TParamType.image, TParamType.video, TParamType.audio, TParamType.textfile, TParamType.jsonfile
]
NOT_ARGUM_INPUTS = [
    TParamType.markdown
]

TSections = { # tools sections order
    "Test":     0,
    "Images":   1,
    "ComfyUI":  2,
    "Code":     3,
}
TSectionIcons = [ # tools icons in the same order!
    "👾", # test
    "🖼",  # image
    "♨️", # comfy
    "📄"  # code
]


# #########################################################################
# #########################################################################
# #########################################################################
# ###########################  FUNCTIONS  #################################
# #########################################################################
# #########################################################################
# #########################################################################

def _load_wav_scaled(filepath, volume):
    """Load WAV file and scale sample amplitude. Returns WAV bytes ready for playback."""
    import io, struct, wave
    with wave.open(filepath, 'rb') as wf:
        params = wf.getparams()
        raw = wf.readframes(params.nframes)

    # scale samples (16-bit PCM expected)
    if params.sampwidth == 2:
        n = len(raw) // 2
        samples = struct.unpack(f'<{n}h', raw)
        scaled = struct.pack(f'<{n}h', *(max(-32768, min(32767, int(s * volume))) for s in samples))
    else:
        scaled = raw  # unsupported sample width, play as-is

    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf_out:
        wf_out.setparams(params)
        wf_out.writeframes(scaled)
    return buf.getvalue()

# preload and cache scaled sounds at import time
_snd_cache = {}

def _snd_preload():
    global _snd_cache
    _sound_files = {
        "start":   "start.wav",
        "finish":  "finish.wav",
        "error":   "error.wav",
        "default": "default.wav",
    }
    for key, fname in _sound_files.items():
        fpath = os.path.join(DIR_CORE, fname)
        try:
            _snd_cache[key] = _load_wav_scaled(fpath, SND_VOLUME)
        except Exception:
            pass

_snd_preload()

def snd_alert(signal=""): # start / finish / error
    import threading, winsound
    data = _snd_cache.get(signal) or _snd_cache.get("default")
    if data:
        threading.Thread(
            target=lambda d: winsound.PlaySound(d, winsound.SND_MEMORY),
            args=(data,), daemon=True
        ).start()


# #########################################################################
ConfigSys = configparser.ConfigParser()

def setup_tools_by_INI(tools_list):
    global ConfigSys
    check = ConfigSys.read(INI_TOOLS, encoding="utf-8")

    for tool in tools_list:
        tool_block = None
        if len(check) > 0:
            try:
                tool_block = ConfigSys.options(tool.name)
            except Exception: pass

        if tool_block is None:
            ini_params = {}
            if CH_ARCHIVE in tool.src_select:
                tool.path_arch = DIR_SUN
                ini_params["path_arch"] = tool.path_arch
            if CH_FOLDER in tool.src_select:
                tool.path_fold = DIR_SUN
                ini_params["path_fold"] = tool.path_fold

            if not ConfigSys.has_section(tool.name):
                ConfigSys.add_section(tool.name)
            ConfigSys[tool.name] = ini_params
        else:
            if (CH_ARCHIVE in tool.src_select) and ("path_arch" in tool_block):
                if os.path.exists(ConfigSys[tool.name]["path_arch"]):
                    tool.path_arch = ConfigSys[tool.name]["path_arch"]
                else:
                    tool.path_arch = DIR_SUN

            if (CH_FOLDER in tool.src_select) and ("path_fold" in tool_block):
                if os.path.exists(ConfigSys[tool.name]["path_fold"]):
                    tool.path_fold = ConfigSys[tool.name]["path_fold"]
                else:
                    tool.path_fold = DIR_SUN

        if len(ConfigSys.items(tool.name)) == 0:
            ConfigSys.remove_section(tool.name) # clear empty ini section

    # refresh or save new ini
    try:
        with open(INI_TOOLS, "w", encoding="utf-8") as configfile:
            ConfigSys.write(configfile)
    except Exception:
        conlog("^NError saving tools.ini!~")


# #########################################################################
def save_tool_INI(toolname, params):
    global ConfigSys
    ConfigSys[toolname] = params
    try:
        with open(INI_TOOLS, "w", encoding="utf-8") as configfile:
            ConfigSys.write(configfile)
    except Exception:
        conlog("^NError saving tools.ini!~")


"""
# #########################################################################
def preformat_image(img): # return in PIL form
    if "PIL.Image.Image" in str(type(img)): # already PIL image
        return img
    elif "numpy.ndarray" in str(type(img)):
        return Image.fromarray(img)
    else: # filepath
        return Image.open(img)


# #########################################################################
def get_media_size(media, m_type, selector=CH_SINGLE): # for image/video size check dialog
    if media is None: return 0, 0

    width = height = 0
    if selector is None or selector == CH_SINGLE: # check only if single file!
        match m_type:
            case "img":
                media = preformat_image(media)
                try:
                    width, height = media.size
                except Exception as e:
                    conlog(f"^NException @ get_media_size/image : {e}~")

            case "vid":
                try:
                    cap = cv2.VideoCapture(media)
                    if cap.isOpened():
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    cap.release()
                except Exception as e:
                    conlog(f"^NException @ get_media_size/video : {e}~")

        if width == 0: conlog("^Nget_media_size: ZERO!~")

    #else: pass
    return width, height


# #########################################################################
def check_image_size_infile(fpath): # check image size without opening
    width = height = 0
    fail = False

    try:
        width, height = imagesize.get(fpath)
    except:
        fail = True
    if width == 0 or height == 0:
        fail = True

    if fail:
        return f"{ERR_IMGFILE} {fpath}"

    if width > IMG_SIZE_WARN or height > IMG_SIZE_WARN:
        return ERR_IMG_OVERSIZE

    return ""
"""

# #########################################################################
# #########################################################################
# #########################################################################
# ############################  TOOL BASE  ################################
# #########################################################################
# #########################################################################
# #########################################################################

class C_SUN_ToolBase:
    version =             "-.-.-" # major . minor . tuning

    advanced_col =        0 # advanced params in which column? count from 1 (0 = no advanced & no search for advanced)
    src_select =          [] # source selector (allowed up to 3 of type CH_SINGLE, CH_FOLDER, CH_ARCHIVE)
    icon =                "" # optional tool tab icon, space finished
    info =                "" # tool info
    input_cols =          1 # total input columns (max 2)
    name =                "NONAME" # Dobr-O-Matic tool tab label
    output_lines =        10 # for TParamType.text output only
    output_type =         TParamType.image # output preview type (image, video, ...)
    path_arch =           "" # default path for archive selection / stored in tools.ini
    path_fold =           "" # default path for folder selection / stored in tools.ini
    section =             TSections["Test"] # tool section tab

    inputs = {} # intefrace parameters: usual-1, advanced-1, usual-2, advanced-2
        # "in_name": { # param name (inner)
            # "_done_":     ..., # default = False / special internal field for interface creation
            # "advanced":   ..., # default = False / is this an advanced parameter? (ignored if advanced_col == 0)
            # "column":     ..., # default = 1 / which gradio column to occupy, count from 1 (ignored if advanced == True and advanced_col > 0)
            # "default":    ..., # default = None / default value
            # "info":       ..., # default = "" / interface detailed label
            # "label":      ..., # default = in_name / interface main label
            # "lines":      ..., # default = 1 / for text field: lines count
            # "main_input": ..., # default = False / exactly ONE input must be with main_input=True (image, video)
            # "range":      ..., # default = None / value range (only for numeric) / list for dropbox
            # "selector":   ..., # default = False / is selector (for media source) ! ONLY ONE SELECTOR ALLOWED, NOT IN ADVANCED !
            # "step":       ..., # default = None / step for slider or number
            # "type":       ..., # default = TParamType.text / data type
            # "use_ini":    ..., # default = False / use ini file to store? path to folder and archive are stored by default
        # },
        # ...

    # #################################
    def __init__(self):
        import copy
        self.inputs = copy.deepcopy(self.__class__.inputs)
        self.src_select = list(self.__class__.src_select)

    # #################################
    def get_input_params(self, in_name): # get input parameters with fallback values ! ORDER IS IMPORTANT !
        return  self.inputs[in_name].get("_done_", False), \
                self.inputs[in_name].get("advanced", False), \
                self.inputs[in_name].get("column", 1), \
                self.inputs[in_name].get("default", None), \
                self.inputs[in_name].get("info", ""), \
                self.inputs[in_name].get("label", in_name), \
                self.inputs[in_name].get("main_input", False), \
                self.inputs[in_name].get("lines", 1), \
                self.inputs[in_name].get("range", None), \
                self.inputs[in_name].get("selector", False), \
                self.inputs[in_name].get("step", None), \
                self.inputs[in_name].get("type", TParamType.text), \
                self.inputs[in_name].get("use_ini", False)

    # #################################
    def set_input_done(self, in_name): # mark input as done in interface
        self.inputs[in_name]["_done_"] = True

    # #################################
    def build_ui(self): # REDEFINABLE - custom UI builder (returns list of inputs or None for standard UI)
        return None

    # #################################
    def run(self, **kwargs): # REDEFINABLE
        return None, None, None # result, file name, log string


# #########################################################################
def load_SUN_tools(): # load and init tool classes
    if DIR_TOOLS not in sys.path:
        sys.path.insert(0, DIR_TOOLS)

    ready_tools = []
    known_names = set()

    for root, dirs, files in os.walk(DIR_TOOLS):
        for file in files:
            if not file.endswith(".py"):
                continue

            module_path = os.path.join(root, file)
            modname = get_filenameext(module_path)[0]
            full_modname = f"tools.{modname}"

            try:
                spec = importlib.util.spec_from_file_location(full_modname, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                # find subclasses of base tool class
                for name, cls in inspect.getmembers(module, inspect.isclass):
                    if issubclass(cls, C_SUN_ToolBase) and cls is not C_SUN_ToolBase:
                        if cls.name in known_names:
                            conlog(f"^N    Tool duplicate found, ignored: `{cls.name}` @ {file}~")
                            continue

                        tool_obj = cls() # init tool!
                        ready_tools.append(tool_obj)
                        known_names.add(cls.name)

                        conlog(f"^A    Tool init: V{tool_obj.version} `{tool_obj.name}` (from {file})~")
            except Exception as e:
                conlog(f"^R    Module `{file}` exception:~ {e}")

    if len(ready_tools) == 0:
        conlog("^R    No loaded tools!~")
        return []

    return sorted(ready_tools, key=lambda x: x.section) # sort tools list by tool section


