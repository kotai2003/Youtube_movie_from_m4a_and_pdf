"""
Step 3 — Slide-Audio Matching

Sends slide text and transcript to a local Ollama LLM to determine when
each slide should appear in the video.  Produces a cuesheet (JSON + CSV)
with start/end times per slide.

Includes JSON repair logic, validation, and fallback to equal-duration
distribution if the LLM output is unusable.
"""

import os
import json
import re
import requests
import time


def _format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _build_prompt(slides_info: list[dict], segments: list[dict]) -> str:
    num_slides = len(slides_info)
    total_duration = segments[-1]["end"] if segments else 0

    slides_text = ""
    for s in slides_info:
        slides_text += f"  スライド{s['slide_number']}: 「{s['title'][:60]}」\n"
        body = s['full_text'][:150]
        if body:
            slides_text += f"    内容: {body}\n"

    # 30秒チャンク化
    transcript_text = ""
    chunk_duration = 30
    chunk_start = 0
    chunk_texts = []

    for seg in segments:
        if seg["start"] >= chunk_start + chunk_duration and chunk_texts:
            start_str = _format_time(chunk_start)
            end_str = _format_time(seg["start"])
            combined = "".join(chunk_texts)
            transcript_text += f"  [{start_str}-{end_str}] {combined}\n"
            chunk_start = seg["start"]
            chunk_texts = []
        chunk_texts.append(seg["text"])

    if chunk_texts:
        start_str = _format_time(chunk_start)
        end_str = _format_time(segments[-1]["end"])
        combined = "".join(chunk_texts)
        transcript_text += f"  [{start_str}-{end_str}] {combined}\n"

    prompt = f"""/no_think
あなたはポッドキャスト動画の制作アシスタントです。
音声の文字起こしを読み、各スライドを表示すべき時間範囲を決定してください。

【重要な制約】
- スライドは全部で{num_slides}枚。必ず{num_slides}個のエントリを出力。
- slide_numberは1から{num_slides}の連番。
- 音声の総再生時間は{total_duration:.1f}秒（{_format_time(total_duration)}）。
- スライド1のstart_timeは0.0。スライド{num_slides}のend_timeは{total_duration:.1f}。
- 各スライドの時間範囲は隙間なく連続（前のend = 次のstart）。
- 音声内容とスライドテキストを照合し、話題が切り替わるポイントで区切る。

【スライド一覧（{num_slides}枚）】
{slides_text}

【音声文字起こし（総{_format_time(total_duration)}）】
{transcript_text}

以下のJSON配列のみ出力してください。説明文不要。必ず{num_slides}個。
start_timeとend_timeは秒数（小数点1桁）で指定してください。

[
{{"slide_number":1,"start_time":0.0,"end_time":XX.X,"reason":"短い理由"}},
{{"slide_number":2,"start_time":XX.X,"end_time":XX.X,"reason":"短い理由"}},
...
{{"slide_number":{num_slides},"start_time":XX.X,"end_time":{total_duration:.1f},"reason":"短い理由"}}
]"""

    return prompt


def _call_ollama(prompt: str, base_url: str, model: str) -> str:
    url = f"{base_url}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 4096
        }
    }

    print(f"  Ollama ({model}) にリクエスト中...")
    start_time = time.time()

    try:
        response = requests.post(url, json=payload, timeout=600)
        response.raise_for_status()
    except requests.ConnectionError:
        raise ConnectionError(
            f"Ollamaに接続できません ({base_url})。\n"
            f"  → ollama serve で起動しているか確認してください。"
        )
    except requests.Timeout:
        raise TimeoutError("Ollamaの応答がタイムアウトしました。")

    elapsed = time.time() - start_time
    print(f"  → 応答受信 ({elapsed:.1f}秒)")

    return response.json()["response"]


def _repair_json(text: str) -> str:
    """壊れたJSONを可能な限り修復する"""

    # JSONブロックを抽出
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    # [ ] の範囲を抽出
    start_idx = text.find("[")
    end_idx = text.rfind("]")
    if start_idx != -1 and end_idx != -1:
        text = text[start_idx:end_idx + 1]

    # まずそのまま試す
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # 修復戦略1: 各行から slide_number, start_time, end_time を正規表現で抽出
    print("  [FIX] JSONが壊れています。正規表現で修復を試みます...")
    entries = []

    # パターン: slide_number と start_time と end_time を探す
    # 様々な壊れ方に対応
    pattern = re.compile(
        r'"?slide_number"?\s*[:=]\s*(\d+).*?'
        r'"?start_time"?\s*[:=]\s*([\d.]+).*?'
        r'"?end_time"?\s*[:=]\s*([\d.]+)',
        re.DOTALL
    )

    for match in pattern.finditer(text):
        slide_num = int(match.group(1))
        start_time = float(match.group(2))
        end_time = float(match.group(3))

        # reasonも可能なら抽出
        reason = ""
        reason_match = re.search(
            r'"?reason"?\s*[:=]\s*"([^"]*)"',
            match.group(0) + text[match.end():match.end()+200]
        )
        if reason_match:
            reason = reason_match.group(1)

        entries.append({
            "slide_number": slide_num,
            "start_time": start_time,
            "end_time": end_time,
            "reason": reason
        })

    if entries:
        print(f"  [FIX] → {len(entries)}個のエントリを復元しました")
        return json.dumps(entries, ensure_ascii=False)

    # 修復戦略2: 数値の組み合わせだけでも抽出を試みる
    print("  [FIX] 正規表現でも抽出できませんでした")
    return text


def _parse_cuesheet(response_text: str, slides_info: list[dict]) -> list[dict]:
    """LLMの応答からキューシートをパース（修復ロジック付き）"""

    repaired_text = _repair_json(response_text)

    try:
        cuesheet = json.loads(repaired_text)
    except json.JSONDecodeError as e:
        print(f"  [WARN] JSON修復後もパース失敗: {e}")
        raise ValueError("LLMの応答をJSONとして解析できませんでした。再実行してください。")

    # 画像パス・表示用時間を追加
    slide_map = {s["slide_number"]: s for s in slides_info}
    for entry in cuesheet:
        sn = entry.get("slide_number", 0)
        if sn in slide_map and slide_map[sn].get("image_path"):
            entry["image_path"] = slide_map[sn]["image_path"]
        entry["start_display"] = _format_time(entry.get("start_time", 0))
        entry["end_display"] = _format_time(entry.get("end_time", 0))

    return cuesheet


def _validate_and_fix_cuesheet(cuesheet: list[dict], slides_info: list[dict],
                                total_duration: float) -> list[dict]:
    """キューシートを検証し、問題があれば修正する"""
    num_slides = len(slides_info)
    slide_map = {s["slide_number"]: s for s in slides_info}

    # 存在するスライド番号のエントリのみ残す
    valid_entries = [e for e in cuesheet if 1 <= e.get("slide_number", 0) <= num_slides]

    # 重複を除去（同じslide_numberが複数ある場合は最初のものを使う）
    seen = set()
    deduped = []
    for e in valid_entries:
        sn = e["slide_number"]
        if sn not in seen:
            seen.add(sn)
            deduped.append(e)
    valid_entries = deduped

    # slide_numberでソート
    valid_entries.sort(key=lambda e: e["slide_number"])

    needs_fallback = False

    if len(valid_entries) != num_slides:
        print(f"  [FIX] スライド数不一致: 復元={len(valid_entries)}個, 期待={num_slides}個")
        needs_fallback = True

    if not needs_fallback and valid_entries:
        last_end = valid_entries[-1].get("end_time", 0)
        if last_end < total_duration * 0.5:
            print(f"  [FIX] 音声の{last_end/total_duration*100:.0f}%しかカバーされていません")
            needs_fallback = True

    if needs_fallback:
        print(f"  [FIX] 均等分配で再生成します...")
        duration_per_slide = total_duration / num_slides
        valid_entries = []
        for i in range(num_slides):
            sn = i + 1
            entry = {
                "slide_number": sn,
                "start_time": round(i * duration_per_slide, 1),
                "end_time": round((i + 1) * duration_per_slide, 1),
                "reason": "均等分配（フォールバック）",
                "start_display": _format_time(i * duration_per_slide),
                "end_display": _format_time((i + 1) * duration_per_slide)
            }
            if sn in slide_map and slide_map[sn].get("image_path"):
                entry["image_path"] = slide_map[sn]["image_path"]
            valid_entries.append(entry)
    else:
        # 時間の連続性を確保
        for i in range(1, len(valid_entries)):
            valid_entries[i]["start_time"] = valid_entries[i - 1]["end_time"]
            valid_entries[i]["start_display"] = _format_time(valid_entries[i]["start_time"])

        # 最初を0に、最後を音声の最後に
        valid_entries[0]["start_time"] = 0.0
        valid_entries[0]["start_display"] = "00:00"
        valid_entries[-1]["end_time"] = total_duration
        valid_entries[-1]["end_display"] = _format_time(total_duration)

    return valid_entries


def match_slides_to_audio(slides_info: list[dict], segments: list[dict],
                          output_dir: str, ollama_config: dict,
                          max_retries: int = 2) -> list[dict]:
    """Match slides to audio segments and generate a cuesheet.

    Sends a prompt to the Ollama LLM containing slide summaries and the
    transcript, then parses the JSON response into a cuesheet.  Retries
    up to *max_retries* times on failure.

    Parameters
    ----------
    slides_info : list[dict]
        Output of Step 1 (slide number, title, text, image path).
    segments : list[dict]
        Output of Step 2 (timestamped transcript segments).
    output_dir : str
        Directory where ``cuesheet.json`` / ``cuesheet.csv`` are written.
    ollama_config : dict
        Ollama settings (``model``, ``base_url``).
    max_retries : int
        Number of LLM retries on parse failure (default 2).

    Returns
    -------
    list[dict]
        Cuesheet entries with ``slide_number``, ``start_time``,
        ``end_time``, ``reason``, etc.
    """

    print(f"\n{'='*50}")
    print(f"ステップ3: スライド ↔ 音声 マッチング")
    print(f"{'='*50}")
    print(f"  スライド数: {len(slides_info)}")
    print(f"  音声セグメント数: {len(segments)}")
    print(f"  モデル: {ollama_config['model']}")

    total_duration = segments[-1]["end"] if segments else 0
    prompt = _build_prompt(slides_info, segments)

    # デバッグ用にプロンプト保存
    with open(os.path.join(output_dir, "debug_prompt.txt"), "w", encoding="utf-8") as f:
        f.write(prompt)

    # リトライループ
    cuesheet = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"\n  --- リトライ {attempt}/{max_retries} ---")

        try:
            response_text = _call_ollama(
                prompt, ollama_config["base_url"], ollama_config["model"]
            )

            # デバッグ用に応答保存
            with open(os.path.join(output_dir, "debug_llm_response.txt"), "w", encoding="utf-8") as f:
                f.write(response_text)

            cuesheet = _parse_cuesheet(response_text, slides_info)

            # パースに成功したら検証
            valid_count = sum(1 for e in cuesheet if 1 <= e.get("slide_number", 0) <= len(slides_info))
            if valid_count >= len(slides_info) * 0.5:
                # 半分以上のスライドが復元できていればOK
                break
            else:
                print(f"  [WARN] 有効なエントリが{valid_count}個しかありません。リトライします...")

        except (ValueError, json.JSONDecodeError) as e:
            print(f"  [WARN] 試行{attempt + 1}失敗: {e}")
            if attempt == max_retries:
                print(f"  [WARN] 全リトライ失敗。均等分配にフォールバックします。")
                cuesheet = []

    # バリデーション＆修正
    cuesheet = _validate_and_fix_cuesheet(cuesheet, slides_info, total_duration)

    # 保存
    cuesheet_path = os.path.join(output_dir, "cuesheet.json")
    with open(cuesheet_path, "w", encoding="utf-8") as f:
        json.dump(cuesheet, f, ensure_ascii=False, indent=2)

    csv_path = os.path.join(output_dir, "cuesheet.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("スライド番号,開始,終了,タイトル,理由\n")
        slide_map = {s["slide_number"]: s for s in slides_info}
        for entry in cuesheet:
            sn = entry["slide_number"]
            title = slide_map.get(sn, {}).get("title", "").replace(",", " ")
            reason = entry.get("reason", "").replace(",", " ")
            f.write(f"{sn},{entry['start_display']},{entry['end_display']},{title},{reason}\n")

    # 表示
    print(f"\n  ── キューシート ──")
    slide_map = {s["slide_number"]: s for s in slides_info}
    for entry in cuesheet:
        sn = entry["slide_number"]
        title = slide_map.get(sn, {}).get("title", "???")[:30]
        print(f"  スライド{sn:2d} | {entry['start_display']} - {entry['end_display']} | {title}")

    print(f"\n  → キューシート: {cuesheet_path}")
    print(f"  → CSV: {csv_path}")

    return cuesheet


if __name__ == "__main__":
    import yaml
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    with open(os.path.join(config["output_dir"], "slides_info.json"), "r", encoding="utf-8") as f:
        slides_info = json.load(f)
    with open(os.path.join(config["output_dir"], "transcript.json"), "r", encoding="utf-8") as f:
        segments = json.load(f)

    match_slides_to_audio(slides_info, segments, config["output_dir"], config["ollama"])
