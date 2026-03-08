# Usage Guide

## GUI (Recommended)

### Launch Podcast AI Studio

```bash
python gui_apps/run_gui_app.py
```

The dark-themed GUI provides a complete workflow:

1. **Project** — Name your project, restore recent projects
2. **Inputs** — Select audio file, slides file, and output folder
3. **AI Settings** — Choose Ollama model and Whisper model/language
4. **Pipeline** — Run individual steps or the full pipeline
5. **Subtitles** — Configure language and subtitle options
6. **Output** — Preview slides, subtitles, and open generated files
7. **Logs** — Colour-coded real-time log output

### Previous GUI Versions

```bash
python gui_apps/run_gui_rev003.py      # 3-panel Studio layout
python gui_apps/run_gui_rev002.py      # Multilingual subtitle support
python gui_apps/run_gui.py             # Original simple GUI
```

---

## CLI

### Run the Full Pipeline

```bash
python main.py
```

### Run Individual Steps

```bash
python main.py --step 1       # Extract slides (text + images)
python main.py --step 2       # Transcribe audio via Whisper
python main.py --step 3       # Match slides to audio (Ollama)
python main.py --step 4       # Generate MP4 video (FFmpeg)
python main.py --step 3 4     # Steps 3 and 4 together
```

### Review Cuesheet Before Generating Video

```bash
python main.py --edit-cuesheet
```

Displays the current cuesheet and prompts for confirmation before
generating the video.  Edit `output/cuesheet.json` manually to adjust
slide timing, then run Step 4 alone:

```bash
python main.py --step 4
```

---

## Configuration

All settings are stored in `config.yaml` at the project root.

### Minimal Configuration

```yaml
audio_file: "input/podcast.mp3"
slides_file: "input/slides.pptx"
```

### Full Configuration Reference

```yaml
# --- Input ---
audio_file: "input/podcast.mp3"       # Audio file path
slides_file: "input/slides.pptx"      # Slides path (.pptx or .pdf)
output_dir: "output"                   # Output directory
output_video: "output/podcast_video.mp4"

# --- Ollama LLM ---
ollama:
  model: "gemma3:27b"                 # Model name (ollama list)
  base_url: "http://localhost:11434"   # Ollama API endpoint

# --- Whisper ---
whisper:
  model: "small"                       # tiny / base / small / medium / large
  language: "ja"                       # ja / ko / en / auto

# --- Video ---
video:
  width: 1920
  height: 1080
  fps: 24

# --- Subtitles ---
subtitle:
  generate_srt: true                   # Generate subtitles.srt
  burn_in: false                       # Burn subtitles into video
  font_size: 42
  margin_bottom: 80

# --- OCR (Step 1) ---
ocr:
  languages: ["ja", "en"]
```

---

## Output Files

After a successful run, the `output/` directory contains:

| File | Step | Description |
|------|------|-------------|
| `slide_images/` | 1 | PNG images per slide |
| `slides_info.json` | 1 | Slide metadata (text, image paths) |
| `transcript.json` | 2 | Timestamped segments |
| `transcript.txt` | 2 | Human-readable transcript |
| `cuesheet.json` | 3 | Slide timing (editable) |
| `cuesheet.csv` | 3 | CSV version of cuesheet |
| `subtitles.srt` | 4 | SRT file for Filmora import |
| `podcast_video.mp4` | 4 | Final video |
| `debug_prompt.txt` | 3 | LLM prompt (debug) |
| `debug_llm_response.txt` | 3 | LLM response (debug) |

---

## Filmora Workflow

1. Import `output/podcast_video.mp4` into Filmora
2. Import `output/subtitles.srt` via *Subtitles → Import Local Subtitle File*
3. Add transitions, captions, intros/outros
4. Export final video

---

## Troubleshooting

### "Cannot connect to Ollama"

Start Ollama first:

```bash
ollama serve
```

### "Model not found"

Check available models and pull the one you need:

```bash
ollama list
ollama pull gemma3:27b
```

### PPTX image export fails

Save your slides as PDF and update `config.yaml`:

```yaml
slides_file: "input/slides.pdf"
```

### Matching results are wrong

Edit `output/cuesheet.json` manually (adjust `start_time` / `end_time`),
then regenerate the video:

```bash
python main.py --step 4
```

### Out of memory (Whisper)

Use a smaller model:

```yaml
whisper:
  model: "tiny"    # or "base"
```

### Japanese folder names cause errors

This was fixed in v0.4.1.  All paths are handled as absolute paths with
explicit UTF-8 encoding.  No action needed.
