# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import gradio as gr
import os
from PIL import Image


TOOL_SUBDIR = "AtlasDecompose"


class C_SUN_AtlasDecompose(C_SUN_ToolBase):
    """
    Version info:
    1.0.0 - atlas decomposer: split atlas image into individual tiles
    """
    version =             "1.0.0"

    src_select =          [CH_SINGLE, CH_FOLDER, CH_ARCHIVE]
    icon =                "🔣 "
    info =                "Decompose atlas image into individual tiles"
    name =                "Atlas Decompose"
    output_type =         TParamType.text
    output_lines =        10
    section =             TSections["Images"]

    inputs = {}

    # #################################
    def __init__(self):
        super().__init__()

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
            f = tk.filedialog.askopenfilename(
                parent=tk_root, initialdir=init_dir, title="Select archive",
                filetypes=[("Zip files", "*.zip"), ("All files", "*.*")]
            )
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
            # single image panel
            with gr.Column(visible=(self.src_select[0] == CH_SINGLE)) as file_in_pan:
                file_in = gr.Image(label=CAP_SRC_IMG, interactive=True, type="filepath")

            # folder panel
            with gr.Column(visible=(self.src_select[0] == CH_FOLDER)) as folder_in_pan:
                with gr.Row():
                    btn_sel_folder = gr.Button("Select folder", scale=1)
                    folder_in = gr.Textbox(value=self.path_fold, show_label=False, interactive=False, container=False, scale=4)
                with gr.Row(): gr.Markdown("<div><br><br></div>")
                btn_sel_folder.click(fn=self._choose_folder, inputs=folder_in, outputs=folder_in)

            # archive panel
            with gr.Column(visible=(self.src_select[0] == CH_ARCHIVE)) as arch_in_pan:
                with gr.Row():
                    btn_sel_arch = gr.Button("Select archive", scale=1)
                    arch_in = gr.Textbox(value=self.path_arch, show_label=False, interactive=False, container=False, scale=4)
                with gr.Row(): gr.Markdown("<div><br><br></div>")
                btn_sel_arch.click(fn=self._choose_arch, inputs=arch_in, outputs=arch_in)

            inputs_list.extend([file_in, folder_in, arch_in])

            with gr.Row():
                gap_width = gr.Number(
                    value=0,
                    label="Gap width",
                    minimum=0,
                    maximum=256,
                    step=1,
                    interactive=True,
                )
                has_border = gr.Checkbox(
                    value=False,
                    label="Has border",
                    interactive=True,
                )
                border_width = gr.Number(
                    value=0,
                    label="Border width",
                    minimum=0,
                    maximum=256,
                    step=1,
                    interactive=True,
                )

            inputs_list.extend([gap_width, has_border, border_width])

            with gr.Row():
                elem_w = gr.Number(
                    value=1024,
                    label="Element width",
                    minimum=1,
                    maximum=16384,
                    step=1,
                    interactive=True,
                )
                elem_h = gr.Number(
                    value=1024,
                    label="Element height",
                    minimum=1,
                    maximum=16384,
                    step=1,
                    interactive=True,
                )

            inputs_list.extend([elem_w, elem_h])

            with gr.Row():
                gr.Markdown("⚠️ WARNING! Processed sources are saved in the tmp/ folder")

        self._selector_out = [file_in_pan, folder_in_pan, arch_in_pan]
        self._selector_inputs = [file_in, folder_in, arch_in]

        return inputs_list

    # #################################
    def run(self, src_select, file_in, folder_in, arch_in, gap_width, has_border, border_width, elem_w, elem_h):
        conlog(f"\n^A>>>>>>> {self.__class__.__name__} run...~")

        gap_width  = int(gap_width)    if gap_width    else 0
        border_w   = int(border_width) if (has_border and border_width) else 0
        elem_w     = int(elem_w)       if elem_w       else 1024
        elem_h     = int(elem_h)       if elem_h       else 1024

        save_tool_INI(self.name, {
            "path_fold": folder_in,
            "path_arch": get_filedir(arch_in),
        })

        # collect source images
        tmp_folder = None
        src_files = []  # list of (fpath, name_no_ext, is_png)

        if src_select == CH_SINGLE:
            if not file_in or not os.path.isfile(file_in):
                snd_alert("error")
                return None, None, ERR_NO_SRCIMAGE
            fname = os.path.basename(file_in)
            name_no_ext = os.path.splitext(fname)[0]
            src_files.append((file_in, name_no_ext, fname.lower().endswith(".png")))

        elif src_select == CH_FOLDER:
            if folder_in == DIR_SUN:
                snd_alert("error")
                return None, None, ERR_SUNFOLDER
            flist = sorted([
                f for f in os.listdir(folder_in)
                if not os.path.isdir(os.path.join(folder_in, f))
                and f.lower().endswith(tuple(ALLOWED_IMG_EXT))
            ])
            if len(flist) == 0:
                snd_alert("error")
                return None, None, "Images not found!"
            for fname in flist:
                name_no_ext = os.path.splitext(fname)[0]
                src_files.append((os.path.join(folder_in, fname), name_no_ext, fname.lower().endswith(".png")))

        else:  # CH_ARCHIVE
            if get_filedir(arch_in) == DIR_SUN:
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
            flist = sorted([
                f for f in os.listdir(work_folder)
                if not os.path.isdir(os.path.join(work_folder, f))
                and f.lower().endswith(tuple(ALLOWED_IMG_EXT))
            ])
            for fname in flist:
                name_no_ext = os.path.splitext(fname)[0]
                src_files.append((os.path.join(work_folder, fname), name_no_ext, fname.lower().endswith(".png")))

        # output directory
        out_dir = os.path.join(DIR_TEMP, TOOL_SUBDIR)
        os.makedirs(out_dir, exist_ok=True)

        Image.MAX_IMAGE_PIXELS = 933120000
        total_saved = 0
        result_lines = []

        for fpath, name_no_ext, is_png in src_files:
            try:
                img = Image.open(fpath)
                img.load()
            except Exception as e:
                if tmp_folder:
                    rem_arch_tmp(tmp_folder)
                snd_alert("error")
                return None, None, f"Error opening {os.path.basename(fpath)}: {e}"

            atlas_w, atlas_h = img.size

            # n = (size - 2*border + gap) / (elem + gap)
            n_cols = max(1, (atlas_w - 2 * border_w + gap_width) // (elem_w + gap_width) if (elem_w + gap_width) > 0 else 1)
            n_rows = max(1, (atlas_h - 2 * border_w + gap_width) // (elem_h + gap_width) if (elem_h + gap_width) > 0 else 1)

            save_ext = ".png" if is_png else ".jpg"
            idx = 1
            for row in range(n_rows):
                for col in range(n_cols):
                    x = border_w + col * (elem_w + gap_width)
                    y = border_w + row * (elem_h + gap_width)
                    if x + elem_w > atlas_w or y + elem_h > atlas_h:
                        continue
                    crop = img.crop((x, y, x + elem_w, y + elem_h))
                    out_path = os.path.join(out_dir, f"{name_no_ext}_{idx:03d}{save_ext}")
                    if is_png:
                        crop.save(out_path, "PNG")
                    else:
                        crop.convert("RGB").save(out_path, "JPEG", quality=100, optimize=True)
                    crop.close()
                    idx += 1

            img.close()
            saved = idx - 1
            total_saved += saved
            result_lines.append(f"{os.path.basename(fpath)}: {n_cols}x{n_rows} = {saved} elem.")

        if tmp_folder:
            rem_arch_tmp(tmp_folder)

        result_text = "\n".join(result_lines) + f"\n\nTotal saved: {total_saved} elements\nFolder: {out_dir}"

        snd_alert("finish")
        return result_text, None, f"Done: {total_saved} elements"
