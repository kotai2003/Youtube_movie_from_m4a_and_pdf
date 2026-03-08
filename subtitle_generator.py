"""
Subtitle Generator

Provides two subtitle generation strategies:

- **SRT file generation** — Creates standard ``.srt`` files for import
  into Filmora or other video editors.
- **Pillow-based subtitle images** — Renders subtitle overlays as
  transparent PNG images for use with moviepy (currently unused in
  the FFmpeg pipeline).
"""

import os
import json
from PIL import Image as PILImage, ImageDraw, ImageFont


def _format_srt_time(seconds: float) -> str:
    """秒数をSRT形式 (HH:MM:SS,mmm) に変換"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(segments: list[dict], output_path: str) -> str:
    """Generate an SRT subtitle file from transcript segments.

    The resulting file can be imported into Filmora via
    *Subtitles → Import Local Subtitle File*.

    Parameters
    ----------
    segments : list[dict]
        Transcript segments (``start``, ``end``, ``text``).
    output_path : str
        Destination ``.srt`` file path.

    Returns
    -------
    str
        The *output_path* that was written.
    """
    print(f"\n  SRTファイル生成中...")
    
    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start = _format_srt_time(seg["start"])
            end = _format_srt_time(seg["end"])
            text = seg["text"].strip()
            
            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n")
            f.write(f"\n")
    
    print(f"  → SRT: {output_path}")
    print(f"  → Filmoraで「字幕 > ローカルの字幕ファイルをインポート」で読み込めます")
    return output_path


def _get_font(font_size: int):
    """日本語対応フォントを取得"""
    # Windows日本語フォント候補
    font_paths = [
        "C:/Windows/Fonts/meiryo.ttc",      # メイリオ
        "C:/Windows/Fonts/msgothic.ttc",     # MSゴシック
        "C:/Windows/Fonts/YuGothM.ttc",      # 游ゴシック
        "C:/Windows/Fonts/BIZ-UDGothicR.ttc",# BIZ UDゴシック
        "C:/Windows/Fonts/arial.ttf",        # フォールバック
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                continue
    
    # どれも見つからない場合はデフォルト
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int, draw: ImageDraw) -> list[str]:
    """テキストを指定幅で折り返す"""
    lines = []
    current_line = ""
    
    for char in text:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font)
        width = bbox[2] - bbox[0]
        
        if width > max_width and current_line:
            lines.append(current_line)
            current_line = char
        else:
            current_line = test_line
    
    if current_line:
        lines.append(current_line)
    
    return lines


def create_subtitle_clips(segments: list[dict], video_width: int, video_height: int,
                          font_size: int = 42, margin_bottom: int = 80,
                          bg_opacity: int = 160):
    """Render subtitle overlays as moviepy ImageClips using Pillow.

    This avoids the ImageMagick dependency of moviepy's ``TextClip``.
    Currently unused in the FFmpeg-based pipeline but retained for
    compatibility.

    Parameters
    ----------
    segments : list[dict]
        Transcript segments (``start``, ``end``, ``text``).
    video_width : int
        Video width in pixels.
    video_height : int
        Video height in pixels.
    font_size : int
        Font size for subtitle text (default 42).
    margin_bottom : int
        Bottom margin in pixels (default 80).
    bg_opacity : int
        Opacity of the semi-transparent background (0–255, default 160).

    Returns
    -------
    list
        List of moviepy ``ImageClip`` objects positioned in time.
    """
    from moviepy.editor import ImageClip
    import numpy as np
    
    font = _get_font(font_size)
    clips = []
    
    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue
        
        start = seg["start"]
        end = seg["end"]
        duration = end - start
        
        if duration <= 0:
            continue
        
        # 透明画像を作成
        img = PILImage.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # テキスト折り返し
        max_text_width = video_width - 200  # 左右100pxマージン
        lines = _wrap_text(text, font, max_text_width, draw)
        
        if not lines:
            continue
        
        # テキスト全体のサイズ計算
        line_height = font_size + 8
        total_text_height = len(lines) * line_height
        
        # 背景矩形の位置（画面下部）
        bg_y = video_height - margin_bottom - total_text_height - 20
        bg_x = 50
        bg_width = video_width - 100
        bg_height = total_text_height + 20
        
        # 半透明背景を描画
        bg_overlay = PILImage.new("RGBA", (bg_width, bg_height), (0, 0, 0, bg_opacity))
        img.paste(bg_overlay, (bg_x, bg_y), bg_overlay)
        
        # テキスト描画
        draw = ImageDraw.Draw(img)
        y = bg_y + 10
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (video_width - text_width) // 2  # 中央揃え
            
            # 影（読みやすさ向上）
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 255))
            # 本文
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
            y += line_height
        
        # numpy配列に変換
        img_array = np.array(img)
        
        # ImageClipとして作成
        clip = (ImageClip(img_array, ismask=False, transparent=True)
                .set_duration(duration)
                .set_start(start))
        
        clips.append(clip)
    
    return clips


if __name__ == "__main__":
    """単体テスト: SRTファイル生成"""
    import yaml
    
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    transcript_path = os.path.join(config["output_dir"], "transcript.json")
    with open(transcript_path, "r", encoding="utf-8") as f:
        segments = json.load(f)
    
    srt_path = os.path.join(config["output_dir"], "subtitles.srt")
    generate_srt(segments, srt_path)
