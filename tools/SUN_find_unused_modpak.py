# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import ast
import io
import json
import os
import re
import yaml


def extract_node_classes(text):
    pattern = r"NODE_CLASS_MAPPINGS\s*=\s*\{.*?\}"
    match1 = re.search(pattern, text, re.DOTALL)
    if match1:
        t = match1.group()
        pattern = r"\{.*?\}"
        match2 = re.search(pattern, t, re.DOTALL)
        if match2:
            t = match2.group()
            try:
                t = ast.unparse(ast.parse(t)) # strip line-comments
            except Exception:
                return None

            t = str(t.encode('ascii', 'backslashreplace'))[1:]
            t = t.replace("\n", " ")

            s = ""
            try:
                d = json.loads(t) # pre-convert, string output
            except Exception:
                s = "{"

            if len(s) > 0: # try to reformat block
                for part in t.split(","):
                    if ":" in part:
                        p2 = part.split(":")[1].strip().strip('{}"\'')
                        if len(s) > 1:
                            s += ", "
                        s += f"\"{p2}\": 0" # stub value
                s += "}"
                d = json.loads(s)

            try:
                d = yaml.load(str(d), Loader=yaml.SafeLoader) # to dictionary!
            except Exception:
                d = {}
            return d
        else:
            return None
    else:
        return None


def incorrect_root(p):
    return (".git" in p) or ("__pycache__" in p) or ("__MACOSX" in p) or (".disabled" in p)


def skip_model_folder(p):
    return ("loras" in p) or ("vae_approx" in p) or ("ApproxVAE" in p) or ("Lora" in p)


def get_custom_node_names(custom_nodes_dir):
    node_names = set()
    node_packs = {}
    p_suspect = []
    for root, _, files in os.walk(custom_nodes_dir):
        if incorrect_root(root) or (root == custom_nodes_dir):
            continue
        pack = os.path.relpath(root, custom_nodes_dir).split(os.sep)[0] # get node pack folder name
        for f in files:
            if f.endswith(".py"): # scan only py-files
                with open(os.path.join(root, f), "r", encoding="utf_8") as file:
                    f_text = file.read()
                    n_classes = extract_node_classes(f_text)
                    if n_classes is not None:
                        if pack not in node_packs:
                            node_packs.update({pack: []}) # init node pack list
                        for b in n_classes:
                            node_packs[pack].append(b) # add node to pack
                            node_names.add(b)
        # report failed packs
        p_flag = False
        try:
            if len(node_packs[pack]) == 0:
                p_flag = True
        except Exception:
            p_flag = True

        if p_flag:
            if pack not in p_suspect:
                p_suspect.append(pack)

    return node_names, node_packs, p_suspect


def is_model_file(s):
    try:
        ext = os.path.splitext(os.path.basename(s))[1]
    except Exception:
        return False
    return ext in ALLOWED_MOD_EXT


def get_used_nodes_models(wf_path):
    used_nodes = set()
    used_models = set()
    for root, _, files in os.walk(wf_path):
        for f in files:
            if f.endswith(".json"): # scan only workflows
                conlog(f"^Achecking ... {f}~")
                with open(os.path.join(root, f), "r", encoding="utf-8") as file:
                    try:
                        data = json.load(file)
                        for node in data.get("nodes", []):
                            if "type" in node:
                                used_nodes.add(node["type"])
                            if "widgets_values" in node:
                                widgets = node["widgets_values"]
                                for w in widgets:
                                    if type(w) is str:
                                        #w = w.replace("\\\\", "\\")
                                        w = os.path.basename(w)
                                        if is_model_file(w):
                                            conlog(f"^A\tref:\t{w}~")
                                            used_models.add(w)
                    except Exception as e:
                        conlog(f"^NError in file {f}: {e}~")
    return used_nodes, used_models


def get_all_models(src_path, stability):
    if stability:
        folders = [os.path.join(src_path, "Models"), os.path.join(src_path, "Packages", "ComfyUI", "models")]
    else:
        folders = [os.path.join(src_path, "models")]

    all_models = set()
    all_models_full = set()
    for folder in folders:
        for root, _, files in os.walk(folder):
            if incorrect_root(root) or skip_model_folder(root):
                continue
            for f in files:
                if is_model_file(f):
                    all_models.add(f) # only names

                    n = os.path.join(root, f)
                    all_models_full.add(n) # full path from src_path

    return all_models, all_models_full


# ###################################################################################################
class C_SUN_FindUnusedModPak(C_SUN_ToolBase):
    """
    Version info:
    1.0.0 - ported to the script manager
    """
    version =             "1.0.0"

    icon =                "🧩 "
    info =                "Find potentially unused models and node packs"
    name =                "Find Unused Models & Packs"
    output_lines =        30
    output_type =         TParamType.text
    section =             TSections["ComfyUI"]

    inputs = {
        "src_path": {
            "label":      "Source folder",
            "info":       INFO_COMFYFOLDER,
            "lines":      1,
            "type":       TParamType.text,
            "use_ini":    True,
        },
        "wf_path": {
            "label":      "Folder with workflows to check",
            "info":       "subfolders will also be checked",
            "lines":      1,
            "type":       TParamType.text,
            "use_ini":    True,
        },
    }


    # #################################
    def run(self, src_path, wf_path):
        conlog(f"\n^A>>>>>>> {self.__class__.__name__} run...~")
        ini_params = {
            "src_path": src_path,
            "wf_path" : wf_path,
        }
        save_tool_INI(self.name, ini_params)

        if len(src_path) == 0:
            snd_alert("error")
            return None, None, ERR_NO_SRCFOLDER

        if not os.path.exists(src_path):
            snd_alert("error")
            return None, None, ERR_SRCFOLDER

        if not os.path.exists(wf_path):
            snd_alert("error")
            return None, None, f"Workflow: {ERR_FOLDER_404}"

        if src_path.endswith("Data"):
            custom_nodes_dir = os.path.join(src_path, "Packages", "ComfyUI", "custom_nodes")
            stability = True
        elif src_path.endswith("ComfyUI"):
            custom_nodes_dir = os.path.join(src_path, "custom_nodes")
            stability = False
        else:
            snd_alert("error")
            return None, None, ERR_SRCFOLDER

        if not os.path.exists(custom_nodes_dir):
            snd_alert("error")
            return None, None, f"Custom nodes: {ERR_FOLDER_404}"

        # process nodes packs #######################################################################
        custom_nodes, node_packs, p_suspect = get_custom_node_names(custom_nodes_dir)
        used_nodes, used_models = get_used_nodes_models(wf_path)
        #result = f"All node packs:\n{json.dumps(node_packs, indent=2)}\n\n"
        result = ""

        unused_nodes = custom_nodes - used_nodes
        unused_packs = []
        for p in node_packs:
            p_used = False
            for n in node_packs[p]:
                if n in used_nodes:
                    p_used = True
                    break
            if not p_used:
                unused_packs.append(p)

        if len(p_suspect) > 0:
            s = "Error scanning these nodes packs:"
            result += f"{s}\n{'-'*len(s)}\n"
            for p in sorted(p_suspect):
                result += f"{p}\n"

        s = "These custom nodes packs MAYBE not used by your workflows (scan errors marked by `?`):"
        result += f"\n\n{s}\n{'-'*len(s)}\n"
        for u in sorted(unused_packs):
            s = f"\t{u}"
            if u in p_suspect:
                s = "?" + s
            result += f"{s}\n"

        # process models #######################################################################
        all_models, all_models_full = get_all_models(src_path, stability)
        unused_models = all_models - used_models

        s = "These models MAYBE not used by your workflows:"
        result += f"\n\n{s}\n{'-'*len(s)}\n"
        um_out = []
        for u in unused_models:
            for a in all_models_full:
                if u in a:
                    um_out.append(a) # full path

        t = 0
        for u in sorted(um_out):
            w = int(os.path.getsize(u) / 1048576) # Mb
            s = u.replace(src_path + os.sep, "") + " | " + f"{'{:,}'.format(w)} Mb"
            result += f"{s}\n"
            t += w
        result += f"\nTotal models size = {'{:.2f}'.format(t / 1024.0)} Gb\n"

        snd_alert("finish")
        return result, None, "Ok!"


