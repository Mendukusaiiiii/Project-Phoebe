import json
import os
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

APP_DIR = os.path.dirname(
    os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
)
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
RESET_MARKER_FILE = os.path.join(APP_DIR, "delete_me_to_reset_personality.phbe")
WINDOW_ICON_FILE = os.path.join(APP_DIR, "assets", "images", "icon.ico")
WINDOW_ICON_ICO_FILE = os.path.join(APP_DIR, "icon.ico")

DEFAULT_CONFIG = {
    "model": "",
    "api_key": "",
    "api_base": "",
    "system_context": "",
    "error_message": "",
    "voice_id": "",
    "voice_volume": 1.0,
    "core_ai_color": "#FA2A55",
}


def load_config():
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(DEFAULT_CONFIG)
            merged.update(data)
            return merged
        except (json.JSONDecodeError, OSError) as exc:
            messagebox.showwarning(
                "Config Editor",
                f"Couldn't read existing config.json ({exc}).\nStarting from defaults.",
            )
    return dict(DEFAULT_CONFIG)


class ConfigEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Phoebe Config Editor")
        self.geometry("820x680")
        self.minsize(820, 680)
        self.configure(bg="#1e1e24")

        self.data = load_config()
        self.vars = {}
        self.color_value = tk.StringVar(value=self.data.get("core_ai_color") or "#00FFFF")
        self._autosave_job = None

        self.committed_context = self.data.get("system_context", "")
        self.reset_required = False
        self._suspend_autosave = True 

        self._build_style()
        self._build_ui()
        self._set_window_icon()
        self._suspend_autosave = False
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_window_icon(self):
        try:
            if os.path.isfile(WINDOW_ICON_ICO_FILE):
                self.iconbitmap(WINDOW_ICON_ICO_FILE)
            if Image is not None and os.path.isfile(WINDOW_ICON_FILE):
                icon_image = Image.open(WINDOW_ICON_FILE).convert("RGBA")
                self._window_icon = ImageTk.PhotoImage(icon_image)
                self.iconphoto(True, self._window_icon)
        except (FileNotFoundError, OSError, tk.TclError) as e:
            print(f"[WINDOW ICON ERROR] {e}")

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        bg = "#17141A"
        fg = "#f2f2f5"
        accent = "#FA2A55"
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg, font=("Verdana", 10))
        style.configure("Header.TLabel", background=bg, foreground=accent, font=("Cascadia Mono", 16, "bold"))
        style.configure("Sub.TLabel", background=bg, foreground="#a5a5b0", font=("Verdana", 9))
        style.configure("Warn.TLabel", background=bg, foreground="#ffb347", font=("Verdana", 9, "bold"))
        style.configure("TEntry", fieldbackground="#2a2a33", foreground=fg)
        style.configure("TButton", font=("Verdana", 10, "bold"), padding=0.4)
        style.configure(
            "Accent.TButton",
            background=accent,
            foreground="white",
        )
        style.map("Accent.TButton", background=[("active", "#c81f42")])

    def _build_ui(self):
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Phoebe Config Editor", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text=f"Editing: {CONFIG_FILE}",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(0, 15))

        form = ttk.Frame(outer)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        row = 0
        row = self._add_entry(form, row, "model", "Model")
        row = self._add_entry(form, row, "api_key", "API Key", show="•")
        row = self._add_entry(form, row, "api_base", "API Base URL")
        row = self._add_text(form, row, "system_context", "System Context", height=6)
        row = self._add_entry(form, row, "error_message", "Error Message")
        row = self._add_entry(form, row, "voice_id", "Voice ID")
        row = self._add_slider(form, row, "voice_volume", "Voice Volume")
        row = self._add_color(form, row, "core_ai_color", "Core AI Color")

    
        btn_bar = ttk.Frame(outer)
        btn_bar.pack(fill="x", pady=(10, 0))
        ttk.Button(btn_bar, text="Reload", command=self.reload_config).pack(side="left")
        self.reset_btn = ttk.Button(
            btn_bar, text="Reset AI", style="Accent.TButton", command=self.save_config
        )
        self.reset_btn.pack(side="right")

        self.status_var = tk.StringVar(value="Changes save automatically.")
        ttk.Label(outer, textvariable=self.status_var, style="Sub.TLabel").pack(
            anchor="w", pady=(8, 0)
        )

        self.warn_var = tk.StringVar(value="")
        ttk.Label(outer, textvariable=self.warn_var, style="Warn.TLabel").pack(
            anchor="w", pady=(4, 0)
        )

    def _add_entry(self, parent, row, key, label, show=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6, padx=(0, 10))
        var = tk.StringVar(value=str(self.data.get(key, "")))
        var.trace_add("write", self._schedule_autosave)
        entry = ttk.Entry(parent, textvariable=var, show=show or "")
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        self.vars[key] = ("entry", var)
        return row + 1

    def _add_text(self, parent, row, key, label, height=4):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="nw", pady=6, padx=(0, 10))
        box = tk.Text(
            parent,
            height=height,
            wrap="word",
            bg="#231F29",
            fg="#f2f2f5",
            insertbackground="#f2f2f5",
            relief="flat",
            padx=6,
            pady=6,
        )
        box.insert("1.0", str(self.data.get(key, "")))
        box.grid(row=row, column=1, sticky="ew", pady=6)
        box.bind("<KeyRelease>", self._schedule_autosave)
        box.bind("<<Paste>>", lambda _e: self.after_idle(self._schedule_autosave))
        box.bind("<<Cut>>", lambda _e: self.after_idle(self._schedule_autosave))
        self.vars[key] = ("text", box)
        return row + 1

    def _add_slider(self, parent, row, key, label):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6, padx=(0, 10))
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=1, sticky="ew", pady=6)
        frame.columnconfigure(0, weight=1)
        var = tk.DoubleVar(value=float(self.data.get(key, 1.0)))
        value_lbl = ttk.Label(frame, text=f"{var.get():.2f}", width=5)

        def on_change(_evt=None):
            value_lbl.config(text=f"{var.get():.2f}")
            self._schedule_autosave()

        slider = ttk.Scale(frame, from_=0.0, to=1.0, variable=var, command=on_change)
        slider.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        value_lbl.grid(row=0, column=1)
        self.vars[key] = ("float", var)
        return row + 1

    def _add_color(self, parent, row, key, label):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6, padx=(0, 10))
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=1, sticky="ew", pady=6)
        swatch = tk.Label(frame, width=4, bg=self.color_value.get(), relief="flat")
        swatch.pack(side="left", padx=(0, 10))
        entry = ttk.Entry(frame, textvariable=self.color_value, width=12)
        entry.pack(side="left", padx=(0, 10))

        def pick_color():
            _rgb, hexval = colorchooser.askcolor(color=self.color_value.get() or "#FA2A55")
            if hexval:
                self.color_value.set(hexval)
                swatch.config(bg=hexval)

        def on_type(*_a):
            val = self.color_value.get()
            try:
                swatch.config(bg=val)
            except tk.TclError:
                pass
            self._schedule_autosave()

        self.color_value.trace_add("write", on_type)
        ttk.Button(frame, text="Pick…", command=pick_color).pack(side="left")
        self.vars[key] = ("color", self.color_value)
        return row + 1

    def _current_context(self):
        return self.vars["system_context"][1].get("1.0", "end-1c")

    def _update_reset_state(self):
        self.reset_required = self._current_context() != self.committed_context
        if self.reset_required:
            self.reset_btn.config(text="Reset AI (required)")
            self.warn_var.set(
                "System Context changed, Resetting AI is required. "
                "Press Reload to undo."
            )
        else:
            self.reset_btn.config(text="Reset AI")
            self.warn_var.set("")

    def _schedule_autosave(self, *_args):
        if self._suspend_autosave:
            return
        self._update_reset_state()
        if self._autosave_job is not None:
            self.after_cancel(self._autosave_job)

        self._autosave_job = self.after(350, self._write_now)

    def _write_now(self):
        self._autosave_job = None
        new_data = self._collect()
        new_data["system_context"] = self.committed_context
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(new_data, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            self.status_var.set(f"Autosave failed: {exc}")
            return
        self.data = new_data
        note = " (System Context pending Reset AI)" if self.reset_required else ""
        self.status_var.set(
            f"Auto-saved to config.json at {time.strftime('%H:%M:%S')}{note}"
        )

    def _collect(self):
        result = {}
        for key, (kind, widget) in self.vars.items():
            if kind == "entry" or kind == "color":
                result[key] = widget.get().strip()
            elif kind == "text":
                result[key] = widget.get("1.0", "end-1c")
            elif kind == "float":
                result[key] = round(float(widget.get()), 3)
        return result

    def reload_config(self):
        self._suspend_autosave = True
        try:
            self.data = load_config()
            for key, (kind, widget) in self.vars.items():
                if kind == "entry":
                    widget.set(str(self.data.get(key, "")))
                elif kind == "text":
                    widget.delete("1.0", "end")
                    widget.insert("1.0", str(self.data.get(key, "")))
                elif kind == "float":
                    widget.set(float(self.data.get(key, 1.0)))
                elif kind == "color":
                    widget.set(str(self.data.get(key, "#FA2A55")))
        finally:
            self._suspend_autosave = False
        self.committed_context = self.data.get("system_context", "")
        self._update_reset_state()
        self.status_var.set("Reloaded from config.json.")

    def save_config(self):
        context_changed = self._current_context() != self.committed_context
        intro = (
            "Your System Context was changed, AI must be ressetted to apply.\n\n"
            if context_changed
            else ""
        )
        confirm = messagebox.askyesno(
            "Reset AI",
            intro + "This will save your current settings and "
            "delete Phoebe's personality memory.\n\nContinue?",
            icon="warning",
        )
        if not confirm:
            self.status_var.set("Reset AI cancelled.")
            return False

        if self._autosave_job is not None:
            self.after_cancel(self._autosave_job)
            self._autosave_job = None

        new_data = self._collect()

        deleted_note = ""
        if os.path.isfile(RESET_MARKER_FILE):
            try:
                os.remove(RESET_MARKER_FILE)
                deleted_note = " Reset marker deleted."
            except OSError as exc:
                messagebox.showerror(
                    "Config Editor",
                    f"Couldn't delete the reset marker:\n{exc}\n\nNothing was saved.",
                )
                return False

        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(new_data, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            messagebox.showerror("Config Editor", f"Failed to save config.json:\n{exc}")
            return False

        self.data = new_data
        self.committed_context = new_data["system_context"]
        self._update_reset_state()
        self.status_var.set(f"Saved to config.json.{deleted_note}")
        return True

    def _on_close(self):
    
        if self._autosave_job is not None:
            self.after_cancel(self._autosave_job)
            self._write_now()

        if self.reset_required:
            answer = messagebox.askyesnocancel(
                "Reset required",
                "You changed the System Context, but the AI hasn't been reset yet.\n\n"
                "Yes = Reset AI now and close.\n"
                "No  = Discard the System Context change and close.\n"
                "Cancel = Keep editing.",
                icon="warning",
            )
            if answer is None:
                return
            if answer and not self.save_config():
                return
        self.destroy()


if __name__ == "__main__":
    app = ConfigEditor()
    app.mainloop()