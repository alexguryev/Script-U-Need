# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import gradio as gr
import os
import tkinter as tk
import tkinter.filedialog


CODE_EXTENSIONS = [
    ".py", ".pyw",
    ".c", ".h",
    ".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".hh", ".h++", ".inl",
    ".lua",
    ".js", ".mjs", ".cjs", ".jsx",
    ".ms", ".mse", ".mcr", ".mzs",
    ".json",
]
CODE_EXT_SET = set(CODE_EXTENSIONS)

TOOL_SUBDIR  = "code_space"
MODE_SP2TAB  = "Spaces → Tabs"
MODE_TAB2SP  = "Tabs → Spaces"


def _choose_folder(init_dir):
    tk_root = tk.Tk()
    tk_root.attributes("-alpha", 0.0)
    tk_root.attributes("-topmost", True)
    f = None
    try:
        f = tk.filedialog.askdirectory(parent=tk_root, initialdir=init_dir, title="Select folder", mustexist=True)
    except Exception as err:
        conlog(f"^NError @ choose_folder:~ {err}")
    tk_root.destroy()
    if f not in [".", " ", "", init_dir]:
        return os.path.normpath(f)
    return init_dir


def convert_indents(text, mode, space_len):
    """Convert leading indentation in every line of text."""
    lines = text.split('\n')
    result = []
    for line in lines:
        if mode == MODE_SP2TAB:
            i = 0
            while i < len(line) and line[i] == ' ':
                i += 1
            tabs, rem = divmod(i, space_len)
            result.append('\t' * tabs + ' ' * rem + line[i:])
        else:  # MODE_TAB2SP
            i = 0
            while i < len(line) and line[i] == '\t':
                i += 1
            result.append(' ' * (i * space_len) + line[i:])
    return '\n'.join(result)


def process_file(fpath, mode, space_len, out_dir):
    """Convert indents in one file. Returns (converted_text, orig_lines, out_path) or None."""
    ext = os.path.splitext(fpath)[1].lower()
    if ext not in CODE_EXT_SET:
        return None
    try:
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
    except Exception as e:
        conlog(f"^NError reading {fpath}: {e}~")
        return None

    converted = convert_indents(text, mode, space_len)
    orig_lines = text.count('\n') + (1 if text else 0)

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, os.path.basename(fpath))
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(converted)

    return converted, orig_lines, out_path


def process_folder(folder_path, output_dir, mode, space_len):
    """Process folder recursively. Returns list of (rel_path, orig_lines)."""
    results = []
    file_count = 0

    for root, dirs, files in os.walk(folder_path):
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in CODE_EXT_SET:
                continue

            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, folder_path)
            rel_dir = os.path.dirname(rel_path)
            file_out_dir = os.path.join(output_dir, rel_dir) if rel_dir else output_dir

            file_count += 1
            info = process_file(fpath, mode, space_len, file_out_dir)
            if info is None:
                continue

            _, orig_lines, _ = info
            results.append((rel_path, orig_lines))
            conlog(f"^A    [{file_count}] {rel_path} — {orig_lines} lines~")

    conlog(f"^A    Folder done, files: {file_count}~")
    return results


def format_folder_result(results, folder_path, output_dir):
    if not results:
        return "No supported files found."

    out  = f"Source: {folder_path}\n"
    out += f"Output: {output_dir}\n"
    out += f"{'─' * 55}\n"
    out += f"{'File':<40} {'Lines':>7}\n"
    out += f"{'─' * 55}\n"
    for rel_path, lines in results:
        out += f"{rel_path:<40} {lines:>7}\n"
    out += f"{'─' * 55}\n"
    out += f"Files: {len(results)}, Total lines: {sum(l for _, l in results)}\n"
    return out


# ########################################################
class C_SUN_CodeSpace(C_SUN_ToolBase):
    """
    Version info:
    1.0.0 - convert indentation (spaces ↔ tabs) in source code files
    """
    version =      "1.0.0"

    src_select =   [CH_SINGLE, CH_FOLDER]
    icon =         "⇄  "
    info =         "Indentation conversion in source code: spaces ↔ tabs. Languages: Python, C, C++, Lua, JS, MaxScript"
    name =         "Code Space"
    output_lines = 20
    output_type =  TParamType.text
    section =      TSections["Code"]

    inputs = {}

    # ########################################################
    def build_ui(self):
        with gr.Column():
            with gr.Row():
                with gr.Column(visible=(self.src_select[0] == CH_SINGLE)) as single_pan:
                    file_in = gr.File(
                        label="Code file",
                        interactive=True,
                        file_count="single",
                        file_types=CODE_EXTENSIONS,
                    )
                with gr.Column(visible=(self.src_select[0] == CH_FOLDER)) as folder_pan:
                    with gr.Row():
                        btn_sel = gr.Button("Select folder", scale=1)
                        folder_in = gr.Textbox(
                            value=self.path_fold,
                            show_label=False,
                            interactive=False,
                            container=False,
                            scale=4,
                        )
                    with gr.Row():
                        gr.Markdown("<div><br><br></div>")
                    btn_sel.click(fn=_choose_folder, inputs=folder_in, outputs=folder_in)

            gr.Markdown("⚠️ WARNING! Processed sources are saved in the tmp/ folder")

            with gr.Row():
                mode = gr.Radio(
                    choices=[MODE_SP2TAB, MODE_TAB2SP],
                    value=MODE_SP2TAB,
                    label="Indentation replacement mode",
                    interactive=True,
                )

            with gr.Row():
                with gr.Column(scale=1):
                    space_len = gr.Dropdown(
                        choices=[2, 4, 8],
                        value=4,
                        label="Space length instead of tab",
                        interactive=True,
                        allow_custom_value=False,
                    )
                with gr.Column(scale=2):
                    gr.Markdown("")

        self._selector_out = [single_pan, folder_pan]
        return [file_in, folder_in, mode, space_len]

    # ########################################################
    def run(self, src_select, file_in, folder_in, mode, space_len):
        conlog(f"\n^A>>>>>>> {self.__class__.__name__} run...~")
        ini_params = {"path_fold": folder_in if folder_in else self.path_fold}
        save_tool_INI(self.name, ini_params)

        space_len = int(space_len)
        out_base = os.path.join(DIR_TEMP, TOOL_SUBDIR)

        if src_select == CH_SINGLE:
            if file_in is None:
                snd_alert("error")
                return None, None, ERR_NO_SRCFILE

            ext = os.path.splitext(file_in)[1].lower()
            if ext not in CODE_EXT_SET:
                snd_alert("error")
                return None, None, "Unsupported file type!"

            fname = os.path.basename(file_in)
            info = process_file(file_in, mode, space_len, out_base)
            if info is None:
                snd_alert("error")
                return None, None, "File processing error!"

            converted, orig_lines, out_path = info
            conlog(f"^A    Saved: {out_path}~")
            snd_alert("finish")
            return converted, out_path, f"Ok! {fname}: {orig_lines} lines ({mode}, tab={space_len})"

        else:  # CH_FOLDER
            if not folder_in or not os.path.isdir(folder_in):
                snd_alert("error")
                return None, None, ERR_NO_SRCFOLDER

            folder_name = os.path.basename(os.path.normpath(folder_in))
            output_dir  = os.path.join(out_base, folder_name)
            os.makedirs(output_dir, exist_ok=True)

            results = process_folder(folder_in, output_dir, mode, space_len)
            if not results:
                snd_alert("finish")
                return "No supported files found.", None, "Ok! (no files)"

            res = format_folder_result(results, folder_in, output_dir)
            snd_alert("finish")
            return res, None, f"Ok! Processed files: {len(results)}"
