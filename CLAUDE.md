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

- **GUI browse dialogs** store absolute paths via `os.path.abspath()` (not `os.path.relpath()`) to prevent path resolution failures with Japanese directory names.
- **All `subprocess.run` / `subprocess.Popen` calls** that read stdout/stderr must specify `encoding="utf-8", errors="replace"` to avoid `UnicodeDecodeError` on Windows (default is cp932 on Japanese locale).
- **FFmpeg concat list** (`step4_generate_video.py`) uses relative filenames only (e.g. `file 'seg_000.mp4'`) instead of absolute paths, so Japanese characters in parent directories don't break FFmpeg's file reader.
- **`PYTHONIOENCODING=utf-8`** is set in the subprocess environment when GUIs launch `main.py`, ensuring the child process outputs UTF-8.

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
├── input/                      # Input audio + slides (gitignored)
└── output/                     # Generated artifacts (gitignored)
```

## Notes

- Each step can be re-run independently using cached intermediate JSON files in `output/`
- `cuesheet.json` can be manually edited to fix slide timing before running step 4
