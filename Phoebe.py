import base64
import binascii
import json
import mimetypes
import os
import re
import random
import hashlib
import socket
import sys
import tempfile
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from urllib.parse import urlparse

try:
    import pygame
except ImportError:
    pygame = None

import requests
import pystray
from PIL import Image, ImageTk, ImageSequence

import emoji_list
from themes import get_theme, load_ui_settings, save_ui_settings

APP_DIR = os.path.dirname(
    os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
)
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
ERROR_LOG_FILE = os.path.join(APP_DIR, "error_log.txt")
WINDOW_ICON_FILE = os.path.join(APP_DIR, "Assets", "Images", "icon.ico")
WINDOW_ICON_ICO_FILE = os.path.join(APP_DIR, "icon.ico")

AUTOSAVE_FILE = os.path.join(APP_DIR, "delete_me_to_reset_personality.phbe")
MUSIC_DIR = os.path.join(APP_DIR, "Assets", "Musics")
MUSIC_EXTENSIONS = (".mp3", ".wav", ".ogg")

EMPTY_CHAT_ART = r""" 






{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}
{}@@@@@@@  @@@  @@@  @@@@@@  @@@@@@@@ @@@@@@@  @@@@@@@@ {}
{}@@!  @@@ @@!  @@@ @@!  @@@ @@!      @@!  @@@ @@!      {}
{}@!@@!@!  @!@!@!@! @!@  !@! @!!!:!   @!@!@!@  @!!!:!   {}
{}!!:      !!:  !!! !!:  !!! !!:      !!:  !!! !!:      {}
{} :        :   : :  : :. :  : :: ::  :: : ::  : :: ::  {}
{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}"""
ENTRY_PLACEHOLDER = "Say something..."

SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")

ALICE_FILETYPES = [("Phoebe mind file", "*.phbe"), ("All files", "*.*")]
ALICE_FORMAT_VERSION = 1
ALICE_ENCRYPTION = "xor-sha256"
ALICE_NEKO = bytes(
    value ^ 0x5A for value in base64.b64decode("a2toY2lv")
).decode("ascii")

EMOJI_FONT = ("Segoe UI Emoji", 11)
TEXT_FONT = ("Verdana", 10)
TEXT_FONT_BOLD = ("Verdana", 10, "bold")
TEXT_FONT_ITALIC = ("Verdana", 10, "italic")
TEXT_FONT_BOLD_ITALIC = ("Verdana", 10, "bold", "italic")

CODE_FONT = ("Courier New", 10)
CODE_FONT_BLOCK = ("Courier New", 10)

THUMB_MAX = 220          
PREVIEW_THUMB_MAX = 84   
ATTACH_REMOVE_BTN_SIZE = 16
GIF_FRAME_DELAY_MIN = 20  


ICONS_DIR = os.path.join(APP_DIR, "Assets", "Images")
ICON_BTN_SIZE = 20 

CONNECTIVITY_CHECK_INTERVAL_MS = 8000
CONNECTIVITY_CHECK_TIMEOUT_S = 3

IMAGE_FILETYPES = [
    ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
    ("All files", "*.*"),
]

MARKDOWN_TOKEN_RE = re.compile(
    r"(?P<code>`[^`]+`)"
    r"|(?P<bolditalic>\*\*\*[^*]+\*\*\*|___[^_]+___)"
    r"|(?P<bold>\*\*[^*]+\*\*|__[^_]+__)"
    r"|(?P<italic>\*[^*]+\*|_[^_]+_)"
)

URL_RE = re.compile(
    r"(?P<url>(?:https?://|www\.)[^\s<>\"'\)\]]+)",
    re.IGNORECASE,
)

def log_app_error(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    try:
        with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception:
        pass


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except FileNotFoundError:
        raise

    if not raw_text.strip():
        raise ValueError("config.json is empty.")

    try:
        config = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"config.json is invalid JSON: {exc}") from exc

    if not isinstance(config, dict):
        raise ValueError("config.json is not a JSON object.")

    return config


def resolve_music_dir():
    candidates = []
    app_root = APP_DIR
    if getattr(sys, "frozen", False):
        app_root = os.path.dirname(os.path.abspath(sys.executable))
        candidates.extend([
            os.path.join(app_root, "Assets", "Musics"),
            os.path.join(app_root, "Musics"),
            os.path.join(getattr(sys, "_MEIPASS", app_root), "Assets", "Musics"),
        ])
    candidates.extend([
        os.path.join(app_root, "Assets", "Musics"),
        os.path.join(app_root, "Musics"),
        os.path.join(os.path.dirname(app_root), "Assets", "Musics"),
    ])
    seen = set()
    for candidate in candidates:
        normalized = os.path.normpath(candidate)
        if normalized not in seen and os.path.isdir(normalized):
            seen.add(normalized)
            return normalized
    return os.path.join(app_root, "Assets", "Musics")


def _strip_unsupported(text):
    return "".join(ch for ch in text if ord(ch) <= 0xFFFF)

class ChatApp:
    def __init__(self, root):
        self.root = root
        self._set_window_icon()
        self.root.title("Phoebe")
        self.root.geometry("600x700")
        self.root.minsize(440, 420)

        default_config = {
            "model": "",
            "api_key": "",
            "api_base": "",
            "system_context": "",
            "error_message": "Err... :/",
        }

        try:
            self.config = load_config()
        except FileNotFoundError:
            log_app_error(f"Config file not found: {CONFIG_FILE}")
            self.config = default_config.copy()
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=2)
            except Exception as e:
                log_app_error(f"Could not create default config.json: {e}")
        except ValueError as e:
            log_app_error(str(e))
            self.config = default_config.copy()

        for required_key in ("api_key", "model", "api_base"):
            value = self.config.get(required_key)
            if value is None or str(value).strip() == "":
                log_app_error(f"config.json is missing or empty: {required_key}")
                self.config[required_key] = default_config.get(required_key, "")

        self.messages = [
            {"role": "system", "content": self.config.get("system_context", "You are a helpful assistant.")}
        ]
        self.image_refs = []
        self.gif_animations = [] 
        self._icon_cache = {}
        self.pending_attachment = None  
        self._preview_frames = []       
        self._preview_anim_job = None   
        self.current_conversation_path = None
        self._temp_render_files = []
        self._link_counter = 0
        ui_settings = load_ui_settings(SETTINGS_FILE)
        self.dark_mode = bool(ui_settings.get("dark_mode", False))
        self.online = None
        self._busy = False
        self._music_tracks = []
        self._music_index = -1
        self._music_enabled = False
        self._music_poll_job = None
        self._music_in_tray = False
        self._music_volume = 0.5
        self._music_tooltip = None
        self._music_tooltip_job = None
        self.emoji_picker = None

        self._build_ui()
        self._apply_theme()
        self._center_window()
        self._load_autosave()
        if not self._has_conversation_messages():
            self._show_empty_placeholder()
        self._start_music()
        self._tray_icon = self._setup_tray()
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        self._poll_connectivity()

    def _center_window(self):
        self.root.update_idletasks()
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        position_x = max(0, (screen_width - window_width) // 2)
        position_y = max(0, (screen_height - window_height) // 2)
        self.root.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")

    def _setup_tray(self):
        tray_image = Image.open(WINDOW_ICON_FILE).convert("RGBA")
        menu = pystray.Menu(
            pystray.MenuItem("Open", self._open_from_tray),
            pystray.MenuItem("Exit", self._exit_from_tray),
        )
        tray_icon = pystray.Icon("Phoebe", tray_image, "Phoebe", menu)
        threading.Thread(target=tray_icon.run, daemon=True).start()
        return tray_icon

    def _open_from_tray(self, icon=None, item=None):
        self.root.after(0, self._show_window)

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if self._music_enabled and self._music_in_tray:
            self._music_in_tray = False
            pygame.mixer.music.unpause()

    def _exit_from_tray(self, icon=None, item=None):
        self.root.after(0, self._on_close)

    def _on_window_close(self):
        if self._music_enabled:
            self._music_in_tray = True
            pygame.mixer.music.pause()
        self.root.withdraw()

    def _set_window_icon(self):
        try:
            if os.path.isfile(WINDOW_ICON_ICO_FILE):

                self.root.iconbitmap(WINDOW_ICON_ICO_FILE)
            icon_image = Image.open(WINDOW_ICON_FILE).convert("RGBA")
            self._window_icon = ImageTk.PhotoImage(icon_image)
            self.root.iconphoto(True, self._window_icon)
        except (FileNotFoundError, OSError, tk.TclError) as e:
            print(f"[WINDOW ICON ERROR] {e}")

    def _load_icon(self, filename):

        if filename in self._icon_cache:
            return self._icon_cache[filename]

        path = os.path.join(ICONS_DIR, filename)
        if not os.path.isfile(path):
            return None

        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((ICON_BTN_SIZE, ICON_BTN_SIZE))
            photo = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"[ICON LOAD ERROR] {filename}: {e}")
            return None

        self._icon_cache[filename] = photo
        return photo

    def _attach_icon_filename(self):
        return "attach_dark.png" if self.dark_mode else "attach_light.png"

    def _resolve_attach_icon(self):
        if self.dark_mode:
            icon = self._load_icon("dark_file_send.png")
            if icon is not None:
                return icon
        return self._load_icon("file_send.png")

    def _emoji_icon_filename(self):
        return "emoji_dark.png" if self.dark_mode else "emoji_light.png"

    def _resolve_emoji_icon(self):
        if self.dark_mode:
            icon = self._load_icon("dark_emoji.png")
            if icon is not None:
                return icon
        return self._load_icon("emoji.png")

    def _resolve_cancel_icon(self):
        if self.dark_mode:
            icon = self._load_icon("dark_cancel.png")
            if icon is not None:
                return icon
        return self._load_icon("cancel.png")

    def _make_icon_button(self, parent, icon, fallback_text, fallback_label, **kwargs):
        if icon is not None:
            btn = tk.Button(
                parent, image=icon, width=28, height=28,
                padx=3, pady=3, **kwargs,
            )
            btn.uses_icon = True
        else:
            btn = self._safe_button(parent, fallback_text, fallback_label, **kwargs)
            btn.uses_icon = False
        return btn


    def _safe_button(self, parent, preferred_text, fallback_text, **kwargs):
        try:
            btn = tk.Button(parent, text=preferred_text, **kwargs)
            btn.used_fallback = False
            return btn
        except tk.TclError:
            btn = tk.Button(parent, text=(fallback_text or ""), **kwargs)
            btn.used_fallback = True
            return btn

    def _build_ui(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save Consciousness", command=self._save_conversation)
        file_menu.add_command(label="Save Consciousness As...", command=self._save_conversation_as)
        file_menu.add_command(label="Import Consciousness", command=self._import_conversation)
        file_menu.add_separator()
        file_menu.add_command(label="Clear Chat", command=self._clear_memory)
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(
            label=self._dark_mode_menu_label(),
            command=self._on_toggle_dark_mode,
        )
        self.view_menu = view_menu
        self._dark_mode_menu_index = 0
        menubar.add_cascade(label="View", menu=view_menu)
        self.root.config(menu=menubar)
        self._ttk_style = ttk.Style(self.root)
        try:
            self._ttk_style.theme_use("clam")
        except tk.TclError:
            pass 

        self.chat_frame = tk.Frame(self.root)
        self.chat_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        self.chat_scrollbar = ttk.Scrollbar(
            self.chat_frame, orient="vertical", style="Themed.Vertical.TScrollbar"
        )
        self.chat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.chat_box = tk.Text(
            self.chat_frame, wrap=tk.WORD, state="normal", font=TEXT_FONT, borderwidth=0,
            highlightthickness=0, yscrollcommand=self.chat_scrollbar.set,
            exportselection=False, selectbackground="#4a90e2", selectforeground="white",
        )
        self.chat_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.chat_box.bind("<Button-3>", self._show_message_menu)
        self.chat_box.bind("<Button-1>", self._clear_message_highlight)
        self.chat_box.bind("<KeyPress>", self._block_chat_box_input)
        self.chat_scrollbar.configure(command=self.chat_box.yview)
        self.attach_frame = tk.Frame(self.root)

        self.attach_preview_box = tk.Frame(
            self.attach_frame, width=PREVIEW_THUMB_MAX, height=PREVIEW_THUMB_MAX
        )
        self.attach_preview_box.pack(side=tk.LEFT, padx=(8, 4), pady=(6, 4))
        self.attach_preview_box.pack_propagate(False) 

        self.attach_thumb_label = tk.Label(self.attach_preview_box)
        self.attach_thumb_label.place(relx=0, rely=0, relwidth=1, relheight=1)

        cancel_icon = self._resolve_cancel_icon()
        self.attach_remove_btn = self._make_icon_button(
            self.attach_preview_box, cancel_icon, "×", "Cancel",
            command=self._clear_attachment,
            font=("Segoe UI", 10, "bold"),
        )
        self.attach_remove_btn.place(
            relx=1.0, rely=0.0, anchor="ne", x=-2, y=2,
            width=ATTACH_REMOVE_BTN_SIZE, height=ATTACH_REMOVE_BTN_SIZE,
        )
        self.input_container = tk.Frame(self.root)
        self.input_container.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.entry = tk.Text(self.input_container, height=2, font=EMOJI_FONT, wrap=tk.WORD,
                              borderwidth=1, highlightthickness=1)
        self.entry.pack(fill=tk.X)
        self.entry.insert("1.0", ENTRY_PLACEHOLDER, "entry_placeholder")
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Shift-Return>", lambda e: None) 
        self.entry.bind("<FocusIn>", self._hide_entry_placeholder)
        self.entry.bind("<FocusOut>", self._show_entry_placeholder)
        self._show_entry_placeholder()
        self.entry.focus_set()

        button_bar = tk.Frame(self.input_container)
        button_bar.pack(fill=tk.X, pady=(4, 0))
        emoji_icon = self._resolve_emoji_icon()
        emoji_btn = self._make_icon_button(
            button_bar, emoji_icon, "😊", "Emoji",
            command=self._open_emoji_picker, font=EMOJI_FONT,
        )
        emoji_btn.pack(side=tk.LEFT)
        self.emoji_btn = emoji_btn
        emoji_btn.bind("<Button-3>", lambda e: self._try_native_emoji_picker())
        emoji_btn.bind("<Button-2>", lambda e: self._try_native_emoji_picker())
        attach_icon = self._resolve_attach_icon()
        attach_btn = self._make_icon_button(
            button_bar, attach_icon, "📎", "Attach",
            command=self._choose_attachment, font=EMOJI_FONT,
        )
        attach_btn.pack(side=tk.LEFT, padx=(4, 0))
        self.attach_btn = attach_btn

        self.status_var = tk.StringVar(value="Ready")

        self.send_btn = tk.Button(button_bar, text="Send", width=10, command=self._send)
        self.send_btn.pack(side=tk.RIGHT)
        self.entry.bind("<<Modified>>", self._on_entry_modified)
        self._update_send_button()

        lower_controls = tk.Frame(self.input_container)
        lower_controls.pack(fill=tk.X, pady=(2, 0))
        self.status_bar = tk.Label(lower_controls, textvariable=self.status_var, anchor="w")
        self.status_bar.pack(side=tk.LEFT)

        music_controls = tk.Frame(lower_controls)
        music_controls.pack(side=tk.RIGHT)
        self.volume_scale = tk.Scale(
            music_controls, from_=0, to=100, orient=tk.HORIZONTAL,
            showvalue=False, width=10, length=90, command=self._set_music_volume,
        )
        self.volume_scale.set(self._music_volume * 100)
        self.volume_scale_visible = False
        self.music_var = tk.StringVar(value="Music: unavailable")
        self.music_label = tk.Label(music_controls, textvariable=self.music_var, anchor="e")
        self.music_label.pack(side=tk.RIGHT, padx=(0, 8))
        self.music_label.bind("<Button-1>", lambda event: self._toggle_volume())
        self.music_label.bind("<Enter>", self._show_music_tooltip)
        self.music_label.bind("<Leave>", self._hide_music_tooltip)
        self.music_label.configure(cursor="hand2")

        self._themed_buttons = [
            emoji_btn, attach_btn,
            self.send_btn, self.attach_remove_btn,
        ]
        self._themed_frames = [
            self.input_container, button_bar, lower_controls, music_controls, self.attach_frame,
        ]

    def _dark_mode_menu_label(self):
        return "Light Mode" if self.dark_mode else "Dark Mode"

    def _start_music(self):
        music_dir = resolve_music_dir()
        if pygame is None or not os.path.isdir(music_dir):
            return

        self._music_tracks = [
            os.path.join(music_dir, filename)
            for filename in sorted(os.listdir(music_dir))
            if filename.lower().endswith(MUSIC_EXTENSIONS)
        ]
        random.shuffle(self._music_tracks)
        if not self._music_tracks:
            return

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 2048)
                pygame.mixer.init()
            self._music_enabled = True
            self._play_next_music()
        except Exception as e:
            print(f"[MUSIC ERROR] {e}")

    def _toggle_volume(self):
        if self.volume_scale_visible:
            self.volume_scale.pack_forget()
        else:
            self.volume_scale.pack(side=tk.LEFT, padx=(0, 4))
        self.volume_scale_visible = not self.volume_scale_visible

    def _show_music_tooltip(self, event):
        self._music_tooltip_job = self.root.after(
            500, lambda: self._create_music_tooltip(event)
        )

    def _create_music_tooltip(self, event):
        if self._music_tooltip is not None or not self.music_label.winfo_exists():
            return
        tooltip = tk.Toplevel(self.root)
        tooltip.wm_overrideredirect(True)
        tooltip.attributes("-topmost", True)
        tooltip.geometry(f"+{event.x_root + 8}+{event.y_root + 18}")
        tk.Label(
            tooltip, text="Adjust volume", bg="#ffffe0", fg="#000000",
            relief="solid", borderwidth=1, padx=4, pady=2,
        ).pack()
        self._music_tooltip = tooltip

    def _hide_music_tooltip(self, event=None):
        if self._music_tooltip_job is not None:
            self.root.after_cancel(self._music_tooltip_job)
            self._music_tooltip_job = None
        if self._music_tooltip is not None:
            self._music_tooltip.destroy()
            self._music_tooltip = None

    def _play_next_music(self):
        if not self._music_enabled or self._music_in_tray:
            return

        available_indices = range(len(self._music_tracks))
        if len(self._music_tracks) > 1 and self._music_index >= 0:
            available_indices = [
                index for index in available_indices if index != self._music_index
            ]
        self._music_index = random.choice(list(available_indices))
        track_path = self._music_tracks[self._music_index]
        try:
            pygame.mixer.music.load(track_path)
            pygame.mixer.music.set_volume(self._music_volume)
            pygame.mixer.music.play()
            self.music_var.set(f"Music: {os.path.splitext(os.path.basename(track_path))[0]}")
        except Exception as e:
            print(f"[MUSIC PLAYBACK ERROR] {e}")
            self.music_var.set("Music: unavailable")
        self._music_poll_job = self.root.after(1000, self._poll_music)

    def _set_music_volume(self, value):
        self._music_volume = float(value) / 100
        if self._music_enabled:
            pygame.mixer.music.set_volume(self._music_volume)

    def _poll_music(self):
        if self._music_enabled and not self._music_in_tray and not pygame.mixer.music.get_busy():
            self._play_next_music()
        elif self._music_enabled and not self._music_in_tray:
            self._music_poll_job = self.root.after(1000, self._poll_music)

    def _on_toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self.view_menu.entryconfigure(self._dark_mode_menu_index, label=self._dark_mode_menu_label())
        self._apply_theme()
        if self._has_conversation_messages():
            self._render_messages()
        save_ui_settings(SETTINGS_FILE, {"dark_mode": self.dark_mode})

    def _apply_theme(self):
        t = get_theme(self.dark_mode)

        self.root.configure(bg=t["root_bg"])

        self.chat_box.configure(
            bg=t["chat_bg"], fg=t["chat_fg"],
            insertbackground=t["entry_insert"],
            selectbackground=t["button_active_bg"],
        )
        self.chat_box.tag_config("user", foreground=t["user"])
        self.chat_box.tag_config(
            "user_name_glow", foreground=t["user_name_glow"],
            font=TEXT_FONT_BOLD,
        )
        self.chat_box.tag_config("assistant", foreground=t["assistant"])
        self.chat_box.tag_config(
            "assistant_name_glow", foreground=t["assistant_name_glow"],
            font=TEXT_FONT_BOLD,
        )
        self.chat_box.tag_config("system", foreground=t["system"])
        self.chat_box.tag_config(
            "right_clicked", background=t["button_active_bg"], foreground=t["chat_fg"]
        )
        self.chat_box.tag_raise("right_clicked")
        self.chat_box.tag_config(
            "empty_placeholder", foreground=t["status_fg"], font=CODE_FONT,
            justify="center", spacing1=2, spacing3=2,
        )
        self.chat_box.tag_config("bold", font=TEXT_FONT_BOLD)
        self.chat_box.tag_config("italic", font=TEXT_FONT_ITALIC)
        self.chat_box.tag_config("bold_italic", font=TEXT_FONT_BOLD_ITALIC)
        self.chat_box.tag_config("code", font=CODE_FONT, background=t["code_bg"], foreground=t["code_fg"],
                                lmargin1=2, lmargin2=2, rmargin=4)
        self.chat_box.tag_config(
            "codeblock", font=CODE_FONT_BLOCK, background=t["code_bg"], foreground=t["code_fg"],
            spacing1=6, spacing3=6, lmargin1=12, lmargin2=12, rmargin=10,
        )
        self.chat_box.tag_config(
            "hyperlink",
            foreground=t.get("hyperlink", "#8ab4f8" if self.dark_mode else "#1a73e8"),
            underline=True,
        )
        self.chat_box.tag_raise("hyperlink")

        self.chat_frame.configure(bg=t["root_bg"])
        self._ttk_style.configure(
            "Themed.Vertical.TScrollbar",
            background=t["scrollbar_bg"],
            troughcolor=t["scrollbar_trough"],
            bordercolor=t["root_bg"],
            arrowcolor=t["chat_fg"],
            darkcolor=t["scrollbar_bg"],
            lightcolor=t["scrollbar_bg"],
            relief="flat",
        )
        self._ttk_style.map(
            "Themed.Vertical.TScrollbar",
            background=[("active", t["scrollbar_active"]), ("pressed", t["scrollbar_active"])],
            arrowcolor=[("disabled", t["scrollbar_bg"])],
        )

        self.attach_frame.configure(bg=t["root_bg"])
        self.attach_preview_box.configure(bg=t["attach_box_bg"])
        self.attach_thumb_label.configure(bg=t["attach_box_bg"])
        self.attach_remove_btn.configure(
            bg=t["attach_remove_bg"], fg=t["attach_remove_fg"],
            activebackground=t["attach_remove_active_bg"],
            activeforeground=t["attach_remove_active_fg"],
        )
        if getattr(self.attach_remove_btn, "uses_icon", False):
            new_cancel_icon = self._resolve_cancel_icon()
            if new_cancel_icon:
                self.attach_remove_btn.configure(image=new_cancel_icon)

        self.entry.configure(
            bg=t["entry_bg"], fg=t["entry_fg"], insertbackground=t["entry_insert"],
            highlightbackground=t["button_bg"], highlightcolor=t["user"],
        )
        self.entry.tag_config("entry_placeholder", foreground=t["status_fg"])

        for frame in self._themed_frames:
            frame.configure(bg=t["root_bg"])

        for btn in self._themed_buttons:
            if btn is self.attach_remove_btn:
                continue 
            btn.configure(bg=t["button_bg"], activebackground=t["button_active_bg"])
            if not getattr(btn, "uses_icon", False):

                btn.configure(fg=t["button_fg"], activeforeground=t["button_fg"])
        if getattr(self.attach_btn, "uses_icon", False):
            new_icon = self._resolve_attach_icon()
            if new_icon:
                self.attach_btn.configure(image=new_icon)

        if getattr(self.emoji_btn, "uses_icon", False):
            new_emoji_icon = self._resolve_emoji_icon()
            if new_emoji_icon:
                self.emoji_btn.configure(image=new_emoji_icon)

        if self.emoji_picker is not None and self.emoji_picker.winfo_exists():
            emoji_list.apply_picker_theme(self.emoji_picker, t)

        self.status_bar.configure(bg=t["root_bg"])
        self.music_label.configure(bg=t["root_bg"], fg=t["status_fg"])
        self.volume_scale.configure(
            bg=t["root_bg"], fg=t["status_fg"],
            troughcolor=t["button_bg"], activebackground=t["button_active_bg"],
            highlightbackground=t["root_bg"],
        )
        self._refresh_status_label() 

    def _open_emoji_picker(self):
        if self.emoji_picker is not None and self.emoji_picker.winfo_exists():
            self.emoji_picker.lift()
            return

        self.entry.focus_set()
        self.emoji_picker = emoji_list.open_picker(
            self.root,
            get_theme(self.dark_mode),
            EMOJI_FONT,
            self._safe_button,
            self._insert_emoji,
        )
        self.emoji_picker.protocol(
            "WM_DELETE_WINDOW", lambda: self._close_emoji_picker(self.emoji_picker)
        )
        self.emoji_btn.configure(state=tk.DISABLED, relief=tk.SUNKEN)

    def _close_emoji_picker(self, picker_window):
        if picker_window is not self.emoji_picker:
            return
        if picker_window.winfo_exists():
            picker_window.destroy()
        self.emoji_picker = None
        self.emoji_btn.configure(state=tk.NORMAL, relief=tk.RAISED)

    def _try_native_emoji_picker(self):
        self.entry.focus_set()
        self._hide_entry_placeholder()
        emoji_list.trigger_native_picker()

    def _insert_emoji(self, emoji, picker_window):
        try:
            self._hide_entry_placeholder()
            self.entry.insert(tk.INSERT, emoji)
        except tk.TclError:
            pass 
        self.entry.focus_set()
        self._close_emoji_picker(picker_window)

    def _choose_attachment(self):
        path = filedialog.askopenfilename(title="Choose an image or GIF", filetypes=IMAGE_FILETYPES)
        if not path:
            return
        if not self._load_preview(path):
            return 
        self.pending_attachment = path
        self.attach_frame.pack(fill=tk.X, padx=8, before=self.input_container)
        self._update_send_button()

    def _load_preview(self, path):
        self._cancel_preview_animation()
        try:
            img = Image.open(path)
        except Exception as e:
            messagebox.showerror("Couldn't open file", str(e))
            return False

        is_gif = getattr(img, "is_animated", False) and img.format == "GIF"
        frames = []
        durations = []

        if is_gif:
            for frame in ImageSequence.Iterator(img):
                f = frame.convert("RGBA")
                f.thumbnail((PREVIEW_THUMB_MAX, PREVIEW_THUMB_MAX))
                frames.append(ImageTk.PhotoImage(f))
                durations.append(max(frame.info.get("duration", 100), GIF_FRAME_DELAY_MIN))
        else:
            f = img.convert("RGBA")
            f.thumbnail((PREVIEW_THUMB_MAX, PREVIEW_THUMB_MAX))
            frames.append(ImageTk.PhotoImage(f))

        self._preview_frames = frames 
        self.attach_thumb_label.configure(image=frames[0])

        if is_gif and len(frames) > 1:
            state = {"index": 0}

            def step():
                if not self.attach_thumb_label.winfo_exists():
                    return
                state["index"] = (state["index"] + 1) % len(frames)
                self.attach_thumb_label.configure(image=frames[state["index"]])
                self._preview_anim_job = self.attach_thumb_label.after(durations[state["index"]], step)

            self._preview_anim_job = self.attach_thumb_label.after(durations[0], step)

        return True

    def _cancel_preview_animation(self):
        if self._preview_anim_job is not None:
            try:
                self.attach_thumb_label.after_cancel(self._preview_anim_job)
            except Exception:
                pass
            self._preview_anim_job = None

    def _clear_attachment(self):
        self._cancel_preview_animation()
        self.pending_attachment = None
        self.attach_thumb_label.configure(image="")
        self._preview_frames = []
        self.attach_frame.pack_forget()
        self._update_send_button()

    def _message_tag(self, message_index):
        return f"message_{message_index}" if message_index is not None else None

    def _block_chat_box_input(self, event):
        if event.state & 0x4:
            return
        if event.keysym in {"Return", "BackSpace", "Delete", "Tab"}:
            return "break"
        if event.keysym in {"Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next"}:
            return
        return "break"

    def _highlight_message(self, message_index):
        message_tag = self._message_tag(message_index)
        self.chat_box.tag_remove("right_clicked", "1.0", tk.END)
        if message_tag:
            ranges = self.chat_box.tag_ranges(message_tag)
            if ranges:
                self.chat_box.tag_add("right_clicked", ranges[0], ranges[-1])

    def _clear_message_highlight(self, event=None):
        self.chat_box.tag_remove("right_clicked", "1.0", tk.END)

    def _show_message_menu(self, event):
        index = self.chat_box.index(f"@{event.x},{event.y}")
        message_tags = [tag for tag in self.chat_box.tag_names(index) if tag.startswith("message_")]
        if not message_tags:
            return

        message_index = int(message_tags[0].split("_", 1)[1])
        self._show_message_menu_for_index(event, message_index)

    def _message_text_for_copy(self, message_index):
        if not 0 <= message_index < len(self.messages):
            return ""

        message = self.messages[message_index]
        content = message.get("content", "")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts)

        return str(content)

    def _copy_message(self, message_index):
        text = self._message_text_for_copy(message_index)
        if not text:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
        except Exception:
            pass

    def _delete_message(self, message_index):
        if not 0 <= message_index < len(self.messages):
            return
        if self.messages[message_index].get("role") == "system":
            return
        if not messagebox.askyesno("Confirm", "Delete this message?"):
            return

        del self.messages[message_index]
        self._render_messages()
        self._autosave()

    def _append_text(self, text, tag=None, message_index=None):
        self._remove_empty_placeholder()
        self.chat_box.configure(state="normal")
        message_tag = self._message_tag(message_index)
        self._insert_markdown(text, tag, message_tag)
        self.chat_box.insert(tk.END, "\n\n", (message_tag,) if message_tag else ())
        self.chat_box.configure(state="disabled")
        self.chat_box.see(tk.END)

    def _append_label_line(self, label, tag=None, message_index=None):
        self._remove_empty_placeholder()
        self.chat_box.configure(state="normal")
        message_tag = self._message_tag(message_index)
        label_tag = f"{tag}_name_glow" if tag in ("user", "assistant") else tag
        label_tags = tuple(tg for tg in (label_tag, message_tag) if tg)
        self.chat_box.insert(tk.END, f"{label}:\n", label_tags)
        self.chat_box.configure(state="disabled")
        self.chat_box.see(tk.END)

    def _append_labeled_text(self, label, text, tag=None, message_index=None):
        self._remove_empty_placeholder()
        self.chat_box.configure(state="normal")
        message_tag = self._message_tag(message_index)
        label_tag = f"{tag}_name_glow" if tag in ("user", "assistant") else tag
        label_tags = tuple(tg for tg in (label_tag, message_tag) if tg)
        self.chat_box.insert(tk.END, f"{label}: ", label_tags)
        self._insert_markdown(text, tag, message_tag)
        self.chat_box.insert(tk.END, "\n\n", (message_tag,) if message_tag else ())
        self.chat_box.configure(state="disabled")
        self.chat_box.see(tk.END)

    def _copy_code_block(self, code_text):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(code_text)
            self.root.update()
        except Exception:
            pass

    def _insert_code_block_window(self, code_text, message_tag=None):
        t = get_theme(self.dark_mode)
        wrapper = tk.Frame(
            self.chat_box,
            bg=t["code_bg"],
            highlightbackground=t["chat_fg"],
            highlightthickness=1,
            bd=0,
            padx=8,
            pady=6,
        )

        header = tk.Frame(wrapper, bg=t["code_bg"], height=18)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        copy_btn = tk.Button(
            header,
            text="Copy",
            font=("Segoe UI", 8, "bold"),
            bg=t["button_bg"],
            fg=t["button_fg"],
            activebackground=t["button_active_bg"],
            activeforeground=t["button_fg"],
            relief="flat",
            padx=6,
            pady=0,
            bd=0,
            command=lambda: self._copy_code_block(code_text),
        )
        copy_btn.pack(side=tk.RIGHT, anchor="ne")

        code_widget = tk.Text(
            wrapper,
            height=max(1, code_text.count("\n") + 1),
            width=100,
            wrap=tk.WORD,
            bg=t["code_bg"],
            fg=t["code_fg"],
            font=CODE_FONT_BLOCK,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            exportselection=False,
            selectbackground=t["button_active_bg"],
            selectforeground=t["chat_fg"],
        )
        code_widget.insert("1.0", code_text)
        code_widget.configure(state="normal")
        code_widget.bind("<KeyPress>", lambda event: "break")
        code_widget.pack(fill=tk.BOTH, expand=True)

        window_start = self.chat_box.index(tk.END)
        self.chat_box.window_create(tk.END, window=wrapper)
        if message_tag:
            self.chat_box.tag_add(message_tag, window_start, self.chat_box.index(tk.END))
        self.chat_box.insert(tk.END, "\n", (message_tag,) if message_tag else ())

    def _insert_markdown(self, text, base_tag, message_tag=None):
        lines = text.split("\n")
        n = len(lines)
        in_code_block = False
        code_lines = []

        for i, line in enumerate(lines):
            if line.strip().startswith("```"):
                if in_code_block:
                    self._insert_code_block_window("\n".join(code_lines), message_tag)
                    if i != n - 1:
                        self.chat_box.insert(tk.END, "\n", (message_tag,) if message_tag else ())
                    code_lines = []
                    in_code_block = False
                else:
                    in_code_block = True
                continue

            if in_code_block:
                code_lines.append(line)
                continue

            self._insert_inline_markdown(line, base_tag, message_tag)
            if i != n - 1:
                self.chat_box.insert(tk.END, "\n", (message_tag,) if message_tag else ())

        if in_code_block and code_lines:
            self._insert_code_block_window("\n".join(code_lines), message_tag)

    def _insert_inline_markdown(self, line, base_tag, message_tag=None):
        pos = 0
        for m in MARKDOWN_TOKEN_RE.finditer(line):
            if m.start() > pos:
                self._insert_run(line[pos:m.start()], base_tag, None, message_tag)

            kind = m.lastgroup
            raw = m.group()
            if kind == "code":
                self._insert_run(raw[1:-1], base_tag, "code", message_tag)
            elif kind == "bolditalic":
                self._insert_run(raw[3:-3], base_tag, "bold_italic", message_tag)
            elif kind == "bold":
                self._insert_run(raw[2:-2], base_tag, "bold", message_tag)
            elif kind == "italic":
                self._insert_run(raw[1:-1], base_tag, "italic", message_tag)

            pos = m.end()

        if pos < len(line):
            self._insert_run(line[pos:], base_tag, None, message_tag)

    def _insert_run(self, text, base_tag, style_tag, message_tag=None):
        if not text:
            return
        tags = tuple(tg for tg in (base_tag, style_tag, message_tag) if tg)
        self._insert_text_with_links(text, tags)

    def _insert_text_with_links(self, text, tags):
        pos = 0
        for m in URL_RE.finditer(text):
            if m.start() > pos:
                self._insert_plain(text[pos:m.start()], tags)
            self._insert_link(m.group("url"), tags)
            pos = m.end()

        if pos < len(text):
            self._insert_plain(text[pos:], tags)

    def _insert_plain(self, text, tags):
        if not text:
            return
        try:
            self.chat_box.insert(tk.END, text, tags)
        except tk.TclError:
            self.chat_box.insert(tk.END, _strip_unsupported(text), tags)

    def _insert_link(self, url, tags):
        trailing = ""
        while url and url[-1] in ".,;:!?)]}\u201d\u2019'\"":
            trailing = url[-1] + trailing
            url = url[:-1]

        if not url:
            self._insert_plain(trailing, tags)
            return

        self._link_counter += 1
        link_tag = f"link_{self._link_counter}"
        full_tags = tuple(tags) + (link_tag, "hyperlink")

        try:
            self.chat_box.insert(tk.END, url, full_tags)
        except tk.TclError:
            self.chat_box.insert(tk.END, _strip_unsupported(url), full_tags)

        target = url if url.lower().startswith(("http://", "https://")) else f"http://{url}"
        self.chat_box.tag_bind(link_tag, "<Button-1>", lambda e, u=target: self._open_link(u))
        self.chat_box.tag_bind(link_tag, "<Enter>", lambda e: self.chat_box.configure(cursor="hand2"))
        self.chat_box.tag_bind(link_tag, "<Leave>", lambda e: self.chat_box.configure(cursor=""))

        if trailing:
            self._insert_plain(trailing, tags)

    def _open_link(self, url):
        try:
            webbrowser.open(url, new=2)
        except Exception as e:
            log_app_error(f"Could not open link {url}: {e}")

    def _append_image(self, path, tag=None, message_index=None):
        self._remove_empty_placeholder()
        try:
            img = Image.open(path)
        except Exception as e:
            self._append_text(f"[Couldn't load image: {e}]", "system")
            return

        is_gif = getattr(img, "is_animated", False) and img.format == "GIF"

        self.chat_box.configure(state="normal")

        t = get_theme(self.dark_mode)
        label = tk.Label(self.chat_box, bg=t["chat_bg"])
        message_tag = self._message_tag(message_index)
        window_start = self.chat_box.index(tk.END)
        self.chat_box.window_create(tk.END, window=label)
        if message_tag:
            self.chat_box.tag_add(message_tag, window_start, self.chat_box.index(tk.END))
        self.chat_box.insert(tk.END, "\n\n", (message_tag,) if message_tag else ())
        if message_index is not None:
            label.bind("<Button-1>", self._clear_message_highlight)
            label.bind(
                "<Button-3>",
                lambda event, index=message_index: self._show_message_menu_for_index(event, index),
            )
        self.chat_box.configure(state="disabled")
        self.chat_box.see(tk.END)

        if is_gif:
            self._animate_gif(label, img)
        else:
            thumb = img.convert("RGBA")
            thumb.thumbnail((THUMB_MAX, THUMB_MAX))
            photo = ImageTk.PhotoImage(thumb)
            self.image_refs.append(photo)
            label.configure(image=photo)

    def _show_message_menu_for_index(self, event, message_index):
        self._highlight_message(message_index)
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Copy", command=lambda: self._copy_message(message_index))
        menu.add_command(label="Delete", command=lambda: self._delete_message(message_index))
        menu.tk_popup(event.x_root, event.y_root)

    def _animate_gif(self, label, img):
        frames = []
        durations = []
        for frame in ImageSequence.Iterator(img):
            f = frame.convert("RGBA")
            f.thumbnail((THUMB_MAX, THUMB_MAX))
            photo = ImageTk.PhotoImage(f)
            self.image_refs.append(photo)  # prevent garbage collection
            frames.append(photo)
            durations.append(max(frame.info.get("duration", 100), GIF_FRAME_DELAY_MIN))

        if not frames:
            return

        state = {"index": 0}
        label.configure(image=frames[0])

        def step():
            if not label.winfo_exists():
                return 
            state["index"] = (state["index"] + 1) % len(frames)
            label.configure(image=frames[state["index"]])
            label.after(durations[state["index"]], step)

        label.after(durations[0], step)

    def _entry_has_placeholder(self):
        return bool(self.entry.tag_ranges("entry_placeholder"))

    def _hide_entry_placeholder(self, event=None):
        if self._entry_has_placeholder():
            self.entry.delete("1.0", tk.END)
        self._update_send_button()

    def _show_entry_placeholder(self, event=None):
        if not self.entry.get("1.0", tk.END).strip():
            self.entry.delete("1.0", tk.END)
            self.entry.insert("1.0", ENTRY_PLACEHOLDER, "entry_placeholder")
        self._update_send_button()

    def _on_entry_modified(self, event=None):
        self.entry.edit_modified(False)
        self._update_send_button()

    def _update_send_button(self):
        if not hasattr(self, "send_btn"):
            return
        has_text = not self._entry_has_placeholder() and bool(
            self.entry.get("1.0", tk.END).strip()
        )
        can_send = has_text or self.pending_attachment is not None
        state = "disabled" if self._busy or not can_send else "normal"
        self.send_btn.configure(state=state)

    def _on_enter(self, event):
        if event.state & 0x0001: 
            return
        if self._entry_has_placeholder():
            self._hide_entry_placeholder()
        self._send()
        return "break"

    def _clear_memory(self):
        if not messagebox.askyesno("Clear Chat", "Are you sure?"):
            return
        self.messages = self.messages[:1] 
        self.chat_box.configure(state="normal")
        self.chat_box.delete("1.0", tk.END)
        self.chat_box.configure(state="disabled")
        self.image_refs.clear()
        self.current_conversation_path = None
        self._show_empty_placeholder()
        self._autosave()

    def _has_conversation_messages(self):
        return any(message.get("role") in ("user", "assistant") for message in self.messages)

    def _remove_empty_placeholder(self):
        if not self.chat_box.tag_ranges("empty_placeholder"):
            return
        self.chat_box.configure(state="normal")
        self.chat_box.delete("1.0", tk.END)
        self.chat_box.configure(state="disabled")

    def _show_empty_placeholder(self):
        self.chat_box.configure(state="normal")
        self.chat_box.delete("1.0", tk.END)
        self.chat_box.insert("1.0", EMPTY_CHAT_ART, "empty_placeholder")
        self.chat_box.configure(state="disabled")

    def _set_busy(self, busy):
        self._busy = busy
        self._update_send_button()
        state = "disabled" if busy else "normal"
        self.entry.configure(state=state)
        self._refresh_status_label()

    def _refresh_status_label(self):
        t = get_theme(self.dark_mode)
        if self._busy:
            text, color = "Thinking...", t["status_fg"]
        elif self.online is None:
            text, color = "Checking connection...", t["status_fg"]
        elif self.online:
            text, color = "Online", t["assistant"]
        else:
            text, color = "Offline", t["attach_remove_active_bg"]
        self.status_var.set(text)
        self.status_bar.configure(fg=color)

    def _get_api_host_port(self):
        try:
            parsed = urlparse(self.config.get("api_base", ""))
            if parsed.hostname:
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
                return parsed.hostname, port
        except Exception:
            pass
        return None, None

    def _check_connection(self):
        host, port = self._get_api_host_port()
        if not host:
            host, port = "8.8.8.8", 53 
        try:
            with socket.create_connection((host, port), timeout=CONNECTIVITY_CHECK_TIMEOUT_S):
                return True
        except OSError:
            return False

    def _poll_connectivity(self):
        threading.Thread(target=self._connectivity_check_worker, daemon=True).start()
        self.root.after(CONNECTIVITY_CHECK_INTERVAL_MS, self._poll_connectivity)

    def _connectivity_check_worker(self):
        online = self._check_connection()
        self.root.after(0, self._on_connectivity_result, online)

    def _on_connectivity_result(self, online):
        self.online = online
        self._refresh_status_label()

    def _encode_image_data_url(self, path):
        mime, _ = mimetypes.guess_type(path)
        mime = mime or "image/png"
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return f"data:{mime};base64,{b64}"

    def _send(self):
        if self._entry_has_placeholder():
            self._hide_entry_placeholder()

        text = self.entry.get("1.0", tk.END).strip()
        attachment = self.pending_attachment

        if not text and not attachment:
            return

        self.entry.delete("1.0", tk.END)
        message_index = len(self.messages)

        if text:
            self._append_labeled_text("You", text, "user", message_index)
        elif attachment:
            self._append_label_line("You", "user", message_index)
        if attachment:
            self._append_image(attachment, "user", message_index)

      
        if attachment:
            try:
                data_url = self._encode_image_data_url(attachment)
            except Exception as e:
                self._append_text(f"[Couldn't attach image: {e}]", "system")
                data_url = None

            content = []
            if text:
                content.append({"type": "text", "text": text})
            if data_url:
                content.append({"type": "image_url", "image_url": {"url": data_url}})
            self.messages.append({"role": "user", "content": content})
        else:
            self.messages.append({"role": "user", "content": text})

        self._clear_attachment()
        self._set_busy(True)
        self._autosave()
        threading.Thread(target=self._call_api, daemon=True).start()

    def _call_api(self):
        try:
            api_key = str(self.config.get("api_key", "")).strip()
            model = str(self.config.get("model", "")).strip()
            api_base = str(self.config.get("api_base", "")).strip()

            if not api_key:
                raise ValueError("API key is empty.")
            if not model:
                raise ValueError("Model is empty.")
            if not api_base:
                raise ValueError("API base URL is empty.")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": self.messages,
            }
            url = f"{api_base.rstrip('/')}/chat/completions"
            resp = requests.post(url, headers=headers, json=payload, timeout=60)

            if resp.status_code != 200:
                error_detail = (resp.text or resp.reason or "Unknown API error").strip()
                print(f"[API ERROR] {resp.status_code}: {error_detail}")
                log_app_error(f"API error {resp.status_code}: {error_detail}")
                reply = self.config.get("error_message", "API error, try again later.")
            else:
                data = resp.json()
                if isinstance(data, dict) and "error" in data and data["error"]:
                    raise ValueError(str(data["error"]))

                if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                    image_data = data["data"][0]
                    if isinstance(image_data, dict):
                        b64_data = image_data.get("b64_json") or image_data.get("image")
                        if b64_data:
                            reply = [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_data}"}}]
                        else:
                            url = image_data.get("url")
                            reply = [{"type": "image_url", "image_url": {"url": url}}] if url else ""
                        self.messages.append({"role": "assistant", "content": reply})
                        return

                if not isinstance(data, dict) or not data.get("choices"):
                    raise ValueError("Daily limit reached, Check back after 24 hours.")

                message = data["choices"][0].get("message", {})
                reply = self._normalize_message_content(message.get("content", ""))
                self.messages.append({"role": "assistant", "content": reply})

        except Exception as e:
            message = str(e)
            print(f"[ERROR] {message}")
            log_app_error(f"Runtime error: {message}")
            reply = self.config.get("error_message", "Internal error occurred.")

        self.root.after(0, self._show_reply, reply)

    def _show_reply(self, reply):
        message_index = len(self.messages) - 1
        self._append_message_content("Phoebe", reply, "assistant", message_index)
        self._set_busy(False)
        self._autosave()


    def _conversation_payload(self):
        return {
            "format": "alice-conversation",
            "version": ALICE_FORMAT_VERSION,
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "model": self.config.get("model"),
            "messages": self.messages,
        }

    @staticmethod
    def _xor_encrypt_json(payload, password):
        plaintext = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        key = hashlib.sha256(password.encode("utf-8")).digest()
        encrypted = bytes(
            value ^ key[index % len(key)]
            for index, value in enumerate(plaintext)
        )
        return {
            "format": "alice-encrypted",
            "version": ALICE_FORMAT_VERSION,
            "encryption": ALICE_ENCRYPTION,
            "ciphertext": base64.b64encode(encrypted).decode("ascii"),
        }

    @staticmethod
    def _xor_decrypt_json(envelope, password):
        if not isinstance(envelope, dict) or envelope.get("format") != "alice-encrypted":
            raise ValueError("Error. File corrupted.")
        if envelope.get("encryption") != ALICE_ENCRYPTION:
            raise ValueError("Error. File corrupted.")
        try:
            encrypted = base64.b64decode(envelope["ciphertext"], validate=True)
        except (KeyError, ValueError, binascii.Error) as error:
            raise ValueError("The encrypted file is damaged.") from error
        key = hashlib.sha256(password.encode("utf-8")).digest()
        plaintext = bytes(
            value ^ key[index % len(key)]
            for index, value in enumerate(encrypted)
        )
        try:
            payload = json.loads(plaintext.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Wrong password or damaged file.") from error
        if not isinstance(payload, dict) or payload.get("format") != "alice-conversation":
            raise ValueError("Wrong password or invalid mind file.")
        return payload

    def _write_alice_file(self, path):
        envelope = self._xor_encrypt_json(self._conversation_payload(), ALICE_NEKO)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(envelope, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)

    def _autosave(self):
        try:
            self._write_alice_file(AUTOSAVE_FILE)
        except Exception as e:
            print(f"[AUTOSAVE ERROR] {e}")

    def _load_autosave(self):
        if not os.path.exists(AUTOSAVE_FILE):
            return
        try:
            with open(AUTOSAVE_FILE, "r", encoding="utf-8") as f:
                payload = self._xor_decrypt_json(json.load(f), ALICE_NEKO)
            messages = payload.get("messages")
            if not messages:
                return
            self.messages = messages
            self._render_messages()
            self.status_var.set("Restored previous concisousness")
        except Exception as e:
            print(f"[AUTOSAVE LOAD ERROR] {e}")

    def _save_conversation(self):
        if self.current_conversation_path:
            try:
                self._write_alice_file(self.current_conversation_path)
                self.status_var.set(f"Saved to {os.path.basename(self.current_conversation_path)}")
            except Exception as e:
                messagebox.showerror("Couldn't save concsiousness", str(e))
        else:
            self._save_conversation_as()

    def _save_conversation_as(self):
        path = filedialog.asksaveasfilename(
            title="Save Concsious",
            defaultextension=".phbe",
            filetypes=ALICE_FILETYPES,
        )
        if not path:
            return
        try:
            self._write_alice_file(path)
            self.current_conversation_path = path
            self.status_var.set(f"Saved to {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Couldn't save concsiousness", str(e))

    def _import_conversation(self):
        path = filedialog.askopenfilename(
            title="Import Conversation",
            filetypes=ALICE_FILETYPES,
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = self._xor_decrypt_json(json.load(f), ALICE_NEKO)
        except Exception as e:
            messagebox.showerror("Couldn't read file", str(e))
            return

        messages = payload.get("messages") if isinstance(payload, dict) else None
        if not isinstance(messages, list) or not messages:
            messagebox.showerror(
                "Invalid conscious file",
                "This doesn't look like a valid .phbe conscious file.",
            )
            return

        if not messages or messages[0].get("role") != "system":
            messages = [
                {"role": "system", "content": self.config.get("system_context", "You are a helpful assistant.")}
            ] + messages

        self.messages = messages
        self.current_conversation_path = path
        self._render_messages()
        self.status_var.set(f"Imported {os.path.basename(path)}")
        self._autosave()

    def _render_messages(self):
        self._cleanup_temp_render_files()
        self.chat_box.configure(state="normal")
        self.chat_box.delete("1.0", tk.END)
        self.chat_box.configure(state="disabled")
        self.image_refs.clear()

        for message_index, msg in enumerate(self.messages):
            role = msg.get("role")
            content = msg.get("content")
            if role == "system":
                continue

            tag = "user" if role == "user" else "assistant"
            label = "You" if role == "user" else "Phoebe"
            self._append_message_content(label, content, tag, message_index)

        if not self._has_conversation_messages():
            self._show_empty_placeholder()

    def _image_url_to_temp_file(self, url):
        if not isinstance(url, str) or not url.strip():
            return None

        if url.startswith("data:"):
            return self._data_url_to_temp_file(url)

        if not url.startswith(("http://", "https://")):
            return None

        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "image/png")
            mime = content_type.split(";", 1)[0].strip() or "image/png"
            ext = mimetypes.guess_extension(mime) or ".png"
            fd, tmp_path = tempfile.mkstemp(suffix=ext, prefix="alice_img_")
            with os.fdopen(fd, "wb") as f:
                f.write(response.content)
            self._temp_render_files.append(tmp_path)
            return tmp_path
        except Exception as e:
            print(f"[IMAGE FETCH ERROR] {e}")
            return None

    def _data_url_to_temp_file(self, data_url):
        try:
            header, b64data = data_url.split(",", 1)
            mime = header.split(";")[0].replace("data:", "") or "image/png"
            ext = mimetypes.guess_extension(mime) or ".png"
            raw = base64.b64decode(b64data)
            fd, tmp_path = tempfile.mkstemp(suffix=ext, prefix="alice_img_")
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
            self._temp_render_files.append(tmp_path)
            return tmp_path
        except Exception as e:
            print(f"[IMAGE DECODE ERROR] {e}")
            return None

    def _normalize_message_content(self, content):
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            if content is None:
                return ""
            return str(content)

        text_parts = []
        image_urls = []

        for part in content:
            if not isinstance(part, dict):
                continue

            part_type = part.get("type")
            if part_type in ("text", "input_text", "output_text"):
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text)
            elif part_type == "image_url":
                image_url = part.get("image_url")
                if isinstance(image_url, dict):
                    url = image_url.get("url")
                else:
                    url = image_url
                if isinstance(url, str) and url.strip():
                    image_urls.append(url)
            elif part_type == "image":
                image_value = part.get("image") or part.get("b64_json")
                if isinstance(image_value, str) and image_value.strip():
                    image_urls.append(f"data:image/png;base64,{image_value}")

        normalized = []
        if text_parts:
            normalized.append({"type": "text", "text": " ".join(text_parts)})
        for image_url in image_urls:
            normalized.append({"type": "image_url", "image_url": {"url": image_url}})

        return normalized if normalized else ""

    def _append_message_content(self, label, content, tag=None, message_index=None):
        if isinstance(content, str):
            if content.strip():
                self._append_labeled_text(label, content, tag, message_index)
            return

        if not isinstance(content, list):
            text = str(content)
            if text.strip():
                self._append_labeled_text(label, text, tag, message_index)
            return

        text_parts = []
        image_urls = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") in ("text", "input_text", "output_text"):
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text)
            elif part.get("type") == "image_url":
                image_url = part.get("image_url", {})
                if isinstance(image_url, dict):
                    url = image_url.get("url")
                else:
                    url = image_url
                if isinstance(url, str) and url.strip():
                    image_urls.append(url)

        if text_parts:
            self._append_labeled_text(label, " ".join(text_parts), tag, message_index)
        elif image_urls:
            self._append_label_line(label, tag, message_index)

        for image_url in image_urls:
            tmp_path = self._image_url_to_temp_file(image_url)
            if tmp_path:
                self._append_image(tmp_path, tag, message_index)

    def _cleanup_temp_render_files(self):
        for p in self._temp_render_files:
            try:
                os.remove(p)
            except Exception:
                pass
        self._temp_render_files = []

    def _on_close(self):
        self._autosave()
        self._cleanup_temp_render_files()
        if self._music_enabled:
            if self._music_poll_job is not None:
                self.root.after_cancel(self._music_poll_job)
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        if self._tray_icon is not None:
            self._tray_icon.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop()