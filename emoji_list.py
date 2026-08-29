import ctypes
import platform
import subprocess
import tkinter as tk


COMMON_EMOJIS = [
    "😀", "😁", "😂", "🤣", "🙂", "🙃", "😉", "😊", "😇", "🥰",
    "😍", "🤩", "😘", "😗", "😎", "🤔", "🫡", "😐", "🙄", "😏",
    "😢", "😭", "😤", "😡", "🤬", "😱", "😳", "🥳", "😴", "🤗",
    "🤭", "🤫", "🤥", "😬", "🤓", "🧐", "😇", "🤠", "👻", "💀",
    "👍", "👎", "👌", "✌", "🤞", "🤟", "🤘", "👏", "🙌", "🙏",
    "💪", "👋", "🫶", "👀", "👂", "👃", "🧠", "💅", "💖", "💔",
    "🔥", "✨", "🌟", "⭐", "🌈", "☀", "🌙", "⚡", "❄", "☁",
    "🌸", "🌹", "🌻", "🍀", "🌲", "🌴", "🌵", "🍎", "🍕", "🍔",
    "🍟", "🌭", "🍩", "🍪", "🍰", "🍿", "☕", "🍺", "🍷", "🎂",
    "⚽", "🏀", "🏆", "🎮", "🎵", "🎶", "🎨", "🎁", "🎉", "🎈",
    "🚀", "✈", "🚗", "🚲", "🏠", "💡", "📱", "💻", "⌚", "📌",
    "✅", "❌", "❗", "❓", "‼", "⁉", "💯", "➕", "➖", "✔",
    "©", "®", "™", "☑", "☮", "☯", "♻", "⚠", "🔒", "🔑",
]


def trigger_native_picker():
    system = platform.system()
    if system == "Windows":
        return _trigger_windows_picker()
    if system == "Darwin":
        return _trigger_macos_picker()
    return False


def _trigger_windows_picker():
    try:
        user32 = ctypes.windll.user32
        vk_lwin = 0x5B
        vk_oem_period = 0xBE
        keyup = 0x0002
        user32.keybd_event(vk_lwin, 0, 0, 0)
        user32.keybd_event(vk_oem_period, 0, 0, 0)
        user32.keybd_event(vk_oem_period, 0, keyup, 0)
        user32.keybd_event(vk_lwin, 0, keyup, 0)
        return True
    except Exception:
        return False


def _trigger_macos_picker():
    try:
        subprocess.Popen([
            "osascript", "-e",
            "tell application \"System Events\" to key code 49 using {control down, command down}",
        ])
        return True
    except Exception:
        return False


def open_picker(parent, theme, emoji_font, make_button, insert_callback):
    picker = tk.Toplevel(parent)
    picker.title("Emoji")
    picker.resizable(False, False)
    picker._emoji_buttons = []
    picker._emoji_notice = None

    cols = 10
    any_rendered = False
    for index, emoji in enumerate(COMMON_EMOJIS):
        button = make_button(
            picker, emoji, "",
            font=emoji_font, width=3,
            bg=theme["button_bg"], fg=theme["button_fg"],
            activebackground=theme["button_active_bg"],
            command=lambda value=emoji: insert_callback(value, picker),
        )
        if not button.used_fallback:
            any_rendered = True
        picker._emoji_buttons.append(button)
        button.grid(row=index // cols, column=index % cols, padx=1, pady=1)

    if not any_rendered:
        notice = tk.Label(
            picker,
            text="Emoji aren't supported by this Python/Tk installation.\n"
                 "Try updating Python, or type emoji from your OS's own\n"
                 "emoji picker (Win+. on Windows, Ctrl+Cmd+Space on macOS).",
            justify="left", fg=theme["status_fg"], bg=theme["root_bg"],
        )
        picker._emoji_notice = notice
        notice.grid(
            row=(len(COMMON_EMOJIS) // cols) + 1,
            column=0,
            columnspan=cols,
            pady=(6, 2),
            padx=4,
        )

    apply_picker_theme(picker, theme)
    return picker


def apply_picker_theme(picker, theme):
    picker.configure(bg=theme["root_bg"])
    for button in picker._emoji_buttons:
        button.configure(
            bg=theme["button_bg"],
            fg=theme["button_fg"],
            activebackground=theme["button_active_bg"],
        )
    if picker._emoji_notice is not None:
        picker._emoji_notice.configure(
            bg=theme["root_bg"], fg=theme["status_fg"]
        )
