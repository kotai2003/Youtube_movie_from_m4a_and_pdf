"""
Step 2 — Audio Transcription

Transcribes audio files using OpenAI Whisper (local model, not API).
Produces timestamped segments and saves them as JSON and plain text.
Supports Japanese, Korean, and English (auto-detected or manually set).
"""

import os
import sys
import json
import shutil
import tempfile


def _ascii_safe_audio(audio_path: str):
    """Return an ASCII-only path for *audio_path*, copying if necessary.

    Some FFmpeg builds on Windows fail to open files whose path contains
    Japanese / non-ASCII characters, which breaks Whisper audio loading.
    On Windows, when the path is not ASCII-only we copy the file to the
    system temp directory and use that copy.

    Returns
    -------
    tuple[str, str | None]
        ``(path_to_use, tmp_to_cleanup)``.  ``tmp_to_cleanup`` is the
        caller's responsibility to remove; ``None`` when no copy was
        required.
    """
    if not audio_path or sys.platform != "win32":
        return audio_path, None
    try:
        audio_path.encode("ascii")
        return audio_path, None
    except UnicodeEncodeError:
        pass
    try:
        ext = os.path.splitext(audio_path)[1]
        fd, tmp = tempfile.mkstemp(suffix=ext, prefix="podcast_ai_")
        os.close(fd)
        shutil.copy2(audio_path, tmp)
        return tmp, tmp
    except Exception:
        return audio_path, None


def transcribe_audio(audio_file: str, output_dir: str,
                     model_name: str = "small", language: str = "ja") -> list[dict]:
    """Transcribe audio with Whisper and return timestamped segments.

    Parameters
    ----------
    audio_file : str
        Path to the audio file (mp3, m4a, wav, ogg, flac).
    output_dir : str
        Directory where ``transcript.json`` and ``transcript.txt``
        are written.
    model_name : str
        Whisper model size (``tiny``, ``base``, ``small``,
        ``medium``, ``large``).
    language : str
        Language code (``ja``, ``ko``, ``en``, or ``auto``).

    Returns
    -------
    list[dict]
        Segments with keys ``start`` (float), ``end`` (float),
        ``text`` (str).
    """
    import whisper
    
    print(f"\n{'='*50}")
    print(f"ステップ2: 音声文字起こし")
    print(f"{'='*50}")
    print(f"  モデル: {model_name}")
    print(f"  言語: {language}")
    print(f"  ファイル: {audio_file}")
    print(f"  (初回はモデルのダウンロードに数分かかります)")
    
    # モデルロード
    print(f"\n  モデルをロード中...")
    model = whisper.load_model(model_name)

    # Whisper は内部で ffmpeg を呼ぶ。Windows では ffmpeg ビルドによって
    # 日本語ファイル名で失敗するため、必要に応じて ASCII 一時コピーを使う。
    audio_for_whisper, tmp_audio = _ascii_safe_audio(audio_file)
    if tmp_audio:
        print(f"  (日本語パス対策: 一時 ASCII コピーを使用)")

    # 文字起こし実行
    print(f"  文字起こし実行中...")
    try:
        result = model.transcribe(
            audio_for_whisper,
            language=language,
            verbose=False
        )
    finally:
        if tmp_audio:
            try:
                os.remove(tmp_audio)
            except OSError:
                pass
    
    # セグメント整形
    segments = []
    for seg in result["segments"]:
        segments.append({
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip()
        })
    
    # 結果保存
    transcript_path = os.path.join(output_dir, "transcript.json")
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)
    
    # 読みやすいテキスト版も保存
    txt_path = os.path.join(output_dir, "transcript.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        for seg in segments:
            start_m, start_s = divmod(int(seg["start"]), 60)
            end_m, end_s = divmod(int(seg["end"]), 60)
            f.write(f"[{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}] {seg['text']}\n")
    
    # 音声の総再生時間
    total_sec = segments[-1]["end"] if segments else 0
    total_m, total_s = divmod(int(total_sec), 60)
    
    print(f"\n  → {len(segments)} セグメントを抽出")
    print(f"  → 音声長: {total_m:02d}:{total_s:02d}")
    print(f"  → JSON: {transcript_path}")
    print(f"  → テキスト: {txt_path}")
    
    return segments


if __name__ == "__main__":
    import yaml
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    os.makedirs(config["output_dir"], exist_ok=True)
    transcribe_audio(
        config["audio_file"],
        config["output_dir"],
        model_name=config["whisper"]["model"],
        language=config["whisper"]["language"]
    )
