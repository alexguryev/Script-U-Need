# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import gradio as gr
import json
import os
import re
import subprocess


TOOL_SUBDIR = "SeqToVid"

SEQ_EXT = [".jpg", ".jpeg", ".png"]

FMT_CHOICES = ["mp4", "mov", "avi"]
DEF_FMT = "mp4"

FPS_CHOICES = ["24", "25", "30"]
DEF_FPS = "24"

Q_CHOICES = ["High", "Good", "Medium", "Low"]
Q_CRF = {"High": 16, "Good": 20, "Medium": 24, "Low": 28} # libx264 (mp4, mov)
Q_QSCALE = {"High": 2, "Good": 4, "Medium": 6, "Low": 9}  # mpeg4 (avi)

DEF_OUT_NAME = "video"

# pixel formats carrying an alpha channel - matched by name prefix rather than an enumerated
# list, since ffmpeg has a "yuva/rgba/bgra/gbrap/ayuv" variant per bit depth (8/9/10/12/16/32,
# be/le) and a fixed list kept missing the less common depths (eg. ProRes 4444 -> yuva444p12le)
ALPHA_PIX_PREFIXES = ("yuva", "rgba", "bgra", "argb", "abgr", "ya8", "ya16", "gbrap", "ayuv")

def has_alpha_pixfmt_name(pix_fmt):
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
def has_alpha_pixfmt(fpath): # -> bool (image alpha check via ffprobe)
    ok, out = ff_call([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=pix_fmt", "-of", "json", fpath
    ])
    if not ok:
        return False
    try:
        pix_fmt = json.loads(out)["streams"][0].get("pix_fmt", "")
    except Exception:
        return False
    return has_alpha_pixfmt_name(pix_fmt)


# #########################################################################
def check_qtrle(): # is the qtrle (alpha-capable mov) encoder available?
    ok, out = ff_call(["ffmpeg", "-hide_banner", "-encoders"])
    return ok and "qtrle" in out


# #########################################################################
def enc_args(ext, quality): # encoder arguments for the target container
    if ext == ".avi": # classic mpeg4 - the most compatible codec for avi
        return ["-c:v", "mpeg4", "-vtag", "xvid", "-q:v", str(Q_QSCALE[quality]), "-pix_fmt", "yuv420p"]

    args = ["-c:v", "libx264", "-crf", str(Q_CRF[quality]), "-preset", "slow", "-pix_fmt", "yuv420p"]
    if ext == ".mp4":
        args += ["-movflags", "+faststart"]
    return args


# #########################################################################
def parse_seq_files(file_list): # -> (sorted [(num, path), ...], error)
    ext_set = set()
    items = []
    for f in file_list:
        name, ext = get_filenameext(f)
        ext_set.add(ext.lower())
        m = re.search(r"(\d+)$", name)
        if not m:
            return None, f"File has no numeric index: '{os.path.basename(f)}'"
        items.append((int(m.group(1)), f))

    if len(ext_set) > 1:
        return None, f"Mixed file types in sequence: {', '.join(sorted(ext_set))}"

    items.sort(key=lambda x: x[0])
    for i in range(1, len(items)):
        if items[i][0] != items[i - 1][0] + 1:
            return None, f"Sequence gap between frame {items[i - 1][0]} and {items[i][0]} - numbering must be consecutive!"

    return items, ""


# ########################################################
class C_SUN_SeqToVid(C_SUN_ToolBase):
    """
    Version info:
    1.0.0 - assemble a numbered JPG/PNG sequence into a video (default FPS 24, default output
            filename "video", container, compression quality); writes an alpha-channel MOV when
            the source PNGs are transparent and MOV is selected; alpha detection matches the
            pixel format by name prefix instead of an enumerated list, so deep bit depths
            (eg. ProRes 4444 -> yuva444p12le) are not missed
    """
    version =             "1.0.0"

    src_select =          [CH_FOLDER, CH_ARCHIVE]
    icon =                "🎥 "
    info =                "Assemble a numbered image sequence (JPG/PNG) into a video. Requires ffmpeg installed in the system"
    name =                "Seq to Vid"
    output_type =         TParamType.video
    section =             TSections["Video"]

    inputs = {}

    # ########################################################
    def __init__(self):
        super().__init__()
        self.params = {
            "out_name": DEF_OUT_NAME,
            "fps":      DEF_FPS,
            "fmt":      DEF_FMT,
            "quality":  Q_CHOICES[0],
        }

    # ########################################################
    def _load_params(self):
        try:
            if ConfigSys.has_section(self.name):
                for key in self.params.keys():
                    if ConfigSys.has_option(self.name, key):
                        self.params[key] = ConfigSys[self.name][key]
        except Exception:
            pass

        if not self.params["out_name"]:
            self.params["out_name"] = DEF_OUT_NAME
        if self.params["fps"] not in FPS_CHOICES:
            self.params["fps"] = DEF_FPS
        if self.params["fmt"] not in FMT_CHOICES:
            self.params["fmt"] = DEF_FMT
        if self.params["quality"] not in Q_CHOICES:
            self.params["quality"] = Q_CHOICES[0]

    # ########################################################
    def _save_params(self):
        stored = dict(self.params)
        stored["path_fold"] = self.path_fold
        stored["path_arch"] = self.path_arch
        save_tool_INI(self.name, stored)

    # ########################################################
    def _set_param(self, key, value):
        self.params[key] = str(value)
        self._save_params()

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
            self.path_fold = result
            self._save_params()
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
            self.path_arch = get_filedir(result)
            self._save_params()
            return result
        return init_path

    # ########################################################
    def build_ui(self):
        self._load_params()
        p = self.params

        inputs_list = []

        with gr.Column(scale=2):
            if not FFMPEG_OK:
                gr.Markdown(f"### ⛔ {ERR_NO_FFMPEG}")

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

            inputs_list.extend([folder_in, arch_in])

            with gr.Group():
                gr.Markdown("**Output**", container=False)
                out_name = gr.Textbox(value=p["out_name"], label="Output filename", info="without extension", interactive=True)
                with gr.Row():
                    fps = gr.Dropdown(value=p["fps"], choices=FPS_CHOICES, label="FPS", interactive=True, allow_custom_value=False)
                    fmt = gr.Dropdown(value=p["fmt"], choices=FMT_CHOICES, label="Format", interactive=True, allow_custom_value=False)
                    quality = gr.Dropdown(value=p["quality"], choices=Q_CHOICES, label="Quality",
                                          info="used for compressed formats", interactive=True, allow_custom_value=False)

            inputs_list.extend([out_name, fps, fmt, quality])

            with gr.Row():
                gr.Markdown("⚠️ WARNING! Assembled video is saved in the tmp/ folder")

            for key, ctrl in (("fps", fps), ("fmt", fmt), ("quality", quality)):
                def make_handler(param_key):
                    def on_change(value):
                        self._set_param(param_key, value)
                    return on_change
                ctrl.change(fn=make_handler(key), inputs=ctrl)

            def on_name_input(value):
                name = legalize_name(str(value or "").strip()) or DEF_OUT_NAME
                self._set_param("out_name", name)
                return gr.update(value=name)
            out_name.input(fn=on_name_input, inputs=out_name, outputs=out_name)

        self._selector_out = [folder_in_pan, arch_in_pan]
        self._selector_inputs = [folder_in, arch_in]

        return inputs_list

    # ########################################################
    def run(self, src_select, folder_in, arch_in, out_name, fps, fmt, quality):
        conlog(f"\n^A>>>>>>> {self.__class__.__name__} run...~")

        if not FFMPEG_OK:
            conlog(f"^N    {ERR_NO_FFMPEG}~")
            snd_alert("error")
            return None, None, ERR_NO_FFMPEG

        # ######## normalize params
        out_name = legalize_name(str(out_name or "").strip()) or DEF_OUT_NAME
        if fps not in FPS_CHOICES: fps = DEF_FPS
        if fmt not in FMT_CHOICES: fmt = DEF_FMT
        if quality not in Q_CHOICES: quality = Q_CHOICES[0]
        out_ext = f".{fmt}"

        self.params.update({"out_name": out_name, "fps": fps, "fmt": fmt, "quality": quality})
        self.path_fold = folder_in
        self.path_arch = get_filedir(arch_in)
        self._save_params()

        # ######## collect sources
        tmp_folder = None

        if src_select == CH_FOLDER:
            if folder_in == DIR_SUN:
                snd_alert("error")
                return None, None, ERR_SUNFOLDER
            if not os.path.isdir(folder_in):
                snd_alert("error")
                return None, None, ERR_FOLDER_404
            work_folder = folder_in

        else: # CH_ARCHIVE
            if get_filedir(arch_in) == DIR_SUN:
                snd_alert("error")
                return None, None, ERR_SUNFOLDER
            count, err = check_archive(arch_in, SEQ_EXT)
            if count == 0:
                snd_alert("error")
                return None, None, err
            work_folder, err = unpack_archive(arch_in, DIR_TEMP, temporary=True)
            if work_folder is None:
                snd_alert("error")
                return None, None, err
            tmp_folder = work_folder

        src_files = [
            os.path.join(work_folder, f) for f in os.listdir(work_folder)
            if not os.path.isdir(os.path.join(work_folder, f))
            and f.lower().endswith(tuple(SEQ_EXT))
        ]
        if len(src_files) == 0:
            if tmp_folder:
                rem_arch_tmp(tmp_folder)
            snd_alert("error")
            return None, None, "Error: no image files found!"

        # ######## validate the sequence
        items, err = parse_seq_files(src_files)
        if items is None:
            if tmp_folder:
                rem_arch_tmp(tmp_folder)
            snd_alert("error")
            return None, None, err

        first_ext = os.path.splitext(items[0][1])[1].lower()
        has_alpha = (first_ext == ".png") and has_alpha_pixfmt(items[0][1])
        want_alpha_out = (out_ext == ".mov" and has_alpha and check_qtrle())

        # ######## build the concat list (frame-accurate slideshow demuxer trick)
        stage_dir = os.path.join(DIR_TEMP, TOOL_SUBDIR, f"_build_{unique_shortid()}")
        os.makedirs(stage_dir, exist_ok=True)
        list_path = os.path.join(stage_dir, "list.txt")
        frame_dur = 1.0 / int(fps)

        try:
            def safe_path(fpath):
                return fpath.replace("\\", "/").replace("'", "'\\''")

            with open(list_path, "w", encoding="utf-8") as lf:
                for _, fpath in items:
                    lf.write(f"file '{safe_path(fpath)}'\n")
                    lf.write(f"duration {frame_dur:.6f}\n")

            out_dir = os.path.join(DIR_TEMP, TOOL_SUBDIR)
            os.makedirs(out_dir, exist_ok=True)
            dst = make_unique_filename(os.path.join(out_dir, f"{out_name}{out_ext}"))

            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
                   "-fps_mode", "cfr", "-r", str(fps)]
            if want_alpha_out:
                cmd += ["-c:v", "qtrle", "-pix_fmt", "argb"]
            else:
                cmd += enc_args(out_ext, quality)
            cmd += [dst]

            snd_alert("start")
            ok, msg = ff_call(cmd)
        finally:
            try:
                if os.path.isfile(list_path): os.remove(list_path)
                os.rmdir(stage_dir)
            except Exception:
                pass
            if tmp_folder:
                rem_arch_tmp(tmp_folder)

        if not ok:
            snd_alert("error")
            return None, None, f"ffmpeg failed - {msg.splitlines()[-1] if msg else 'unknown error'}"

        note = " [alpha]" if want_alpha_out else ""
        log = f"Done: {len(items)} frames @ {fps} fps -> {dst}{note}"
        conlog(f"^A    {log}~")
        snd_alert("finish")
        return dst, dst, log
