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

### 3. 設定ファイル

```bash
cp config.yaml.example config.yaml
```

`config.yaml` を開いて、音声ファイルとスライドのパスを設定します：

```yaml
audio_file: "input/podcast.mp3"     # 音声ファイルのパス
slides_file: "input/slides.pptx"    # スライドのパス（.pptx or .pdf）
```

最低限、上記2つのパスを正しく設定すれば動作します。

### 4. ファイル配置

`input/` ディレクトリに音声ファイルとスライドを配置してください。

```
input/
├── podcast.mp3          ← 音声ファイル
└── slides.pptx          ← スライド（またはslides.pdf）
```

## 使い方

### Windows インストーラ版（エンドユーザ向け推奨）

`installer_output\PodcastAIStudio-Setup-{version}.exe` をダブルクリックしてインストール後、スタートメニューまたはデスクトップから **Podcast AI Studio** を起動してください。Python 環境のセットアップは不要です（FFmpeg と Ollama は別途必要）。

インストーラのビルド方法は [PyInstaller / インストーラビルド](#pyinstaller--インストーラビルド) を参照してください。

### GUI（開発者向け / Python 環境がある場合）

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

### 日本語フォルダ名・ファイル名で動作しない
→ v0.4.2 で根本対策済み。Audio File / Slides File / Output Folder のいずれに日本語（非ASCII文字）が含まれていても正常に動作します。
→ 対策内容:
  - GUI のすべてのパス処理を `_resolve_path()`（pathlib ベース）に統一し、設定ファイルへ常に絶対パスで保存
  - Whisper／FFmpeg に渡す音声ファイルは、非ASCIIを含む場合のみシステム一時領域へコピー（`tempfile.mkstemp`）し、ASCII 安全なパス経由で実行（処理後に自動削除）
  - Step 4 の中間ファイル用 `temp_dir` は `tempfile.mkdtemp()` でシステム一時領域に作成し、ユーザの出力フォルダに日本語があっても FFmpeg の concat 入力経路は ASCII で完結
  - subprocess 呼び出しは `encoding="utf-8", errors="replace"` を指定して cp932 デコードエラーを回避

## プロジェクト構成

```
├── gui_apps/                   # GUI アプリケーション
│   ├── run_gui_app.py          #   Podcast AI Studio（推奨）
│   ├── run_gui_rev003.py       #   Studio 3パネル版
│   ├── run_gui_rev002.py       #   多言語字幕対応版
│   ├── run_gui.py              #   初期版ランチャー
│   ├── gui_app.py              #   初期版実装
│   └── ollama_utils.py         #   Ollamaモデル一覧ユーティリティ
├── main.py                     # CLIエントリーポイント
├── step1_extract_slides.py     # スライド抽出（PPTX/PDF + OCR）
├── step2_transcribe.py         # Whisper文字起こし
├── step3_match.py              # Ollama LLMマッチング
├── step4_generate_video.py     # FFmpeg動画生成
├── subtitle_generator.py       # SRT字幕生成
├── pyinstaller/                # PyInstaller + Inno Setup ビルド資産
│   ├── build.bat               #   PyInstaller ビルドエントリ
│   ├── run_gui_app.spec        #   PyInstaller spec
│   ├── installer.iss           #   Inno Setup インストーラスクリプト
│   ├── app_icon.ico            #   マルチ解像度アプリアイコン
│   └── rthook_stdio.py         #   ランタイムフック
├── config.yaml.example         # 設定ファイルテンプレート
└── requirements.txt            # Pythonパッケージ
```

## PyInstaller / インストーラビルド

開発者向けに、Python 環境なしでも動作する Windows インストーラを生成できます。

### 必要なもの

- **PyInstaller** (`pip install pyinstaller`)
- **Inno Setup 6** ([https://jrsoftware.org/isinfo.php](https://jrsoftware.org/isinfo.php) からインストール)
- **UPX**（任意・推奨）— exe を圧縮。PATH に通すか、spec の `strip` / `upx` フラグを `False` に変更

### 1. exe フォルダのビルド

```bash
cd pyinstaller
build.bat
# → ../dist/run_gui_app/run_gui_app.exe (folder distribution, 約 4.2 GB)
```

### 2. インストーラ生成

```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" pyinstaller/installer.iss
# → installer_output/PodcastAIStudio-Setup-{version}.exe (約 1.6 GB)
```

### 配布フォルダのサイズについて

`dist/run_gui_app/` は PyTorch / Whisper モデル / scipy / cv2 等を含むため約 **4.2 GB**、Inno Setup の lzma2/ultra64 圧縮後は約 **1.6 GB** です。これは Whisper を完全オフラインで動作させるために必要なサイズです。

### 動作確認（exe ビルド後の推奨スモークテスト）

```bash
# dispatcher が正しく組み込まれているか
dist\run_gui_app\run_gui_app.exe --step 99
# → "argument --step: invalid choice: '99'" と表示されて exit 2 になればOK
```

詳細なビルド仕様 / トラブルシューティングは [`CLAUDE.md`](CLAUDE.md) の "PyInstaller Build" / "Inno Setup installer" セクションを参照してください。

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
