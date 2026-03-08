"""
Podcast AI Studio - Rev004
Commercial-grade dark-themed GUI for podcast/lecture video generation.

Usage: python gui_apps/run_gui_rev004.py
"""

import os
import sys
import json
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from datetime import datetime

import yaml
from PIL import Image, ImageTk, ImageDraw

# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")
RECENT_PATH = os.path.join(PROJECT_ROOT, ".recent_projects.json")

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]
LANG_OPTIONS = {"auto": "Auto Detect", "ja": "Japanese", "ko": "Korean", "en": "English"}
LANG_DISPLAY = {
    "ja": "Japanese", "ko": "Korean", "en": "English",
    "zh": "Chinese", "fr": "French", "de": "German", "es": "Spanish",
}
STEP_META = {
    1: {"label": "Extract Slides",   "icon": "S", "desc": "PPTX/PDF to images + text"},
    2: {"label": "Transcribe Audio",  "icon": "T", "desc": "Whisper speech-to-text"},
    3: {"label": "Match Slides",      "icon": "M", "desc": "LLM slide-audio alignment"},
    4: {"label": "Generate Video",    "icon": "V", "desc": "FFmpeg MP4 composition"},
}

# ---------------------------------------------------------------------------
# Color palette  (dark theme)
# ---------------------------------------------------------------------------
C = {
    "bg":           "#1e1e2e",   # main background
    "bg_dark":      "#181825",   # sidebar / deeper areas
    "bg_card":      "#282840",   # card / panel surfaces
    "bg_card_h":    "#313150",   # card hover
    "bg_input":     "#2a2a3e",   # entry / combo bg
    "border":       "#3b3b55",   # subtle borders
    "border_light": "#50506a",   # lighter borders
    "fg":           "#cdd6f4",   # primary text
    "fg_dim":       "#a6adc8",   # secondary text
    "fg_muted":     "#6c7086",   # muted text
    "accent":       "#89b4fa",   # primary accent (blue)
    "accent_dark":  "#6a96d9",   # accent hover
    "accent_bg":    "#2a3a5a",   # accent background tint
    "green":        "#a6e3a1",   # success
    "green_bg":     "#1e3a2a",
    "red":          "#f38ba8",   # danger / error
    "red_bg":       "#3a1e2a",
    "yellow":       "#f9e2af",   # warning / running
    "yellow_bg":    "#3a351e",
    "orange":       "#fab387",   # info secondary
    "surface0":     "#313244",
    "surface1":     "#45475a",
    "surface2":     "#585b70",
}

FONT_TITLE    = ("Segoe UI", 16, "bold")
FONT_SECTION  = ("Segoe UI", 12, "bold")
FONT_LABEL    = ("Segoe UI", 10)
FONT_SMALL    = ("Segoe UI", 9)
FONT_TINY     = ("Segoe UI", 8)
FONT_LOG      = ("Cascadia Code", 9)
FONT_SIDEBAR  = ("Segoe UI", 10)
FONT_STATUS   = ("Segoe UI", 9)
FONT_STEP_NUM = ("Segoe UI", 18, "bold")
FONT_STEP_LBL = ("Segoe UI", 10, "bold")
FONT_BUTTON   = ("Segoe UI", 10)

# ---------------------------------------------------------------------------
def lang_display_name(code: str) -> str:
    return LANG_DISPLAY.get(code, code)

def get_ollama_models() -> list[str]:
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace")
        if result.returncode != 0:
            return []
        lines = result.stdout.strip().split("\n")
        return [line.split()[0] for line in lines[1:] if line.split()]
    except Exception:
        return []

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def save_config(audio_file, slides_file, ollama_model, output_dir,
                whisper_model="small", whisper_language="auto"):
    config = load_config()
    config["audio_file"] = audio_file
    config["slides_file"] = slides_file
    config["output_dir"] = output_dir
    config["output_video"] = os.path.join(output_dir, "podcast_video.mp4")
    config.setdefault("ollama", {})["model"] = ollama_model
    config.setdefault("whisper", {})["model"] = whisper_model
    config["whisper"]["language"] = whisper_language
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False,
                  allow_unicode=True, sort_keys=False)

def _format_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def generate_transcript_srt(segments, output_path):
    with open(output_path, "w", encoding="utf-8-sig") as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n{_format_srt_time(seg['start'])} --> "
                    f"{_format_srt_time(seg['end'])}\n{seg['text'].strip()}\n\n")
    return output_path

def transcribe_with_language_detection(audio_file, output_dir,
                                       model_name="small", language="auto",
                                       log_fn=None):
    import whisper
    log = log_fn or print
    log("Whisper transcription started")
    log(f"  Model: {model_name}  |  Language: {language}")
    log(f"  File: {audio_file}")
    log("  Loading model...")
    model = whisper.load_model(model_name)
    log("  Transcribing...")
    args = {"task": "transcribe", "verbose": False}
    if language != "auto":
        args["language"] = language
    result = model.transcribe(audio_file, **args)
    detected_lang = result.get("language", "en")
    log(f"  Detected language: {lang_display_name(detected_lang)} ({detected_lang})")
    segments = [{"start": round(s["start"], 2), "end": round(s["end"], 2),
                 "text": s["text"].strip()} for s in result["segments"]]
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "transcript.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)
    log(f"  -> JSON: {json_path}")
    txt_path = os.path.join(output_dir, "transcript.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        for seg in segments:
            sm, ss = divmod(int(seg["start"]), 60)
            em, es = divmod(int(seg["end"]), 60)
            f.write(f"[{sm:02d}:{ss:02d} - {em:02d}:{es:02d}] {seg['text']}\n")
    log(f"  -> TXT: {txt_path}")
    srt_path = os.path.join(output_dir, "transcript.srt")
    generate_transcript_srt(segments, srt_path)
    log(f"  Generating subtitles: {lang_display_name(detected_lang)}")
    log(f"  -> SRT: {srt_path}")
    total_sec = segments[-1]["end"] if segments else 0
    tm, ts = divmod(int(total_sec), 60)
    log(f"  -> {len(segments)} segments, duration: {tm:02d}:{ts:02d}")
    return segments, detected_lang

# ---------------------------------------------------------------------------
# Recent projects
# ---------------------------------------------------------------------------
def load_recent_projects() -> list[dict]:
    if os.path.exists(RECENT_PATH):
        try:
            with open(RECENT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_recent_project(name, audio, slides, output_dir):
    projects = load_recent_projects()
    entry = {"name": name, "audio": audio, "slides": slides,
             "output_dir": output_dir, "date": datetime.now().isoformat()[:16]}
    projects = [p for p in projects if p.get("name") != name]
    projects.insert(0, entry)
    projects = projects[:10]
    with open(RECENT_PATH, "w", encoding="utf-8") as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Generate app icon programmatically
# ---------------------------------------------------------------------------
def _create_app_icon(size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # rounded rect bg
    draw.rounded_rectangle([0, 0, size-1, size-1], radius=size//6,
                           fill="#89b4fa", outline="#6a96d9", width=2)
    # play triangle
    cx, cy = size // 2, size // 2
    s = size // 4
    pts = [(cx - s//2 + 2, cy - s), (cx - s//2 + 2, cy + s), (cx + s, cy)]
    draw.polygon(pts, fill="#1e1e2e")
    return img


# ============================================================================
# Main Application
# ============================================================================
class PodcastAIStudio(tk.Tk):

    NAV_ITEMS = [
        ("project",   "Project"),
        ("inputs",    "Inputs"),
        ("ai",        "AI Settings"),
        ("pipeline",  "Pipeline"),
        ("subtitles", "Subtitles"),
        ("output",    "Output"),
        ("logs",      "Logs"),
    ]

    def __init__(self):
        super().__init__()
        self.title("Podcast AI Studio")
        self.geometry("1360x820")
        self.minsize(1100, 700)
        self.configure(bg=C["bg"])

        # App icon
        try:
            icon_img = _create_app_icon(64)
            self._icon_photo = ImageTk.PhotoImage(icon_img)
            self.iconphoto(True, self._icon_photo)
        except Exception:
            pass

        # State
        self.log_queue: queue.Queue = queue.Queue()
        self.process = None
        self._running = False
        self._preview_image = None
        self._slide_images: list[str] = []
        self._current_slide = 0
        self._step_states: dict[int, str] = {i: "pending" for i in range(1, 5)}
        self._active_nav = "pipeline"

        self._setup_styles()
        config = load_config()
        self._build_ui(config)
        self._poll_log_queue()
        self._check_ollama_status()

    # -----------------------------------------------------------------------
    # ttk Styles  (dark theme, commercial look)
    # -----------------------------------------------------------------------
    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Global defaults
        style.configure(".", background=C["bg"], foreground=C["fg"],
                        borderwidth=0, focuscolor=C["accent"],
                        font=FONT_LABEL)
        style.map(".", foreground=[("disabled", C["fg_muted"])])

        # Frames
        style.configure("TFrame", background=C["bg"])
        style.configure("Card.TFrame", background=C["bg_card"])
        style.configure("Sidebar.TFrame", background=C["bg_dark"])
        style.configure("TopBar.TFrame", background=C["bg_dark"])
        style.configure("StatusBar.TFrame", background=C["bg_dark"])
        style.configure("Preview.TFrame", background=C["bg_card"])

        # Labels
        style.configure("TLabel", background=C["bg"], foreground=C["fg"])
        style.configure("Card.TLabel", background=C["bg_card"],
                        foreground=C["fg"])
        style.configure("CardDim.TLabel", background=C["bg_card"],
                        foreground=C["fg_dim"], font=FONT_SMALL)
        style.configure("CardMuted.TLabel", background=C["bg_card"],
                        foreground=C["fg_muted"], font=FONT_TINY)
        style.configure("Sidebar.TLabel", background=C["bg_dark"],
                        foreground=C["fg_dim"], font=FONT_SIDEBAR, padding=(16, 8))
        style.configure("SidebarActive.TLabel", background=C["accent_bg"],
                        foreground=C["accent"], font=("Segoe UI", 10, "bold"),
                        padding=(16, 8))
        style.configure("TopBar.TLabel", background=C["bg_dark"],
                        foreground=C["fg"])
        style.configure("TopBarTitle.TLabel", background=C["bg_dark"],
                        foreground=C["accent"], font=FONT_TITLE)
        style.configure("TopBarSub.TLabel", background=C["bg_dark"],
                        foreground=C["fg_muted"], font=FONT_SMALL)
        style.configure("StatusBar.TLabel", background=C["bg_dark"],
                        foreground=C["fg_dim"], font=FONT_STATUS)
        style.configure("StatusGreen.TLabel", background=C["bg_dark"],
                        foreground=C["green"], font=FONT_STATUS)
        style.configure("StatusRed.TLabel", background=C["bg_dark"],
                        foreground=C["red"], font=FONT_STATUS)
        style.configure("StatusYellow.TLabel", background=C["bg_dark"],
                        foreground=C["yellow"], font=FONT_STATUS)
        style.configure("Section.TLabel", background=C["bg"],
                        foreground=C["accent"], font=FONT_SECTION)
        style.configure("Preview.TLabel", background=C["bg_card"],
                        foreground=C["fg"])
        style.configure("PreviewDim.TLabel", background=C["bg_card"],
                        foreground=C["fg_dim"], font=FONT_SMALL)
        style.configure("Heading.TLabel", background=C["bg"],
                        foreground=C["fg"], font=FONT_SECTION)

        # Entry
        style.configure("TEntry", fieldbackground=C["bg_input"],
                        foreground=C["fg"], insertcolor=C["fg"],
                        borderwidth=1, padding=6)
        style.map("TEntry",
                  fieldbackground=[("focus", C["bg_card"])],
                  bordercolor=[("focus", C["accent"])])

        # Combobox
        style.configure("TCombobox", fieldbackground=C["bg_input"],
                        background=C["surface1"], foreground=C["fg"],
                        arrowcolor=C["fg_dim"], padding=5)
        style.map("TCombobox",
                  fieldbackground=[("readonly", C["bg_input"])],
                  selectbackground=[("readonly", C["bg_input"])],
                  selectforeground=[("readonly", C["fg"])])

        # Buttons - Primary (accent)
        style.configure("Primary.TButton",
                        background=C["accent"], foreground=C["bg_dark"],
                        font=("Segoe UI", 10, "bold"), padding=(16, 8),
                        borderwidth=0)
        style.map("Primary.TButton",
                  background=[("active", C["accent_dark"]),
                              ("disabled", C["surface1"])],
                  foreground=[("disabled", C["fg_muted"])])

        # Buttons - Secondary
        style.configure("Secondary.TButton",
                        background=C["surface1"], foreground=C["fg"],
                        font=FONT_BUTTON, padding=(12, 6), borderwidth=0)
        style.map("Secondary.TButton",
                  background=[("active", C["surface2"]),
                              ("disabled", C["surface0"])],
                  foreground=[("disabled", C["fg_muted"])])

        # Buttons - Danger
        style.configure("Danger.TButton",
                        background=C["red"], foreground=C["bg_dark"],
                        font=FONT_BUTTON, padding=(12, 6), borderwidth=0)
        style.map("Danger.TButton",
                  background=[("active", "#d97085"), ("disabled", C["surface1"])],
                  foreground=[("disabled", C["fg_muted"])])

        # Buttons - Ghost (subtle)
        style.configure("Ghost.TButton",
                        background=C["bg_card"], foreground=C["fg_dim"],
                        font=FONT_SMALL, padding=(8, 4), borderwidth=0)
        style.map("Ghost.TButton",
                  background=[("active", C["surface1"])],
                  foreground=[("active", C["fg"])])

        # Buttons - Sidebar
        style.configure("Sidebar.TButton",
                        background=C["bg_dark"], foreground=C["fg_dim"],
                        font=FONT_SIDEBAR, padding=(20, 9), anchor="w",
                        borderwidth=0)
        style.map("Sidebar.TButton",
                  background=[("active", C["surface0"])],
                  foreground=[("active", C["fg"])])
        style.configure("SidebarActive.TButton",
                        background=C["accent_bg"], foreground=C["accent"],
                        font=("Segoe UI", 10, "bold"), padding=(20, 9),
                        anchor="w", borderwidth=0)

        # Radiobutton
        style.configure("TRadiobutton", background=C["bg"],
                        foreground=C["fg"], font=FONT_LABEL,
                        indicatorcolor=C["surface2"], padding=(4, 3))
        style.map("TRadiobutton",
                  indicatorcolor=[("selected", C["accent"])],
                  background=[("active", C["bg"])])
        style.configure("Card.TRadiobutton", background=C["bg_card"],
                        foreground=C["fg"], font=FONT_LABEL,
                        indicatorcolor=C["surface2"])
        style.map("Card.TRadiobutton",
                  indicatorcolor=[("selected", C["accent"])],
                  background=[("active", C["bg_card"])])

        # Separator
        style.configure("TSeparator", background=C["border"])

        # Progressbar
        style.configure("Accent.Horizontal.TProgressbar",
                        troughcolor=C["surface0"], background=C["accent"],
                        borderwidth=0, thickness=6)

        # Scrollbar
        style.configure("Vertical.TScrollbar",
                        background=C["surface1"], troughcolor=C["bg_card"],
                        arrowcolor=C["fg_dim"], borderwidth=0)

        # LabelFrame
        style.configure("TLabelframe", background=C["bg"],
                        foreground=C["fg_dim"], borderwidth=1,
                        relief="flat")
        style.configure("TLabelframe.Label", background=C["bg"],
                        foreground=C["fg_dim"], font=FONT_SMALL)

        # Notebook (for internal use)
        style.configure("TNotebook", background=C["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=C["surface0"],
                        foreground=C["fg_dim"], padding=(14, 6),
                        font=FONT_LABEL)
        style.map("TNotebook.Tab",
                  background=[("selected", C["bg_card"])],
                  foreground=[("selected", C["fg"])])

    # -----------------------------------------------------------------------
    # Build UI
    # -----------------------------------------------------------------------
    def _build_ui(self, config):
        # --- Top Bar ---
        self._build_topbar()

        # --- Main body ---
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=180)
        body.columnconfigure(1, weight=1, minsize=500)
        body.columnconfigure(2, weight=0, minsize=300)
        body.rowconfigure(0, weight=1)

        self._build_sidebar(body)
        self._build_main_workspace(body, config)
        self._build_preview_panel(body, config)

        # --- Status Bar ---
        self._build_statusbar()

    # -----------------------------------------------------------------------
    # Top Bar
    # -----------------------------------------------------------------------
    def _build_topbar(self):
        bar = ttk.Frame(self, style="TopBar.TFrame", height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Left: title
        left = ttk.Frame(bar, style="TopBar.TFrame")
        left.pack(side="left", padx=(16, 0), fill="y")

        ttk.Label(left, text="Podcast AI Studio",
                  style="TopBarTitle.TLabel").pack(side="left", pady=8)
        ttk.Label(left, text="  Video Production Pipeline",
                  style="TopBarSub.TLabel").pack(side="left", pady=8)

        # Right: quick actions
        right = ttk.Frame(bar, style="TopBar.TFrame")
        right.pack(side="right", padx=16, fill="y")

        self._ollama_status_var = tk.StringVar(value="Checking...")
        self._ollama_status_label = ttk.Label(
            right, textvariable=self._ollama_status_var,
            style="TopBar.TLabel", font=FONT_SMALL)
        self._ollama_status_label.pack(side="right", padx=(12, 0), pady=12)

        ttk.Button(right, text="About", style="Ghost.TButton",
                   command=self._show_about).pack(side="right", padx=2, pady=12)
        ttk.Button(right, text="Open Folder", style="Ghost.TButton",
                   command=self._open_output_folder).pack(side="right", padx=2, pady=12)
        ttk.Button(right, text="Save Config", style="Ghost.TButton",
                   command=self._save_current_config).pack(side="right", padx=2, pady=12)

        # thin accent line under topbar
        accent_line = tk.Frame(self, bg=C["accent"], height=2)
        accent_line.pack(fill="x")

    # -----------------------------------------------------------------------
    # Sidebar
    # -----------------------------------------------------------------------
    def _build_sidebar(self, parent):
        sidebar = ttk.Frame(parent, style="Sidebar.TFrame", width=180)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        # logo area
        logo_frame = ttk.Frame(sidebar, style="Sidebar.TFrame")
        logo_frame.pack(fill="x", pady=(12, 6), padx=8)
        ttk.Label(logo_frame, text="NAVIGATION",
                  style="Sidebar.TLabel",
                  font=("Segoe UI", 8, "bold"),
                  foreground=C["fg_muted"]).pack(anchor="w", padx=8)

        sep = tk.Frame(sidebar, bg=C["border"], height=1)
        sep.pack(fill="x", padx=16, pady=(0, 6))

        self._nav_buttons = {}
        for key, label in self.NAV_ITEMS:
            btn_style = ("SidebarActive.TButton" if key == self._active_nav
                         else "Sidebar.TButton")
            btn = ttk.Button(sidebar, text=f"  {label}", style=btn_style,
                             command=lambda k=key: self._nav_to(k))
            btn.pack(fill="x", padx=6, pady=1)
            self._nav_buttons[key] = btn

        # bottom spacer + version
        spacer = ttk.Frame(sidebar, style="Sidebar.TFrame")
        spacer.pack(fill="both", expand=True)
        ttk.Label(sidebar, text="v0.4.0", style="Sidebar.TLabel",
                  font=FONT_TINY, foreground=C["fg_muted"]).pack(
            side="bottom", pady=8)

    def _nav_to(self, key):
        self._active_nav = key
        for k, btn in self._nav_buttons.items():
            btn.configure(style=("SidebarActive.TButton" if k == key
                                 else "Sidebar.TButton"))
        # Scroll workspace to matching section
        if hasattr(self, "_section_frames") and key in self._section_frames:
            widget = self._section_frames[key]
            self._workspace_canvas.update_idletasks()
            y = widget.winfo_y()
            ch = self._workspace_inner.winfo_reqheight()
            vh = self._workspace_canvas.winfo_height()
            if ch > vh:
                self._workspace_canvas.yview_moveto(y / ch)

    # -----------------------------------------------------------------------
    # Main Workspace (scrollable)
    # -----------------------------------------------------------------------
    def _build_main_workspace(self, parent, config):
        outer = ttk.Frame(parent)
        outer.grid(row=0, column=1, sticky="nsew", padx=(1, 1))

        # Scrollable canvas
        canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0,
                           borderwidth=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical",
                                  command=canvas.yview)
        inner = ttk.Frame(canvas)

        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")
        canvas.configure(yscrollcommand=scrollbar.set)

        # bind mousewheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # resize inner to canvas width
        def _resize_inner(event):
            canvas.itemconfig("inner", width=event.width)
        canvas.bind("<Configure>", _resize_inner)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._workspace_canvas = canvas
        self._workspace_inner = inner
        self._section_frames = {}

        # Build sections
        self._build_section_project(inner, config)
        self._build_section_inputs(inner, config)
        self._build_section_ai(inner, config)
        self._build_section_pipeline(inner)
        self._build_section_subtitles(inner, config)
        self._build_section_logs(inner)

    # --- Section helpers ---
    def _section_header(self, parent, key, title):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=20, pady=(20, 4))
        self._section_frames[key] = frame
        ttk.Label(frame, text=title, style="Section.TLabel").pack(anchor="w")
        sep = tk.Frame(parent, bg=C["border"], height=1)
        sep.pack(fill="x", padx=20, pady=(2, 8))
        return frame

    def _card(self, parent, **kw):
        card = tk.Frame(parent, bg=C["bg_card"], highlightbackground=C["border"],
                        highlightthickness=1, **kw)
        card.pack(fill="x", padx=20, pady=(0, 10))
        return card

    # --- Project ---
    def _build_section_project(self, parent, config):
        self._section_header(parent, "project", "Project")
        card = self._card(parent)

        inner = ttk.Frame(card, style="Card.TFrame")
        inner.pack(fill="x", padx=16, pady=12)

        ttk.Label(inner, text="Project Name", style="Card.TLabel",
                  font=FONT_SMALL).grid(row=0, column=0, sticky="w", pady=(0,4))
        self.project_name_var = tk.StringVar(
            value=os.path.basename(config.get("output_dir", "output")))
        ttk.Entry(inner, textvariable=self.project_name_var, width=36).grid(
            row=1, column=0, sticky="ew", pady=(0, 8), columnspan=2)

        ttk.Label(inner, text="Recent Projects", style="CardDim.TLabel").grid(
            row=2, column=0, sticky="w", pady=(4, 2))

        recent = load_recent_projects()
        if recent:
            self.recent_var = tk.StringVar(value="")
            names = [f"{p['name']}  ({p.get('date','')})" for p in recent[:5]]
            combo = ttk.Combobox(inner, textvariable=self.recent_var,
                                 values=names, state="readonly", width=34)
            combo.grid(row=3, column=0, sticky="ew", columnspan=2, pady=(0, 4))
            combo.bind("<<ComboboxSelected>>",
                       lambda e: self._load_recent_project(recent))
        else:
            ttk.Label(inner, text="No recent projects",
                      style="CardMuted.TLabel").grid(
                row=3, column=0, sticky="w", columnspan=2)

        inner.columnconfigure(0, weight=1)

    def _load_recent_project(self, recent):
        idx = self.recent_var.current()
        if 0 <= idx < len(recent):
            p = recent[idx]
            self.audio_var.set(p.get("audio", ""))
            self.slides_var.set(p.get("slides", ""))
            self.output_var.set(p.get("output_dir", "output"))
            self.project_name_var.set(p.get("name", ""))
            self._log("[Project] Loaded: " + p.get("name", ""))

    # --- Inputs ---
    def _build_section_inputs(self, parent, config):
        self._section_header(parent, "inputs", "Inputs")
        card = self._card(parent)
        inner = ttk.Frame(card, style="Card.TFrame")
        inner.pack(fill="x", padx=16, pady=12)
        inner.columnconfigure(1, weight=1)

        # Audio
        ttk.Label(inner, text="Audio File", style="Card.TLabel",
                  font=FONT_SMALL).grid(row=0, column=0, columnspan=3,
                                        sticky="w", pady=(0, 2))
        self.audio_var = tk.StringVar(value=config.get("audio_file", ""))
        e_audio = ttk.Entry(inner, textvariable=self.audio_var)
        e_audio.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 6))
        ttk.Button(inner, text="Browse", style="Secondary.TButton",
                   command=self._browse_audio).grid(row=1, column=2, sticky="e")

        # Slides
        ttk.Label(inner, text="Slides File (PPTX / PDF)", style="Card.TLabel",
                  font=FONT_SMALL).grid(row=2, column=0, columnspan=3,
                                        sticky="w", pady=(10, 2))
        self.slides_var = tk.StringVar(value=config.get("slides_file", ""))
        ttk.Entry(inner, textvariable=self.slides_var).grid(
            row=3, column=0, columnspan=2, sticky="ew", padx=(0, 6))
        ttk.Button(inner, text="Browse", style="Secondary.TButton",
                   command=self._browse_slides).grid(row=3, column=2, sticky="e")

        # Output
        ttk.Label(inner, text="Output Folder", style="Card.TLabel",
                  font=FONT_SMALL).grid(row=4, column=0, columnspan=3,
                                        sticky="w", pady=(10, 2))
        self.output_var = tk.StringVar(
            value=config.get("output_dir", "output"))
        ttk.Entry(inner, textvariable=self.output_var).grid(
            row=5, column=0, columnspan=2, sticky="ew", padx=(0, 6))
        ttk.Button(inner, text="Browse", style="Secondary.TButton",
                   command=self._browse_output).grid(row=5, column=2, sticky="e")

        # Validate hint
        self._input_status_var = tk.StringVar(value="")
        ttk.Label(inner, textvariable=self._input_status_var,
                  style="CardMuted.TLabel").grid(
            row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))

        ttk.Button(inner, text="Validate Inputs", style="Ghost.TButton",
                   command=self._validate_inputs_display).grid(
            row=7, column=0, sticky="w", pady=(6, 0))

    # --- AI Settings ---
    def _build_section_ai(self, parent, config):
        self._section_header(parent, "ai", "AI Settings")
        card = self._card(parent)
        inner = ttk.Frame(card, style="Card.TFrame")
        inner.pack(fill="x", padx=16, pady=12)

        # LLM model
        row = 0
        ttk.Label(inner, text="LLM Model (Ollama)", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).grid(
            row=row, column=0, sticky="w", pady=(0, 4), columnspan=3)

        row += 1
        models = get_ollama_models()
        current_model = config.get("ollama", {}).get("model", "")
        if models:
            val = current_model if current_model in models else models[0]
        else:
            models = ["(Ollama not detected)"]
            val = models[0]

        self.ollama_var = tk.StringVar(value=val)
        self.ollama_combo = ttk.Combobox(
            inner, textvariable=self.ollama_var,
            values=models, state="readonly", width=28)
        self.ollama_combo.grid(row=row, column=0, sticky="w", padx=(0, 8))
        ttk.Button(inner, text="Refresh", style="Ghost.TButton",
                   command=self._refresh_models).grid(row=row, column=1, sticky="w")

        # Whisper model
        row += 1
        ttk.Label(inner, text="Whisper Model", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).grid(
            row=row, column=0, sticky="w", pady=(14, 4), columnspan=3)

        row += 1
        self.whisper_var = tk.StringVar(
            value=config.get("whisper", {}).get("model", "small"))
        f_whisper = ttk.Frame(inner, style="Card.TFrame")
        f_whisper.grid(row=row, column=0, columnspan=3, sticky="w")

        for i, m in enumerate(WHISPER_MODELS):
            rb = ttk.Radiobutton(f_whisper, text=m, variable=self.whisper_var,
                                 value=m, style="Card.TRadiobutton")
            rb.pack(side="left", padx=(0, 12))

        # Whisper language hint
        row += 1
        ttk.Label(inner, text="tiny/base: fastest | small: balanced | "
                  "medium/large: highest accuracy",
                  style="CardMuted.TLabel").grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(2, 0))

        inner.columnconfigure(0, weight=0)

    # --- Pipeline ---
    def _build_section_pipeline(self, parent):
        self._section_header(parent, "pipeline", "Pipeline")

        # Step cards in a horizontal flow
        flow = ttk.Frame(parent)
        flow.pack(fill="x", padx=20, pady=(0, 6))
        flow.columnconfigure(0, weight=1)
        flow.columnconfigure(1, weight=0)
        flow.columnconfigure(2, weight=1)
        flow.columnconfigure(3, weight=0)
        flow.columnconfigure(4, weight=1)
        flow.columnconfigure(5, weight=0)
        flow.columnconfigure(6, weight=1)

        self._step_cards = {}
        self._step_status_labels = {}
        self._step_buttons = {}

        for idx, (step_num, meta) in enumerate(STEP_META.items()):
            col = idx * 2
            card = self._build_step_card(flow, step_num, meta)
            card.grid(row=0, column=col, sticky="nsew", padx=4, pady=4)
            self._step_cards[step_num] = card

            # Arrow between cards
            if idx < 3:
                arrow_label = ttk.Label(flow, text="\u25B6", font=("Segoe UI", 14),
                                        foreground=C["fg_muted"])
                arrow_label.grid(row=0, column=col + 1, padx=2)

        # Run All + Stop
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill="x", padx=20, pady=(4, 6))

        self.run_all_btn = ttk.Button(
            action_frame, text="  Run Full Pipeline  ",
            style="Primary.TButton", command=self._on_run_all)
        self.run_all_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = ttk.Button(
            action_frame, text="Stop", style="Danger.TButton",
            command=self._on_stop, state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 16))

        # Progress
        prog_frame = ttk.Frame(parent)
        prog_frame.pack(fill="x", padx=20, pady=(0, 4))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            prog_frame, variable=self.progress_var, maximum=100,
            mode="determinate", style="Accent.Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x", pady=(0, 2))

        self.progress_label = tk.StringVar(value="Ready")
        ttk.Label(prog_frame, textvariable=self.progress_label,
                  font=FONT_SMALL, foreground=C["fg_dim"]).pack(anchor="w")

    def _build_step_card(self, parent, step_num, meta):
        card = tk.Frame(parent, bg=C["bg_card"],
                        highlightbackground=C["border"], highlightthickness=1)

        # Step number + icon
        header = tk.Frame(card, bg=C["bg_card"])
        header.pack(fill="x", padx=12, pady=(10, 2))

        num_label = tk.Label(header, text=str(step_num), font=FONT_STEP_NUM,
                             fg=C["accent"], bg=C["bg_card"])
        num_label.pack(side="left")

        # Status indicator
        status_var = tk.StringVar(value="Pending")
        status_label = tk.Label(header, textvariable=status_var,
                                font=FONT_TINY, fg=C["fg_muted"],
                                bg=C["bg_card"])
        status_label.pack(side="right", pady=4)
        self._step_status_labels[step_num] = (status_var, status_label)

        # Title
        tk.Label(card, text=meta["label"], font=FONT_STEP_LBL,
                 fg=C["fg"], bg=C["bg_card"]).pack(
            anchor="w", padx=12, pady=(0, 1))

        # Description
        tk.Label(card, text=meta["desc"], font=FONT_TINY,
                 fg=C["fg_muted"], bg=C["bg_card"]).pack(
            anchor="w", padx=12, pady=(0, 6))

        # Run button
        btn = ttk.Button(card, text=f"Run Step {step_num}",
                         style="Secondary.TButton",
                         command=lambda s=step_num: self._on_run_step(s))
        btn.pack(padx=12, pady=(0, 10), anchor="w")
        self._step_buttons[step_num] = btn

        return card

    def _update_step_card_state(self, step_num, state):
        """state: pending, running, done, failed"""
        self._step_states[step_num] = state
        status_var, status_label = self._step_status_labels[step_num]
        card = self._step_cards[step_num]

        state_config = {
            "pending": ("Pending",  C["fg_muted"], C["border"]),
            "running": ("Running",  C["yellow"],   C["yellow"]),
            "done":    ("Done",     C["green"],    C["green"]),
            "failed":  ("Failed",   C["red"],      C["red"]),
        }
        text, fg, border = state_config.get(state, state_config["pending"])
        status_var.set(text)
        status_label.configure(fg=fg)
        card.configure(highlightbackground=border)

    # --- Subtitles ---
    def _build_section_subtitles(self, parent, config):
        self._section_header(parent, "subtitles", "Subtitles")
        card = self._card(parent)
        inner = ttk.Frame(card, style="Card.TFrame")
        inner.pack(fill="x", padx=16, pady=12)

        ttk.Label(inner, text="Subtitle Language", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))

        self.lang_var = tk.StringVar(
            value=config.get("whisper", {}).get("language", "auto"))

        lang_frame = ttk.Frame(inner, style="Card.TFrame")
        lang_frame.pack(anchor="w")
        for code, label in LANG_OPTIONS.items():
            ttk.Radiobutton(lang_frame, text=label, variable=self.lang_var,
                            value=code, style="Card.TRadiobutton").pack(
                side="left", padx=(0, 16))

        # Detected language
        det_frame = ttk.Frame(inner, style="Card.TFrame")
        det_frame.pack(fill="x", pady=(12, 0))
        ttk.Label(det_frame, text="Detected Language:", style="CardDim.TLabel").pack(
            side="left")
        self.detected_lang_var = tk.StringVar(value="--")
        ttk.Label(det_frame, textvariable=self.detected_lang_var,
                  style="Card.TLabel", font=("Segoe UI", 11, "bold"),
                  foreground=C["accent"]).pack(side="left", padx=8)

    # --- Logs ---
    def _build_section_logs(self, parent):
        self._section_header(parent, "logs", "Processing Log")

        log_card = tk.Frame(parent, bg=C["bg_card"],
                            highlightbackground=C["border"],
                            highlightthickness=1)
        log_card.pack(fill="x", padx=20, pady=(0, 20))

        # toolbar
        toolbar = tk.Frame(log_card, bg=C["bg_card"])
        toolbar.pack(fill="x", padx=8, pady=(6, 2))
        ttk.Button(toolbar, text="Clear Log", style="Ghost.TButton",
                   command=self._clear_log).pack(side="right")

        self.log_text = scrolledtext.ScrolledText(
            log_card, wrap="word", height=14, font=FONT_LOG,
            bg="#141420", fg=C["fg_dim"], insertbackground=C["fg"],
            selectbackground=C["accent_bg"], selectforeground=C["fg"],
            borderwidth=0, highlightthickness=0, state="disabled",
            padx=10, pady=8)
        self.log_text.pack(fill="x", padx=8, pady=(0, 8))

        # Tag config for colored log lines
        self.log_text.tag_configure("error", foreground=C["red"])
        self.log_text.tag_configure("warn", foreground=C["yellow"])
        self.log_text.tag_configure("success", foreground=C["green"])
        self.log_text.tag_configure("info", foreground=C["accent"])
        self.log_text.tag_configure("step", foreground=C["accent"],
                                    font=("Cascadia Code", 9, "bold"))

    # -----------------------------------------------------------------------
    # Preview Panel (right)
    # -----------------------------------------------------------------------
    def _build_preview_panel(self, parent, config):
        panel = tk.Frame(parent, bg=C["bg_card"],
                         highlightbackground=C["border"], highlightthickness=1)
        panel.grid(row=0, column=2, sticky="nsew", padx=(0, 0))

        # Title
        header = tk.Frame(panel, bg=C["bg_card"])
        header.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(header, text="Preview", font=FONT_SECTION,
                 fg=C["accent"], bg=C["bg_card"]).pack(anchor="w")

        sep = tk.Frame(panel, bg=C["border"], height=1)
        sep.pack(fill="x", padx=14, pady=(0, 8))

        # --- Slide Preview ---
        tk.Label(panel, text="Slide Preview", font=FONT_SMALL,
                 fg=C["fg_dim"], bg=C["bg_card"]).pack(
            anchor="w", padx=14, pady=(0, 4))

        self.slide_canvas = tk.Canvas(panel, width=268, height=151,
                                      bg="#0e0e18", highlightthickness=0)
        self.slide_canvas.pack(padx=14)

        # placeholder text
        self.slide_canvas.create_text(
            134, 76, text="No slides loaded", fill=C["fg_muted"],
            font=FONT_SMALL)

        nav_frame = tk.Frame(panel, bg=C["bg_card"])
        nav_frame.pack(fill="x", padx=14, pady=(4, 8))
        ttk.Button(nav_frame, text="\u25C0", style="Ghost.TButton",
                   command=self._prev_slide, width=3).pack(side="left")
        self.slide_index_var = tk.StringVar(value="-- / --")
        tk.Label(nav_frame, textvariable=self.slide_index_var,
                 font=FONT_SMALL, fg=C["fg_dim"],
                 bg=C["bg_card"]).pack(side="left", expand=True)
        ttk.Button(nav_frame, text="\u25B6", style="Ghost.TButton",
                   command=self._next_slide, width=3).pack(side="right")

        sep2 = tk.Frame(panel, bg=C["border"], height=1)
        sep2.pack(fill="x", padx=14, pady=(0, 8))

        # --- Subtitle Preview ---
        tk.Label(panel, text="Subtitle Preview", font=FONT_SMALL,
                 fg=C["fg_dim"], bg=C["bg_card"]).pack(
            anchor="w", padx=14, pady=(0, 4))

        self.subtitle_text = scrolledtext.ScrolledText(
            panel, wrap="word", height=7, font=("Segoe UI", 9),
            bg="#141420", fg=C["fg_dim"], insertbackground=C["fg"],
            borderwidth=0, highlightthickness=0, state="disabled",
            padx=8, pady=6)
        self.subtitle_text.pack(fill="x", padx=14, pady=(0, 8))

        sep3 = tk.Frame(panel, bg=C["border"], height=1)
        sep3.pack(fill="x", padx=14, pady=(0, 8))

        # --- Output Summary ---
        tk.Label(panel, text="Output Files", font=FONT_SMALL,
                 fg=C["fg_dim"], bg=C["bg_card"]).pack(
            anchor="w", padx=14, pady=(0, 4))

        self._output_files_frame = tk.Frame(panel, bg=C["bg_card"])
        self._output_files_frame.pack(fill="x", padx=14, pady=(0, 8))
        self._output_file_labels = {}

        for fname in ["slides_info.json", "transcript.json", "transcript.srt",
                       "cuesheet.json", "podcast_video.mp4"]:
            row = tk.Frame(self._output_files_frame, bg=C["bg_card"])
            row.pack(fill="x", pady=1)
            status_lbl = tk.Label(row, text="\u25CB", font=FONT_TINY,
                                  fg=C["fg_muted"], bg=C["bg_card"], width=2)
            status_lbl.pack(side="left")
            tk.Label(row, text=fname, font=FONT_TINY, fg=C["fg_dim"],
                     bg=C["bg_card"]).pack(side="left", padx=(4, 0))
            self._output_file_labels[fname] = status_lbl

        sep4 = tk.Frame(panel, bg=C["border"], height=1)
        sep4.pack(fill="x", padx=14, pady=(8, 8))

        # --- Action Buttons ---
        actions = tk.Frame(panel, bg=C["bg_card"])
        actions.pack(fill="x", padx=14, pady=(0, 12))

        ttk.Button(actions, text="Open Video", style="Secondary.TButton",
                   command=self._open_video).pack(fill="x", pady=2)
        ttk.Button(actions, text="Open Cuesheet", style="Ghost.TButton",
                   command=self._open_cuesheet).pack(fill="x", pady=2)
        ttk.Button(actions, text="Open Output Folder", style="Ghost.TButton",
                   command=self._open_output_folder).pack(fill="x", pady=2)
        ttk.Button(actions, text="Reload Preview", style="Ghost.TButton",
                   command=self._reload_preview).pack(fill="x", pady=2)

    # -----------------------------------------------------------------------
    # Status Bar
    # -----------------------------------------------------------------------
    def _build_statusbar(self):
        bar = ttk.Frame(self, style="StatusBar.TFrame", height=28)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        # top line
        line = tk.Frame(self, bg=C["border"], height=1)
        line.pack(fill="x", side="bottom")

        self._status_state_var = tk.StringVar(value="Ready")
        self._status_state_label = ttk.Label(
            bar, textvariable=self._status_state_var,
            style="StatusGreen.TLabel")
        self._status_state_label.pack(side="left", padx=(16, 12), pady=3)

        sep = ttk.Separator(bar, orient="vertical")
        sep.pack(side="left", fill="y", padx=4, pady=4)

        self._status_lang_var = tk.StringVar(value="Language: --")
        ttk.Label(bar, textvariable=self._status_lang_var,
                  style="StatusBar.TLabel").pack(side="left", padx=8, pady=3)

        sep2 = ttk.Separator(bar, orient="vertical")
        sep2.pack(side="left", fill="y", padx=4, pady=4)

        self._status_ollama_var = tk.StringVar(value="Ollama: --")
        ttk.Label(bar, textvariable=self._status_ollama_var,
                  style="StatusBar.TLabel").pack(side="left", padx=8, pady=3)

        sep3 = ttk.Separator(bar, orient="vertical")
        sep3.pack(side="left", fill="y", padx=4, pady=4)

        self._status_whisper_var = tk.StringVar(value="Whisper: small")
        ttk.Label(bar, textvariable=self._status_whisper_var,
                  style="StatusBar.TLabel").pack(side="left", padx=8, pady=3)

        sep4 = ttk.Separator(bar, orient="vertical")
        sep4.pack(side="left", fill="y", padx=4, pady=4)

        self._status_progress_var = tk.StringVar(value="0%")
        ttk.Label(bar, textvariable=self._status_progress_var,
                  style="StatusBar.TLabel").pack(side="left", padx=8, pady=3)

        # Right: last operation
        self._status_last_op_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self._status_last_op_var,
                  style="StatusBar.TLabel").pack(side="right", padx=16, pady=3)

        # Bind whisper var changes
        self.whisper_var.trace_add("write", lambda *a:
            self._status_whisper_var.set(f"Whisper: {self.whisper_var.get()}"))

    def _update_status_bar_state(self, state):
        """state: Ready, Running, Error, Done"""
        self._status_state_var.set(state)
        style_map = {
            "Ready": "StatusGreen.TLabel",
            "Running": "StatusYellow.TLabel",
            "Error": "StatusRed.TLabel",
            "Done": "StatusGreen.TLabel",
        }
        self._status_state_label.configure(
            style=style_map.get(state, "StatusBar.TLabel"))

    # -----------------------------------------------------------------------
    # Ollama check
    # -----------------------------------------------------------------------
    def _check_ollama_status(self):
        models = get_ollama_models()
        if models:
            self._ollama_status_var.set(f"Ollama: {len(models)} models")
            model = self.ollama_var.get()
            self._status_ollama_var.set(f"Ollama: {model}")
        else:
            self._ollama_status_var.set("Ollama: not detected")
            self._status_ollama_var.set("Ollama: N/A")

    def _refresh_models(self):
        models = get_ollama_models()
        if models:
            self.ollama_combo["values"] = models
            if self.ollama_var.get() not in models:
                self.ollama_var.set(models[0])
            self._log(f"[INFO] Ollama models refreshed: {', '.join(models)}")
            self._ollama_status_var.set(f"Ollama: {len(models)} models")
            self._status_ollama_var.set(f"Ollama: {self.ollama_var.get()}")
        else:
            self.ollama_combo["values"] = ["(Ollama not detected)"]
            self.ollama_var.set("(Ollama not detected)")
            self._log("[WARN] Ollama not detected.")
            self._ollama_status_var.set("Ollama: not detected")

    # -----------------------------------------------------------------------
    # File browsing
    # -----------------------------------------------------------------------
    def _browse_audio(self):
        path = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=[("Audio", "*.mp3 *.m4a *.wav *.ogg *.flac"),
                       ("All", "*.*")],
            initialdir=os.path.join(PROJECT_ROOT, "input"))
        if path:
            self.audio_var.set(os.path.abspath(path))

    def _browse_slides(self):
        path = filedialog.askopenfilename(
            title="Select Slides File",
            filetypes=[("Slides", "*.pptx *.pdf"), ("All", "*.*")],
            initialdir=os.path.join(PROJECT_ROOT, "input"))
        if path:
            self.slides_var.set(os.path.abspath(path))

    def _browse_output(self):
        path = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=os.path.join(PROJECT_ROOT,
                                    self.output_var.get() or "output"))
        if path:
            self.output_var.set(os.path.abspath(path))

    # -----------------------------------------------------------------------
    # Preview
    # -----------------------------------------------------------------------
    def _load_slide_images(self):
        output_dir = os.path.join(
            PROJECT_ROOT, self.output_var.get().strip() or "output")
        img_dir = os.path.join(output_dir, "slide_images")
        self._slide_images = []
        self._current_slide = 0
        if not os.path.isdir(img_dir):
            return
        files = sorted(f for f in os.listdir(img_dir) if f.lower().endswith(".png"))
        for fname in files:
            self._slide_images.append(os.path.join(img_dir, fname))

    def _show_slide(self, index):
        if not self._slide_images:
            self.slide_canvas.delete("all")
            self.slide_canvas.create_text(
                134, 76, text="No slides loaded", fill=C["fg_muted"],
                font=FONT_SMALL)
            self.slide_index_var.set("-- / --")
            return
        index = max(0, min(index, len(self._slide_images) - 1))
        self._current_slide = index
        img = Image.open(self._slide_images[index])
        img.thumbnail((268, 151), Image.LANCZOS)
        self._preview_image = ImageTk.PhotoImage(img)
        self.slide_canvas.delete("all")
        self.slide_canvas.create_image(134, 76, image=self._preview_image,
                                       anchor="center")
        self.slide_index_var.set(f"{index + 1} / {len(self._slide_images)}")

    def _prev_slide(self):
        if self._slide_images:
            self._show_slide(self._current_slide - 1)

    def _next_slide(self):
        if self._slide_images:
            self._show_slide(self._current_slide + 1)

    def _load_subtitle_preview(self):
        output_dir = os.path.join(
            PROJECT_ROOT, self.output_var.get().strip() or "output")
        srt_path = os.path.join(output_dir, "transcript.srt")
        txt_path = os.path.join(output_dir, "transcript.txt")
        preview_path = srt_path if os.path.exists(srt_path) else txt_path
        if not os.path.exists(preview_path):
            return
        with open(preview_path, "r", encoding="utf-8-sig") as f:
            content = f.read(3000)
        self.subtitle_text.config(state="normal")
        self.subtitle_text.delete("1.0", "end")
        self.subtitle_text.insert("end", content)
        self.subtitle_text.config(state="disabled")

    def _update_output_file_status(self):
        output_dir = os.path.join(
            PROJECT_ROOT, self.output_var.get().strip() or "output")
        for fname, label in self._output_file_labels.items():
            path = os.path.join(output_dir, fname)
            if os.path.exists(path):
                label.configure(text="\u25CF", fg=C["green"])
            else:
                label.configure(text="\u25CB", fg=C["fg_muted"])

    def _reload_preview(self):
        self._load_slide_images()
        if self._slide_images:
            self._show_slide(0)
        else:
            self._show_slide(-1)
        self._load_subtitle_preview()
        self._update_output_file_status()
        self._log("[INFO] Preview reloaded")

    def _open_video(self):
        config = load_config()
        video_path = os.path.join(
            PROJECT_ROOT, config.get("output_video", "output/podcast_video.mp4"))
        if os.path.exists(video_path):
            os.startfile(video_path)
        else:
            self._log("[WARN] Video file not found. Run pipeline first.")

    def _open_cuesheet(self):
        output_dir = os.path.join(
            PROJECT_ROOT, self.output_var.get().strip() or "output")
        cs_path = os.path.join(output_dir, "cuesheet.json")
        if os.path.exists(cs_path):
            os.startfile(cs_path)
        else:
            self._log("[WARN] Cuesheet not found. Run Step 3 first.")

    def _open_output_folder(self):
        output_dir = os.path.join(
            PROJECT_ROOT, self.output_var.get().strip() or "output")
        if os.path.isdir(output_dir):
            os.startfile(output_dir)
        else:
            os.makedirs(output_dir, exist_ok=True)
            os.startfile(output_dir)

    # -----------------------------------------------------------------------
    # Validate inputs
    # -----------------------------------------------------------------------
    def _validate_inputs_display(self):
        issues = []
        audio = self.audio_var.get().strip()
        slides = self.slides_var.get().strip()
        ollama = self.ollama_var.get()

        if not audio:
            issues.append("Audio file not set")
        elif not os.path.exists(os.path.join(PROJECT_ROOT, audio)):
            issues.append(f"Audio file not found: {audio}")

        if not slides:
            issues.append("Slides file not set")
        elif not os.path.exists(os.path.join(PROJECT_ROOT, slides)):
            issues.append(f"Slides file not found: {slides}")

        if ollama.startswith("("):
            issues.append("Ollama model not selected")

        if issues:
            self._input_status_var.set(" | ".join(issues))
            self._log("[WARN] Validation: " + "; ".join(issues))
        else:
            self._input_status_var.set("All inputs OK")
            self._log("[INFO] All inputs validated successfully")

    def _validate_for_step(self, step) -> bool:
        audio = self.audio_var.get().strip()
        slides = self.slides_var.get().strip()
        ollama = self.ollama_var.get()

        if step in ("all", 1) and not slides:
            self._log("[ERROR] Slides file is required.")
            return False
        if step in ("all", 2) and not audio:
            self._log("[ERROR] Audio file is required.")
            return False
        if step in ("all", 3) and ollama.startswith("("):
            self._log("[ERROR] Ollama model not selected.")
            return False
        return True

    # -----------------------------------------------------------------------
    # Config save
    # -----------------------------------------------------------------------
    def _save_current_config(self):
        ollama = self.ollama_var.get()
        save_config(
            audio_file=self.audio_var.get().strip(),
            slides_file=self.slides_var.get().strip(),
            ollama_model=ollama if not ollama.startswith("(") else "",
            output_dir=self.output_var.get().strip(),
            whisper_model=self.whisper_var.get(),
            whisper_language=self.lang_var.get(),
        )
        # Save to recent projects
        name = self.project_name_var.get().strip() or "Untitled"
        save_recent_project(name, self.audio_var.get().strip(),
                            self.slides_var.get().strip(),
                            self.output_var.get().strip())

        self._status_ollama_var.set(f"Ollama: {self.ollama_var.get()}")
        self._log("[INFO] Configuration saved")
        self._status_last_op_var.set("Config saved")

    # -----------------------------------------------------------------------
    # Execution
    # -----------------------------------------------------------------------
    def _set_running(self, running):
        self._running = running
        state = "disabled" if running else "normal"
        for btn in self._step_buttons.values():
            btn.config(state=state)
        self.run_all_btn.config(state=state)
        self.stop_btn.config(state="normal" if running else "disabled")

        if running:
            self._update_status_bar_state("Running")
        else:
            has_error = any(s == "failed" for s in self._step_states.values())
            self._update_status_bar_state("Error" if has_error else "Ready")

    def _on_run_step(self, step_num):
        if self._running:
            return
        if not self._validate_for_step(step_num):
            return
        self._save_current_config()
        self._set_running(True)
        self._update_step_card_state(step_num, "running")

        if step_num == 2:
            thread = threading.Thread(
                target=self._run_single_step_whisper, args=(step_num,),
                daemon=True)
        else:
            cmd = [sys.executable, os.path.join(PROJECT_ROOT, "main.py"),
                   "--step", str(step_num)]
            thread = threading.Thread(
                target=self._run_steps_subprocess, args=(cmd, step_num),
                daemon=True)
        thread.start()

    def _on_run_all(self):
        if self._running:
            return
        if not self._validate_for_step("all"):
            return
        self._save_current_config()
        self._set_running(True)
        for i in range(1, 5):
            self._update_step_card_state(i, "pending")
        thread = threading.Thread(target=self._run_full_pipeline, daemon=True)
        thread.start()

    def _on_stop(self):
        if self.process:
            self.process.terminate()
            self._log("[INFO] Process terminated by user.")
        self._running = False
        self.after(0, lambda: self._set_running(False))

    # --- Full pipeline ---
    def _run_full_pipeline(self):
        try:
            steps = [
                (1, "Extract Slides"),
                (2, "Transcribe Audio"),
                (3, "Match Slides"),
                (4, "Generate Video"),
            ]
            for idx, (step_num, label) in enumerate(steps):
                pct_start = idx * 25
                self.after(0, lambda s=step_num: self._update_step_card_state(s, "running"))
                self._update_progress(pct_start, f"Step {step_num}: {label}...")
                self._log("")
                self._log(f"{'='*50}")
                self._log(f"[Step {step_num}] {label}")

                if step_num == 2:
                    segments, detected_lang = self._run_whisper_inprocess()
                    if segments is None:
                        self.after(0, lambda: self._update_step_card_state(2, "failed"))
                        return
                else:
                    cmd = [sys.executable,
                           os.path.join(PROJECT_ROOT, "main.py"),
                           "--step", str(step_num)]
                    self._run_subprocess_blocking(cmd)

                self.after(0, lambda s=step_num: self._update_step_card_state(s, "done"))
                self._update_progress(pct_start + 25,
                                      f"Step {step_num} complete")

                if step_num in (1, 4):
                    self.after(0, self._reload_preview)

            self._log("")
            self._log(f"{'='*50}")
            self._log("[SUCCESS] All tasks completed successfully!")
            self._log(f"{'='*50}")
            self._update_progress(100, "Pipeline complete!")
            self._status_last_op_var.set("Pipeline complete")
            self.after(0, self._reload_preview)

        except Exception as e:
            self._log(f"[ERROR] {e}")
            self._update_status_bar_state("Error")
        finally:
            self._running = False
            self.after(0, lambda: self._set_running(False))

    # --- Single step whisper ---
    def _run_single_step_whisper(self, step_num):
        try:
            self._update_progress(0, "Step 2: Transcribing audio...")
            self._log(f"{'='*50}")
            self._log("[Step 2] Transcribe Audio")
            segments, detected_lang = self._run_whisper_inprocess()
            if segments is not None:
                self._update_progress(100, "Step 2 complete")
                self._log("[Step 2] Completed")
                self.after(0, lambda: self._update_step_card_state(2, "done"))
            else:
                self.after(0, lambda: self._update_step_card_state(2, "failed"))
        except Exception as e:
            self._log(f"[ERROR] {e}")
            self.after(0, lambda: self._update_step_card_state(2, "failed"))
        finally:
            self._running = False
            self.after(0, lambda: self._set_running(False))

    # --- Whisper in-process ---
    def _run_whisper_inprocess(self):
        config = load_config()
        audio_file = config.get("audio_file", "")
        audio_path = os.path.join(PROJECT_ROOT, audio_file)
        if not os.path.exists(audio_path):
            self._log(f"[ERROR] Audio file not found: {audio_file}")
            return None, None

        output_dir = os.path.join(
            PROJECT_ROOT, config.get("output_dir", "output"))

        segments, detected_lang = transcribe_with_language_detection(
            audio_path, output_dir,
            model_name=self.whisper_var.get(),
            language=self.lang_var.get(),
            log_fn=self._log)

        display = lang_display_name(detected_lang)
        det_text = f"{display} ({detected_lang})"
        self.after(0, lambda: self.detected_lang_var.set(det_text))
        self.after(0, lambda: self._status_lang_var.set(
            f"Language: {det_text}"))

        config["whisper"]["language"] = detected_lang
        config["whisper"]["model"] = self.whisper_var.get()
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False,
                      allow_unicode=True, sort_keys=False)

        self.after(0, self._load_subtitle_preview)
        return segments, detected_lang

    # --- Subprocess ---
    def _run_steps_subprocess(self, cmd, step_num):
        try:
            self._log(f"[Step {step_num}] {STEP_META[step_num]['label']}")
            self._run_subprocess_blocking(cmd)
            self._update_progress(100, f"Step {step_num} complete")
            self._log(f"[Step {step_num}] Completed")
            self.after(0, lambda: self._update_step_card_state(step_num, "done"))
            self._status_last_op_var.set(
                f"Step {step_num} done")
            if step_num in (1, 4):
                self.after(0, self._reload_preview)
        except Exception as e:
            self._log(f"[ERROR] {e}")
            self.after(0, lambda: self._update_step_card_state(step_num, "failed"))
        finally:
            self._running = False
            self.after(0, lambda: self._set_running(False))

    def _run_subprocess_blocking(self, cmd):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=PROJECT_ROOT, encoding="utf-8",
            errors="replace", bufsize=1, env=env)
        self.process = proc
        for line in proc.stdout:
            self.log_queue.put(line)
        proc.wait()
        self.process = None
        if proc.returncode != 0:
            self._log(f"[WARN] Process exited with code {proc.returncode}")

    # -----------------------------------------------------------------------
    # Progress
    # -----------------------------------------------------------------------
    def _update_progress(self, value, text):
        self.after(0, lambda: self.progress_var.set(value))
        self.after(0, lambda: self.progress_label.set(text))
        self.after(0, lambda: self._status_progress_var.set(f"{int(value)}%"))

    # -----------------------------------------------------------------------
    # Logging
    # -----------------------------------------------------------------------
    def _log(self, text):
        self.log_queue.put(text + "\n")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _poll_log_queue(self):
        while True:
            try:
                msg = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.config(state="normal")

            # Color coding
            tag = None
            if "[ERROR]" in msg:
                tag = "error"
            elif "[WARN]" in msg:
                tag = "warn"
            elif "[SUCCESS]" in msg:
                tag = "success"
            elif "[INFO]" in msg:
                tag = "info"
            elif "[Step" in msg:
                tag = "step"

            if tag:
                self.log_text.insert("end", msg, tag)
            else:
                self.log_text.insert("end", msg)

            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.after(100, self._poll_log_queue)

    # -----------------------------------------------------------------------
    # About
    # -----------------------------------------------------------------------
    def _show_about(self):
        win = tk.Toplevel(self)
        win.title("About Podcast AI Studio")
        win.geometry("420x300")
        win.configure(bg=C["bg_dark"])
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        tk.Label(win, text="Podcast AI Studio", font=FONT_TITLE,
                 fg=C["accent"], bg=C["bg_dark"]).pack(pady=(24, 4))
        tk.Label(win, text="Version 0.4.0", font=FONT_SMALL,
                 fg=C["fg_dim"], bg=C["bg_dark"]).pack()

        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=40, pady=12)

        desc = ("AI-powered video production pipeline.\n"
                "Podcast / YouTube / Lecture / Seminar\n\n"
                "Whisper + Ollama + FFmpeg\n"
                "Multilingual: Japanese / Korean / English")
        tk.Label(win, text=desc, font=FONT_LABEL, fg=C["fg_dim"],
                 bg=C["bg_dark"], justify="center").pack(pady=(0, 16))

        ttk.Button(win, text="Close", style="Secondary.TButton",
                   command=win.destroy).pack(pady=(0, 16))


# ============================================================================
def main():
    app = PodcastAIStudio()
    app.mainloop()

if __name__ == "__main__":
    main()
