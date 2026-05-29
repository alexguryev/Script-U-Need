# Script-U-Need

Gradio-based launcher for various utility scripts, organized as pluggable modules with a web UI.

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![Gradio 5.x](https://img.shields.io/badge/Gradio-5.x-orange)
![Windows](https://img.shields.io/badge/Platform-Windows-lightgrey)

---

## Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Running](#running)
4. [Tools](#tools)
5. [Adding your own tools](#adding-your-own-tools)
6. [Disclaimer & Security](#disclaimer--security)

---

## Requirements

- Python 3.10 or newer
- Windows (sound notifications use `winsound`)
- ~200 MB for the virtual environment

---

## Installation

```bat
git clone <repo-url>
cd Script-U-Need
setup.bat
```

`setup.bat` creates a `.venv` virtual environment and installs all dependencies from `requirements.txt`.

---

## Running

```bat
start.bat
```

The application opens in your browser at `http://127.0.0.1:7860`.

---

## Tools

### Images

| Tool | Description |
|------|-------------|
| **Aspect Ratio** | Calculates image aspect ratio from a given resolution |
| **Atlas Compose** | Combines a set of images into a single sprite atlas (grid layout) |
| **Atlas Decompose** | Splits a sprite atlas into individual elements by a defined grid |
| **Clear Metadata** | Strips EXIF and other metadata from images without quality loss |
| **Color Pick** | Extracts the color of a pixel at given coordinates; outputs HEX and RGB |

### ComfyUI

| Tool | Description |
|------|-------------|
| **Find Models in Workflow** | Parses a ComfyUI workflow JSON and lists all referenced models |
| **Find Unused Models & Packs** | Compares installed models/nodepacks against a workflow and finds unused ones |
| **Store Unused Models** | Moves unused models to a specified storage folder |
| **Store Unused Nodepacks** | Moves unused nodepacks to a specified storage folder |

### Code

| Tool | Description |
|------|-------------|
| **Code Lines Counter** | Counts effective lines of code (excluding blank lines and comments) |
| **Code Space** | Converts indentation in source files: spaces ↔ tabs |
| **Code Strip Comments** | Removes comments from source code while preserving structure |
| **JSON Good!** | Formats and validates JSON files (pretty-print with syntax check) |

> **Settings persistence:** key parameters of each tool (paths, modes, etc.) are saved to `tools/tools.ini` and automatically restored in the UI on the next launch.

---

## Adding your own tools

1. Create `tools/SUN_myname.py`
2. Subclass `C_SUN_ToolBase` (imported via `from core import *`)
3. Define class attributes: `name`, `section`, `inputs`, `output_type`
4. Implement the `run(**kwargs)` method — it must return `(result, file, log_string)`

The tool is picked up automatically on next launch — no registration needed.

---

## Disclaimer & Security

**Disclaimer:**  
Tools are provided as-is. The author is not responsible for data loss when using file-moving tools (Store Unused *). ! Back up your data before use !

**Security:**
- Runs locally; no external access (Gradio `share=False` by default).
- Tools operate only on local files explicitly provided by the user.
- ComfyUI tools read workflow files in read-only mode; models/nodepacks are moved only on explicit user action.
