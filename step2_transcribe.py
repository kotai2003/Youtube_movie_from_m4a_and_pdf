"""
Step 2 — Audio Transcription

Transcribes audio files using OpenAI Whisper (local model, not API).
Produces timestamped segments and saves them as JSON and plain text.
Supports Japanese, Korean, and English (auto-detected or manually set).
"""

import os
import json


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
    
    # 文字起こし実行
    print(f"  文字起こし実行中...")
    result = model.transcribe(
        audio_file,
        language=language,
        verbose=False
    )
    
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
