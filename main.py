"""
Podcast Video Generator — Main Orchestrator

Orchestrates the 4-step pipeline that converts podcast audio and
presentation slides into an MP4 video with timed slide transitions.

Usage:
    python main.py                  # Run all steps
    python main.py --step 1         # Step 1 only
    python main.py --step 3         # Step 3 only (reuse prior results)
    python main.py --step 3 4       # Steps 3 and 4
    python main.py --edit-cuesheet  # Review cuesheet, then generate video

Steps:
    1. Extract slides (text + images) from PPTX / PDF
    2. Transcribe audio via Whisper (timestamped segments)
    3. Match slides to audio via Ollama LLM → cuesheet
    4. Generate MP4 video via FFmpeg
"""

import os
import sys
import json
import argparse
import yaml


def load_config(config_path: str = "config.yaml") -> dict:
    """Load the YAML configuration file.

    Parameters
    ----------
    config_path : str
        Path to the YAML configuration file (default ``config.yaml``).

    Returns
    -------
    dict
        Parsed configuration dictionary.
    """
    if not os.path.exists(config_path):
        print(f"[ERROR] 設定ファイルが見つかりません: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_transcript(output_dir: str) -> list[dict]:
    """Load the transcript JSON produced by Step 2.

    Parameters
    ----------
    output_dir : str
        Directory containing ``transcript.json``.

    Returns
    -------
    list[dict] or None
        List of ``{"start", "end", "text"}`` segment dicts, or *None*
        if the file does not exist.
    """
    path = os.path.join(output_dir, "transcript.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_step1(config: dict) -> list[dict]:
    """Run Step 1 — extract text and images from slides.

    Parameters
    ----------
    config : dict
        Full configuration dictionary (needs ``slides_file``,
        ``output_dir``, and optional ``ocr.languages``).

    Returns
    -------
    list[dict]
        Per-slide information (number, title, text, image path).
    """
    from step1_extract_slides import extract_slides

    if not os.path.exists(config["slides_file"]):
        print(f"[ERROR] スライドファイルが見つかりません: {config['slides_file']}")
        sys.exit(1)

    ocr_langs = config.get("ocr", {}).get("languages", ["ja", "en"])
    return extract_slides(config["slides_file"], config["output_dir"], ocr_langs)


def run_step2(config: dict) -> list[dict]:
    """Run Step 2 — transcribe audio via Whisper.

    Parameters
    ----------
    config : dict
        Full configuration dictionary (needs ``audio_file``,
        ``output_dir``, ``whisper.model``, ``whisper.language``).

    Returns
    -------
    list[dict]
        Timestamped transcript segments.
    """
    from step2_transcribe import transcribe_audio

    if not os.path.exists(config["audio_file"]):
        print(f"[ERROR] 音声ファイルが見つかりません: {config['audio_file']}")
        sys.exit(1)

    return transcribe_audio(
        config["audio_file"],
        config["output_dir"],
        model_name=config["whisper"]["model"],
        language=config["whisper"]["language"]
    )


def run_step3(config: dict, slides_info: list = None, segments: list = None) -> list[dict]:
    """Run Step 3 — match slides to audio via Ollama LLM.

    Parameters
    ----------
    config : dict
        Full configuration dictionary.
    slides_info : list, optional
        Output of Step 1.  Loaded from JSON if *None*.
    segments : list, optional
        Output of Step 2.  Loaded from JSON if *None*.

    Returns
    -------
    list[dict]
        Cuesheet entries with slide timing.
    """
    from step3_match import match_slides_to_audio

    if slides_info is None:
        path = os.path.join(config["output_dir"], "slides_info.json")
        if not os.path.exists(path):
            print(f"[ERROR] {path} が見つかりません。先にステップ1を実行してください。")
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            slides_info = json.load(f)

    if segments is None:
        path = os.path.join(config["output_dir"], "transcript.json")
        if not os.path.exists(path):
            print(f"[ERROR] {path} が見つかりません。先にステップ2を実行してください。")
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            segments = json.load(f)

    return match_slides_to_audio(
        slides_info, segments, config["output_dir"], config["ollama"]
    )


def run_step4(config: dict, cuesheet: list = None) -> str:
    """Run Step 4 — generate the final MP4 video via FFmpeg.

    Parameters
    ----------
    config : dict
        Full configuration dictionary.
    cuesheet : list, optional
        Output of Step 3.  Loaded from JSON if *None*.

    Returns
    -------
    str
        Path to the generated video file.
    """
    from step4_generate_video import generate_video
    from subtitle_generator import generate_srt

    if cuesheet is None:
        path = os.path.join(config["output_dir"], "cuesheet.json")
        if not os.path.exists(path):
            print(f"[ERROR] {path} が見つかりません。先にステップ3を実行してください。")
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            cuesheet = json.load(f)

    subtitle_config = config.get("subtitle", {})
    transcript_segments = load_transcript(config["output_dir"])

    if subtitle_config.get("generate_srt", True) and transcript_segments:
        srt_path = os.path.join(config["output_dir"], "subtitles.srt")
        generate_srt(transcript_segments, srt_path)

    return generate_video(
        cuesheet,
        config["audio_file"],
        config["output_video"],
        config["video"],
        transcript_segments=transcript_segments,
        subtitle_config=subtitle_config
    )


def edit_cuesheet_interactive(config: dict):
    path = os.path.join(config["output_dir"], "cuesheet.json")

    if not os.path.exists(path):
        print(f"[ERROR] {path} が見つかりません。先にステップ3を実行してください。")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        cuesheet = json.load(f)

    print(f"\n{'='*60}")
    print(f"  現在のキューシート ({path})")
    print(f"{'='*60}")

    for entry in cuesheet:
        sn = entry["slide_number"]
        start = entry.get("start_display", f"{int(entry['start_time'])//60:02d}:{int(entry['start_time'])%60:02d}")
        end = entry.get("end_display", f"{int(entry['end_time'])//60:02d}:{int(entry['end_time'])%60:02d}")
        reason = entry.get("reason", "")
        print(f"  スライド{sn:2d} | {start} - {end} | {reason}")

    print(f"\n  修正が必要な場合は {path} を直接編集してください。")
    answer = input(f"\n  このまま動画を生成しますか？ (y/n): ")
    if answer.lower() in ("y", "yes", ""):
        run_step4(config, cuesheet)
    else:
        print(f"  → 編集後: python main.py --step 4")


def main():
    parser = argparse.ArgumentParser(
        description="ポッドキャスト動画生成ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python main.py                  # 全ステップ実行
  python main.py --step 1         # スライド抽出のみ（OCR付き）
  python main.py --step 2         # 文字起こしのみ
  python main.py --step 3         # マッチングのみ
  python main.py --step 4         # 動画生成のみ（SRT + 動画）
  python main.py --step 3 4       # マッチング → 動画生成
  python main.py --edit-cuesheet  # キューシート確認 → 動画生成
        """
    )
    parser.add_argument("--step", nargs="+", type=int, choices=[1, 2, 3, 4],
                        help="実行するステップ番号（複数指定可）")
    parser.add_argument("--config", default="config.yaml",
                        help="設定ファイルのパス（デフォルト: config.yaml）")
    parser.add_argument("--edit-cuesheet", action="store_true",
                        help="キューシートを確認してから動画生成")

    args = parser.parse_args()
    config = load_config(args.config)

    os.makedirs(config["output_dir"], exist_ok=True)
    os.makedirs("input", exist_ok=True)

    print(r"""
    ╔══════════════════════════════════════════╗
    ║   ポッドキャスト動画生成ツール           ║
    ╚══════════════════════════════════════════╝
    """)

    if args.edit_cuesheet:
        edit_cuesheet_interactive(config)
        return

    if args.step:
        steps = sorted(args.step)
        slides_info = None
        segments = None
        cuesheet = None

        for step in steps:
            if step == 1:
                slides_info = run_step1(config)
            elif step == 2:
                segments = run_step2(config)
            elif step == 3:
                cuesheet = run_step3(config, slides_info, segments)
            elif step == 4:
                run_step4(config, cuesheet)
        return

    # 全ステップ
    print("  全ステップを順次実行します...\n")

    slides_info = run_step1(config)
    segments = run_step2(config)
    cuesheet = run_step3(config, slides_info, segments)
    run_step4(config, cuesheet)

    print(f"\n{'='*50}")
    print(f"  ✓ すべて完了!")
    print(f"  → 動画: {config['output_video']}")
    print(f"  → 字幕: output/subtitles.srt")
    print(f"  → Filmoraに動画を読み込み、字幕はSRTをインポートして仕上げてください")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
