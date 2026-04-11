# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Podcast AI Studio (run_gui_app.py)
Folder-based distribution with Cython-compiled modules.
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None

SPEC_DIR = os.path.abspath(SPECPATH)
PROJECT_ROOT = os.path.dirname(SPEC_DIR)
COMPILED_DIR = os.path.join(SPEC_DIR, "compiled_modules")
APP_ICON = os.path.join(SPEC_DIR, "app_icon.ico")

# ---------------------------------------------------------------------------
# Pre-collect packages whose C extensions / data files / sub-modules are
# not picked up by hiddenimports alone.
#
# `requests` checks at import time for chardet OR charset_normalizer; if
# only the .pyd ends up in _internal/charset_normalizer/ (without the
# Python __init__.py and friends), Python sees a directory without an
# __init__.py and the import fails, leaving the warning:
#   RequestsDependencyWarning: Unable to find acceptable character
#   detection dependency (chardet or charset_normalizer)
#
# `collect_all` returns (datas, binaries, hiddenimports) so the package
# is bundled completely.
# ---------------------------------------------------------------------------
_extra_datas = []
_extra_binaries = []
_extra_hiddenimports = []
for _pkg in ("charset_normalizer", "chardet"):
    try:
        _d, _b, _h = collect_all(_pkg)
        _extra_datas += _d
        _extra_binaries += _b
        _extra_hiddenimports += _h
    except Exception as _e:
        print(f"[SPEC] WARNING: collect_all({_pkg!r}) failed: {_e}")

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [os.path.join(PROJECT_ROOT, "gui_apps", "run_gui_app.py")],
    pathex=[PROJECT_ROOT],
    binaries=[*_extra_binaries],
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
        # App icon — bundled next to other data so the GUI can load it
        # at runtime instead of generating one with Pillow.
        (APP_ICON, "."),
        # charset_normalizer / chardet — full collection (Python files +
        # C extensions + dist-info metadata) so `requests` can find them
        # at import time.
        *_extra_datas,
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
        # Pipeline modules — needed because the bundled exe re-launches
        # itself in pipeline mode (see _is_pipeline_invocation in
        # gui_apps/run_gui_app.py) and imports `main` to dispatch the
        # step.  Listed explicitly so PyInstaller's static analyser
        # always pulls them into the PYZ regardless of how the GUI
        # source is read.
        "main",
        "step1_extract_slides",
        "step2_transcribe",
        "step3_match",
        "step4_generate_video",
        "subtitle_generator",
        # Step 1 OCR fallback (easyocr → torchvision → torch._dynamo)
        # transitively needs sympy.  Some of torch's _dynamo paths use
        # dynamic / string-based imports that PyInstaller can't always
        # follow, so we list it explicitly.
        "sympy",
        # `requests` (used by Ollama HTTP calls in step3) needs a
        # character detection backend; without it, requests emits
        # `RequestsDependencyWarning: Unable to find acceptable
        # character detection dependency (chardet or charset_normalizer)`
        # and falls back unsafely. The full package is also collected
        # via collect_all() above to bring in C extensions and metadata.
        "charset_normalizer",
        "chardet",
        *_extra_hiddenimports,
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
        # NOTE: do NOT exclude scipy / cv2 / sympy — they are required
        # by easyocr (Step 1 OCR fallback) → torchvision → torch.
        # Excluding them previously broke `python main.py --step 1`
        # in the bundled exe with ModuleNotFoundError.
        "sklearn", "scikit-learn",
        "pandas", "matplotlib", "seaborn", "plotly",
        "statsmodels",
        "tensorboard", "tensorflow", "keras",
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
        # NOTE: do NOT exclude `pydoc` — scipy._lib._docscrape imports
        # it, and excluding it breaks any easyocr / scipy import chain.
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
    icon=APP_ICON,
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
