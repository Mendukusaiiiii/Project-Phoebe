import sys
from pathlib import Path

from cx_Freeze import Executable, setup

project_dir = Path(__file__).resolve().parent
icon_file = project_dir / "icon.ico"

build_exe_options = {
    "include_files": [
        "config.json",
        (str(project_dir / "Assets"), "Assets"),
    ],
    "packages": ["PIL", "requests", "pystray", "pygame", "tkinter"],
}

setup(
    name="Phoebe",
    version="1.0",
    description="Project Phoebe AI Assistant",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            script=str(project_dir / "Phoebe.py"),
            base="gui" if sys.platform == "win32" else "console",
            icon=str(icon_file),
            copyright="Copyright (C) 2026 Mendukusai. All rights reserved.",
        )
    ],
)
