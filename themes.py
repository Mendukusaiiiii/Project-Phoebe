import json
import os

THEMES = {
    "light": {
        "root_bg": "#f3f3f3",
        "chat_bg": "#ffffff",
        "chat_fg": "#1a1a1a",
        "entry_bg": "#ffffff",
        "entry_fg": "#1a1a1a",
        "entry_insert": "#1a1a1a",
        "button_bg": "#e6e6e6",
        "button_fg": "#1a1a1a",
        "button_active_bg": "#d9d9d9",
        "scrollbar_bg": "#e6e6e6",
        "scrollbar_trough": "#f3f3f3",
        "scrollbar_active": "#c9c9c9",
        "status_fg": "#666666",
        "attach_box_bg": "#2b2b2b",
        "attach_remove_bg": "#e6e6e6",
        "attach_remove_fg": "#1a1a1a",
        "attach_remove_active_bg": "#e04343",
        "attach_remove_active_fg": "#ffffff",
        "code_bg": "#f0f0f0",
        "code_fg": "#c7254e",
        "user": "#006A7C",
        "user_name_glow": "#007D93",
        "assistant": "#0f7b0f",
        "assistant_name_glow": "#038f07",
        "system": "#888888",
    },
    "dark": {
        "root_bg": "#1e1e1e",
        "chat_bg": "#181818",
        "chat_fg": "#e6e6e6",
        "entry_bg": "#2a2a2a",
        "entry_fg": "#e6e6e6",
        "entry_insert": "#e6e6e6",
        "button_bg": "#333333",
        "button_fg": "#e6e6e6",
        "button_active_bg": "#3f3f3f",
        "scrollbar_bg": "#3a3a3a",
        "scrollbar_trough": "#1e1e1e",
        "scrollbar_active": "#4f4f4f",
        "status_fg": "#9a9a9a",
        "attach_box_bg": "#111111",
        "attach_remove_bg": "#4a4a4a",
        "attach_remove_fg": "#e6e6e6",
        "attach_remove_active_bg": "#e04343",
        "attach_remove_active_fg": "#ffffff",
        "code_bg": "#262626",
        "code_fg": "#e0a458",
        "user": "#01B7D7",
        "user_name_glow": "#00AECD",
        "assistant": "#37d447",
        "assistant_name_glow": "#86ed8e",
        "system": "#9a9a9a",
    },
}


def get_theme(dark_mode):
    return THEMES["dark" if dark_mode else "light"]

def load_ui_settings(settings_file):
    try:
        with open(settings_file, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_ui_settings(settings_file, settings):
    try:
        tmp_path = settings_file + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(settings, f)
        os.replace(tmp_path, settings_file)
    except Exception as e:
        print(f"[UI SETTINGS SAVE ERROR] {e}")
