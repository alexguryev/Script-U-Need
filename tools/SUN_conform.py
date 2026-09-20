# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import gradio as gr
import json
import math
import os
import subprocess


TOOL_SUBDIR = "Conform"

WORK_EXT = [".mp4", ".mov", ".avi"] # containers kept as is, everything else goes to mp4
DEF_EXT = ".mp4"

MIN_DIM = 16 # macroblock size - the lowest common denominator for h264 / mpeg4 (mp4, mov, avi)
MAX_DIM = 16384

W_CHOICES = ["0", "1024", "1280", "1920", "2048", "2560", "3840"]
H_CHOICES = ["0", "720", "768", "1024", "1080", "1152", "2560", "2880"]
FPS_CHOICES = ["0", "24", "25", "30"]

PAD_FREEZE = "Freeze"
PAD_PINGPONG = "Ping-pong"
PAD_CHOICES = [PAD_FREEZE, PAD_PINGPONG]

SCHEME_PRESET = "Preset"
SCHEME_MANUAL = "Manual"
SCHEME_CHOICES = [SCHEME_PRESET, SCHEME_MANUAL]

MIN_FRAMES = 1 # lowest target frame count accepted by every output container (mp4/mov/avi)

Q_CHOICES = ["High", "Good", "Medium", "Low"]
Q_CRF = {"High": 16, "Good": 20, "Medium": 24, "Low": 28} # libx264 (mp4, mov)
Q_QSCALE = {"High": 2, "Good": 4, "Medium": 6, "Low": 9}  # mpeg4 (avi)
Q_TEMP_CRF = 12 # intermediate files for ping-pong assembly

DEF_COLOR = "#000000"

# process creation flags - no console window popup on Windows
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# #########################################################################
def parse_color(value): # ColorPicker value (hex / rgb / rgba) -> 0xRRGGBB for ffmpeg
    if not value:
        return "0x000000"
    val = str(value).strip()

    if val.startswith("rgb"):
        try:
            nums = val[val.index("(") + 1: val.index(")")].split(",")
            r, g, b = [max(0, min(255, int(float(x.strip())))) for x in nums[:3]]
            return f"0x{r:02x}{g:02x}{b:02x}"
        except Exception:
            return "0x000000"

    val = val.lstrip("#")
    if len(val) == 3:
        val = "".join(c * 2 for c in val)
    if len(val) != 6:
        return "0x000000"
    try:
        int(val, 16)
    except Exception:
        return "0x000000"
    return f"0x{val.lower()}"


# #########################################################################
def norm_dim(value): # any user input -> valid even frame dimension (0 = keep)
    try:
        dim = int(float(str(value).strip()))
    except Exception:
        return 0
    if dim <= 0:
        return 0
    dim = max(MIN_DIM, min(MAX_DIM, dim))
    if dim % 2:
        dim += 1 # h264 needs even dimensions
    return dim


# #########################################################################
def even(value):
    val = int(round(value))
    if val < 2: val = 2
    if val % 2: val += 1
    return val


# #########################################################################
def norm_frames(value): # any user input -> valid target frame count
    try:
        val = int(round(float(value)))
    except Exception:
        val = MIN_FRAMES
    if val < MIN_FRAMES:
        val = MIN_FRAMES
    return val


# #########################################################################
def _grid_frames(target, step, remainder): # smallest int of form step*k+remainder that is >= target
    k = max(0, math.ceil((target - remainder) / step))
    return int(step * k + remainder)


# Real output frame count per generator, researched 2026-09 (docs + community reports):
#   - Minimax H3: confirmed grid `17k+5` (atlascloud.ai) - 5s asks for 120 frames, actually gets 124
#   - Seedance 2.5: confirmed `duration*fps+1` offset (ByteDance blog, checked against 2 data points)
#   - Wan 3.0: duration/fps range confirmed; `4k+1` grid extrapolated from the open Wan 2.x causal-VAE
#     architecture (temporal compression step 4) - NOT verified directly against the closed Wan 3.0 API
#   - Flux 3.0, Gemini Omni Flash 1.1, Kling 2.6/3.0, Seedance 2.0, Veo 3.1: no anomaly found in docs
#     or community reports - using the plain `duration*fps` the providers document
GEN_PRESETS = {
    "Flux 3.0":              {"fps": 24, "dur_min": 5, "dur_max": 20, "dur_step": 1, "code": "f30",
                               "frames": lambda d: d * 24},
    "Gemini Omni Flash 1.1": {"fps": 24, "dur_min": 3, "dur_max": 10, "dur_step": 1, "code": "of11",
                               "frames": lambda d: d * 24},
    "Kling 2.6":             {"fps": 24, "dur_min": 5, "dur_max": 10, "dur_step": 5, "code": "k26",
                               "frames": lambda d: d * 24},
    "Kling 3.0":             {"fps": 24, "dur_min": 3, "dur_max": 15, "dur_step": 1, "code": "k30",
                               "frames": lambda d: d * 24},
    "Minimax H3":            {"fps": 24, "dur_min": 5, "dur_max": 15, "dur_step": 1, "code": "mmh3",
                               "frames": lambda d: _grid_frames(d * 24, 17, 5)},
    "Seedance 2.0":          {"fps": 24, "dur_min": 4, "dur_max": 15, "dur_step": 1, "code": "sd20",
                               "frames": lambda d: d * 24},
    "Seedance 2.5":          {"fps": 24, "dur_min": 4, "dur_max": 30, "dur_step": 1, "code": "sd25",
                               "frames": lambda d: d * 24 + 1},
    "Veo 3.1":               {"fps": 24, "dur_min": 4, "dur_max": 8, "dur_step": 2, "code": "veo31",
                               "frames": lambda d: d * 24},
    "Wan 3.0":               {"fps": 30, "dur_min": 2, "dur_max": 30, "dur_step": 1, "code": "wan3",
                               "frames": lambda d: _grid_frames(d * 30, 4, 1)},
}
DEFAULT_GEN = next(iter(GEN_PRESETS)) # "Flux 3.0"


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
def probe_video(fpath): # -> (info dict, error string)
    ok, out = ff_call([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,avg_frame_rate,nb_frames,duration:format=duration",
        "-of", "json", fpath
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

    rate = stream.get("r_frame_rate") or stream.get("avg_frame_rate") or "0/0"
    try:
        num, den = rate.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 0.0
    except Exception:
        rate, fps = "0/0", 0.0
    if fps <= 0:
        return None, "cannot read frame rate!"

    duration = 0.0
    for src in (stream.get("duration"), (data.get("format") or {}).get("duration")):
        try:
            duration = float(src)
            if duration > 0: break
        except Exception:
            continue

    frames = 0
    try:
        frames = int(stream.get("nb_frames"))
    except Exception:
        frames = 0
    if frames <= 0: # container without frame count in the header - count them
        ok, out = ff_call([
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
            "-show_entries", "stream=nb_read_frames", "-of", "default=nokey=1:noprint_wrappers=1", fpath
        ])
        try:
            frames = int(out.strip())
        except Exception:
            frames = 0
    if frames <= 0 and duration > 0:
        frames = int(round(duration * fps))
    if frames <= 0:
        return None, "cannot read frame count!"

    return {
        "width": width, "height": height,
        "fps": fps, "fps_str": rate,
        "frames": frames,
        "duration": duration if duration > 0 else frames / fps,
    }, ""


# #########################################################################
def enc_args(ext, quality): # encoder arguments for the target container
    if ext == ".avi": # classic mpeg4 - the most compatible codec for avi
        return ["-c:v", "mpeg4", "-vtag", "xvid", "-q:v", str(Q_QSCALE[quality]), "-pix_fmt", "yuv420p"]

    args = ["-c:v", "libx264", "-crf", str(Q_CRF[quality]), "-preset", "slow", "-pix_fmt", "yuv420p"]
    if ext == ".mp4":
        args += ["-movflags", "+faststart"]
    return args


# ########################################################
class C_SUN_Conform(C_SUN_ToolBase):
    """
    Version info:
    1.0.0 - video conform: frame size, frame rate, reverse, duration padding
    1.1.0 - Timing: Preset scheme (video-generator presets with real frame count) or Manual scheme
            (direct FPS + Frames control); replaces the old Frame Rate section and free-form Duration
    """
    version =             "1.1.0"

    src_select =          [CH_SINGLE, CH_FOLDER, CH_ARCHIVE]
    icon =                "🎬 "
    info =                "Conform video: frame size, timing (FPS/frames or a generator preset), reverse. Requires ffmpeg installed in the system"
    name =                "Video Conform"
    output_type =         TParamType.video
    section =             TSections["Video"]

    inputs = {}

    # ########################################################
    def __init__(self):
        super().__init__()
        self.params = {
            "out_w":    "0",
            "out_h":    "0",
            "cache":    "True",
            "pad_color": DEF_COLOR,
            "scheme":   SCHEME_PRESET,
            "fps":      "0",
            "frames":   "120",
            "gen_name": DEFAULT_GEN,
            "gen_duration": str(GEN_PRESETS[DEFAULT_GEN]["dur_min"]),
            "reverse":  "False",
            "padmode":  PAD_FREEZE,
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

        if self.params["scheme"] not in SCHEME_CHOICES:
            self.params["scheme"] = SCHEME_PRESET
        if self.params["gen_name"] not in GEN_PRESETS:
            self.params["gen_name"] = DEFAULT_GEN
        preset = GEN_PRESETS[self.params["gen_name"]]
        try:
            dur = int(round(float(self.params["gen_duration"])))
        except Exception:
            dur = preset["dur_min"]
        self.params["gen_duration"] = str(max(preset["dur_min"], min(preset["dur_max"], dur)))
        self.params["frames"] = str(norm_frames(self.params.get("frames", MIN_FRAMES)))

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
    def _file_info(self, path):
        if not path or not os.path.isfile(path):
            return ""
        info, err = probe_video(path)
        if info is None:
            return f"⚠ {err}"
        return f"{info['width']}×{info['height']} px · {info['fps']:.3f} fps · {info['frames']} frames"

    # ########################################################
    def build_ui(self):
        self._load_params()
        p = self.params

        inputs_list = []

        with gr.Column(scale=2):
            if not FFMPEG_OK:
                gr.Markdown(f"### ⛔ {ERR_NO_FFMPEG}")

            # single file panel
            with gr.Column(visible=(self.src_select[0] == CH_SINGLE)) as file_in_pan:
                file_in = gr.Video(label=CAP_SRC_VID, interactive=True, sources=["upload"], format=None, autoplay=False)
                file_info = gr.Textbox(value="", show_label=False, interactive=False, container=False)
                file_in.change(fn=self._file_info, inputs=file_in, outputs=file_info)

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

            # ######## frame size
            with gr.Group():
                gr.Markdown("**Frame size**", container=False)
                with gr.Row():
                    out_w = gr.Dropdown(value=p["out_w"], choices=W_CHOICES, label="Width",
                                        info="0 = keep", interactive=True, allow_custom_value=True)
                    out_h = gr.Dropdown(value=p["out_h"], choices=H_CHOICES, label="Height",
                                        info="0 = keep", interactive=True, allow_custom_value=True)
                with gr.Row():
                    cache = gr.Checkbox(value=(p["cache"] == "True"), label="Cache",
                                        info="keep aspect ratio and pad to the frame size", interactive=True)
                    pad_color = gr.ColorPicker(value=p["pad_color"], label="Pad color", interactive=True)

            # ######## timing
            gen_preset = GEN_PRESETS[p["gen_name"]]
            is_manual = (p["scheme"] == SCHEME_MANUAL)
            with gr.Group():
                gr.Markdown("**Timing**", container=False)
                scheme = gr.Radio(value=p["scheme"], choices=SCHEME_CHOICES, label="Scheme",
                                  info="Preset: match a video generator's output / Manual: set FPS and Frames directly",
                                  interactive=True)

                with gr.Row(visible=is_manual) as manual_pan:
                    fps = gr.Dropdown(value=p["fps"], choices=FPS_CHOICES, label="FPS",
                                      info="0 = keep / conform without interpolation: frame count is preserved",
                                      interactive=True, allow_custom_value=False)
                    frames = gr.Number(value=int(p["frames"]), label="Frames", info="target frame count",
                                       minimum=MIN_FRAMES, step=1, precision=0, interactive=True)

                with gr.Column(visible=(not is_manual)) as preset_pan:
                    gen_name = gr.Dropdown(value=p["gen_name"], choices=list(GEN_PRESETS.keys()),
                                           label="Generator", interactive=True, allow_custom_value=False)
                    gen_duration = gr.Slider(value=int(p["gen_duration"]), minimum=gen_preset["dur_min"],
                                             maximum=gen_preset["dur_max"], step=gen_preset["dur_step"],
                                             label="Duration, sec", interactive=True)
                    with gr.Row():
                        gen_fps_ro = gr.Number(value=gen_preset["fps"], label="FPS", interactive=False)
                        gen_frames_ro = gr.Number(value=gen_preset["frames"](int(p["gen_duration"])),
                                                  label="Real frames",
                                                  info="actual output frame count for this generator/duration",
                                                  interactive=False)

                with gr.Row():
                    reverse = gr.Checkbox(value=(p["reverse"] == "True"), label="Reverse",
                                          info="reverse the video in time", interactive=True)
                    padmode = gr.Radio(value=p["padmode"], choices=PAD_CHOICES, label="Padding",
                                       info="how to fill up a longer duration", interactive=True)

            # ######## output
            with gr.Group():
                gr.Markdown("**Output**", container=False)
                quality = gr.Dropdown(value=p["quality"], choices=Q_CHOICES, label="Quality",
                                      info="source container is kept when possible, otherwise mp4",
                                      interactive=True, allow_custom_value=False)

            inputs_list.extend([out_w, out_h, cache, pad_color,
                               scheme, fps, frames, gen_name, gen_duration,
                               reverse, padmode, quality])

            with gr.Row():
                gr.Markdown("⚠️ WARNING! Processed sources are saved in the tmp/ folder")

            # store every changed parameter in tools.ini
            for key, ctrl in (
                ("cache", cache), ("pad_color", pad_color), ("fps", fps),
                ("reverse", reverse),
                ("padmode", padmode), ("quality", quality),
            ):
                def make_handler(param_key):
                    def on_change(value):
                        self._set_param(param_key, value)
                    return on_change
                ctrl.change(fn=make_handler(key), inputs=ctrl)

            # frame size accepts custom values - normalize them right in the field
            for key, ctrl in (("out_w", out_w), ("out_h", out_h)):
                def make_dim_handler(param_key):
                    def on_change(value):
                        dim = str(norm_dim(value))
                        self._set_param(param_key, dim)
                        return gr.update(value=dim)
                    return on_change
                ctrl.input(fn=make_dim_handler(key), inputs=ctrl, outputs=ctrl) # `input`, not `change`: writing
                                                                               # back into the same field would
                                                                               # retrigger `change` endlessly

            # manual frames - same custom-value normalization
            def on_frames_input(value):
                val = norm_frames(value)
                self._set_param("frames", val)
                return gr.update(value=val)
            frames.input(fn=on_frames_input, inputs=frames, outputs=frames)

            # scheme switch - toggle the Manual / Preset panels
            def on_scheme_change(value):
                self._set_param("scheme", value)
                is_man = (value == SCHEME_MANUAL)
                return gr.update(visible=is_man), gr.update(visible=(not is_man))
            scheme.change(fn=on_scheme_change, inputs=scheme, outputs=[manual_pan, preset_pan])

            # generator switch - reset the duration slider to the new generator's range and refresh the readouts
            def on_gen_change(value):
                if value not in GEN_PRESETS:
                    value = DEFAULT_GEN
                self._set_param("gen_name", value)
                preset = GEN_PRESETS[value]
                dur = preset["dur_min"]
                self._set_param("gen_duration", dur)
                return (
                    gr.update(minimum=preset["dur_min"], maximum=preset["dur_max"],
                             step=preset["dur_step"], value=dur),
                    gr.update(value=preset["fps"]),
                    gr.update(value=preset["frames"](dur)),
                )
            gen_name.change(fn=on_gen_change, inputs=gen_name, outputs=[gen_duration, gen_fps_ro, gen_frames_ro])

            # duration slider - refresh the real-frames readout for the current generator
            def on_gen_duration_change(gname, dur_val):
                if gname not in GEN_PRESETS:
                    gname = DEFAULT_GEN
                preset = GEN_PRESETS[gname]
                dur = int(round(float(dur_val)))
                self._set_param("gen_duration", dur)
                return gr.update(value=preset["frames"](dur))
            gen_duration.change(fn=on_gen_duration_change, inputs=[gen_name, gen_duration], outputs=gen_frames_ro)

        self._selector_out = [file_in_pan, folder_in_pan, arch_in_pan]
        self._selector_inputs = [file_in, folder_in, arch_in]

        return inputs_list

    # ########################################################
    def _size_filters(self, info, out_w, out_h, cache, color): # -> (filter list, log note)
        src_w, src_h = info["width"], info["height"]

        if out_w == 0 and out_h == 0:
            return [], ""

        if out_w and not out_h: # one dimension given - the other follows the aspect ratio
            return [f"scale={out_w}:-2:flags=lanczos"], ""
        if out_h and not out_w:
            return [f"scale=-2:{out_h}:flags=lanczos"], ""

        if not cache: # plain resize to the exact frame size
            return [f"scale={out_w}:{out_h}:flags=lanczos"], ""

        # cache: keep aspect ratio (width first), pad the rest with the given color
        note = ""
        fit_w, fit_h = out_w, even(out_w * src_h / src_w)
        if fit_h > out_h: # does not fit in height - fall back to height priority, nothing gets cropped
            fit_h, fit_w = out_h, even(out_h * src_w / src_h)
            note = "cache: height priority (source is taller than the target frame)"

        flt = [f"scale={fit_w}:{fit_h}:flags=lanczos"]
        if fit_w != out_w or fit_h != out_h:
            flt.append(f"pad={out_w}:{out_h}:{(out_w - fit_w) // 2}:{(out_h - fit_h) // 2}:{color}")
        return flt, note

    # ########################################################
    def _convert(self, src, dst, out_w, out_h, cache, color, fps_sel, reverse, frames, padmode, quality):
        """Conform one file. Returns (ok, log line)."""
        info, err = probe_video(src)
        if info is None:
            return False, f"{os.path.basename(src)}: {err}"

        name = os.path.basename(src)
        ext = os.path.splitext(dst)[1].lower()

        # frame rate: conform without interpolation - frame count stays, the denominator changes
        if fps_sel > 0:
            out_fps = float(fps_sel)
            out_fps_str = str(fps_sel)
            retime = True
        else:
            out_fps = info["fps"]
            out_fps_str = info["fps_str"]
            retime = False

        src_frames = info["frames"]

        # timing: target frame count is already resolved (Manual: user value / Preset: generator's real frames)
        trim_frames = 0
        pad_frames = 0
        tgt_frames = max(1, int(frames))
        if tgt_frames < src_frames:
            trim_frames = tgt_frames
        elif tgt_frames > src_frames:
            pad_frames = tgt_frames - src_frames

        size_flt, note = self._size_filters(info, out_w, out_h, cache, color)

        # ######## ping-pong padding needs the conformed clip on disk first
        if pad_frames > 0 and padmode == PAD_PINGPONG and src_frames > 1:
            ok, msg = self._make_pingpong(src, dst, size_flt, reverse, retime, out_fps_str,
                                          src_frames, tgt_frames, ext, quality)
            if not ok:
                return False, f"{name}: {msg}"
        else:
            flt = list(size_flt)
            if reverse:
                flt.append("reverse")
            if trim_frames > 0:
                flt.append(f"select='lt(n\\,{trim_frames})'")
            if retime:
                flt.append(f"setpts=N/{out_fps_str}/TB")
            if pad_frames > 0: # freeze: clone the last frame (after the reverse!)
                flt.append(f"tpad=stop_mode=clone:stop={pad_frames}")

            cmd = ["ffmpeg", "-y", "-i", src]
            if flt:
                cmd += ["-vf", ",".join(flt)]
            cmd += ["-an"]
            if retime:
                cmd += ["-r", out_fps_str]
            cmd += enc_args(ext, quality) + [dst]

            ok, msg = ff_call(cmd)
            if not ok:
                return False, f"{name}: ffmpeg failed - {msg.splitlines()[-1] if msg else 'unknown error'}"

        done = f"{name} -> {os.path.basename(dst)}: {tgt_frames} fr, {out_fps:.3f} fps, {tgt_frames / out_fps:.3f} s"
        if note:
            done += f" [{note}]"
        return True, done

    # ########################################################
    def _make_pingpong(self, src, dst, size_flt, reverse, retime, out_fps_str,
                       src_frames, tgt_frames, ext, quality):
        """Fill the duration up by alternating forward and reversed copies of the clip.

        The turnaround frame is never repeated: the full clip goes first, every following
        copy drops its own first frame, which is the one the previous copy ended on.
        For a 38 frame clip that gives 0..37, 36..0, 1..37, 36..0, ... - no duplicates,
        no skipped frames, each following copy is one frame shorter than the original.
        """
        work = os.path.join(DIR_TEMP, TOOL_SUBDIR, f"_pp_{unique_shortid()}")
        os.makedirs(work, exist_ok=True)
        base = os.path.join(work, "base.mp4") # full clip, frames 0..N-1
        back = os.path.join(work, "back.mp4") # backwards without the turnaround frame, N-2..0
        fwd = os.path.join(work, "fwd.mp4")   # forward without the turnaround frame, 1..N-1
        lst = os.path.join(work, "list.txt")
        temp_enc = ["-c:v", "libx264", "-crf", str(Q_TEMP_CRF), "-preset", "veryfast", "-pix_fmt", "yuv420p"]

        try:
            # the base clip: size, reverse and frame rate are already applied here
            flt = list(size_flt)
            if reverse:
                flt.append("reverse")
            if retime:
                flt.append(f"setpts=N/{out_fps_str}/TB")

            cmd = ["ffmpeg", "-y", "-i", src]
            if flt:
                cmd += ["-vf", ",".join(flt)]
            cmd += ["-an", "-r", out_fps_str] + temp_enc + [base]
            ok, msg = ff_call(cmd)
            if not ok:
                return False, f"ffmpeg failed (base) - {msg.splitlines()[-1] if msg else ''}"

            # the same clip backwards, first frame dropped - it duplicates the turnaround
            ok, msg = ff_call(["ffmpeg", "-y", "-i", base,
                               "-vf", f"reverse,select='gt(n\\,0)',setpts=N/{out_fps_str}/TB",
                               "-an", "-r", out_fps_str] + temp_enc + [back])
            if not ok:
                return False, f"ffmpeg failed (reverse) - {msg.splitlines()[-1] if msg else ''}"

            # and forward again, first frame dropped for the same reason
            ok, msg = ff_call(["ffmpeg", "-y", "-i", base,
                               "-vf", f"select='gt(n\\,0)',setpts=N/{out_fps_str}/TB",
                               "-an", "-r", out_fps_str] + temp_enc + [fwd])
            if not ok:
                return False, f"ffmpeg failed (forward) - {msg.splitlines()[-1] if msg else ''}"

            # full clip once, then the shortened copies until the required length is covered
            repeats = int(math.ceil((tgt_frames - src_frames) / (src_frames - 1)))
            with open(lst, "w", encoding="utf-8") as f:
                parts = [base] + [(back if (i % 2 == 0) else fwd) for i in range(repeats)]
                for part in parts:
                    f.write("file '" + part.replace("\\", "/").replace("'", "'\\''") + "'\n")

            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                   "-vf", f"select='lt(n\\,{tgt_frames})',setpts=N/{out_fps_str}/TB",
                   "-an", "-r", out_fps_str] + enc_args(ext, quality) + [dst]
            ok, msg = ff_call(cmd)
            if not ok:
                return False, f"ffmpeg failed (concat) - {msg.splitlines()[-1] if msg else ''}"

            return True, ""
        finally:
            try:
                for f in (base, back, fwd, lst):
                    if os.path.isfile(f): os.remove(f)
                os.rmdir(work)
            except Exception:
                pass

    # ########################################################
    def run(self, src_select, file_in, folder_in, arch_in,
            out_w, out_h, cache, pad_color, scheme, fps, frames, gen_name, gen_duration,
            reverse, padmode, quality):
        conlog(f"\n^A>>>>>>> {self.__class__.__name__} run...~")

        if not FFMPEG_OK:
            conlog(f"^N    {ERR_NO_FFMPEG}~")
            snd_alert("error")
            return None, None, ERR_NO_FFMPEG

        # ######## normalize params
        out_w = norm_dim(out_w)
        out_h = norm_dim(out_h)
        cache = bool(cache)
        color = parse_color(pad_color)
        reverse = bool(reverse)
        if padmode not in PAD_CHOICES: padmode = PAD_FREEZE
        if quality not in Q_CHOICES: quality = Q_CHOICES[0]
        if scheme not in SCHEME_CHOICES: scheme = SCHEME_PRESET
        if gen_name not in GEN_PRESETS: gen_name = DEFAULT_GEN

        gen_preset = GEN_PRESETS[gen_name]
        try:
            gen_dur = int(round(float(gen_duration)))
        except Exception:
            gen_dur = gen_preset["dur_min"]
        gen_dur = max(gen_preset["dur_min"], min(gen_preset["dur_max"], gen_dur))

        if scheme == SCHEME_MANUAL:
            try:
                fps_sel = int(float(str(fps).strip()))
            except Exception:
                fps_sel = 0
            if fps_sel < 0: fps_sel = 0
            tgt_frames = norm_frames(frames)
        else: # SCHEME_PRESET
            fps_sel = gen_preset["fps"]
            tgt_frames = gen_preset["frames"](gen_dur)

        # ######## store the user choice
        self.params.update({
            "out_w": str(out_w), "out_h": str(out_h), "cache": str(cache), "pad_color": str(pad_color),
            "scheme": scheme, "fps": str(fps), "frames": str(norm_frames(frames)),
            "gen_name": gen_name, "gen_duration": str(gen_dur),
            "reverse": str(reverse), "padmode": padmode, "quality": quality,
        })
        self.path_fold = folder_in
        self.path_arch = get_filedir(arch_in)
        self._save_params()

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
        out_dir = os.path.join(DIR_TEMP, TOOL_SUBDIR)
        os.makedirs(out_dir, exist_ok=True)

        suffix = "_conform" if scheme == SCHEME_MANUAL else f"_conform_{gen_preset['code']}"

        snd_alert("start")
        first_out = None
        done_count = 0
        fails = []

        for src in src_files:
            base_name, src_ext = get_filenameext(src)
            src_ext = src_ext.lower()
            out_ext = src_ext if src_ext in WORK_EXT else DEF_EXT
            dst = make_unique_filename(os.path.join(out_dir, f"{base_name}{suffix}{out_ext}"))

            ok, line = self._convert(src, dst, out_w, out_h, cache, color,
                                     fps_sel, reverse, tgt_frames, padmode, quality)
            if ok:
                done_count += 1
                conlog(f"^A    {line}~")
                if first_out is None:
                    first_out = dst
            else:
                fails.append(line)
                conlog(f"^N    {line}~")

        if tmp_folder:
            rem_arch_tmp(tmp_folder)

        if done_count == 0:
            snd_alert("error")
            return None, None, "Failed: " + ("; ".join(fails) if fails else ERR_GETOUTPUT)

        log = f"Done: {done_count} of {len(src_files)} file(s) -> {out_dir}"
        if fails:
            log += "\nErrors: " + "; ".join(fails)

        snd_alert("finish")
        if src_select == CH_SINGLE:
            return first_out, first_out, log
        return first_out, None, log
