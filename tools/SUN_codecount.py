# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import os

# file extensions by language
LANG_EXTENSIONS = {
    "Python":    [".py", ".pyw"],
    "C":         [".c", ".h"],
    "C++":       [".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".hh", ".h++", ".inl"],
    "Lua":       [".lua"],
    "JS":        [".js", ".mjs", ".cjs", ".jsx"],
    "MaxScript": [".ms", ".mse", ".mcr", ".mzs"],
}

# reverse mapping: extension -> language
EXT_TO_LANG = {}
for lang, exts in LANG_EXTENSIONS.items():
    for ext in exts:
        EXT_TO_LANG[ext] = lang

ALL_CODE_EXT = set(EXT_TO_LANG.keys())


def detect_language(filepath):
    """Detect language by file extension."""
    _, ext = os.path.splitext(filepath)
    return EXT_TO_LANG.get(ext.lower())


def count_effective_lines(filepath, lang):
    """Count effective lines of code (excluding blank lines and comments)."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        conlog(f"^NError reading {filepath}: {e}~")
        return 0, 0  # total, effective

    total = len(lines)
    effective = 0
    in_block_comment = False

    for line in lines:
        stripped = line.strip()

        # blank line
        if not stripped:
            continue

        # block and line comments for C/C++/JS/MaxScript
        if lang in ("C", "C++", "JS", "MaxScript"):
            if in_block_comment:
                if "*/" in stripped:
                    in_block_comment = False
                continue
            if stripped.startswith("/*"):
                if "*/" not in stripped or stripped.endswith("*/") and not stripped[2:-2].strip():
                    in_block_comment = "*/" not in stripped
                    continue
                # single-line block comment /* ... */
                continue
            if stripped.startswith("//"):
                continue
            # MaxScript also supports line comments with --
            if lang == "MaxScript" and stripped.startswith("--"):
                continue

        # block comments for Python (docstrings treated as comments)
        if lang == "Python":
            if in_block_comment:
                if stripped.endswith('"""') or stripped.endswith("'''"):
                    in_block_comment = False
                continue
            if stripped.startswith('"""') or stripped.startswith("'''"):
                marker = stripped[:3]
                # check if it closes on the same line (excluding the opening marker)
                rest = stripped[3:]
                if marker in rest:
                    continue  # single-line docstring comment
                in_block_comment = True
                continue
            if stripped.startswith("#"):
                continue

        # block and line comments for Lua
        if lang == "Lua":
            if in_block_comment:
                if "]]" in stripped:
                    in_block_comment = False
                continue
            if stripped.startswith("--[["):
                if "]]" not in stripped[4:]:
                    in_block_comment = True
                continue
            if stripped.startswith("--"):
                continue

        effective += 1

    return total, effective


def process_single_file(filepath):
    """Process a single file. Returns (lang, total, effective) or None."""
    lang = detect_language(filepath)
    if lang is None:
        return None
    total, effective = count_effective_lines(filepath, lang)
    return lang, total, effective


def process_folder(folder_path):
    """Process folder recursively. Returns list of per-file results."""
    results = []
    file_count = 0
    for root, dirs, files in os.walk(folder_path):
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in ALL_CODE_EXT:
                continue
            fpath = os.path.join(root, fname)
            file_count += 1
            info = process_single_file(fpath)
            if info is not None:
                lang, total, effective = info
                rel_path = os.path.relpath(fpath, folder_path)
                results.append((rel_path, lang, total, effective))
                conlog(f"^A    [{file_count}] {rel_path} ({lang}) — {effective}/{total}~")
    conlog(f"^A    Folder done, files: {file_count}~")
    return results


def format_single_result(filepath, lang, total, effective):
    """Format result for a single file."""
    fname = os.path.basename(filepath)
    skipped = total - effective
    pct = (effective / total * 100) if total > 0 else 0
    out = f"File: {fname}\n"
    out += f"Language: {lang}\n"
    out += f"Total lines: {total}\n"
    out += f"Effective lines: {effective} ({pct:.1f}%)\n"
    out += f"Skipped (blank + comments): {skipped}\n"
    return out


def format_folder_result(results, folder_path):
    """Format summary table for folder results."""
    if not results:
        return "No supported code files found."

    # group by language
    lang_stats = {}
    grand_total = 0
    grand_effective = 0

    out = f"Folder: {folder_path}\n"
    out += f"{'─' * 60}\n"
    out += f"{'File':<40} {'Lang':<8} {'Total':>7} {'Effect.':>8}\n"
    out += f"{'─' * 60}\n"

    for rel_path, lang, total, effective in results:
        out += f"{rel_path:<40} {lang:<8} {total:>7} {effective:>8}\n"
        grand_total += total
        grand_effective += effective
        if lang not in lang_stats:
            lang_stats[lang] = {"files": 0, "total": 0, "effective": 0}
        lang_stats[lang]["files"] += 1
        lang_stats[lang]["total"] += total
        lang_stats[lang]["effective"] += effective

    out += f"{'─' * 60}\n"
    grand_pct = (grand_effective / grand_total * 100) if grand_total > 0 else 0
    out += f"{'TOTAL':<40} {'':8} {grand_total:>7} {grand_effective:>8}\n"
    out += f"Effectiveness: {grand_pct:.1f}%  |  Files: {len(results)}\n"

    if len(lang_stats) > 1:
        out += f"\nBy language:\n"
        for lang, s in sorted(lang_stats.items()):
            pct = (s['effective'] / s['total'] * 100) if s['total'] > 0 else 0
            out += f"  {lang:<10}  files: {s['files']}, lines: {s['total']}, effect.: {s['effective']} ({pct:.1f}%)\n"

    return out


# ########################################################
class C_SUN_CodeCount(C_SUN_ToolBase):
    """
    Version info:
    1.1.0 - added MaxScript, progress log to console
    1.0.0 - effective lines of code counting
    """
    version =             "1.1.0"

    src_select =          [CH_SINGLE, CH_FOLDER]
    icon =                "🧮 "
    info =                "Count effective lines of code (excluding blank lines and comments). Languages: Python, C, C++, Lua, JS, MaxScript"
    name =                "Code Lines Counter"
    output_lines =        20
    output_type =         TParamType.text
    section =             TSections["Code"]

    inputs = {
        "file_in": {
            "label":      "Code file",
            "main_input": True,
            "selector":   True,
            "type":       TParamType.textfile,
        },
    }

    # ########################################################
    def run(self, src_select, file_in, folder_in):
        conlog(f"\n^A>>>>>>> {self.__class__.__name__} run...~")
        # save tool settings to ini
        ini_params = {"path_fold": folder_in}
        save_tool_INI(self.name, ini_params)

        if src_select == CH_SINGLE:
            if file_in is None:
                snd_alert("error")
                return None, None, ERR_NO_SRCFILE

            lang = detect_language(file_in)
            if lang is None:
                snd_alert("error")
                return None, None, "Unsupported file type!"

            conlog(f"^A    File: {os.path.basename(file_in)} ({lang})~")
            info = process_single_file(file_in)
            if info is None:
                snd_alert("error")
                return None, None, "File processing error!"

            lang, total, effective = info
            conlog(f"^A    Result: {effective}/{total} effective lines~")
            res = format_single_result(file_in, lang, total, effective)
            snd_alert("finish")
            return res, None, "Ok!"

        else:  # CH_FOLDER
            if not folder_in or not os.path.isdir(folder_in):
                snd_alert("error")
                return None, None, ERR_NO_SRCFOLDER

            conlog(f"^A    Scanning folder: {folder_in}~")
            results = process_folder(folder_in)
            if not results:
                snd_alert("finish")
                return "No supported code files found.", None, "Ok! (no files found)"

            res = format_folder_result(results, folder_in)
            snd_alert("finish")
            return res, None, f"Ok! Processed files: {len(results)}"
