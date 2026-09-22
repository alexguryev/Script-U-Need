# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import gradio as gr
import json
import os
import subprocess


TOOL_SUBDIR = "VidToSeq"

# pixel formats carrying an alpha channel - matched by name prefix rather than an enumerated
# list, since ffmpeg has a "yuva/rgba/bgra/gbrap/ayuv" variant per bit depth (8/9/10/12/16/32,
# be/le) and a fixed list kept missing the less common depths (eg. ProRes 4444 -> yuva444p12le)
ALPHA_PIX_PREFIXES = ("yuva", "rgba", "bgra", "argb", "abgr", "ya8", "ya16", "gbrap", "ayuv")

def has_alpha_pixfmt(pix_fmt):
    p = str(pix_fmt or "").lower()
    return p.startswith(ALPHA_PIX_PREFIXES)

# process creation flags - no console window popup on Windows
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# #########################################################################
def ff_call(args): # run ffmpeg/ffprobe, return (ok, output)
    try:
        proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", creationflags=NOWIN)
    except Exception as e:
        return False, str(e)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "").strip()
    return True, (proc.stdout or "").strip()


# #########################################################################
def probe_video_alpha(fpath): # -> (info dict, error string)
    ok, out = ff_call([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,pix_fmt", "-of", "json", fpath
    ])
    if not ok:
        return None, f"ffprobe failed: {out}"

    try:
        data = json.loads(out)
        stream = data["streams"][0]
    except Exception:
        return None, "no video stream found!"

    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    if width == 0 or height == 0:
        return None, "cannot read frame size!"

    pix_fmt = str(stream.get("pix_fmt") or "")
    return {"width": width, "height": height, "has_alpha": has_alpha_pixfmt(pix_fmt)}, ""


# ########################################################
class C_SUN_VidToSeq(C_SUN_ToolBase):
    """
    Version info:
    1.0.0 - extract video frames into a numbered image sequence: JPG (max quality) at source
            resolution, or PNG with transparency when the source is a MOV with an alpha channel;
            alpha detection matches the pixel format by name prefix instead of an enumerated
            list, so deep bit depths (eg. ProRes 4444 -> yuva444p12le) are not missed
    """
    version =             "1.0.0"

    src_select =          [CH_SINGLE, CH_FOLDER, CH_ARCHIVE]
    icon =                "📽️ "
    info =                "Extract video frames into a numbered image sequence (JPG, or PNG with alpha for a MOV with transparency). Requires ffmpeg installed in the system"
    name =                "Vid to Seq"
    output_type =         TParamType.text
    output_lines =        10
    section =             TSections["Video"]

    inputs = {}

    # ########################################################
    def __init__(self):
        super().__init__()

    # ########################################################
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

    # ########################################################
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

    # ########################################################
    def build_ui(self):
        inputs_list = []

        with gr.Column(scale=2):
            if not FFMPEG_OK:
                gr.Markdown(f"### ⛔ {ERR_NO_FFMPEG}")

            # single file panel
            with gr.Column(visible=(self.src_select[0] == CH_SINGLE)) as file_in_pan:
                file_in = gr.Video(label=CAP_SRC_VID, interactive=True, sources=["upload"], format=None, autoplay=False)

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
                gr.Markdown("⚠️ WARNING! Frames are saved in the tmp/ folder, one subfolder per source video")

        self._selector_out = [file_in_pan, folder_in_pan, arch_in_pan]
        self._selector_inputs = [file_in, folder_in, arch_in]

        return inputs_list

    # ########################################################
    def _extract(self, src, out_root):
        """Extract one video into its own numbered sequence subfolder. Returns (ok, log line)."""
        name = get_filenameext(src)[0]
        ext = os.path.splitext(src)[1].lower()

        info, err = probe_video_alpha(src)
        if info is None:
            return False, f"{os.path.basename(src)}: {err}"

        use_png = (ext == ".mov" and info["has_alpha"])
        sub_dir = os.path.join(out_root, name)
        os.makedirs(sub_dir, exist_ok=True)
        pattern = os.path.join(sub_dir, f"{name}_%05d.{'png' if use_png else 'jpg'}")

        cmd = ["ffmpeg", "-y", "-i", src, "-start_number", "0", "-fps_mode", "passthrough"]
        if use_png:
            cmd += ["-pix_fmt", "rgba"]
        else:
            cmd += ["-q:v", "1"]
        cmd += [pattern]

        ok, msg = ff_call(cmd)
        if not ok:
            return False, f"{os.path.basename(src)}: ffmpeg failed - {msg.splitlines()[-1] if msg else 'unknown error'}"

        frame_count = len([f for f in os.listdir(sub_dir) if not os.path.isdir(os.path.join(sub_dir, f))])
        fmt = "PNG (alpha)" if use_png else "JPG"
        return True, f"{os.path.basename(src)}: {frame_count} frames, {info['width']}x{info['height']}, {fmt} -> {sub_dir}"

    # ########################################################
    def run(self, src_select, file_in, folder_in, arch_in):
        conlog(f"\n^A>>>>>>> {self.__class__.__name__} run...~")

        if not FFMPEG_OK:
            conlog(f"^N    {ERR_NO_FFMPEG}~")
            snd_alert("error")
            return None, None, ERR_NO_FFMPEG

        save_tool_INI(self.name, {
            "path_fold": folder_in,
            "path_arch": get_filedir(arch_in),
        })

        # ######## collect sources
        tmp_folder = None
        src_files = []

        if src_select == CH_SINGLE:
            if not file_in or not os.path.isfile(file_in):
                snd_alert("error")
                return None, None, ERR_NO_SRCVIDEO
            src_files.append(file_in)

        elif src_select == CH_FOLDER:
            if folder_in == DIR_SUN:
                snd_alert("error")
                return None, None, ERR_SUNFOLDER
            if not os.path.isdir(folder_in):
                snd_alert("error")
                return None, None, ERR_FOLDER_404
            src_files = [
                os.path.join(folder_in, f) for f in sorted(os.listdir(folder_in))
                if not os.path.isdir(os.path.join(folder_in, f))
                and f.lower().endswith(tuple(ALLOWED_VID_EXT))
            ]
            if len(src_files) == 0:
                snd_alert("error")
                return None, None, ERR_NO_VIDFILES

        else: # CH_ARCHIVE
            if get_filedir(arch_in) == DIR_SUN:
                snd_alert("error")
                return None, None, ERR_SUNFOLDER
            count, err = check_archive(arch_in, ALLOWED_VID_EXT)
            if count == 0:
                snd_alert("error")
                return None, None, err
            work_folder, err = unpack_archive(arch_in, DIR_TEMP, temporary=True)
            if work_folder is None:
                snd_alert("error")
                return None, None, err
            tmp_folder = work_folder
            src_files = [
                os.path.join(work_folder, f) for f in sorted(os.listdir(work_folder))
                if not os.path.isdir(os.path.join(work_folder, f))
                and f.lower().endswith(tuple(ALLOWED_VID_EXT))
            ]
            if len(src_files) == 0:
                rem_arch_tmp(tmp_folder)
                snd_alert("error")
                return None, None, ERR_NO_VIDFILES

        # ######## process
        out_root = os.path.join(DIR_TEMP, TOOL_SUBDIR)
        os.makedirs(out_root, exist_ok=True)

        snd_alert("start")
        result_lines = []
        fails = []
        done_count = 0

        for src in src_files:
            ok, line = self._extract(src, out_root)
            if ok:
                done_count += 1
                conlog(f"^A    {line}~")
                result_lines.append(line)
            else:
                fails.append(line)
                conlog(f"^N    {line}~")

        if tmp_folder:
            rem_arch_tmp(tmp_folder)

        if done_count == 0:
            snd_alert("error")
            return None, None, "Failed: " + ("; ".join(fails) if fails else ERR_GETOUTPUT)

        result_text = "\n".join(result_lines)
        if fails:
            result_text += "\n\nErrors:\n" + "\n".join(fails)

        snd_alert("finish")
        return result_text, None, f"Done: {done_count} of {len(src_files)} video(s) -> {out_root}"
