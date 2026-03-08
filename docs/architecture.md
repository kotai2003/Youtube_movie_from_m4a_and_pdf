# Architecture

## Pipeline Overview

Podcast AI Studio uses a **4-step sequential pipeline** orchestrated by
`main.py` and configured via `config.yaml`.

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Step 1    │    │   Step 2    │    │   Step 3    │    │   Step 4    │
│   Slides    │───▶│  Transcribe │───▶│   Match     │───▶│   Video     │
│  Extraction │    │  (Whisper)  │    │  (Ollama)   │    │  (FFmpeg)   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
     PPTX/PDF          Audio            LLM cuesheet       MP4 + SRT
```

Each step reads from and writes to the `output/` directory, making it
possible to re-run individual steps without re-running the entire pipeline.

---

## Data Flow

```
input/
  ├── podcast.mp3           # Source audio
  └── slides.pptx           # Source slides (or .pdf)

output/
  ├── slide_images/          # Step 1: PNG images per slide
  ├── slides_info.json       # Step 1: slide text + image paths
  ├── transcript.json        # Step 2: timestamped segments
  ├── transcript.txt         # Step 2: human-readable text
  ├── cuesheet.json          # Step 3: slide timing from LLM
  ├── cuesheet.csv           # Step 3: CSV version
  ├── subtitles.srt          # Step 4: SRT for Filmora
  └── podcast_video.mp4      # Step 4: final video
```

---

## Step Details

### Step 1 — Slide Extraction (`step1_extract_slides.py`)

Extracts text and images from presentation files.

| Input Format | Text Extraction | Image Export |
|-------------|----------------|-------------|
| `.pptx` | python-pptx | PowerPoint COM → LibreOffice fallback |
| `.pdf` | PyMuPDF `get_text()` | PyMuPDF rasterisation (2.5x matrix) |

**OCR Fallback:** When a slide has no extractable text (image-only slides),
EasyOCR is invoked with configurable language support (default: `ja`, `en`).

**Output:** `slides_info.json` — an array of objects:

```json
{
  "slide_number": 1,
  "title": "Introduction",
  "full_text": "Welcome to ...",
  "image_path": "/abs/path/to/slide_001.png",
  "ocr_used": false
}
```

### Step 2 — Audio Transcription (`step2_transcribe.py`)

Uses OpenAI Whisper (local model, **not** the API) to produce timestamped
transcript segments.

- Models: `tiny`, `base`, `small` (default), `medium`, `large`
- Languages: `ja`, `ko`, `en`, or `auto` (Whisper auto-detection)
- First run downloads the model (~500 MB for `small`)

**Output:** `transcript.json` — array of `{ "start", "end", "text" }`.

### Step 3 — Slide-Audio Matching (`step3_match.py`)

Sends slide summaries and the transcript to a **local Ollama LLM** to
determine when each slide should appear.

```
Slide summaries + Transcript  ──▶  Ollama LLM  ──▶  JSON cuesheet
```

**Robustness features:**

- JSON repair logic (fixes common LLM output issues)
- Up to 2 retries on parse failure
- Validation and gap-filling
- Fallback to equal-duration distribution if LLM output is unusable

**Output:** `cuesheet.json` — array of:

```json
{
  "slide_number": 1,
  "start_time": 0.0,
  "end_time": 45.2,
  "reason": "Speaker introduces topic"
}
```

### Step 4 — Video Generation (`step4_generate_video.py`)

Generates the final MP4 using **FFmpeg** (not moviepy):

1. Create a still-image video segment per cuesheet entry
2. Concatenate all segments via FFmpeg concat protocol
3. Mux with the original audio track
4. Optionally burn in SRT subtitles

**Output:** `podcast_video.mp4`

---

## GUI Architecture

All GUIs live under `gui_apps/` and share the same pattern:

1. Calculate `PROJECT_ROOT` from `__file__` (parent of `gui_apps/`)
2. Load/save `config.yaml` at the project root
3. Launch `main.py` as a subprocess with `cwd=PROJECT_ROOT`
4. Stream subprocess stdout to a log widget via a thread-safe queue
5. Step 2 (Whisper) runs **in-process** for language auto-detection

| Version | File | Description |
|---------|------|-------------|
| v4 (recommended) | `run_gui_app.py` | Dark theme, sidebar nav, pipeline cards, project management |
| v3 | `run_gui_rev003.py` | 3-panel layout (Input / Processing / Preview) |
| v2 | `run_gui_rev002.py` | Single panel, multilingual subtitle support |
| v1 | `run_gui.py` + `gui_app.py` | Simple radio-button mode selector |

---

## External Dependencies

| Dependency | Purpose | Required |
|-----------|---------|----------|
| **Ollama** | Local LLM for slide matching (Step 3) | Yes |
| **FFmpeg** | Video generation and audio probing (Step 4) | Yes |
| **Whisper** | Audio transcription (Step 2) | Yes (auto-downloads) |
| **PowerPoint** | PPTX image export via COM (Step 1) | Optional (LibreOffice fallback) |
| **EasyOCR** | OCR for image-only slides (Step 1) | Optional |

---

## Unicode / Japanese Path Handling

The project is fully compatible with Japanese (non-ASCII) folder names:

- GUI browse dialogs store **absolute paths** (`os.path.abspath`)
- All `subprocess` calls use `encoding="utf-8"` and `errors="replace"`
- FFmpeg concat lists use **relative filenames** only
- Child processes inherit `PYTHONIOENCODING=utf-8`
