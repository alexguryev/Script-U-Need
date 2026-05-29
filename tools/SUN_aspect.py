# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import math


class C_SUN_Aspect(C_SUN_ToolBase):
    """
    Version info:
    1.0.0 - aspect ratio calculator
    """
    version =             "1.0.0"

    icon =                "📐 "
    info =                "Approximate image aspect ratio based on its resolution"
    name =                "Aspect Ratio"
    output_lines =        1
    output_type =         TParamType.text
    section =             TSections["Images"]

    inputs = {
        "width_in": {
            "label":   "Width (W)",
            "type":    TParamType.number,
            "default": 1024,
            "step":    1,
        },
        "height_in": {
            "label":   "Height (H)",
            "type":    TParamType.number,
            "default": 1024,
            "step":    1,
        },
    }

    # #################################
    def run(self, width_in, height_in):
        conlog(f"\n^A>>>>>>> {self.__class__.__name__} run...~")

        w = int(width_in) if width_in is not None else 0
        h = int(height_in) if height_in is not None else 0

        if w < 1 or h < 1:
            snd_alert("error")
            return "Error: width and height must be at least 1", None, "Error: invalid resolution"

        gcd = math.gcd(w, h)
        result = f"{w // gcd}:{h // gcd}"

        snd_alert("finish")
        return result, None, "Ok!"
