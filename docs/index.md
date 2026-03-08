# Podcast AI Studio

**Podcast AI Studio** is a Python tool that automatically generates MP4 videos
from podcast audio and presentation slides (PPTX / PDF).  Slides switch at
appropriate timestamps determined by an AI matching engine.

The generated video is intended for final editing in **Filmora** — add
transitions, captions, intros/outros, and export.

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Slide extraction** | Text + images from PPTX (COM / LibreOffice) and PDF (PyMuPDF), with EasyOCR fallback |
| **Audio transcription** | Local Whisper models (tiny → large), auto language detection |
| **AI slide matching** | Local Ollama LLM determines when each slide should appear |
| **Video generation** | FFmpeg-based, produces broadcast-quality MP4 |
| **Subtitle support** | SRT generation, optional burn-in, multilingual (ja / ko / en) |
| **GUI** | Commercial-grade dark-themed desktop app (tkinter/ttk) |

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install external tools

- **Ollama** — <https://ollama.com/> → `ollama pull gemma3:27b`
- **FFmpeg** — <https://www.gyan.dev/ffmpeg/builds/> → add to PATH

### 3. Launch the GUI

```bash
python gui_apps/run_gui_app.py
```

Or run from the command line:

```bash
python main.py
```

---

## Project Structure

```
├── gui_apps/                   # GUI applications
│   ├── run_gui_app.py       #   Podcast AI Studio (recommended)
│   ├── run_gui_rev003.py       #   Studio 3-panel layout
│   ├── run_gui_rev002.py       #   Multilingual subtitle GUI
│   ├── run_gui.py              #   Simple GUI launcher
│   ├── gui_app.py              #   Simple GUI implementation
│   └── ollama_utils.py         #   Ollama model list utility
├── main.py                     # CLI entry point
├── step1_extract_slides.py     # Slide extraction (PPTX / PDF + OCR)
├── step2_transcribe.py         # Whisper transcription
├── step3_match.py              # Ollama LLM slide-audio matching
├── step4_generate_video.py     # FFmpeg video generation
├── subtitle_generator.py       # SRT subtitle generation
├── config.yaml                 # Runtime configuration
├── input/                      # Input audio + slides
└── output/                     # Generated artifacts
```

---

## Documentation Sections

- [**Architecture**](architecture.md) — Pipeline design, data flow, and module responsibilities
- [**API Reference**](api.md) — Auto-generated from Python docstrings
- [**Usage Guide**](usage.md) — GUI walkthrough, CLI commands, configuration reference
