# Script-U-Need (C) Alexander Guryev, 2026 | https://alexguryev.com

import base64
import gradio as gr
import os
import sys
import tkinter as tk
import tkinter.filedialog

sys.path.insert(0, os.path.dirname(__file__))
from gu_funclib import *

SUN_NAME = "Script-U-Need"
__version__ = "1.3.1" # maj:arch.changes . min:new functionality . tuning:fixes,tuning (main module only!)
CurVerInfo = f"{SUN_NAME} Manager: V{__version__} | Gradio: V{gr.__version__}"
conlog(f"^U{CurVerInfo}~")

from core import *

SUNTools = load_SUN_tools()
setup_tools_by_INI(SUNTools)

conlog("^U\nAll imports are finished~\n")

# #########################################################################
# #########################################################################
# #########################################################################
# ###########################  GRADIO SETUP  ##############################
# #########################################################################
# #########################################################################
# #########################################################################

#https://stackoverflow.com/a/74643784
def choose_folder(init_dir):
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

    return init_dir # fallback


# #########################################################################
def choose_arch(init_path):
    init_dir = get_filedir(init_path)
    filetypes = (
        ("Zip files", "*.zip"),
        ("All files", "*.*")
    )

    tk_root = tk.Tk()
    tk_root.attributes("-alpha", 0.0)
    tk_root.attributes("-topmost", True)
    f = None
    try:
        f = tk.filedialog.askopenfilename(parent=tk_root, initialdir=init_dir, title="Select archive", filetypes=filetypes)
    except Exception as err:
        conlog(f"^NError @ choose_arch:~ {err}")
    tk_root.destroy()

    if f not in [".", " ", "", init_dir]:
        return os.path.normpath(f)

    return init_path # fallback


# #########################################################################
def row_set_vis(flag):
    return gr.Row(visible=flag)


# #########################################################################
def source_pan_switch(state, selector):
    ret = [state]
    for i in range(len(selector)):
        if selector[i] == CH_SINGLE:
            ret.append(gr.Column(visible=(state == CH_SINGLE)))
        elif selector[i] == CH_FOLDER:
            ret.append(gr.Column(visible=(state == CH_FOLDER)))
        elif selector[i] == CH_ARCHIVE:
            ret.append(gr.Column(visible=(state == CH_ARCHIVE)))

    return tuple(ret)


# #########################################################################
def create_iface_input(ftype, label, info, default, range, step, lines):
    inp = None

    if ftype is TParamType.markdown: # ##################################
        inp = gr.Markdown(value=label, container=False)

    elif ftype is TParamType.text: # ##################################
        inp = gr.Textbox(value=default, label=label, info=info, lines=lines, max_lines=lines, interactive=True)

    elif ftype is TParamType.number: # ##################################
        if range is not None:
            a = range[0]
            b = range[1]
            if step is not None:
                inp = gr.Number(value=default, label=label, info=info, minimum=a, maximum=b, step=step, interactive=True)
            else:
                inp = gr.Number(value=default, label=label, info=info, minimum=a, maximum=b, interactive=True)
        else:
            inp = gr.Number(value=default, label=label, info=info, interactive=True)

    elif ftype is TParamType.slider: # ##################################
        if range is not None:
            a = range[0]
            b = range[1]
            if step is not None:
                inp = gr.Slider(value=default, label=label, info=info, interactive=True, minimum=a, maximum=b, step=step)
            else:
                inp = gr.Slider(value=default, label=label, info=info, interactive=True, minimum=a, maximum=b)
        else:
            inp = gr.Slider(value=default, label=label, info=info, interactive=True)

    elif ftype is TParamType.check: # ##################################
        inp = gr.Checkbox(value=default, label=label, info=info, interactive=True)

    elif ftype is TParamType.checkgroup: # ##################################
        if range is not None:
            inp = gr.CheckboxGroup(value=default, choices=range, label=label, info=info, interactive=True) # range is special

    elif ftype is TParamType.radio: # ##################################
        if range is not None:
            inp = gr.Radio(value=default, choices=range, label=label, info=info, interactive=True) # range is special

    elif ftype is TParamType.dropbox: # ##################################
        if range is not None:
            inp = gr.Dropdown(value=default, choices=range, label=label, info=info, interactive=True, allow_custom_value=False) # range is special

    elif ftype is TParamType.image: # ##################################
        inp = gr.Image(label=label, interactive=True, type="filepath")

    elif ftype is TParamType.imageedit: # ##################################
        inp = gr.ImageEditor(label=label, type="filepath", canvas_size=(512, 512), height=512, transforms=None, layers=False,
            brush=gr.Brush(color_mode="fixed", default_color="magenta", colors=["magenta", "black", "white"]), interactive=True)

    elif ftype is TParamType.video: # ##################################
        inp = gr.Video(label=label, interactive=True, sources=["upload"], format="mp4", autoplay=False)

    elif ftype is TParamType.audio: # ##################################
        inp = gr.Audio(label=label, interactive=True, type="filepath",
            waveform_options=gr.WaveformOptions(skip_length=5, show_recording_waveform=True)
        )

    elif ftype is TParamType.folder: # ##################################
        inp = gr.File(label=label, interactive=True, file_count="directory", height=150)

    elif ftype is TParamType.archive: # ##################################
        inp = gr.File(label=label, interactive=True, file_count="single", file_types=[".zip"])

    elif ftype is TParamType.textfile: # ##################################
        inp = gr.File(label=label, interactive=True, file_count="single",
                      file_types=[".txt", ".py", ".pyw", ".c", ".h", ".cpp", ".cxx", ".cc",
                                  ".hpp", ".hxx", ".hh", ".inl", ".lua", ".js", ".mjs", ".cjs", ".jsx",
                                  ".ms", ".mse", ".mcr", ".mzs"])

    elif ftype is TParamType.jsonfile: # ##################################
        inp = gr.File(label=label, interactive=True, file_count="single", file_types=[".json"])

    return inp


# !!!!!!!!!!    IMPLEMENT INPUT GROUPS    !!!!!!!!!
# #########################################################################
def integrate_tools(tool_sect=None):
    global SUNTools
    global ConfigSys
    tools_iter = iter(SUNTools) # all tools already sorted by section!
    tool = next(tools_iter, None)
    while tool is not None:
        # skip all non-specified tool sections
        if (tool_sect is not None) and (tool_sect != tool.section):
            tool = next(tools_iter, None)
            continue

        # normally skip any test tool
        #if (tool_sect is None) and (tool.section == TSections["Test"]):
        #    tool = next(tools_iter, None)
        #    continue

        # create tool section tab
        sect_cur = tool.section
        sect_name = get_key_by_value(TSections, sect_cur)
        with gr.Tab(f"{TSectionIcons[tool.section]} {sect_name}"):
            conlog(f"^ASection `{sect_name}` integration...~")
            while True:
                # specific tool in current section tab
                with gr.Tab(f"{tool.icon}{tool.name}"):
                    with gr.Row(): # info
                        gr.Markdown(tool.info)

                    # source selector and buttons
                    all_inputs = []
                    preseted_inputs = []
                    tool_errors = ""
                    src_select = None
                    selector_out = []
                    with gr.Row():
                        with gr.Column(scale=1):
                            with gr.Row():
                                if len(tool.src_select) > 0: # if src selector is available
                                    src_select_state = gr.State(tool.src_select[0])
                                    src_select = gr.Radio(label=CAP_SRC_SELECTOR, choices=tool.src_select, value=tool.src_select[0], interactive=True)
                                    all_inputs.append(src_select)
                                    selector_out = [src_select_state]
                                else:
                                    src_select = gr.Markdown(visible=False) # stub!
                        with gr.Column(scale=5):
                            gr.Markdown()
                        with gr.Column(scale=1):
                            with gr.Row():
                                submit_btn = gr.Button(CAP_SUBMIT, variant="primary")

                    with gr.Row():
                        # custom UI or standard inputs
                        _custom_ui = tool.build_ui()
                        if _custom_ui is not None:
                            all_inputs.extend(_custom_ui)
                            # custom selector panels support
                            if hasattr(tool, '_selector_out'):
                                selector_out.extend(tool._selector_out)

                        # setup inputs
                        selector_done = False
                        main_done = False
                        col_current = 1
                        while _custom_ui is None and col_current < 3: # column limit = 2!
                            with gr.Column(scale=1):
                                for inp_name in tool.inputs.keys(): # usual params @ current column
                                    done, advanced, column, default, info, label, main_input, lines, rang, selector, step, ftype, use_ini = \
                                        tool.get_input_params(inp_name)
                                    if done: continue

                                    if column == col_current:
                                        if tool.advanced_col == col_current and advanced: continue

                                        tool.set_input_done(inp_name)

                                        if selector:
                                            if len(tool.src_select) == 0:
                                                tool_errors += f"    no selector options specified: `{inp_name}`\n"
                                                continue
                                            if selector_done:
                                                tool_errors += f"    src selector already exists: `{inp_name}`\n"
                                                continue
                                            selector_done = True
                                            with gr.Column(scale=1):
                                                with gr.Row():
                                                    if CH_SINGLE in tool.src_select:
                                                        with gr.Column(visible=(tool.src_select[0]==CH_SINGLE)) as single_in_pan:
                                                            if ftype in ALLOWED_SINGLE_INPUTS:
                                                                single_in = create_iface_input(ftype, label, "", default, None, None, lines)
                                                            else:
                                                                tool_errors += f"    src selector of incorrect type: `{inp_name}`\n"
                                                                continue
                                                            all_inputs.append(single_in)
                                                            selector_out.append(single_in_pan)

                                                    if CH_FOLDER in tool.src_select:
                                                        with gr.Column(visible=(tool.src_select[0]==CH_FOLDER)) as folder_in_pan:
                                                            with gr.Row():
                                                                btn_sel_folder = gr.Button("Select folder", scale=1)
                                                                folder_in = gr.Textbox(value=tool.path_fold, show_label=False, interactive=False, container=False, scale=4)
                                                            with gr.Row(): gr.Markdown("<div><br><br></div>")
                                                            btn_sel_folder.click(fn=choose_folder, inputs=folder_in, outputs=folder_in)
                                                            all_inputs.append(folder_in)
                                                            selector_out.append(folder_in_pan)

                                                    if CH_ARCHIVE in tool.src_select:
                                                        with gr.Column(visible=(tool.src_select[0]==CH_ARCHIVE)) as arch_in_pan:
                                                            with gr.Row():
                                                                btn_sel_arch = gr.Button("Select archive", scale=1)
                                                                arch_in = gr.Textbox(value=tool.path_arch, show_label=False, interactive=False, container=False, scale=4)
                                                            with gr.Row(): gr.Markdown("<div><br><br></div>")
                                                            btn_sel_arch.click(fn=choose_arch, inputs=arch_in, outputs=arch_in)
                                                            all_inputs.append(arch_in)
                                                            selector_out.append(arch_in_pan)
                                        else:
                                            if use_ini:
                                                try:
                                                    default = ConfigSys[tool.name][inp_name]
                                                except Exception: pass
                                            inp = create_iface_input(ftype, label, info, default, rang, step, lines)
                                            if inp is not None:
                                                if not (ftype in NOT_ARGUM_INPUTS):
                                                    all_inputs.append(inp) # append only allowed inputs
                                            else:
                                                tool_errors += f"    input failed: `{inp_name}`\n"

                                        if main_input: # only in usual params!
                                            if main_done:
                                                tool_errors += f"    main input already specified: `{inp_name}`\n"
                                            else:
                                                main_done = True

                                if tool.advanced_col == col_current: # advanced params @ current column
                                    with gr.Accordion(CAP_ADVANCED, open=False):
                                        for inp_name in tool.inputs.keys():
                                            done, advanced, column, default, info, label, main_input, lines, rang, selector, step, ftype, use_ini = \
                                                tool.get_input_params(inp_name)
                                            if done: continue

                                            tool.set_input_done(inp_name)
                                            if selector:
                                                tool_errors += f"    src selector is not allowed in Advanced Params: `{inp_name}`\n"
                                                continue
                                            else:
                                                if column == col_current and advanced:
                                                    if use_ini:
                                                        try:
                                                            default = ConfigSys[tool.name][inp_name]
                                                        except Exception: pass
                                                    inp = create_iface_input(ftype, label, info, default, rang, step, lines)
                                                    if inp is not None:
                                                        if not (ftype in NOT_ARGUM_INPUTS):
                                                            all_inputs.append(inp) # append only allowed inputs
                                                    else:
                                                        tool_errors += f"    input failed: `{inp_name}`\n"
                            if tool.input_cols == col_current: break
                            col_current += 1

                        # output / col (last)
                        all_outputs = []
                        #with gr.Column(scale=(2 if tool.input_cols == 1 else 1)):
                        with gr.Column(scale=1):
                            log = gr.Textbox(label=CAP_LOG, lines=LOGLINES, max_lines=LOGLINES)
                            if tool.output_type in ALLOWED_TOOL_OUT:
                                if tool.output_type == TParamType.text:
                                    out_file = gr.Markdown(visible=False)
                                    out_preview = gr.Textbox(label=CAP_RESULT, lines=tool.output_lines, max_lines=tool.output_lines) # special textbox
                                else:
                                    out_file = gr.File(label=CAP_RES_DWNL + " (will appear after run)", value=None, file_count="single")

                                if tool.output_type == TParamType.image:
                                    out_preview = gr.Image(label=CAP_RES_PREV, format="png", type="pil", interactive=False, show_download_button=False)
                                elif tool.output_type == TParamType.video:
                                    out_preview = gr.Video(label=CAP_RES_PREV, format="mp4", interactive=False, autoplay=True)
                                elif tool.output_type == TParamType.audio:
                                    out_preview = gr.Audio(label=CAP_RES_PREV, interactive=False, type="filepath",
                                        waveform_options=gr.WaveformOptions(skip_length=5, show_recording_waveform=True)
                                    )
                                elif tool.output_type == TParamType.textfile:
                                    out_preview = gr.Markdown(visible=False)
                            else:
                                tool_errors += f"    output has incorrect type\n"

                            all_outputs.append(out_preview)
                            all_outputs.append(out_file)
                            all_outputs.append(log)

                        if len(tool.src_select) > 0: # if src selector is available
                            selector_in = [src_select, gr.State(tool.src_select)]
                            src_select.change(source_pan_switch,
                                inputs=selector_in,
                                outputs=selector_out
                            )

                        submit_btn.click(tool.run, inputs=all_inputs, outputs=all_outputs)

                    if len(tool_errors) > 0:
                        conlog(f"^N    `{tool.name}` has errors:\n{tool_errors}~")
                    #else:
                    #    conlog(f"^Y    `{tool.name}` - OK~")

                tool = next(tools_iter, None)
                if tool is not None:
                    if tool.section != sect_cur:
                        break # skip to next section
                else: break


# #########################################################################
try:
    with open(os.path.join("core", "style.css"), "r") as file: CustomCSS = file.read()
except Exception:
    CustomCSS = ""
    conlog("^Nstyle.css not found, using defaults~")

_icon_b64 = ""
try:
    with open(os.path.join(DIR_CORE, "icon.png"), "rb") as _f:
        _icon_b64 = base64.b64encode(_f.read()).decode()
except Exception:
    pass

with gr.Blocks(title=SUN_NAME, fill_width=True, css=CustomCSS, #js=CustomJS,
        theme=gr.themes.Glass(primary_hue="sky", radius_size=gr.themes.sizes.radius_sm,
            font=[gr.themes.GoogleFont("IBM Plex Mono"), "ui-monospace", "Consolas", "monospace"]
        )
    ) as full_ui:

    gr.HTML(f'<div style="display:flex;align-items:center;gap:10px;padding:6px 8px"><img src="data:image/png;base64,{_icon_b64}" width="32" height="32" style="border-radius:6px;flex-shrink:0"><span>Script-U-Need</span></div>')


    with gr.Row():
        with gr.Tab("", visible=False): gr.Markdown() # stub

        integrate_tools() # all work tools
        conlog("^UTools setup is complete~\n")

        with gr.Tab("⏱️ Versions"): vers_info = gr.Markdown()


    @full_ui.load(outputs=[vers_info])
    def page_init(request: gr.Request):
        global CurVerInfo
        with open(os.path.join(os.getcwd(), "core", "version_info.txt"), "r", encoding="utf-8") as file:
            ver = CurVerInfo + "\n\n" + file.read()

        return ver


# #########################################################################
if __name__ == "__main__":
    this_dir = os.getcwd()
    full_ui.launch(
        server_name="127.0.0.1",
        server_port=7870,
        allowed_paths=[
            os.path.join(this_dir, "core"),
            os.path.join(this_dir, "tools"),
            os.path.join(this_dir, "work"),
        ],
        favicon_path=os.path.join(this_dir, "core", "icon.png")
    )

