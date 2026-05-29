# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import colorsys
import gradio as gr
import os


NUM_COLORS = 10
COLORS_PER_ROW = 5
DEFAULT_COLOR = "#ff0000"


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        raise ValueError("Invalid hex color")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def hex_to_hsl(hex_color):
    r, g, b = hex_to_rgb(hex_color)
    h, l, s = colorsys.rgb_to_hls(r/255, g/255, b/255)
    return round(h * 360), round(s * 100), round(l * 100)


def hsl_to_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h/360, l/100, s/100)
    return rgb_to_hex(round(r * 255), round(g * 255), round(b * 255))


def parse_picker_value(val):
    """Parse ColorPicker value (rgba/rgb string or hex) to #rrggbb."""
    if not val:
        return DEFAULT_COLOR
    val = val.strip()
    # hex format
    if val.startswith('#'):
        return val
    # rgba(r, g, b, a) or rgb(r, g, b)
    import re
    m = re.match(r'rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)', val)
    if m:
        r = max(0, min(255, round(float(m.group(1)))))
        g = max(0, min(255, round(float(m.group(2)))))
        b = max(0, min(255, round(float(m.group(3)))))
        return rgb_to_hex(r, g, b)
    # fallback: try as bare hex
    try:
        hex_to_rgb('#' + val)
        return '#' + val
    except Exception:
        return DEFAULT_COLOR


def format_hex(hex_color):
    return hex_color.lstrip('#')


def format_rgb(hex_color):
    r, g, b = hex_to_rgb(hex_color)
    return f"{r}, {g}, {b}"


def format_hsl(hex_color):
    h, s, l = hex_to_hsl(hex_color)
    return f"{h}, {s}, {l}"


# ########################################################
class C_SUN_ColorPick(C_SUN_ToolBase):
    """
    Version info:
    1.0.0 - color palette with 10 customizable colors
    """
    version =             "1.0.0"

    icon =                "🎨 "
    info =                "Palette of 10 customizable colors with saving. HEX/RGB - Enter to apply"
    name =                "Color Pick"
    output_lines =        15
    output_type =         TParamType.text
    section =             TSections["Images"]

    inputs = {}

    # ########################################################
    def __init__(self):
        super().__init__()
        self.colors = [DEFAULT_COLOR] * NUM_COLORS

    # ########################################################
    def _load_colors(self):
        try:
            if ConfigSys.has_section(self.name):
                for i in range(NUM_COLORS):
                    key = f"color_{i}"
                    if ConfigSys.has_option(self.name, key):
                        val = ConfigSys[self.name][key]
                        if not val.startswith('#'):
                            val = '#' + val
                        self.colors[i] = val
        except Exception:
            pass

    # ########################################################
    def _save_colors(self):
        params = {}
        for i in range(NUM_COLORS):
            params[f"color_{i}"] = self.colors[i]
        save_tool_INI(self.name, params)
        #conlog(f"^A    ColorPick: saved {NUM_COLORS} colors~")

    # ########################################################
    def build_ui(self):
        self._load_colors()

        pickers = []
        hex_fields = []
        rgb_fields = []
        hsl_fields = []

        with gr.Column(scale=2):
            for row_idx in range(NUM_COLORS // COLORS_PER_ROW):
                with gr.Row(elem_classes=["colorpick-row"]):
                    for col_idx in range(COLORS_PER_ROW):
                        i = row_idx * COLORS_PER_ROW + col_idx

                        with gr.Column(scale=1, min_width=120, elem_classes=["colorpick-cell"]):
                            cp = gr.ColorPicker(
                                value=self.colors[i],
                                label=f"{i+1}",
                                interactive=True,
                            )
                            hex_f = gr.Textbox(
                                value=format_hex(self.colors[i]),
                                label="HEX",
                                interactive=True,
                                lines=1,
                                max_lines=1,
                            )
                            rgb_f = gr.Textbox(
                                value=format_rgb(self.colors[i]),
                                label="RGB",
                                interactive=True,
                                lines=1,
                                max_lines=1,
                            )
                            hsl_f = gr.Textbox(
                                value=format_hsl(self.colors[i]),
                                label="HSL",
                                interactive=True,
                                lines=1,
                                max_lines=1,
                            )

                            pickers.append(cp)
                            hex_fields.append(hex_f)
                            rgb_fields.append(rgb_f)
                            hsl_fields.append(hsl_f)

            # change events
            for i in range(NUM_COLORS):
                def make_picker_handler(idx):
                    def on_change(color):
                        #conlog(f"^A    ColorPick [{idx+1}]: picker raw -> {color}~")
                        hex_val = parse_picker_value(color)
                        #conlog(f"^A    ColorPick [{idx+1}]: parsed -> {hex_val}~")
                        self.colors[idx] = hex_val
                        self._save_colors()
                        return format_hex(hex_val), format_rgb(hex_val), format_hsl(hex_val)
                    return on_change

                def make_hex_handler(idx):
                    def on_change(hex_val):
                        hex_val = hex_val.strip().lstrip('#')
                        if len(hex_val) != 6:
                            return gr.update(), gr.update(), gr.update(), gr.update()
                        hex_full = '#' + hex_val
                        try:
                            hex_to_rgb(hex_full)
                        except Exception:
                            return gr.update(), gr.update(), gr.update(), gr.update()
                        #conlog(f"^A    ColorPick [{idx+1}]: hex -> {hex_full}~")
                        self.colors[idx] = hex_full
                        self._save_colors()
                        return hex_full, hex_val, format_rgb(hex_full), format_hsl(hex_full)
                    return on_change

                def make_rgb_handler(idx):
                    def on_change(rgb_str):
                        try:
                            parts = [int(x.strip()) for x in rgb_str.replace(',', ' ').split() if x.strip()]
                            if len(parts) != 3:
                                return gr.update(), gr.update(), gr.update()
                            r, g, b = [max(0, min(255, x)) for x in parts]
                            hex_val = rgb_to_hex(r, g, b)
                            #conlog(f"^A    ColorPick [{idx+1}]: rgb -> {hex_val}~")
                            self.colors[idx] = hex_val
                            self._save_colors()
                            return hex_val, format_hex(hex_val), format_hsl(hex_val)
                        except Exception:
                            return gr.update(), gr.update(), gr.update()
                    return on_change

                def make_hsl_handler(idx):
                    def on_change(hsl_str):
                        try:
                            clean = hsl_str.replace('%', ' ').replace(',', ' ')
                            parts = [int(x.strip()) for x in clean.split() if x.strip()]
                            if len(parts) != 3:
                                return gr.update(), gr.update(), gr.update()
                            h = max(0, min(360, parts[0]))
                            s = max(0, min(100, parts[1]))
                            l = max(0, min(100, parts[2]))
                            hex_val = hsl_to_hex(h, s, l)
                            #conlog(f"^A    ColorPick [{idx+1}]: hsl -> {hex_val}~")
                            self.colors[idx] = hex_val
                            self._save_colors()
                            return hex_val, format_hex(hex_val), format_rgb(hex_val)
                        except Exception:
                            return gr.update(), gr.update(), gr.update()
                    return on_change

                pickers[i].change(
                    fn=make_picker_handler(i),
                    inputs=[pickers[i]],
                    outputs=[hex_fields[i], rgb_fields[i], hsl_fields[i]]
                )
                hex_fields[i].submit(
                    fn=make_hex_handler(i),
                    inputs=[hex_fields[i]],
                    outputs=[pickers[i], hex_fields[i], rgb_fields[i], hsl_fields[i]]
                )
                rgb_fields[i].submit(
                    fn=make_rgb_handler(i),
                    inputs=[rgb_fields[i]],
                    outputs=[pickers[i], hex_fields[i], hsl_fields[i]]
                )
                hsl_fields[i].submit(
                    fn=make_hsl_handler(i),
                    inputs=[hsl_fields[i]],
                    outputs=[pickers[i], hex_fields[i], rgb_fields[i]]
                )

        return []  # no inputs for run()

    # ########################################################
    def run(self):
        self._load_colors()
        result = ""
        for i in range(NUM_COLORS):
            c = self.colors[i]
            r, g, b = hex_to_rgb(c)
            h, s, l = hex_to_hsl(c)
            result += f"[{i+1}]  {format_hex(c)}  |  RGB({r}, {g}, {b})  |  HSL({h}, {s}, {l})\n"

        snd_alert("finish")
        return result, None, "Ok!"
