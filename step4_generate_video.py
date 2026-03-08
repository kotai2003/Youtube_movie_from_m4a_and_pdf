"""
Step 4 — Video Generation

Generates the final MP4 video from a cuesheet, slide images, and audio
using FFmpeg.  Creates per-slide video segments, concatenates them, then
muxes with the audio track.  Optionally burns in SRT subtitles.

Much faster than the moviepy-based approach used in earlier versions.
"""

import os
import json
import subprocess
import shutil


def _check_ffmpeg():
    """FFmpegが利用可能か確認"""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "FFmpegが見つかりません。\n"
            "  → https://www.gyan.dev/ffmpeg/builds/ からダウンロードしてPATHを通してください。"
        )


def _to_ffmpeg_path(path: str) -> str:
    """Windowsのバックスラッシュをスラッシュに変換（FFmpeg用）"""
    return path.replace("\\", "/")


def _format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def generate_video(cuesheet: list[dict], audio_file: str, output_path: str,
                   video_config: dict, transcript_segments: list[dict] = None,
                   subtitle_config: dict = None) -> str:
    """Generate an MP4 video using FFmpeg.

    For each cuesheet entry a still-image video segment is created, then
    all segments are concatenated and muxed with the audio.

    Parameters
    ----------
    cuesheet : list[dict]
        Slide timing entries (``slide_number``, ``start_time``,
        ``end_time``, ``image_path``).
    audio_file : str
        Path to the source audio file.
    output_path : str
        Destination path for the output ``.mp4``.
    video_config : dict
        Video settings — ``width``, ``height``, ``fps``.
    transcript_segments : list[dict], optional
        Transcript segments for subtitle generation.
    subtitle_config : dict, optional
        Subtitle settings — ``generate_srt``, ``burn_in``, etc.

    Returns
    -------
    str
        Path to the generated video file.
    """

    width = video_config.get("width", 1920)
    height = video_config.get("height", 1080)
    fps = video_config.get("fps", 24)

    print(f"\n{'='*50}")
    print(f"ステップ4: 動画生成（FFmpeg高速モード）")
    print(f"{'='*50}")
    print(f"  解像度: {width}x{height}")
    print(f"  FPS: {fps}")

    _check_ffmpeg()

    # 音声の長さを取得
    probe_cmd = [
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_file
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    total_duration = float(result.stdout.strip())
    print(f"  音声長: {_format_time(total_duration)}")

    # 最後のスライドの終了時間を音声の最後に合わせる
    if cuesheet:
        cuesheet[-1]["end_time"] = max(cuesheet[-1]["end_time"], total_duration)

    # 一時ディレクトリ（絶対パスで管理）
    output_abs = os.path.abspath(os.path.dirname(output_path) or ".")
    temp_dir = os.path.join(output_abs, "_temp_segments")
    os.makedirs(temp_dir, exist_ok=True)

    # 各スライドを動画セグメントに変換
    print(f"\n  スライドセグメントを生成中...")
    segment_files = []

    for i, entry in enumerate(cuesheet):
        start = entry["start_time"]
        end = entry["end_time"]
        img_path = entry.get("image_path")
        slide_num = entry.get("slide_number", i + 1)
        duration = end - start

        if duration <= 0:
            print(f"  [WARN] スライド{slide_num}: duration={duration}、スキップ")
            continue

        segment_path = os.path.join(temp_dir, f"seg_{i:03d}.mp4")

        if not img_path or not os.path.exists(img_path):
            print(f"  [WARN] スライド{slide_num}: 画像なし、黒背景を使用")
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"color=c=black:s={width}x{height}:d={duration}:r={fps}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "ultrafast", "-tune", "stillimage",
                segment_path
            ]
        else:
            img_abs = os.path.abspath(img_path)
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", img_abs,
                "-t", str(duration),
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                "-r", str(fps),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "ultrafast", "-tune", "stillimage",
                segment_path
            ]

        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            print(f"  [ERROR] セグメント{i}: {proc.stderr[-200:]}")
        else:
            segment_files.append(segment_path)

        start_str = _format_time(start)
        end_str = _format_time(end)
        print(f"  スライド{slide_num:2d} | {start_str} - {end_str} | {duration:.1f}秒")

    # concatリストファイル作成
    concat_list_path = os.path.join(temp_dir, "concat_list.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for seg_path in segment_files:
            # Use filename only (relative to concat file dir) to avoid
            # Japanese/Unicode characters in parent path breaking FFmpeg
            seg_name = os.path.basename(seg_path)
            f.write(f"file '{seg_name}'\n")

    # セグメントを結合
    print(f"\n  セグメントを結合中...")
    merged_video = os.path.join(temp_dir, "merged_video.mp4")
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        merged_video
    ]
    proc = subprocess.run(concat_cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(f"  [ERROR] 結合エラー: {proc.stderr[-300:]}")

    # 音声と合成
    print(f"  音声を合成中...")
    output_abs_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_abs_path) if os.path.dirname(output_abs_path) else ".", exist_ok=True)

    audio_abs = os.path.abspath(audio_file)
    merged_abs = os.path.abspath(merged_video)

    # 字幕焼き込みチェック
    subtitle_config = subtitle_config or {}
    burn_subtitles = subtitle_config.get("burn_in", False)
    srt_path = os.path.join(os.path.dirname(output_abs_path), "subtitles.srt")

    if burn_subtitles and os.path.exists(srt_path):
        font_size = subtitle_config.get("font_size", 42)
        margin_bottom = subtitle_config.get("margin_bottom", 80)
        srt_escaped = _to_ffmpeg_path(srt_path).replace(":", "\\:")

        mux_cmd = [
            "ffmpeg", "-y",
            "-i", merged_abs,
            "-i", audio_abs,
            "-vf", f"subtitles={srt_escaped}:force_style='FontSize={font_size},MarginV={margin_bottom},FontName=Meiryo,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2'",
            "-c:v", "libx264", "-preset", "medium",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_abs_path
        ]
    else:
        mux_cmd = [
            "ffmpeg", "-y",
            "-i", merged_abs,
            "-i", audio_abs,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_abs_path
        ]

    proc = subprocess.run(mux_cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(f"  [ERROR] 合成エラー: {proc.stderr[-500:]}")

    # 一時ファイル削除
    print(f"  一時ファイルを削除中...")
    shutil.rmtree(temp_dir, ignore_errors=True)

    # 結果表示
    if os.path.exists(output_abs_path):
        file_size_mb = os.path.getsize(output_abs_path) / (1024 * 1024)
        print(f"\n  → 動画生成完了!")
        print(f"  → ファイル: {output_path}")
        print(f"  → サイズ: {file_size_mb:.1f} MB")
        print(f"  → 長さ: {_format_time(total_duration)}")
    else:
        print(f"\n  [ERROR] 動画の生成に失敗しました。")

    return output_path


if __name__ == "__main__":
    import yaml
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    with open(os.path.join(config["output_dir"], "cuesheet.json"), "r", encoding="utf-8") as f:
        cuesheet = json.load(f)

    transcript_segments = None
    subtitle_config = config.get("subtitle", {})
    transcript_path = os.path.join(config["output_dir"], "transcript.json")
    if os.path.exists(transcript_path):
        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript_segments = json.load(f)

    generate_video(
        cuesheet,
        config["audio_file"],
        config["output_video"],
        config["video"],
        transcript_segments=transcript_segments,
        subtitle_config=subtitle_config
    )
