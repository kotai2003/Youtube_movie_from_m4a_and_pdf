# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Podcast AI Studio (run_gui_app.py)
Folder-based distribution with Cython-compiled modules.
"""

import os
import sys
from pathlib import Path

block_cipher = None

SPEC_DIR = os.path.abspath(SPECPATH)
PROJECT_ROOT = os.path.dirname(SPEC_DIR)
COMPILED_DIR = os.path.join(SPEC_DIR, "compiled_modules")

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [os.path.join(PROJECT_ROOT, "gui_apps", "run_gui_app.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        # Include config.yaml template
        (os.path.join(PROJECT_ROOT, "config.yaml"), "."),
        # Include pipeline scripts (called via subprocess by the GUI)
        (os.path.join(PROJECT_ROOT, "main.py"), "."),
        (os.path.join(PROJECT_ROOT, "step1_extract_slides.py"), "."),
        (os.path.join(PROJECT_ROOT, "step2_transcribe.py"), "."),
        (os.path.join(PROJECT_ROOT, "step3_match.py"), "."),
        (os.path.join(PROJECT_ROOT, "step4_generate_video.py"), "."),
        (os.path.join(PROJECT_ROOT, "subtitle_generator.py"), "."),
        # Whisper assets (mel_filters.npz, tiktoken files, normalizers)
        (os.path.join(sys.prefix, "Lib", "site-packages", "whisper", "assets"), os.path.join("whisper", "assets")),
        (os.path.join(sys.prefix, "Lib", "site-packages", "whisper", "normalizers"), os.path.join("whisper", "normalizers")),
    ],
    hiddenimports=[
        "whisper",
        "yaml",
        "PIL",
        "PIL.Image",
        "PIL.ImageTk",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "requests",
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.scrolledtext",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(SPEC_DIR, "rthook_stdio.py")],
    excludes=[
        # Test frameworks (keep unittest — Whisper depends on it)
        "pytest", "doctest", "test", "_pytest",
        # Dev / debug tools
        "IPython", "ipykernel", "ipywidgets", "jupyter",
        "notebook", "nbconvert", "nbformat",
        "setuptools", "pip", "wheel", "distutils",
        "Cython",
        # Unused scientific / ML packages
        "scipy", "sklearn", "scikit-learn",
        "pandas", "matplotlib", "seaborn", "plotly",
        "sympy", "statsmodels",
        "tensorboard", "tensorflow", "keras",
        "cv2", "opencv-python",
        # Unused network / web frameworks
        "flask", "django", "fastapi", "uvicorn", "starlette",
        "aiohttp", "tornado", "twisted",
        # Unused database
        "sqlite3", "psycopg2", "pymongo", "sqlalchemy",
        # Unused misc
        "babel", "boto3", "botocore",
        "cryptography", "paramiko",
        "lxml", "html5lib",
        "pygments",
        "pydoc",
        "lib2to3",
        "multiprocessing.popen_spawn_posix",
        "multiprocessing.popen_fork",
        "multiprocessing.popen_forkserver",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ---------------------------------------------------------------------------
# Replace .py modules with compiled .pyd if available
# ---------------------------------------------------------------------------
if os.path.isdir(COMPILED_DIR):
    compiled_files = [f for f in os.listdir(COMPILED_DIR) if f.endswith(".pyd")]
    for cf in compiled_files:
        module_name = cf.replace(".pyd", "")
        # Remove the original .py from the analysis
        a.pure = [
            (name, src, typ)
            for (name, src, typ) in a.pure
            if name != module_name and not name.startswith(f"gui_apps.{module_name}")
        ]
        # Add the compiled .pyd as a binary
        a.binaries.append(
            (f"gui_apps/{cf}", os.path.join(COMPILED_DIR, cf), "EXTENSION")
        )
    print(f"[SPEC] Loaded {len(compiled_files)} compiled module(s) from {COMPILED_DIR}")
else:
    print(f"[SPEC] WARNING: No compiled_modules directory found at {COMPILED_DIR}")
    print("[SPEC]          Run cython_build.py first for source protection.")

# ---------------------------------------------------------------------------
# Remove original .py source files for compiled modules from datas
# ---------------------------------------------------------------------------
PROTECTED_MODULES = {"ollama_utils.py"}
a.datas = [
    (dest, src, typ)
    for (dest, src, typ) in a.datas
    if os.path.basename(src) not in PROTECTED_MODULES
    or "gui_apps" not in src
]

# ---------------------------------------------------------------------------
# PYZ (Python bytecode archive)
# ---------------------------------------------------------------------------
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---------------------------------------------------------------------------
# EXE
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="run_gui_app",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,      # GUI app - no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# ---------------------------------------------------------------------------
# COLLECT (folder-based distribution)
# ---------------------------------------------------------------------------
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name="run_gui_app",
)
