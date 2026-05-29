# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

from core import *
from gu_funclib import *
import json
import os
import re
import requests


USER_AGENT = "model-finder/1.0"


def load_token_from_file():
    token_path = os.path.splitext(__file__)[0] + ".token"
    if os.path.isfile(token_path):
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                token = f.read().strip()
                conlog(f"^PLoaded token from: {token_path}~")
            return token
        except Exception:
            return None
    return None


def iter_json_strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from iter_json_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_json_strings(v)
    elif isinstance(obj, str):
        yield obj
    else:
        return


def find_model_files(workflow_json):
    ext_group = "|".join(re.escape(e) for e in ALLOWED_MOD_EXT)
    pattern = re.compile(r"([A-Za-z0-9_\-.\s]+(?:%s))" % ext_group, flags=re.IGNORECASE)

    found: set[str] = set()
    for s in iter_json_strings(workflow_json):
        for m in pattern.findall(s):
            candidate = m.strip()
            parts = re.split(r"[\\/]", candidate)
            base = parts[-1]
            if base not in found:
                low = base.lower()
                if any(low.endswith(ext) for ext in ALLOWED_MOD_EXT):
                    found.add(base)
    return sorted(found, key=lambda x: x.lower())


def search_civitai(filename):
    # Search on Civitai for a given filename:
    # - query by base name,
    # - prefer exact filename matches inside modelVersions[*].files[*].name,
    # - fallback to partial matches (basename in filename),
    # - if nothing found, fallback to model name containing the basename.
    # Returns model page URL (https://civitai.com/models/{id}) or None.
    base, _ = os.path.splitext(filename)
    params = {"query": base, "limit": 50}
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.get("https://civitai.com/api/v1/models", params=params, timeout=15, headers=headers)
        if r.status_code != 200:
            conlog(f"^N[civitai] HTTP {r.status_code}~")
            return None
        data = r.json()
        items = data.get("items") or []
        if not items:
            conlog("^N[civitai] no items~")
            return None

        filename_low = filename.lower()
        base_low = base.lower()

        exact_hits = []     
        partial_hits = []   
        name_hits = []      

        for it in items:
            model_name = (it.get("name") or "").lower()
            if base_low in model_name:
                name_hits.append(it)
            for mv in it.get("modelVersions") or []:
                for f in (mv.get("files") or []):
                    fname = (f.get("name") or "").strip().lower()
                    if not fname:
                        continue
                    if fname == filename_low:
                        exact_hits.append((it, mv, f))
                    elif base_low in fname:
                        partial_hits.append((it, mv, f))

        if exact_hits:
            it, mv, f = exact_hits[0]
            conlog(f"^A[civitai] exact match: {it.get('id')}, {it.get('name')} -> {f.get('name')}~")
            return f"https://civitai.com/models/{it['id']}"

        if partial_hits:
            it, mv, f = partial_hits[0]
            conlog(f"^A[civitai] partial match: {it.get('id')}, {it.get('name')} -> {f.get('name')}~")
            return f"https://civitai.com/models/{it['id']}"

        if name_hits:
            it = name_hits[0]
            conlog(f"^A[civitai] fallback model-name match: {it.get('id')}, {it.get('name')}~")
            return f"https://civitai.com/models/{it['id']}"

        conlog(f"^A[civitai] no useful hits for {filename}~")
        return None

    except Exception as e:
        conlog(f"^N[civitai] exception: {e}~")
        return None


def search_huggingface(filename, token=None):
    # Search Hugging Face for a file by filename.
    # Returns a direct link if found.
    base, _ = os.path.splitext(filename)
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        # 1. search by basename
        r = requests.get(
            "https://huggingface.co/api/models",
            params={"search": base, "limit": 20},
            headers=headers,
            timeout=20,
        )
        if r.status_code != 200:
            conlog(f"^N[huggingface] HTTP {r.status_code}~")
            return None
        repos = r.json()
        if not repos:
            conlog(f"^N[huggingface] no repos for {base}~")
            return None

        # 2. check files inside repo
        for repo in repos:
            repo_id = repo.get("id")
            if not repo_id:
                continue

            tree_url = f"https://huggingface.co/api/models/{repo_id}/tree/main?recursive=1"
            rt = requests.get(tree_url, headers=headers, timeout=20)
            if rt.status_code != 200:
                continue

            for f in rt.json():
                fname = f.get("path", "").split("/")[-1].lower()
                if fname == filename.lower():
                    # exact
                    url = f"https://huggingface.co/{repo_id}/blob/main/{f['path']}"
                    conlog(f"^A[huggingface] exact file match: {url}~")
                    return url

        # 3. not exact, return repo page
        if repos:
            url = f"https://huggingface.co/{repos[0]['id']}"
            conlog(f"^A[huggingface] fallback repo: {url}~")
            return url

        return None

    except Exception as e:
        conlog(f"^N[huggingface] exception: {e}~")
        return None


def search_github(filename, token=None):
    # Search GitHub for a file by exact filename using the code search API.
    # Returns a direct link if found. Otherwise returns None (no fallback repo).
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        r = requests.get(
            "https://api.github.com/search/code",
            params={"q": f'"{filename}" in:path'},
            headers=headers,
            timeout=20,
        )
        if r.status_code != 200:
            conlog(f"^N[github] HTTP {r.status_code}: {r.text[:200]}~")
            return None
        items = r.json().get("items", [])
        if not items:
            conlog(f"^N[github] no code results for {filename}~")
            return None

        # exact
        for item in items:
            repo = item["repository"]["full_name"]
            path = item.get("path", "")
            if not path:
                continue
            fname = path.split("/")[-1].lower()
            if fname == filename.lower():
                branch = "main"
                if "ref=" in item.get("url", ""):
                    branch = item["url"].split("ref=")[-1]
                url = f"https://github.com/{repo}/blob/{branch}/{path}"
                conlog(f"^A[github] exact file match: {url}~")
                return url

        # no exact - nothing to return
        conlog(f"^N[github] no exact match for {filename}~")
        return None

    except Exception as e:
        conlog(f"^N[github] exception: {e}~")
        return None


def generate_report(path_json, token):
    with open(path_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    files = find_model_files(data)
    out_str = ""

    if not files:
        out_str = "No model filenames found"
        return out_str

    for fname in files:
        out_str += f"{fname}\n"
        found = False
        civ = search_civitai(fname)
        if civ:
            found = True
            out_str += f"\t{civ}\n"
        hf = search_huggingface(fname)
        if hf:
            found = True
            out_str += f"\t{hf}\n"
        gh = search_github(fname, token)
        if gh:
            found = True
            out_str += f"\t{gh}\n"

        if not found:
            out_str += f"\tnot found (or access denied)\n"
        out_str += "\n"

    return out_str


# ########################################################
class C_SUN_FindModelsInWF(C_SUN_ToolBase):
    """
    Version info:
    1.0.0 - ported to the script manager
    """
    version =             "1.0.1"

    icon =                "🌐 "
    info =                "Find online links to models used in workflow"
    name =                "Find Models in Workflow"
    output_lines =        20
    output_type =         TParamType.text
    section =             TSections["ComfyUI"]

    inputs = {
        "file_in": {
            "label":      "Workflow",
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

        # process!
        res = None
        err = "Ok!"
        token = load_token_from_file() # SUN_find_models_in_wf.token, if exists

        try:
            res = generate_report(file_in, token)
            snd_alert("finish")
        except json.JSONDecodeError:
            err = "Error: invalid JSON"
            snd_alert("error")
        except Exception as e:
            err = f"Unexpected error: {e}"
            snd_alert("error")

        return res, None, err


