# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Podcast video generator tool. Takes podcast audio + slides (PPTX/PDF) and produces an MP4 video where slides switch at appropriate timestamps, intended for final editing in Filmora. Supports multilingual subtitles (Japanese, Korean, English) with Whisper auto-detection.

## Running

```bash
# GUI - Podcast AI Studio (dark theme, commercial-grade, recommended)
python gui_apps/run_gui_app.py

# GUI - previous versions
python gui_apps/run_gui_rev003.py      # Studio 3-panel layout
python gui_apps/run_gui_rev002.py      # Multilingual subtitle support
python gui_apps/run_gui.py             # Original simple GUI

# CLI - full pipeline (all 4 steps)
python main.py

# CLI - specific steps
python main.py --step 1       # Extract slides (text + images, with OCR fallback)
python main.py --step 2       # Transcribe audio via Whisper
python main.py --step 3       # Match slides to audio via Ollama LLM
python main.py --step 4       # Generate MP4 video via FFmpeg
python main.py --step 3 4     # Multiple steps
python main.py --edit-cuesheet  # Review cuesheet interactively, then generate video
```

## Architecture

4-step pipeline orchestrated by `main.py`, configured via `config.yaml`:

1. **step1_extract_slides.py** — Extracts text + images from PPTX (via python-pptx + COM/LibreOffice) or PDF (via PyMuPDF). Falls back to EasyOCR for image-based slides with no extractable text.

2. **step2_transcribe.py** — Transcribes audio using OpenAI Whisper (local, not API). Produces timestamped segments.

3. **step3_match.py** — Sends slide text + transcript to Ollama (local LLM) to determine when each slide should appear. Includes JSON repair logic and fallback to equal distribution if LLM output is unusable. Retries up to 2 times.

4. **step4_generate_video.py** — Generates MP4 using FFmpeg (not moviepy). Creates per-slide video segments, concatenates them, then muxes with audio. Optionally burns in subtitles.

**subtitle_generator.py** — Generates SRT files from transcript segments. Also has Pillow-based subtitle image rendering (for moviepy, currently unused in FFmpeg pipeline).

### GUI versions (all under `gui_apps/`)

- **`gui_apps/run_gui_app.py`** (Podcast AI Studio, recommended) — Commercial-grade dark-themed GUI with sidebar navigation, scrollable workspace, and preview panel. Catppuccin-inspired dark palette (`#1e1e2e` base, blue accent). Features: sidebar nav (Project/Inputs/AI Settings/Pipeline/Subtitles/Output/Logs) that scrolls workspace to sections, pipeline step cards with visual status (Pending/Running/Done/Failed) connected by arrows, project management with recent projects (`.recent_projects.json`), color-coded log output (`[ERROR]` red, `[WARN]` yellow, `[SUCCESS]` green), output file existence indicators in preview panel, status bar (state/language/model/progress). Programmatic app icon via Pillow. Step 2 runs Whisper in-process; other steps delegate to `main.py` via subprocess. Uses `clam` theme with extensive custom ttk styles.
- **`gui_apps/run_gui_rev003.py`** (Studio) — 3-panel tkinter/ttk GUI (Input | Processing | Preview). Features: Ollama model combobox, Whisper model selector (tiny-large), language selection (Auto/ja/ko/en), per-step execution buttons + Run All, progress bar, real-time log, slide preview with navigation, subtitle preview, Open Video/Folder buttons. Step 2 runs Whisper in-process for language detection; other steps delegate to `main.py` via subprocess. Uses `clam` theme.
- **`gui_apps/run_gui_rev002.py`** — Single-panel GUI with multilingual subtitle support and in-process Whisper language detection. Generates `transcript.srt` (UTF-8 BOM).
- **`gui_apps/run_gui.py`** / **`gui_apps/gui_app.py`** — Original simple GUI with radio-button execution mode.
- **`gui_apps/ollama_utils.py`** — `get_ollama_models()`: runs `ollama list`, parses output, returns list of installed model names.

## Key Data Flow

```
input/ (audio + slides)
  → output/slides_info.json    (step1: slide text + image paths)
  → output/transcript.json     (step2: timestamped segments)
  → output/cuesheet.json       (step3: slide timing from LLM)
  → output/podcast_video.mp4   (step4: final video)
  → output/subtitles.srt       (step4: SRT for Filmora import)
  → output/transcript.srt      (step2 via GUI: SRT with auto-detected language)
```

## External Dependencies

- **Ollama** must be running locally (`ollama serve`) with the model specified in `config.yaml` pulled
- **FFmpeg** must be on PATH (used by step4 for video generation and ffprobe for duration)
- **Whisper** model downloads automatically on first run (~500MB for "small")
- PPTX image export uses Windows COM automation (PowerPoint) with LibreOffice as fallback

## Config (config.yaml)

`config.yaml` is gitignored (contains local paths). Users copy `config.yaml.example` to `config.yaml` and edit.

Key settings: `audio_file`, `slides_file`, `ollama.model`, `whisper.model`, `whisper.language`, `video.*` (resolution/fps), `subtitle.*` (SRT generation, burn-in options).

## Language

Pipeline steps (`step1`-`step4`, `main.py`) use Japanese for console output and comments. GUI rev002/rev003/rev004 use English labels. Supports multilingual audio: Japanese, Korean, English (auto-detected by Whisper or manually selected). OCR defaults to ["ja", "en"].

## Unicode / Japanese Path Support

All file paths are handled as absolute paths to avoid issues with Japanese (non-ASCII) folder names on Windows. Key conventions:

- **`_resolve_path(p)` helper** in `gui_apps/run_gui_app.py` is the single source of truth for path resolution: returns *p* normalised and absolute (resolved against `PROJECT_ROOT` if relative). All GUI methods that touch user-supplied paths go through this helper instead of `os.path.join(PROJECT_ROOT, ...)`.
- **GUI browse dialogs** store absolute paths via `_resolve_path()` to prevent path resolution failures with Japanese directory names.
- **`save_config()`** writes only resolved absolute paths to `config.yaml` so subprocess steps work regardless of CWD.
- **`_ascii_safe_audio(audio_path)`** (defined in `gui_apps/run_gui_app.py`, `step2_transcribe.py`, and `step4_generate_video.py`) is the canonical workaround for the FFmpeg / Whisper Japanese-filename failure on Windows. On Windows, when `audio_path` contains non-ASCII characters, the file is copied to `tempfile.mkstemp(...)` (system temp, always ASCII-safe) and the temp path is returned for use by FFmpeg/Whisper. The caller must delete the returned tmp path in a `finally` block. **Reason**: some FFmpeg builds on Windows fail to open files whose argv path is non-ASCII, breaking `whisper.transcribe()` audio loading and ffprobe duration probing.
- **Step 4 temp directory** (`step4_generate_video.py`) is created via `tempfile.mkdtemp(prefix="podcast_ai_segs_")` (system temp, ASCII-safe) instead of inside `output_dir`, so Japanese characters in the user's Output Folder do not propagate to FFmpeg's concat list parent path.
- **All `subprocess.run` / `subprocess.Popen` calls** that read stdout/stderr must specify `encoding="utf-8", errors="replace"` to avoid `UnicodeDecodeError` on Windows (default is cp932 on Japanese locale).
- **FFmpeg concat list** (`step4_generate_video.py`) uses relative filenames only (e.g. `file 'seg_000.mp4'`) instead of absolute paths, so Japanese characters in parent directories don't break FFmpeg's file reader. Combined with `tempfile.mkdtemp()` above, the entire concat path stays ASCII.
- **`PYTHONIOENCODING=utf-8`** is set in the subprocess environment when GUIs launch `main.py`, ensuring the child process outputs UTF-8.

> When adding new code that passes a user-supplied audio file to FFmpeg or Whisper on Windows, always wrap it with `_ascii_safe_audio()` and clean up the temp copy in `finally`. When joining a user path with PROJECT_ROOT in `gui_apps/run_gui_app.py`, use `_resolve_path()` instead of `os.path.join(PROJECT_ROOT, ...)`.

## Project Structure

```
├── gui_apps/                   # GUI applications (all tkinter/ttk GUIs)
│   ├── run_gui_app.py          #   Podcast AI Studio (recommended)
│   ├── run_gui_rev003.py       #   Studio 3-panel layout
│   ├── run_gui_rev002.py       #   Multilingual subtitle GUI
│   ├── run_gui.py              #   Original simple GUI launcher
│   ├── gui_app.py              #   Original simple GUI implementation
│   └── ollama_utils.py         #   Ollama model list utility
├── main.py                     # CLI entry point (orchestrates steps)
├── step1_extract_slides.py     # Slide extraction (PPTX/PDF + OCR)
├── step2_transcribe.py         # Whisper transcription
├── step3_match.py              # Ollama LLM slide-audio matching
├── step4_generate_video.py     # FFmpeg video generation
├── subtitle_generator.py       # SRT subtitle generation
├── config.yaml.example         # Configuration template
├── pyinstaller/                # PyInstaller + Inno Setup build assets
│   ├── build.bat               #   Standard PyInstaller build entry point
│   ├── secure_build.bat        #   Cython-protected build entry point
│   ├── run_gui_app.spec        #   PyInstaller spec for run_gui_app
│   ├── rthook_stdio.py         #   Runtime hook (stdio redirect for --noconsole)
│   ├── cython_build.py         #   Pre-build step that compiles GUI sources to .pyd
│   ├── installer.iss           #   Inno Setup installer script
│   └── app_icon.ico            #   Multi-resolution app icon (16-256 px)
├── dist/run_gui_app/           # PyInstaller output (folder distribution, gitignored)
├── build/run_gui_app/          # PyInstaller intermediate files (gitignored)
├── installer_output/           # Inno Setup installer .exe output (gitignored)
├── input/                      # Input audio + slides (gitignored)
└── output/                     # Generated artifacts (gitignored)
```

## PyInstaller Build (Windows EXE distribution)

The GUI is packaged as a folder-mode Windows distribution rooted at
`dist/run_gui_app/`, with `run_gui_app.exe` as the entry point and all
dependencies (including Whisper assets, PyTorch, FFmpeg-via-imageio,
Tk runtime) under `_internal/`.

### Build commands

```bash
# Plain build (uses .py sources)
cd pyinstaller
build.bat

# Or, equivalently from PROJECT_ROOT:
python -m PyInstaller --distpath ./dist --workpath ./build \
    --noconfirm --clean ./pyinstaller/run_gui_app.spec
```

For source-protected builds, run `python pyinstaller/cython_build.py`
first to generate `pyinstaller/compiled_modules/*.pyd`; the spec then
swaps the matching `.py` modules out of `a.pure` and adds the `.pyd`
files as binaries (see the `COMPILED_DIR` block in
`pyinstaller/run_gui_app.spec`). Without that pre-step the spec emits
a `[SPEC] WARNING: No compiled_modules directory found` and falls
back to plain Python sources — this is intentional, not an error.

### Spec key points (`pyinstaller/run_gui_app.spec`)

- **Entry point**: `gui_apps/run_gui_app.py`
- **Pipeline scripts bundled as `datas`** *and* **as `hiddenimports`**:
  `main`, `step1_extract_slides`, `step2_transcribe`, `step3_match`,
  `step4_generate_video`, `subtitle_generator`. They are listed in
  `hiddenimports` so PyInstaller compiles them into the PYZ archive,
  and also copied as raw `.py` next to `run_gui_app.exe` (legacy paths
  still expect to find them on disk). **When you add a new pipeline
  file, add it in BOTH `a.datas` AND `hiddenimports`** or the bundled
  exe will fail to dispatch the new step.
- **Pipeline-mode dispatch (critical for the bundled exe)**: in a
  frozen build there is no separate `python.exe`, so the GUI's
  `subprocess.Popen([sys.executable, "main.py", "--step", N])` would
  silently relaunch the GUI instead of running the step. To work
  around this, `gui_apps/run_gui_app.py`'s `main()` checks
  `sys.argv` at startup via `_is_pipeline_invocation()` and, when
  pipeline flags are present, calls `_setup_stdio_for_pipeline()` and
  `import main as _pipeline_main; _pipeline_main.main()` in-process.
  See the comments around `_setup_stdio_for_pipeline` in
  `gui_apps/run_gui_app.py`. **Do not remove these helpers** — they
  are what makes Steps 1, 3, and 4 work in the bundled exe.
- **Stdio in pipeline mode**: `_setup_stdio_for_pipeline()` re-wraps
  FD 1 / FD 2 as utf-8 text streams, overriding the devnull
  assignment from `rthook_stdio.py`. The runtime hook is needed for
  the windowed-launch case (no parent pipe → FD 1 invalid → fdopen
  raises OSError → leave devnull alone), and the in-`main()` re-wrap
  is needed for the pipeline-launch case (parent's `Popen` provides a
  pipe on FD 1 → fdopen succeeds → prints flow back to the GUI).
- **`PROJECT_ROOT` resolution**: `gui_apps/run_gui_app.py` checks
  `getattr(sys, "frozen", False)` and uses `sys._MEIPASS` (i.e. the
  `_internal/` folder) as `PROJECT_ROOT` in frozen mode. In dev mode
  it stays as the parent of `gui_apps/`. This is what lets the
  bundled `import main` find `_internal/main.py`.
- **Whisper assets**: `whisper/assets` and `whisper/normalizers` from
  the active site-packages are copied wholesale (mel filters,
  tiktoken, etc).
- **App icon**: `pyinstaller/app_icon.ico` is set as the EXE icon
  resource AND bundled in `a.datas` so the running GUI can pick it up
  via `_find_app_icon_path()` (`gui_apps/run_gui_app.py`). The .ico
  is a multi-resolution file (16/24/32/48/64/128/256 px) generated
  with Pillow — see the `make_icon` snippet committed in the project
  history if you need to regenerate.
- **`charset_normalizer` + `chardet` via `collect_all`**: `requests`
  checks for one of these at import time. Listing them as
  `hiddenimports` alone is **not enough** — PyInstaller drops the
  `.pyd` C extensions into `_internal/charset_normalizer/` but
  without an `__init__.py`, which makes the directory un-importable.
  The spec uses `from PyInstaller.utils.hooks import collect_all` to
  fully bundle both packages (Python files + binaries + dist-info
  metadata). **If you see `RequestsDependencyWarning: Unable to find
  acceptable character detection dependency`**, that's the symptom.
- **Runtime hook**: `rthook_stdio.py` reassigns `sys.stdout` /
  `sys.stderr` to `os.devnull` when running `--noconsole` so that
  stray prints don't crash on `NoneType.write`. The pipeline-mode
  dispatcher overrides this re-wrap (see above).
- **`console=False`** — windowed mode, no console pops up.
- **`strip=True, upx=True`** — UPX compression. If UPX is not on
  PATH, PyInstaller may emit a non-fatal `FileNotFoundError`
  traceback during the COLLECT step but still completes the build
  successfully. To silence it, install UPX or set both flags to
  `False`.
- **Excludes — be conservative**: the spec excludes heavy unused
  packages (sklearn, pandas, matplotlib, tensorflow, web frameworks,
  ORMs, etc) to keep the dist manageable. **Do NOT exclude any of:
  `unittest` (Whisper imports it), `sympy` (torch._dynamo →
  torch.utils._sympy), `scipy` (easyocr), `cv2` / `opencv-python`
  (easyocr), `pydoc` (scipy._lib._docscrape).** Each one of these
  was excluded at some point and broke a different step at runtime.
  The current excludes list has comments marking these as
  "do not exclude" to prevent regressions.

### Verifying a build

After `build.bat`, confirm:

1. `dist/run_gui_app/run_gui_app.exe` exists and is freshly timestamped.
2. `dist/run_gui_app/_internal/step2_transcribe.py` and
   `dist/run_gui_app/_internal/step4_generate_video.py` contain
   `_ascii_safe_audio` (regression check for the Japanese path fix).
3. `dist/run_gui_app/_internal/charset_normalizer/__init__.py` and
   `dist/run_gui_app/_internal/chardet/__init__.py` both exist (the
   collect_all check — if missing you'll get the requests warning).
4. Smoke-test the dispatcher without launching the GUI:
   `dist/run_gui_app/run_gui_app.exe --step 99` should print an
   argparse error about an invalid step choice and exit with code 2.
   If it instead launches the GUI, the dispatcher is broken.
5. Launching the exe brings up the dark-themed GUI with the custom
   icon (blue play triangle on dark navy) in the title bar.
6. Running Step 2 against an audio file with non-ASCII characters in
   its filename succeeds and writes `transcript.json` / `transcript.srt`.

The full `dist/run_gui_app/` folder is on the order of 4–4.5 GB
because of PyTorch + Whisper model assets + scipy + cv2 — that is
expected.

## Inno Setup installer (`pyinstaller/installer.iss`)

After `build.bat` produces `dist/run_gui_app/`, run Inno Setup to
package it as a single Windows installer `.exe`:

```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" pyinstaller/installer.iss
# → installer_output/PodcastAIStudio-Setup-{version}.exe (~1.6 GB,
#   compressed from the ~4 GB dist via lzma2/ultra64)
```

### Key directives

- **`AppId`** is a fixed GUID (`{8E5D1C30-7B4A-4FB2-9C8E-A1F0B2C3D4E5}`).
  **Do NOT change it between releases** — it is what allows new
  versions to upgrade in place over old installations.
- **`AppVersion`** is hard-coded as `#define MyAppVersion`. Bump it
  for each release; the output filename and the Add/Remove Programs
  display version both pull from this.
- **Source paths** are written relative to `SourcePath` (the
  directory containing the .iss) so the script works regardless of
  the caller's CWD: `{#SourceRoot}` → `../dist/run_gui_app`,
  `{#OutputBaseDir}` → `../installer_output`.
- **Languages**: English + Japanese (`compiler:Languages\Japanese.isl`).
- **`SetupIconFile` / `UninstallDisplayIcon`**: both reference
  `app_icon.ico` so Setup.exe and the Add/Remove Programs entry both
  show the custom icon.
- **Compression**: `lzma2/ultra64` with `LZMANumBlockThreads=4` —
  packaging takes ~5 minutes on a typical dev machine.
- **`PrivilegesRequired=admin`** — installs to `{autopf}\PodcastAIStudio`
  (`C:\Program Files\PodcastAIStudio` on 64-bit Windows). Per-user
  install would also work; the override dialog is enabled via
  `PrivilegesRequiredOverridesAllowed=dialog`.
- **`[UninstallDelete]`** removes `config.yaml`, `.recent_projects.json`,
  and `output/` on uninstall so user state created in the install
  directory does not get left behind.

### When to rebuild the installer

The installer **only repackages `dist/run_gui_app/`** — it does not
re-run PyInstaller. So after changing any Python source you must:

1. `pyinstaller/build.bat`  (or the equivalent `python -m PyInstaller`)
2. `ISCC.exe pyinstaller/installer.iss`

Skipping step 1 will silently package the previous build.

## Notes

- Each step can be re-run independently using cached intermediate JSON files in `output/`
- `cuesheet.json` can be manually edited to fix slide timing before running step 4
