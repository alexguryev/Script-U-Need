# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import gradio as gr
import math
import os
from PIL import Image


DEFAULT_GAP_COLOR = "#000000"


def parse_picker_value(val):
    """Parse ColorPicker value (rgba/rgb string or hex) to #rrggbb."""
    if not val:
        return DEFAULT_GAP_COLOR
    val = val.strip()
    if val.startswith('#'):
        return val
    import re
    m = re.match(r'rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)', val)
    if m:
        r = max(0, min(255, round(float(m.group(1)))))
        g = max(0, min(255, round(float(m.group(2)))))
        b = max(0, min(255, round(float(m.group(3)))))
        return f"#{r:02x}{g:02x}{b:02x}"
    return DEFAULT_GAP_COLOR


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


class C_SUN_AtlasCompose(C_SUN_ToolBase):
    """
    Version info:
    1.0.0 - atlas composer from uniform images
    """
    version =             "1.0.0"

    src_select =          [CH_FOLDER, CH_ARCHIVE]
    icon =                "🔢 "
    info =                "Assemble a square atlas from same-size images"
    name =                "Atlas Compose"
    output_type =         TParamType.image
    section =             TSections["Images"]

    inputs = {}

    # #################################
    def __init__(self):
        super().__init__()
        self.gap_color = DEFAULT_GAP_COLOR

    # #################################
    def _choose_folder(self, init_dir):
        import tkinter as tk, tkinter.filedialog
        tk_root = tk.Tk()
        tk_root.attributes("-alpha", 0.0)
        tk_root.attributes("-topmost", True)
        f = None
        try:
            f = tk.filedialog.askdirectory(parent=tk_root, initialdir=init_dir, title="Select folder", mustexist=True)
        except Exception: pass
        tk_root.destroy()
        if f not in [".", " ", "", init_dir]:
            result = os.path.normpath(f)
            save_tool_INI(self.name, {"path_fold": result, "path_arch": self.path_arch})
            self.path_fold = result
            return result
        return init_dir

    def _choose_arch(self, init_path):
        import tkinter as tk, tkinter.filedialog
        init_dir = get_filedir(init_path)
        tk_root = tk.Tk()
        tk_root.attributes("-alpha", 0.0)
        tk_root.attributes("-topmost", True)
        f = None
        try:
            f = tk.filedialog.askopenfilename(parent=tk_root, initialdir=init_dir, title="Select archive", filetypes=[("Zip files", "*.zip"), ("All files", "*.*")])
        except Exception: pass
        tk_root.destroy()
        if f not in [".", " ", "", init_dir]:
            result = os.path.normpath(f)
            save_tool_INI(self.name, {"path_fold": self.path_fold, "path_arch": get_filedir(result)})
            self.path_arch = get_filedir(result)
            return result
        return init_path

    # #################################
    def build_ui(self):
        inputs_list = []

        with gr.Column(scale=2):
            # folder/archive selector panels
            with gr.Column(visible=(self.src_select[0]==CH_FOLDER)) as folder_in_pan:
                with gr.Row():
                    btn_sel_folder = gr.Button("Select folder", scale=1)
                    folder_in = gr.Textbox(value=self.path_fold, show_label=False, interactive=False, container=False, scale=4)
                with gr.Row(): gr.Markdown("<div><br><br></div>")
                btn_sel_folder.click(fn=self._choose_folder, inputs=folder_in, outputs=folder_in)

            with gr.Column(visible=(self.src_select[0]==CH_ARCHIVE)) as arch_in_pan:
                with gr.Row():
                    btn_sel_arch = gr.Button("Select archive", scale=1)
                    arch_in = gr.Textbox(value=self.path_arch, show_label=False, interactive=False, container=False, scale=4)
                with gr.Row(): gr.Markdown("<div><br><br></div>")
                btn_sel_arch.click(fn=self._choose_arch, inputs=arch_in, outputs=arch_in)

            inputs_list.extend([folder_in, arch_in])

            with gr.Row(variant="panel"):
                gap_width = gr.Number(
                    value=0,
                    label="Gap width",
                    minimum=0,
                    maximum=256,
                    step=1,
                    interactive=True,
                )
                gap_color_picker = gr.ColorPicker(
                    value=self.gap_color,
                    label="Gap color",
                    interactive=True,
                )
                border_check = gr.Checkbox(
                    value=False,
                    label="Add border",
                    interactive=True,
                )

            inputs_list.extend([gap_width, gap_color_picker, border_check])

        # register selector panels for src_select switching
        self._selector_out = [folder_in_pan, arch_in_pan]
        self._selector_inputs = [folder_in, arch_in]

        return inputs_list

    # #################################
    def run(self, src_select, folder_in, arch_in, gap_width, gap_color_raw, border):
        conlog(f"\n^A>>>>>>> {self.__class__.__name__} run...~")

        gap_width = int(gap_width) if gap_width else 0
        gap_color_hex = parse_picker_value(gap_color_raw)
        gap_rgb = hex_to_rgb(gap_color_hex)

        ini_params = {
            "path_arch": get_filedir(arch_in),
            "path_fold": folder_in,
        }
        save_tool_INI(self.name, ini_params)

        # get source folder
        tmp_folder = None
        if src_select == CH_FOLDER:
            if folder_in == DIR_SUN:
                snd_alert("error")
                return None, None, ERR_SUNFOLDER

            work_folder = folder_in

        else: # CH_ARCHIVE
            output_dir = get_filedir(arch_in)
            if output_dir == DIR_SUN:
                snd_alert("error")
                return None, None, ERR_SUNFOLDER

            count, err = check_archive(arch_in, ALLOWED_IMG_EXT)
            if count == 0:
                snd_alert("error")
                return None, None, err

            work_folder, err = unpack_archive(arch_in, DIR_TEMP, temporary=True)
            if work_folder is None:
                snd_alert("error")
                return None, None, err
            tmp_folder = work_folder

        # collect image files (alphabetical order)
        img_files = sorted([
            f for f in os.listdir(work_folder)
            if not os.path.isdir(os.path.join(work_folder, f))
            and f.lower().endswith(tuple(ALLOWED_IMG_EXT))
        ])

        if len(img_files) == 0:
            if tmp_folder:
                rem_arch_tmp(tmp_folder)
            snd_alert("error")
            return None, None, "Images not found!"

        # open images and check sizes
        Image.MAX_IMAGE_PIXELS = 933120000
        images = []
        ref_size = None
        for fname in img_files:
            fpath = os.path.join(work_folder, fname)
            try:
                img = Image.open(fpath)
                img.load()
            except Exception as e:
                if tmp_folder:
                    rem_arch_tmp(tmp_folder)
                snd_alert("error")
                return None, None, f"Error opening file {fname}: {e}"

            if ref_size is None:
                ref_size = img.size
            elif img.size != ref_size:
                if tmp_folder:
                    rem_arch_tmp(tmp_folder)
                snd_alert("error")
                return None, None, "Check image set - size mismatch"

            images.append(img)

        # calculate grid
        n = len(images)
        grid_side = math.ceil(math.sqrt(n))
        img_w, img_h = ref_size
        border_w = gap_width if border else 0

        # atlas dimensions
        atlas_w = grid_side * img_w + (grid_side - 1) * gap_width + 2 * border_w
        atlas_h = grid_side * img_h + (grid_side - 1) * gap_width + 2 * border_w

        # create atlas
        atlas = Image.new("RGB", (atlas_w, atlas_h), gap_rgb)

        for idx, img in enumerate(images):
            row = idx // grid_side
            col = idx % grid_side
            x = border_w + col * (img_w + gap_width)
            y = border_w + row * (img_h + gap_width)
            atlas.paste(img, (x, y))
            img.close()

        # save to tmp
        os.makedirs(DIR_TEMP, exist_ok=True)
        out_path = os.path.join(DIR_TEMP, "atlas.jpg")
        atlas.save(out_path, "JPEG", quality=100, optimize=True)

        if tmp_folder:
            rem_arch_tmp(tmp_folder)

        snd_alert("finish")
        return atlas, out_path, f"Atlas {grid_side}x{grid_side} ({atlas_w}x{atlas_h}px), {n} images"
