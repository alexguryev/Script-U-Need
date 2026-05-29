# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import os
from PIL import Image
import time

class C_SUN_ClearMeta(C_SUN_ToolBase):
    """
    Version info:
    1.0.2 - file counter
    1.0.1 - tuning
    1.0.0 - ported to the script manager
    """
    version =             "1.0.2"

    src_select =          [CH_FOLDER, CH_ARCHIVE]
    icon =                "🧼 "
    info =                "Remove metadata from images"
    name =                "Clear Metadata"
    output_type =         TParamType.text
    section =             TSections["Images"]

    inputs = {
        "stub": { # just for selector!
            "main_input": True,
            "selector":   True,
            "type":       TParamType.text,
        },
    }


    # #################################
    def run(self, src_select, folder_in, arch_in):
        conlog(f"\n^A>>>>>>> {self.__class__.__name__} run...~")
        ini_params = {
            "path_arch": get_filedir(arch_in),
            "path_fold": folder_in,
        }
        save_tool_INI(self.name, ini_params)

        nometa = os.sep + "_nometa"

        if src_select == CH_FOLDER: # =========================================================
            if folder_in == DIR_SUN:
                snd_alert("error")
                return None, None, ERR_SUNFOLDER

            output_folder = folder_in + nometa

        else: # CH_ARCHIVE =========================================================
            output_folder = get_filedir(arch_in)
            if output_folder == DIR_SUN:
                snd_alert("error")
                return None, None, ERR_SUNFOLDER

            count, err = check_archive(arch_in, ALLOWED_IMG_EXT) # check content
            if count == 0:
                snd_alert("error")
                return None, None, err

            output_folder += nometa
            folder_in, err = unpack_archive(arch_in, DIR_TEMP, temporary=True) # to tmp folder
            if folder_in is None:
                snd_alert("error")
                return None, None, err


        # process!
        os.makedirs(output_folder, exist_ok=True)
        Image.MAX_IMAGE_PIXELS = 933120000 # allow big files
        res = ""
        count = 0
        for filename in os.listdir(folder_in):
            input_path = os.path.join(folder_in, filename)
            if not os.path.isdir(input_path):
                if filename.lower().endswith(tuple(ALLOWED_IMG_EXT)):
                    t_start = time.time()
                    output_path = os.path.join(output_folder, get_filenameext(filename)[0] + ".jpg")
                    try:
                        with Image.open(input_path) as img:
                            img = img.convert("RGB")
                            img.save(output_path, "jpeg", quality=100, optimize=True)
                            elapsed = "{:.2f}".format(time.time() - t_start)
                            res += f"{filename} ..... ok, elapsed {elapsed} sec\n"
                            count += 1
                    except Exception as e:
                        res += f"{filename} ..... ERROR: {e}\n"
                else:
                    res += f"{filename} ..... is unknown file type!\n"
        res += f"\n{count} files are saved in: {output_folder}"

        if src_select == CH_ARCHIVE:
            rem_arch_tmp(folder_in) # remove archive tmp folder

        snd_alert("finish")
        return res, None, "Ok!"


