import tkinter as tk
from tkinter import scrolledtext
import threading
try:
    import customtkinter as ctk
    USING_CTK = True
except Exception:
    ctk = None
    USING_CTK = False
import g4f
# message font and colors
MSG_FONT_NAME = "Rubik"
MSG_FONT_SIZE = 14
MSG_BG = "black"
MSG_FG = "white"

# Key mapping for hotkey selection
KEY_TO_VK = {
    'Home': 0x24, 'End': 0x23, 'Insert': 0x2D, 'Delete': 0x2E,
    'PageUp': 0x21, 'PageDown': 0x22,
    'Up': 0x26, 'Down': 0x28, 'Left': 0x25, 'Right': 0x27,
    'F1': 0x70, 'F2': 0x71, 'F3': 0x72, 'F4': 0x73, 'F5': 0x74, 'F6': 0x75, 'F7': 0x76, 'F8': 0x77, 'F9': 0x78, 'F10': 0x79, 'F11': 0x7A, 'F12': 0x7B,
    'F1': 0x70, 'F2': 0x71, 'F3': 0x72, 'F4': 0x73, 'F5': 0x74, 'F6': 0x75, 'F7': 0x76, 'F8': 0x77, 'F9': 0x78, 'F10': 0x79, 'F11': 0x7A, 'F12': 0x7B,
    'Space': 0x20, 'Tab': 0x09, 'Enter': 0x0D, 'Escape': 0x1B,
    'PrintScreen': 0x2C, 'Pause': 0x13,
}
# Reverse mapping for display
VK_TO_KEY = {v: k for k, v in KEY_TO_VK.items()}

# Control structure for the hotkey worker thread
HOTKEY_CONTROL = {
    'thread_id': 0,
    'vk': KEY_TO_VK.get('Home', 0x24),
    'hotkey_id': 1,
}

# Custom message to notify the worker to reconfigure the registered hotkey
WM_RECONFIGURE_HOTKEY = 0x0401

def request_hotkey_change(vk_code: int) -> bool:
    """Request the hotkey worker to switch to `vk_code`.

    Returns True if the request was posted to the worker thread, False otherwise.
    If the worker hasn't started yet, the worker will pick up the `vk` value at startup.
    """
    HOTKEY_CONTROL['vk'] = int(vk_code)
    try:
        import ctypes
        user32 = ctypes.windll.user32
        tid = HOTKEY_CONTROL.get('thread_id', 0)
        if tid:
            # Post a custom message to the worker thread to notify reconfiguration
            user32.PostThreadMessageW(tid, WM_RECONFIGURE_HOTKEY, 0, 0)
            return True
    except Exception:
        pass
    return False


def create_app():
    if USING_CTK:
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        root = ctk.CTk()
    else:
        root = tk.Tk()

    root.title("AI Assistant")
    width, height = 300, 300
    screen_h = root.winfo_screenheight()
    y = max(0, screen_h - height)
    root.geometry(f"{width}x{height}+0+{y}")
    root.resizable(False, False)
    # default transparency and always-on-top
    try:
        root.attributes('-alpha', 0.5)
    except Exception:
        pass
    try:
        root.attributes('-topmost', True)
    except Exception:
        pass

    import tkinter.font as tkfont

    # determine font (Rubik if available, else fallback)
    available_fonts = list(tkfont.families())
    if MSG_FONT_NAME in available_fonts:
        chosen_font = (MSG_FONT_NAME, MSG_FONT_SIZE)
    else:
        chosen_font = ("Consolas", MSG_FONT_SIZE)
    # Conversation history kept in-memory for this session only
    conversation_history = []
    # loading indicator for AI responses (three animated dots)
    loading_var = tk.StringVar(value='')
    spinner_running = False
    spinner_after_id = None
    spinner_index = 0

    def _spinner_step():
        nonlocal spinner_index, spinner_after_id, spinner_running
        if not spinner_running:
            return
        spinner_index = (spinner_index + 1) % 4
        states = ['.', '..', '...']
        try:
            loading_var.set(states[spinner_index])
        except Exception:
            pass
        try:
            spinner_after_id = root.after(400, _spinner_step)
        except Exception:
            spinner_after_id = None

    def start_spinner():
        nonlocal spinner_running, spinner_after_id, spinner_index
        try:
            if spinner_running:
                return
            spinner_running = True
            spinner_index = -1
            _spinner_step()
        except Exception:
            pass

    def stop_spinner():
        nonlocal spinner_running, spinner_after_id
        try:
            spinner_running = False
            if spinner_after_id:
                try:
                    root.after_cancel(spinner_after_id)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            loading_var.set('')
        except Exception:
            pass

    def make_scrolled_text(parent, font, use_grid=False, grid_opts=None, pack_opts=None):
        container = tk.Frame(parent)
        text = tk.Text(
            container,
            wrap='word',
            font=font,
            bg=MSG_BG,
            fg=MSG_FG,
            insertbackground=MSG_FG,
            state='disabled',
        )
        vsb = tk.Scrollbar(container, orient='vertical', command=text.yview, bg=MSG_BG, activebackground=MSG_FG)
        text.configure(yscrollcommand=vsb.set)
        text.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        if use_grid and grid_opts:
            container.grid(**grid_opts)
        elif pack_opts is not None:
            container.pack(**pack_opts)
        return text

    # transparency window state
    trans_win = None
    trans_btn = None
    hide_trans_btn = lambda: None
    show_trans_btn = lambda: None
    # window hide/show state for all windows
    windows_hidden = False
    saved_trans_win_exists = False

    def toggle_all_windows(event=None):
        nonlocal windows_hidden, saved_trans_win_exists, trans_win
        if not windows_hidden:
            # hide main and transparency window (remember state)
            try:
                saved_trans_win_exists = trans_win is not None and trans_win.winfo_exists()
            except Exception:
                saved_trans_win_exists = False
            try:
                if saved_trans_win_exists and trans_win is not None:
                    trans_win.withdraw()
            except Exception:
                pass
            try:
                # hide the transparency button
                hide_trans_btn()
            except Exception:
                pass
            try:
                root.withdraw()
            except Exception:
                pass
            windows_hidden = True
        else:
            # show main and restore transparency window if it was open
            try:
                root.deiconify()
                root.lift()
                root.attributes('-topmost', True)
            except Exception:
                pass
            try:
                if saved_trans_win_exists and trans_win is not None and trans_win.winfo_exists():
                    trans_win.deiconify()
                    trans_win.lift()
                    try:
                        trans_win.attributes('-topmost', True)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                show_trans_btn()
            except Exception:
                pass
            windows_hidden = False

    def toggle_transparency_window(event=None):
        nonlocal trans_win
        try:
            exists = trans_win is not None and trans_win.winfo_exists()
        except Exception:
            exists = False
        if exists:
            try:
                trans_win.destroy()
            except Exception:
                trans_win = None
            trans_win = None
            return

        # create new small window with slider
        if USING_CTK and hasattr(ctk, 'CTkToplevel'):
            try:
                trans_win = ctk.CTkToplevel(root)
            except Exception:
                trans_win = tk.Toplevel(root)
        else:
            trans_win = tk.Toplevel(root)
        try:
            trans_win.title('Transparency')
        except Exception:
            pass
        trans_win.resizable(False, False)
        trans_win.geometry('260x72')
        try:
            trans_win.attributes('-topmost', True)
        except Exception:
            pass

        # keep the transparency button visible (do not hide when opening settings)

        def on_close():
            nonlocal trans_win
            try:
                trans_win.destroy()
            except Exception:
                pass
            trans_win = None

        trans_win.protocol('WM_DELETE_WINDOW', on_close)

        # current alpha
        try:
            cur_alpha = float(root.attributes('-alpha'))
        except Exception:
            cur_alpha = 1.0

        def on_scale(v):
            try:
                root.attributes('-alpha', float(v))
            except Exception:
                pass

        # Build a lightweight scrollable area while preserving widget styles
        container = tk.Frame(trans_win)
        container.pack(fill='both', expand=True)
        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        # prefer CTk scrollbar if available, otherwise style the tk.Scrollbar to match dark theme
        if USING_CTK and hasattr(ctk, 'CTkScrollbar'):
            try:
                vscroll = ctk.CTkScrollbar(container, orientation='vertical', command=canvas.yview)
                try:
                    vscroll.configure(fg_color=MSG_BG)
                except Exception:
                    pass
            except Exception:
                vscroll = tk.Scrollbar(container, orient='vertical', command=canvas.yview, bg=MSG_BG, troughcolor=MSG_BG, activebackground=MSG_FG, highlightthickness=0)
        else:
            vscroll = tk.Scrollbar(container, orient='vertical', command=canvas.yview, bg=MSG_BG, troughcolor=MSG_BG, activebackground=MSG_FG, highlightthickness=0)
        canvas.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        content = tk.Frame(canvas)
        canvas.create_window((0, 0), window=content, anchor='nw')

        def _on_config(e):
            try:
                canvas.configure(scrollregion=canvas.bbox('all'))
            except Exception:
                pass

        content.bind('<Configure>', _on_config)

        # Apply dark theme to the settings window and inner widgets
        try:
            # Try CTk-specific background first
            if USING_CTK and hasattr(trans_win, 'configure'):
                try:
                    trans_win.configure(fg_color=MSG_BG)
                except Exception:
                    trans_win.configure(bg=MSG_BG)
            else:
                trans_win.configure(bg=MSG_BG)
        except Exception:
            pass

        try:
            container.configure(bg=MSG_BG)
        except Exception:
            pass
        try:
            canvas.configure(bg=MSG_BG)
        except Exception:
            pass
        try:
            content.configure(bg=MSG_BG)
        except Exception:
            pass

        def _on_mousewheel(e):
            try:
                delta = int(-1 * (e.delta / 120))
                canvas.yview_scroll(delta, 'units')
            except Exception:
                pass

        canvas.bind_all('<MouseWheel>', _on_mousewheel)

        # Slider (inside content so it scrolls)
        if USING_CTK and hasattr(ctk, 'CTkSlider'):
            try:
                slider = ctk.CTkSlider(content, from_=0.0, to=1.0, command=on_scale)
                slider.set(cur_alpha)
                slider.pack(padx=8, pady=8, fill='x')
            except Exception:
                slider = tk.Scale(content, from_=0.0, to=1.0, orient='horizontal', resolution=0.01, command=on_scale, length=220)
                slider.set(cur_alpha)
                slider.pack(padx=8, pady=8, fill='x')
        else:
            slider = tk.Scale(content, from_=0.0, to=1.0, orient='horizontal', resolution=0.01, command=on_scale, length=220)
            slider.set(cur_alpha)
            slider.pack(padx=8, pady=8, fill='x')

        # Hotkey selection UI (inside content)
        try:
            current_label = VK_TO_KEY.get(HOTKEY_CONTROL.get('vk', 0x24), 'Home')
        except Exception:
            current_label = 'Home'
        hotkey_var = tk.StringVar(value=current_label)
        hotkey_options = list(KEY_TO_VK.keys())
        if USING_CTK and hasattr(ctk, 'CTkOptionMenu'):
            try:
                hotkey_menu = ctk.CTkOptionMenu(content, values=hotkey_options, command=lambda v: hotkey_var.set(v))
                hotkey_menu.set(current_label)
                hotkey_menu.pack(padx=8, pady=(4, 0))
            except Exception:
                hotkey_menu = tk.OptionMenu(content, hotkey_var, *hotkey_options)
                hotkey_menu.pack(padx=8, pady=(4, 0))
        else:
            hotkey_menu = tk.OptionMenu(content, hotkey_var, *hotkey_options)
            hotkey_menu.pack(padx=8, pady=(4, 0))

        # Style the OptionMenu and its dropdown to match dark theme
        try:
            try:
                hotkey_menu.configure(bg=MSG_BG, fg=MSG_FG)
            except Exception:
                hotkey_menu.config(bg=MSG_BG, fg=MSG_FG)
            # for tk OptionMenu adjust the internal menu colors
            try:
                hotkey_menu['menu'].config(bg=MSG_BG, fg=MSG_FG)
            except Exception:
                pass
        except Exception:
            pass

        def apply_hotkey_cmd():
            sel = hotkey_var.get()
            vk = KEY_TO_VK.get(sel)
            if vk is None:
                try:
                    append_message(f"System: Unknown key {sel}")
                except Exception:
                    pass
                return
            ok = request_hotkey_change(vk)
            try:
                append_message(f"System: Hotkey set to {sel} (posted={ok})")
            except Exception:
                pass

        if USING_CTK and hasattr(ctk, 'CTkButton'):
            try:
                apply_btn = ctk.CTkButton(content, text='Apply Hotkey', command=apply_hotkey_cmd)
                apply_btn.pack(padx=8, pady=(2, 4))
            except Exception:
                apply_btn = tk.Button(content, text='Apply Hotkey', command=apply_hotkey_cmd)
                apply_btn.pack(padx=8, pady=(2, 4))
        else:
            apply_btn = tk.Button(content, text='Apply Hotkey', command=apply_hotkey_cmd)
            apply_btn.pack(padx=8, pady=(2, 4))

        # Style apply button to dark theme
        try:
            try:
                apply_btn.configure(bg=MSG_BG, fg=MSG_FG, activebackground=MSG_BG, activeforeground=MSG_FG)
            except Exception:
                apply_btn.config(bg=MSG_BG, fg=MSG_FG, activebackground=MSG_BG, activeforeground=MSG_FG)
        except Exception:
            try:
                apply_btn.configure(fg_color=MSG_BG, text_color=MSG_FG)
            except Exception:
                pass

        # Reset conversation/context button (in-memory only)
        def reset_conversation():
            try:
                conversation_history.clear()
            except Exception:
                pass
            try:
                messages.config(state='normal')
                messages.delete('1.0', 'end')
                messages.config(state='disabled')
            except Exception:
                pass
            try:
                append_message('System: Context cleared')
            except Exception:
                pass

        if USING_CTK and hasattr(ctk, 'CTkButton'):
            try:
                reset_btn = ctk.CTkButton(content, text='Reset Context', command=reset_conversation)
                reset_btn.pack(padx=8, pady=(4, 8))
            except Exception:
                reset_btn = tk.Button(content, text='Reset Context', bg='red', fg='white', command=reset_conversation)
                reset_btn.pack(padx=8, pady=(4, 8))
        else:
            reset_btn = tk.Button(content, text='Reset Context', bg='red', fg='white', command=reset_conversation)
            reset_btn.pack(padx=8, pady=(4, 8))

        # Style reset button to dark theme (if tk button used)
        try:
            try:
                reset_btn.configure(bg=MSG_BG if getattr(reset_btn, 'cget', lambda x: None)('bg') != 'red' else 'red', fg=MSG_FG)
            except Exception:
                reset_btn.config(bg=MSG_BG if getattr(reset_btn, 'cget', lambda x: None)('bg') != 'red' else 'red', fg=MSG_FG)
        except Exception:
            try:
                reset_btn.configure(fg_color=MSG_BG, text_color=MSG_FG)
            except Exception:
                pass


    if USING_CTK:
        root.grid_rowconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=0)
        root.grid_columnconfigure(0, weight=1)
        messages = make_scrolled_text(
            root,
            chosen_font,
            use_grid=True,
            grid_opts={"row": 0, "column": 0, "sticky": "nsew", "padx": 8, "pady": (8, 4)},
        )
        # create loading label under messages (row 1)
        loading_frame = tk.Frame(root, bg=MSG_BG)
        loading_label = tk.Label(loading_frame, textvariable=loading_var, bg=MSG_BG, fg=MSG_FG)
        loading_label.pack(anchor='w', padx=8)
        try:
            loading_frame.grid(row=1, column=0, sticky='ew', padx=8)
        except Exception:
            try:
                loading_frame.pack(fill='x')
            except Exception:
                pass
        input_frame = ctk.CTkFrame(root)
        # place input frame on row 2 to leave space for loading indicator at row 1
        input_frame.grid(row=2, column=0, sticky='ew', padx=8, pady=8)
        input_frame.grid_columnconfigure(0, weight=1)
        entry = ctk.CTkEntry(input_frame)
        entry.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        entry.focus_set()
        send_btn = ctk.CTkButton(input_frame, text='Send', width=70)
        send_btn.grid(row=0, column=1)
        trans_btn = ctk.CTkButton(input_frame, text='☰', width=30, command=toggle_transparency_window)
        trans_btn.grid(row=0, column=2, padx=(6, 0))
        # status indicator
        # loading indicator is displayed under the messages area (row 1)
        # define hide/show behavior for this button
        def _hide():
            try:
                trans_btn.grid_remove()
            except Exception:
                pass

        def _show():
            try:
                trans_btn.grid()
            except Exception:
                pass

        hide_trans_btn = _hide
        show_trans_btn = _show
    else:
        messages = make_scrolled_text(
            root,
            chosen_font,
            use_grid=False,
            pack_opts={"fill": "both", "expand": True, "padx": 8, "pady": (8, 4)},
        )
        # create loading label under messages (before bottom_frame)
        loading_frame = tk.Frame(root, bg=MSG_BG)
        loading_label = tk.Label(loading_frame, textvariable=loading_var, bg=MSG_BG, fg=MSG_FG)
        loading_label.pack(anchor='w', padx=8)
        loading_frame.pack(fill='x')

        bottom_frame = tk.Frame(root)
        bottom_frame.pack(fill='x', padx=8, pady=8)
        entry = tk.Entry(bottom_frame)
        entry.pack(side='left', fill='x', expand=True, padx=(0, 6))
        # loading indicator is shown above (under messages)
        send_btn = tk.Button(bottom_frame, text='Send', width=8)
        send_btn.pack(side='right')
        trans_btn = tk.Button(bottom_frame, text='☰', width=2, command=toggle_transparency_window)
        trans_btn.pack(side='right', padx=(0, 6))
        # define hide/show behavior for this button
        def _hide():
            try:
                trans_btn.pack_forget()
            except Exception:
                pass

        def _show():
            try:
                trans_btn.pack(side='right', padx=(0, 6))
            except Exception:
                pass

        hide_trans_btn = _hide
        show_trans_btn = _show

    def append_message(text: str):
        messages.config(state='normal')
        messages.insert('end', text + '\n')
        messages.see('end')
        messages.config(state='disabled')

    # start with empty in-memory conversation (no persisted JSON)

    def call_g4f(messages_list):
        try:
            return g4f.ChatCompletion.create(
                model="",
                messages=messages_list,
                stream=False,
            )
        except Exception as ex:
            return f"Error: {ex}"

    def send():
        prompt = entry.get().strip()
        if not prompt:
            return
        entry.delete(0, 'end')
        try:
            send_btn.configure(state='disabled')
        except Exception:
            send_btn.config(state='disabled')
        try:
            start_spinner()
        except Exception:
            try:
                loading_var.set('...')
            except Exception:
                pass
        append_message(f"You: {prompt}")
        # append to in-memory conversation history
        try:
            conversation_history.append({"role": "user", "content": prompt})
        except Exception:
            pass

        def worker():
            resp = call_g4f(conversation_history)
            if hasattr(resp, '__iter__') and not isinstance(resp, str):
                try:
                    resp = ''.join(str(x) for x in resp)
                except Exception:
                    resp = str(resp)
            # append AI response to in-memory history
            try:
                conversation_history.append({"role": "assistant", "content": resp})
            except Exception:
                pass
            def finish_ui():
                try:
                    append_message(f"AI: {resp}")
                except Exception:
                    pass
                try:
                    stop_spinner()
                except Exception:
                    try:
                        loading_var.set('')
                    except Exception:
                        pass
                try:
                    send_btn.configure(state='normal')
                except Exception:
                    try:
                        send_btn.config(state='normal')
                    except Exception:
                        pass

            root.after(0, finish_ui)

        threading.Thread(target=worker, daemon=True).start()

    try:
        send_btn.configure(command=send)
    except Exception:
        send_btn.config(command=send)
    entry.bind('<Return>', lambda e: send())

    # expose toggle function so external/global hooks can call it
    try:
        root.toggle_all_windows = toggle_all_windows
    except Exception:
        pass
    return root


if __name__ == '__main__':
    app = create_app()

    # register OS-level hotkeys via RegisterHotKey in a dedicated thread
    try:
        import ctypes
        import ctypes.wintypes as wintypes
        import atexit

        def _hotkey_worker():
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            WM_HOTKEY = 0x0312

            HOTKEY_ID = HOTKEY_CONTROL.get('hotkey_id', 1)

            # publish this thread's id so UI can post reconfigure messages
            try:
                HOTKEY_CONTROL['thread_id'] = kernel32.GetCurrentThreadId()
            except Exception:
                HOTKEY_CONTROL['thread_id'] = 0

            cur_vk = HOTKEY_CONTROL.get('vk', 0x24)
            try:
                user32.RegisterHotKey(None, HOTKEY_ID, 0, cur_vk)
            except Exception:
                pass

            def _unregister():
                try:
                    user32.UnregisterHotKey(None, HOTKEY_ID)
                except Exception:
                    pass

            atexit.register(_unregister)

            msg = wintypes.MSG()
            while True:
                b = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if b == 0:
                    break
                if msg.message == WM_HOTKEY:
                    try:
                        if getattr(msg, 'wParam', None) == HOTKEY_ID:
                            try:
                                app.after(0, app.toggle_all_windows)
                            except Exception:
                                pass
                    except Exception:
                        pass
                elif msg.message == WM_RECONFIGURE_HOTKEY:
                    try:
                        new_vk = HOTKEY_CONTROL.get('vk', cur_vk)
                        if new_vk != cur_vk:
                            try:
                                user32.UnregisterHotKey(None, HOTKEY_ID)
                            except Exception:
                                pass
                            try:
                                user32.RegisterHotKey(None, HOTKEY_ID, 0, new_vk)
                                cur_vk = new_vk
                            except Exception:
                                try:
                                    # try to restore previous registration
                                    user32.RegisterHotKey(None, HOTKEY_ID, 0, cur_vk)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        t = threading.Thread(target=_hotkey_worker, daemon=True)
        t.start()
    except Exception:
        print("Global hotkeys not available on this platform.")

    app.mainloop()
