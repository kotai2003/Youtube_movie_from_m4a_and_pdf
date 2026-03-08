# Podcast AI Studio

ポッドキャストの音声 + スライド（PPTX/PDF）から、スライドが適切なタイミングで切り替わる動画を自動生成するツールです。

Podcast / YouTube講義 / セミナー / 社内教育 / スライド付きナレーション動画の制作に対応しています。

生成された動画をFilmoraに読み込んで、テロップやエフェクトの仕上げ編集を行うワークフローを想定しています。

## 処理の流れ

```
ステップ1: スライド → テキスト抽出 + 画像化
ステップ2: 音声 → Whisperで文字起こし（タイムスタンプ付き）
ステップ3: Ollamaでスライドと音声をマッチング → キューシート生成
ステップ4: 音声 + スライド画像 + キューシート → MP4動画生成
```

## セットアップ

### 1. 前提ソフトウェア

**Ollama**（必須）
https://ollama.com/ からダウンロード・インストール

```bash
# インストール後、モデルをダウンロード
ollama pull gemma3:27b
```

> モデルは `gemma3:27b` を推奨。PCのスペックに応じて `gemma3:12b` や `llama3.1:8b` でも可。
> config.yaml の `ollama.model` を使用するモデル名に合わせてください。

**FFmpeg**（必須）
https://www.gyan.dev/ffmpeg/builds/ から `ffmpeg-release-essentials.zip` をダウンロードし、PATHを通す。

```bash
# 確認
ffmpeg -version
```

### 2. Pythonパッケージ

```bash
cd podcast-video-generator
pip install -r requirements.txt
```

> Whisperの初回実行時にモデルがダウンロードされます（smallモデルで約500MB）

### 3. ファイル配置

```
podcast-video-generator/
├── input/
│   ├── podcast.mp3          ← 音声ファイルをここに置く
│   └── slides.pptx          ← スライドをここに置く（またはslides.pdf）
├── gui_apps/                 ← GUI関連
│   ├── run_gui_app.py     ← メインGUI（推奨）
│   ├── run_gui_rev003.py
│   ├── run_gui_rev002.py
│   ├── run_gui.py
│   ├── gui_app.py
│   └── ollama_utils.py
├── config.yaml               ← パスやモデルを設定
├── main.py                   ← CLIエントリーポイント
├── step1_extract_slides.py
├── step2_transcribe.py
├── step3_match.py
├── step4_generate_video.py
├── subtitle_generator.py
└── old/                      ← 旧バージョン（未使用）
```

### 4. 設定ファイル（config.yaml）

```yaml
audio_file: "input/podcast.mp3"     # 音声ファイルのパス
slides_file: "input/slides.pptx"    # スライドのパス（.pptx or .pdf）
```

最低限、上記2つのパスを正しく設定すれば動作します。

## 使い方

### GUI（推奨）

```bash
# Podcast AI Studio（ダークテーマ・商用ソフト風GUI）
python gui_apps/run_gui_app.py
```

サイドバーナビゲーション、パイプラインステップカード（状態可視化）、スライドプレビュー、字幕プレビュー、カラーログ、ステータスバーを備えた本格的なGUIです。

多言語対応（日本語・韓国語・英語）、Whisper言語自動判定、OllamaモデルGUI選択、プロジェクト管理（最近のプロジェクト保存）に対応しています。

```bash
# 過去バージョンのGUI
python gui_apps/run_gui_rev003.py      # 3パネルStudio版
python gui_apps/run_gui_rev002.py      # 多言語字幕対応版
python gui_apps/run_gui.py             # 初期版
```

### CLI（全ステップ一括）

```bash
python main.py
```

### CLI（ステップごとに実行）

```bash
python main.py --step 1       # スライド抽出のみ
python main.py --step 2       # 文字起こしのみ
python main.py --step 3       # マッチングのみ（ステップ1,2完了後）
python main.py --step 4       # 動画生成のみ（ステップ3完了後）
python main.py --step 3 4     # マッチング → 動画生成
```

### キューシートを確認してから動画生成

```bash
python main.py --edit-cuesheet
```

AIが生成したキューシート（`output/cuesheet.json`）を表示し、確認後に動画を生成します。
タイミングを手動で調整したい場合は、`cuesheet.json` の `start_time` / `end_time` を編集してから `python main.py --step 4` を実行してください。

## 出力ファイル

```
output/
├── slide_images/          # スライド画像（PNG）
├── slides_info.json       # スライド情報（テキスト + 画像パス）
├── transcript.json        # 文字起こし（タイムスタンプ付き）
├── transcript.txt         # 文字起こし（テキスト版・読みやすい）
├── cuesheet.json          # キューシート（各スライドの表示タイミング）
├── cuesheet.csv           # キューシート（CSV版）
├── transcript.srt         # 字幕ファイル（SRT・UTF-8 BOM）← GUIから自動生成
├── subtitles.srt          # 動画焼き込み用SRT（Step4で生成）
├── podcast_video.mp4      # 生成された動画 ← これをFilmoraに読み込む
├── debug_prompt.txt       # デバッグ用: LLMに送ったプロンプト
└── debug_llm_response.txt # デバッグ用: LLMの応答
```

## Filmoraでの仕上げワークフロー

1. `output/podcast_video.mp4` をFilmoraに読み込む
2. 必要に応じてテロップ・字幕を追加
3. トランジション・エフェクトを調整
4. イントロ・アウトロを追加
5. 最終書き出し

## トラブルシューティング

### 「Ollamaに接続できません」
→ `ollama serve` でOllamaを起動してから再実行

### 「モデルが見つかりません」
→ `ollama list` で利用可能なモデルを確認、`ollama pull モデル名` でダウンロード

### PPTXの画像化に失敗する
→ スライドをPDF形式で保存し、`config.yaml` で `slides_file: "input/slides.pdf"` に変更

### マッチング結果がおかしい
→ `output/cuesheet.json` を手動で修正し、`python main.py --step 4` で動画だけ再生成

### メモリ不足（Whisper）
→ `config.yaml` の `whisper.model` を `tiny` または `base` に変更
→ GUIの場合は AI Settings セクションで Whisper Model を変更

### 日本語フォルダ名で動作しない
→ v0.4.1で修正済み。プロジェクトフォルダや入力ファイルのパスに日本語（非ASCII文字）が含まれていても正常に動作します。
→ GUIのファイル選択では絶対パスを使用し、FFmpegへのパス受け渡しもUnicode対応済みです。

## GUI画面構成（rev004）

```
┌──────────────────────────────────────────────────────────────┐
│ Top Bar: Podcast AI Studio | Save Config | Open Folder      │
├────────────┬──────────────────────────────────┬──────────────┤
│ Sidebar    │ Main Workspace (scroll)          │ Preview      │
│            │                                  │              │
│ Project    │ [Project] 名前 + 最近のPJ        │ Slide画像    │
│ Inputs     │ [Inputs] 音声/スライド/出力先    │ ◀ 1/18 ▶    │
│ AI Settings│ [AI] Ollama + Whisperモデル選択  │              │
│ Pipeline   │ [Pipeline] 4ステップカード       │ 字幕プレビュー│
│ Subtitles  │   [1]→[2]→[3]→[4] 状態表示      │              │
│ Output     │ [Run All] [Stop] プログレス      │ 出力ファイル │
│ Logs       │ [Subtitles] 言語選択             │ ● ○ ○ ● ●   │
│            │ [Logs] カラー付きログ表示        │              │
│ v0.4.0     │                                  │ [Open Video] │
├────────────┴──────────────────────────────────┴──────────────┤
│ Ready | Language: Korean | Ollama: gemma3:27b | Whisper: sm  │
└──────────────────────────────────────────────────────────────┘
```

### 主な機能

- ダークテーマ（Catppuccin風配色）
- サイドバーナビゲーション（セクション自動スクロール）
- パイプラインステップカード（Pending / Running / Done / Failed 状態表示）
- スライドプレビュー（画像ナビゲーション付き）
- 字幕プレビュー（日本語・韓国語・英語対応）
- 出力ファイル存在確認インジケーター（●=生成済 / ○=未生成）
- カラーログ（ERROR=赤 / WARN=黄 / SUCCESS=緑 / INFO=青）
- ステータスバー（状態 / 言語 / モデル / 進捗%）
- プロジェクト管理（最近のプロジェクト保存・復元）
- Ollamaモデル一覧の自動取得・選択
- Whisperモデル選択（tiny / base / small / medium / large）
- config.yaml への設定自動保存
