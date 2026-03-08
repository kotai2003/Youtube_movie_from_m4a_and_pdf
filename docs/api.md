# API Reference

Auto-generated documentation from Python docstrings.

---

## Pipeline Orchestrator

::: main
    options:
      show_if_no_docstring: false
      members:
        - load_config
        - load_transcript
        - run_step1
        - run_step2
        - run_step3
        - run_step4
        - edit_cuesheet_interactive
        - main

---

## Step 1 — Slide Extraction

::: step1_extract_slides
    options:
      show_if_no_docstring: false
      members:
        - extract_slides
        - extract_from_pptx
        - extract_from_pdf

---

## Step 2 — Audio Transcription

::: step2_transcribe
    options:
      show_if_no_docstring: false
      members:
        - transcribe_audio

---

## Step 3 — Slide-Audio Matching

::: step3_match
    options:
      show_if_no_docstring: false
      members:
        - match_slides_to_audio

---

## Step 4 — Video Generation

::: step4_generate_video
    options:
      show_if_no_docstring: false
      members:
        - generate_video

---

## Subtitle Generator

::: subtitle_generator
    options:
      show_if_no_docstring: false
      members:
        - generate_srt
        - create_subtitle_clips

---

## GUI — App

::: gui_apps.gui_app
    options:
      show_if_no_docstring: false
      members:
        - App
        - load_config
        - save_config
        - main

---

## GUI — Ollama Utilities

::: gui_apps.ollama_utils
    options:
      show_if_no_docstring: false
      members:
        - get_ollama_models
