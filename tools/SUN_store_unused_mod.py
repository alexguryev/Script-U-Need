# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import os
import shutil


class C_SUN_StoreUnusedMod(C_SUN_ToolBase):
    """
    Version info:
    1.0.0 - ported to the script manager
    """
    version =             "1.0.0"

    icon =                "📦 "
    info =                "Remove unused models"
    name =                "Store Unused Models"
    output_lines =        30
    output_type =         TParamType.text
    section =             TSections["ComfyUI"]

    inputs = {
        "src_path": {
            "label":      "Source folder",
            "info":       INFO_COMFYFOLDER,
            "lines":      1,
            "type":       TParamType.text,
            "use_ini":    True,
        },
        "back_path": {
            "label":      "Folder for storing unused models",
            "lines":      1,
            "type":       TParamType.text,
            "use_ini":    True,
        },
        "mlist": {
            "label":      "List of MODELS TO REMOVE",
            "lines":      20,
            "type":       TParamType.text,
            "use_ini":    True,
        },
    }


    # #################################
    def run(self, src_path, back_path, mlist):
        conlog(f"\n^A>>>>>>> {self.__class__.__name__} run...~")
        ini_params = {
            "src_path": src_path,
            "back_path": back_path,
            "mlist"   : mlist,
        }
        save_tool_INI(self.name, ini_params)

        if len(src_path) == 0:
            snd_alert("error")
            return None, None, ERR_NO_SRCFOLDER

        if src_path.endswith("Data"):
            custom_nodes_dir = os.path.join(src_path, "Packages", "ComfyUI", "custom_nodes")
        elif src_path.endswith("ComfyUI"):
            custom_nodes_dir = os.path.join(src_path, "custom_nodes")
        else:
            snd_alert("error")
            return None, None, ERR_SRCFOLDER

        if not os.path.exists(src_path):
            snd_alert("error")
            return None, None, ERR_SRCFOLDER

        if not os.path.exists(custom_nodes_dir):
            snd_alert("error")
            return None, None, f"{ERR_FOLDER_404} {custom_nodes_dir}"

        if len(back_path) == 0:
            snd_alert("error")
            return None, None, "Storage folder for unused models not set!"

        if len(mlist) == 0:
            snd_alert("error")
            return None, None, "List of models to remove not set!"

        result = ""

        # each line split by '|' --> get first element --> strip spaces from right
        relative_paths = []
        for line in mlist.split("\n"):
            relative_paths.append( (line.strip()).split("|")[0].rstrip() )

        for rel_path in relative_paths:
            source_file = os.path.join(src_path, rel_path)
            dest_file = os.path.join(back_path, rel_path)

            if not os.path.isfile(source_file):
                continue

            dest_dir = os.path.dirname(dest_file)
            os.makedirs(dest_dir, exist_ok=True) # crate folder for current file

            # file move
            try:
                shutil.move(source_file, dest_file)
                result += f"[Ok] moved:   {rel_path}\n"
            except Exception as e:
                result += f"[ERROR]:   {rel_path} — {e}\n"

        snd_alert("finish")
        return result, None, "Ok!"


