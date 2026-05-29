# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import json
import os


# ########################################################
class C_SUN_JsonGood(C_SUN_ToolBase):
    """
    Version info:
    1.0.0 - validate and pretty-print JSON files
    """
    version =             "1.0.0"

    icon =                "⤴️ "
    info =                "Validate JSON and format into readable form"
    name =                "JSON Good!"
    output_lines =        20
    output_type =         TParamType.text
    section =             TSections["Code"]

    inputs = {
        "file_in": {
            "label":      "JSON file",
            "main_input": True,
            "type":       TParamType.jsonfile,
        },
    }

    # ########################################################
    def run(self, file_in):
        conlog(f"\n^A>>>>>>> {self.__class__.__name__} run...~")

        if file_in is None:
            snd_alert("error")
            return None, None, ERR_NO_SRCFILE

        fname = os.path.basename(file_in)
        conlog(f"^A    File: {fname}~")

        # read file
        try:
            with open(file_in, 'r', encoding='utf-8', errors='replace') as f:
                raw_text = f.read()
        except Exception as e:
            snd_alert("error")
            return None, None, f"Error reading file: {e}"

        # strip BOM if present
        if raw_text.startswith('\ufeff'):
            raw_text = raw_text[1:]

        # validate JSON
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            snd_alert("error")
            err_msg = f"JSON invalid!\n\nError: {e.msg}\nLine: {e.lineno}, pos: {e.colno}"
            return err_msg, None, f"Error! {fname}: {e.msg} (line {e.lineno})"

        # pretty-print
        formatted = json.dumps(data, indent=4, ensure_ascii=False)

        # save to tmp
        os.makedirs(DIR_TEMP, exist_ok=True)
        out_path = os.path.join(DIR_TEMP, fname)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(formatted)
        conlog(f"^A    Saved: {out_path}~")

        orig_lines = raw_text.count('\n') + (1 if raw_text and not raw_text.endswith('\n') else 0)
        new_lines = formatted.count('\n') + (1 if formatted and not formatted.endswith('\n') else 0)

        snd_alert("finish")
        return formatted, out_path, f"Ok! {fname}: JSON is valid, {orig_lines} -> {new_lines} lines"
