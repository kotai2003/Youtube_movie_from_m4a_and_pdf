"""
Cython Build Script
Compiles gui_apps/ollama_utils.py and gui_apps/__init__.py to .pyd extensions.
Run from the pyinstaller/ directory.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GUI_APPS_DIR = PROJECT_ROOT / "gui_apps"
BUILD_DIR = Path(__file__).resolve().parent / "cython_build_tmp"

# Modules to compile
# NOTE: __init__.py is excluded because Cython cannot compile __init__ modules
# and it is empty (no source to protect).
MODULES = [
    "ollama_utils.py",
]


def create_setup_script(build_dir: Path, sources: list[Path]) -> Path:
    """Create a temporary setup.py for Cython compilation."""
    setup_path = build_dir / "setup.py"
    ext_entries = []
    for src in sources:
        module_name = src.stem
        ext_entries.append(
            f'    Extension("{module_name}", [r"{src}"])'
        )
    ext_list = ",\n".join(ext_entries)

    setup_path.write_text(f"""\
from setuptools import setup
from Cython.Build import cythonize
from setuptools import Extension

extensions = [
{ext_list}
]

setup(
    ext_modules=cythonize(
        extensions,
        compiler_directives={{
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
        }},
    ),
)
""", encoding="utf-8")
    return setup_path


def main():
    print("=" * 60)
    print("Cython Build - Compiling Python modules to .pyd")
    print("=" * 60)

    # Verify Cython is installed
    try:
        import Cython
        print(f"Cython version: {Cython.__version__}")
    except ImportError:
        print("ERROR: Cython is not installed. Run: pip install cython")
        sys.exit(1)

    # Clean previous build
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)

    # Collect source files
    sources = []
    for mod in MODULES:
        src = GUI_APPS_DIR / mod
        if not src.exists():
            print(f"WARNING: {src} not found, skipping")
            continue
        sources.append(src)

    if not sources:
        print("ERROR: No source files found to compile")
        sys.exit(1)

    print(f"\nModules to compile:")
    for s in sources:
        print(f"  {s.name}")

    # Create setup.py
    setup_path = create_setup_script(BUILD_DIR, sources)
    print(f"\nSetup script: {setup_path}")

    # Run Cython compilation
    print("\nCompiling with Cython...")
    result = subprocess.run(
        [sys.executable, str(setup_path), "build_ext", "--inplace"],
        cwd=str(BUILD_DIR),
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print("ERROR: Cython compilation failed")
        sys.exit(1)

    # Find and copy .pyd files to gui_apps/
    print("\nLocating compiled .pyd files...")
    pyd_files = list(BUILD_DIR.rglob("*.pyd"))
    if not pyd_files:
        # On some setups the files end up in build/ subdirectories
        pyd_files = list(BUILD_DIR.rglob("*.so"))

    if not pyd_files:
        print("ERROR: No compiled .pyd/.so files found")
        sys.exit(1)

    output_dir = Path(__file__).resolve().parent / "compiled_modules"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir()

    for pyd in pyd_files:
        # Normalize name: remove cpython-3xx-win_amd64 suffix if present
        # e.g. ollama_utils.cpython-313-x86_64-linux-gnu.so -> ollama_utils.pyd
        stem = pyd.stem.split(".")[0]
        ext = ".pyd" if sys.platform == "win32" else ".so"
        dest = output_dir / f"{stem}{ext}"
        shutil.copy2(pyd, dest)
        print(f"  {pyd.name} -> {dest}")

    # Clean up build temp
    shutil.rmtree(BUILD_DIR)

    print("\n" + "=" * 60)
    print("Cython compilation complete!")
    print(f"Compiled modules in: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
