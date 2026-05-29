# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import os
import shutil

class C_SUN_StoreUnusedPak(C_SUN_ToolBase):
    """
    Version info:
    1.0.0 - ported to the script manager
    """
    version =             "1.0.0"

    icon =                "📚 "
    info =                "Remove unused node packs"
    name =                "Store Unused Nodepacks"
    output_lines =        2
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
            "label":      "Folder for storing unused node packs",
            "lines":      1,
            "type":       TParamType.text,
            "use_ini":    True,
        },
        "plist": {
            "label":      "List of NEEDED node packs (lines starting with '#' are ignored)",
            "lines":      20,
            "type":       TParamType.text,
            "use_ini":    True,
        },
    }


    # #################################
    def run(self, src_path, back_path, plist):
        conlog(f"\n^A>>>>>>> {self.__class__.__name__} run...~")
        ini_params = {
            "src_path" : src_path,
            "back_path": back_path,
            "plist"    : plist,
        }
        save_tool_INI(self.name, ini_params)

        if len(src_path) == 0:
            snd_alert("error")
            return None, None, ERR_NO_SRCFOLDER

        if not os.path.exists(src_path):
            snd_alert("error")
            return None, None, ERR_SRCFOLDER

        if len(back_path) == 0:
            snd_alert("error")
            return None, None, "Storage folder for unused node packs not set!"

        keep_names = []
        for line in plist.split("\n"):
            ln = line.strip().lower()
            if not ln.startswith("#"):
                keep_names.append(ln)

        if len(keep_names) == 0:
            snd_alert("error")
            return None, None, "Fill in the list of needed node packs correctly"

        if src_path.endswith("Data"):
            custom_nodes_dir = os.path.join(src_path, "Packages", "ComfyUI", "custom_nodes")
        elif src_path.endswith("ComfyUI"):
            custom_nodes_dir = os.path.join(src_path, "custom_nodes")
        else:
            snd_alert("error")
            return None, None, ERR_SRCFOLDER

        if not os.path.exists(custom_nodes_dir):
            snd_alert("error")
            return None, None, f"{ERR_FOLDER_404} {custom_nodes_dir}"

        os.makedirs(back_path, exist_ok=True)
        moved = []
        skipped = []

        # Process all directories in custom_nodes
        for item in os.listdir(custom_nodes_dir):
            full_path = os.path.join(custom_nodes_dir, item)
            if not os.path.isdir(full_path): # move only dirs!
                continue

            if item.lower() in keep_names:
                skipped.append(item)
                continue

            target_path = os.path.join(back_path, item)
            conlog(f"^AMoving {item}...~")
            if os.path.exists(target_path):
                conlog("^A  Skipping: target already exists.~")
                continue
            try:
                shutil.move(full_path, target_path)
                moved.append(item)
            except Exception as e:
                conlog(f"^N  Failed to move {item}: {e}~")

        res = f"Moved: {len(moved)}\nSkipped: {len(skipped)}"

        snd_alert("finish")
        return res, None, "Ok!"


