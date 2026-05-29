# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import os


# file extensions by language (same as SUN_codecount)
LANG_EXTENSIONS = {
    "Python":    [".py", ".pyw"],
    "C":         [".c", ".h"],
    "C++":       [".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".hh", ".h++", ".inl"],
    "Lua":       [".lua"],
    "JS":        [".js", ".mjs", ".cjs", ".jsx"],
    "MaxScript": [".ms", ".mse", ".mcr", ".mzs"],
}

EXT_TO_LANG = {}
for lang, exts in LANG_EXTENSIONS.items():
    for ext in exts:
        EXT_TO_LANG[ext] = lang

ALL_CODE_EXT = set(EXT_TO_LANG.keys())


def detect_language(filepath):
    """Detect language by file extension."""
    _, ext = os.path.splitext(filepath)
    return EXT_TO_LANG.get(ext.lower())


# #########################################################
# C / C++ / JS / MaxScript comment stripping
# #########################################################

def _strip_c_family(text, lang):
    """Strip comments from C/C++/JS/MaxScript source code."""
    out = []
    i = 0
    n = len(text)

    while i < n:
        c = text[i]

        # string literal
        if c in ('"', "'"):
            q = c
            out.append(c)
            i += 1
            while i < n and text[i] != '\n':
                if text[i] == '\\' and i + 1 < n:
                    out.append(text[i])
                    out.append(text[i + 1])
                    i += 2
                    continue
                out.append(text[i])
                if text[i] == q:
                    i += 1
                    break
                i += 1
            continue

        # block comment /* ... */
        if c == '/' and i + 1 < n and text[i + 1] == '*':
            end = text.find('*/', i + 2)
            if end >= 0:
                # add space to prevent token merging (e.g. int/**/x -> int x)
                if out and out[-1] not in (' ', '\t', '\n', '\r'):
                    out.append(' ')
                i = end + 2
            else:
                i = n  # unterminated block comment
            continue

        # line comment //
        if c == '/' and i + 1 < n and text[i + 1] == '/':
            while i < n and text[i] != '\n':
                i += 1
            continue

        # MaxScript line comment --
        if lang == 'MaxScript' and c == '-' and i + 1 < n and text[i + 1] == '-':
            while i < n and text[i] != '\n':
                i += 1
            continue

        out.append(c)
        i += 1

    return ''.join(out)


# #########################################################
# Python comment stripping
# #########################################################

def _prev_line_continues(text, current_line_start):
    """Check if the previous non-blank line ends with an expression continuation char.
    Used to detect multi-line string literals vs standalone docstrings."""
    CONTINUATORS = ('=', '(', '[', '{', ',', '+', '-', '*', '/', '|', '&', '\\')
    if current_line_start <= 0:
        return False
    pos = current_line_start - 1  # skip the \n before current line
    while pos > 0:
        line_start = text.rfind('\n', 0, pos) + 1
        line = text[line_start:pos].strip()
        if line:
            return line[-1] in CONTINUATORS
        pos = line_start - 1  # skip blank lines
    return False


def _strip_python(text):
    """Strip comments from Python source code.
    Tracks bracket depth and previous-line context to distinguish
    standalone docstrings/comments from multi-line string literals."""
    out = []
    i = 0
    n = len(text)
    bracket_depth = 0

    while i < n:
        c = text[i]

        # check for triple-quoted string/docstring
        tri = text[i:i + 3]
        if tri in ('"""', "'''"):
            # check if standalone: nothing before on this line except whitespace
            line_start = text.rfind('\n', 0, i) + 1
            before = text[line_start:i].strip()

            # find closing triple-quote
            end = text.find(tri, i + 3)
            if end < 0:
                end = n - 3  # unterminated

            # decide: comment/docstring vs string literal
            is_comment = False
            if before == '':
                if bracket_depth > 0:
                    is_comment = False  # inside (), [], {} -> string
                elif _prev_line_continues(text, line_start):
                    is_comment = False  # expression continues from prev line
                else:
                    is_comment = True   # standalone block -> comment/docstring

            if is_comment:
                # remove indentation already appended before the opening marker
                indent_len = i - line_start
                if indent_len > 0:
                    del out[-indent_len:]
                # strip the entire block
                i = end + 3
                # skip trailing whitespace and newline
                while i < n and text[i] in (' ', '\t', '\r'):
                    i += 1
                if i < n and text[i] == '\n':
                    i += 1
                continue

            # keep as string literal
            out.extend(list(tri))
            i += 3
            while i < n:
                if text[i] == '\\' and i + 1 < n:
                    out.append(text[i])
                    out.append(text[i + 1])
                    i += 2
                    continue
                if text[i:i + 3] == tri:
                    out.extend(list(tri))
                    i += 3
                    break
                out.append(text[i])
                i += 1
            continue

        # single-quoted string
        if c in ('"', "'"):
            q = c
            out.append(c)
            i += 1
            while i < n and text[i] != '\n':
                if text[i] == '\\' and i + 1 < n:
                    out.append(text[i])
                    out.append(text[i + 1])
                    i += 2
                    continue
                out.append(text[i])
                if text[i] == q:
                    i += 1
                    break
                i += 1
            continue

        # hash comment
        if c == '#':
            while i < n and text[i] != '\n':
                i += 1
            continue

        # track bracket depth (only actual code reaches here)
        if c in ('(', '[', '{'):
            bracket_depth += 1
        elif c in (')', ']', '}'):
            bracket_depth = max(0, bracket_depth - 1)

        out.append(c)
        i += 1

    return ''.join(out)


# #########################################################
# Lua comment stripping
# #########################################################

def _strip_lua(text):
    """Strip comments from Lua source code."""
    out = []
    i = 0
    n = len(text)

    while i < n:
        c = text[i]

        # string literal
        if c in ('"', "'"):
            q = c
            out.append(c)
            i += 1
            while i < n and text[i] != '\n':
                if text[i] == '\\' and i + 1 < n:
                    out.append(text[i])
                    out.append(text[i + 1])
                    i += 2
                    continue
                out.append(text[i])
                if text[i] == q:
                    i += 1
                    break
                i += 1
            continue

        # long string [[...]] (not a comment, keep it)
        if c == '[' and i + 1 < n and text[i + 1] == '[':
            end = text.find(']]', i + 2)
            if end >= 0:
                out.extend(list(text[i:end + 2]))
                i = end + 2
            else:
                out.extend(list(text[i:]))
                i = n
            continue

        # block comment --[[...]]  (must check before line comment --)
        if text[i:i + 4] == '--[[':
            end = text.find(']]', i + 4)
            if end >= 0:
                if out and out[-1] not in (' ', '\t', '\n', '\r'):
                    out.append(' ')
                i = end + 2
            else:
                i = n
            continue

        # line comment --
        if c == '-' and i + 1 < n and text[i + 1] == '-':
            while i < n and text[i] != '\n':
                i += 1
            continue

        out.append(c)
        i += 1

    return ''.join(out)


# #########################################################
# Common post-processing
# #########################################################

def _collapse_blanks(text):
    """Collapse consecutive blank lines to max one. Trim leading/trailing blanks."""
    lines = text.split('\n')
    result = []
    prev_blank = False

    for line in lines:
        line = line.rstrip()
        if line == '':
            if prev_blank:
                continue
            prev_blank = True
            result.append('')
        else:
            prev_blank = False
            result.append(line)

    # trim leading blank lines
    while result and result[0] == '':
        result.pop(0)

    # trim trailing blank lines
    while result and result[-1] == '':
        result.pop()

    if not result:
        return ''
    return '\n'.join(result) + '\n'


def strip_comments(text, lang):
    """Strip all comments from source text. Returns cleaned text."""
    # strip BOM if present
    if text.startswith('\ufeff'):
        text = text[1:]
    if lang in ('C', 'C++', 'JS', 'MaxScript'):
        stripped = _strip_c_family(text, lang)
    elif lang == 'Python':
        stripped = _strip_python(text)
    elif lang == 'Lua':
        stripped = _strip_lua(text)
    else:
        return text
    return _collapse_blanks(stripped)


# #########################################################
# File processing
# #########################################################

def process_single_file(filepath):
    """Process one file. Returns (lang, cleaned_text) or None."""
    lang = detect_language(filepath)
    if lang is None:
        return None
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
    except Exception as e:
        conlog(f"^NError reading {filepath}: {e}~")
        return None

    cleaned = strip_comments(text, lang)
    return lang, cleaned


def count_lines(text):
    """Count non-empty trailing lines in text."""
    if not text or text == '\n':
        return 0
    lines = text.split('\n')
    # remove trailing empty element from final newline
    if lines and lines[-1] == '':
        lines = lines[:-1]
    return len(lines)


def process_folder(folder_path, output_dir):
    """Process folder recursively. Save cleaned files to output_dir.
    Returns list of (rel_path, lang, orig_lines, clean_lines)."""
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
            if info is None:
                continue

            lang, cleaned = info
            rel_path = os.path.relpath(fpath, folder_path)

            # count original lines
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    orig_lines = sum(1 for _ in f)
            except Exception:
                orig_lines = 0
            clean_lines = count_lines(cleaned)

            # save cleaned file
            out_path = os.path.join(output_dir, rel_path)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(cleaned)

            results.append((rel_path, lang, orig_lines, clean_lines))
            removed = orig_lines - clean_lines
            conlog(f"^A    [{file_count}] {rel_path} ({lang}) — {orig_lines} -> {clean_lines} (-{removed})~")

    conlog(f"^A    Folder done, files: {file_count}~")
    return results


def format_folder_result(results, folder_path, output_dir):
    """Format summary table for folder processing."""
    if not results:
        return "No supported code files found."

    out = f"Source: {folder_path}\n"
    out += f"Output: {output_dir}\n"
    out += f"{'─' * 65}\n"
    out += f"{'File':<40} {'Lang':<8} {'Orig':>7} {'Clean':>7}\n"
    out += f"{'─' * 65}\n"

    grand_orig = 0
    grand_clean = 0

    for rel_path, lang, orig, clean in results:
        out += f"{rel_path:<40} {lang:<8} {orig:>7} {clean:>7}\n"
        grand_orig += orig
        grand_clean += clean

    out += f"{'─' * 65}\n"
    removed = grand_orig - grand_clean
    pct = (removed / grand_orig * 100) if grand_orig > 0 else 0
    out += f"{'TOTAL':<40} {'':8} {grand_orig:>7} {grand_clean:>7}\n"
    out += f"Removed: {removed} lines ({pct:.1f}%)  |  Files: {len(results)}\n"

    return out


# ########################################################
class C_SUN_CodeStripCom(C_SUN_ToolBase):
    """
    Version info:
    1.0.0 - strip comments from source code files
    """
    version =             "1.0.0"

    src_select =          [CH_SINGLE, CH_FOLDER]
    icon =                "🧼 "
    info =                "Strip comments from source code. Languages: Python, C, C++, Lua, JS, MaxScript"
    name =                "Code Strip Comments"
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
        "warning": {
            "label":      "⚠️ WARNING! Processed sources are saved in the tmp/ folder",
            "type":       TParamType.markdown,
        },
    }

    # ########################################################
    def run(self, src_select, file_in, folder_in):
        conlog(f"\n^A>>>>>>> {self.__class__.__name__} run...~")
        ini_params = {"path_fold": folder_in}
        save_tool_INI(self.name, ini_params)

        if src_select == CH_SINGLE:
            if file_in is None:
                snd_alert("error")
                return None, None, ERR_NO_SRCFILE

            info = process_single_file(file_in)
            if info is None:
                snd_alert("error")
                return None, None, "Unsupported file type!"

            lang, cleaned = info
            fname = os.path.basename(file_in)
            conlog(f"^A    File: {fname} ({lang})~")

            # count lines
            try:
                with open(file_in, 'r', encoding='utf-8', errors='replace') as f:
                    orig_lines = sum(1 for _ in f)
            except Exception:
                orig_lines = 0
            clean_lines = count_lines(cleaned)
            removed = orig_lines - clean_lines

            # save cleaned file to tmp
            os.makedirs(DIR_TEMP, exist_ok=True)
            out_path = os.path.join(DIR_TEMP, fname)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(cleaned)
            conlog(f"^A    Saved: {out_path}~")

            snd_alert("finish")
            return cleaned, out_path, f"Ok! {fname}: {orig_lines} -> {clean_lines} (-{removed})"

        else:  # CH_FOLDER
            if not folder_in or not os.path.isdir(folder_in):
                snd_alert("error")
                return None, None, ERR_NO_SRCFOLDER

            conlog(f"^A    Scanning folder: {folder_in}~")
            folder_name = os.path.basename(os.path.normpath(folder_in))
            output_dir = os.path.join(DIR_TEMP, folder_name)
            os.makedirs(output_dir, exist_ok=True)

            results = process_folder(folder_in, output_dir)
            if not results:
                snd_alert("finish")
                return "No supported code files found.", None, "Ok! (no files found)"

            res = format_folder_result(results, folder_in, output_dir)
            snd_alert("finish")
            return res, None, f"Ok! Processed files: {len(results)}"
