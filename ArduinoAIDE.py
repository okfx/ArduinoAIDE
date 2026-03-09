#!/usr/bin/env python3
"""
Teensy Ollama IDE — Arduino IDE 2.x inspired desktop app
with local LLM (Ollama) integration for Teensy development.

Usage:
    python3 ArduinoAIDE.py [project_path]

Requirements:
    pip3 install PyQt6 PyQt6-QScintilla requests
"""

import sys, os, json, glob, re, threading, subprocess, math, html, time
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Auto-venv bootstrap — find and activate the app's virtual environment
# so the app works without manual `source .../activate`.
# ---------------------------------------------------------------------------
_VENV_CANDIDATES = [
    os.path.expanduser("~/teensy-ide-env"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv"),
]

def _bootstrap_venv():
    """If not already in a venv, find one and re-exec under its Python."""
    if sys.prefix != sys.base_prefix:
        return  # already in a venv
    for venv_dir in _VENV_CANDIDATES:
        python = os.path.join(venv_dir, "bin", "python3")
        if os.path.isfile(python):
            os.execv(python, [python] + sys.argv)
            # execv replaces the process — does not return

_bootstrap_venv()

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTreeView, QPlainTextEdit, QStackedWidget,
    QLineEdit, QPushButton, QToolBar, QTabWidget, QTabBar,
    QLabel, QComboBox, QFileDialog, QMessageBox, QTextEdit,
    QGroupBox, QSizePolicy, QListWidget, QListWidgetItem,
    QScrollArea, QFrame, QInputDialog, QStatusBar
)
from PyQt6.QtCore import (
    Qt, QDir, QModelIndex, pyqtSignal, QObject, QThread,
    QTimer, QSize, QPointF
)
from PyQt6.QtGui import (
    QFont, QColor, QAction, QKeySequence, QTextCursor,
    QTextCharFormat, QPalette, QFileSystemModel,
    QStandardItemModel, QStandardItem, QPainter, QPen,
    QPainterPath, QPolygonF
)

try:
    from PyQt6.Qsci import QsciScintilla, QsciLexerCPP
    HAS_QSCINTILLA = True
except ImportError:
    HAS_QSCINTILLA = False

import requests

# =============================================================================
# Colors — Arduino IDE 2.x palette
# =============================================================================
C = {
    # Backgrounds — from darkest to lightest
    "bg_dark":      "#1a1a1a",     # Darkest: chat area, file tree, bottom panel, line numbers
    "bg":           "#1e1e1e",     # Standard: editor, toolbar, panel headers, apply bar, input areas
    "bg_sidebar":   "#181818",     # Sidebar strip only
    "bg_input":     "#2a2a2a",     # Input fields, combo boxes, user chat bubbles, code blocks
    "bg_hover":     "#252525",     # Hover state for items, also active sidebar button bg
    # Borders
    "border":       "#2a2a2a",     # Primary border — dividers, panel edges, separators
    "border_light": "#333333",     # Secondary border — toolbar button outlines, subtle dividers
    # Text
    "fg":           "#d4d4d4",     # Primary text — body copy, labels, code
    "fg_dim":       "#888888",     # Secondary text — placeholders, descriptions, hints
    "fg_head":      "#e0e0e0",     # Emphasis text — active tabs, headers, bright labels
    "fg_muted":     "#555555",     # Muted — line numbers, disabled text
    # Semantic colors
    "teal":         "#00979d",     # Primary accent — active states, primary buttons, AI name, links
    "teal_hover":   "#00b5bc",     # Hover state for teal elements
    "teal_light":   "#4ecdc4",     # Success messages, lighter teal accents
    "danger":       "#c62828",     # Danger buttons (delete, destructive actions)
    "fg_err":       "#f44747",     # Error labels (speaker name "Error")
    "fg_err_text":  "#f08080",     # Error body text (softer red)
    "fg_warn":      "#e8b54d",     # Warnings, folder icons
    "fg_ok":        "#4ec9b0",     # Success/applied messages
    "fg_link":      "#7aafff",     # User speaker name "You", clickable links
    # Syntax highlighting (editor only)
    "syn_kw":       "#569cd6",     # Keywords (if, else, for, return)
    "syn_cmt":      "#6a9955",     # Comments
    "syn_str":      "#ce9178",     # Strings
    "syn_num":      "#b5cea8",     # Numbers
    "syn_pp":       "#c586c0",     # Preprocessor, control flow
    "syn_type":     "#4ec9b0",     # Types (int, void, uint8_t)
    "syn_fn":       "#dcdcaa",     # Function names
}

# =============================================================================
# Design System — consistent sizes, styles, colors
# =============================================================================
FONT_TITLE    = "font-size: 14px; font-weight: bold;"     # Panel titles (branch, project name)
FONT_SECTION  = "font-size: 13px; font-weight: bold;"     # Section headers (Branches, Tags)
FONT_BODY     = "font-size: 13px;"                        # Standard body text
FONT_SMALL    = "font-size: 11px;"                        # Hints, status, secondary labels
FONT_CODE     = "font-family: Menlo, Monaco, 'Courier New', monospace; font-size: 13px;"
FONT_CHAT     = "font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 14px;"
FONT_CHAT_BOLD = "font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 14px; font-weight: bold;"
FONT_ICON      = "font-size: 16px;"                        # Sidebar icon characters

# Shared button style strings
BTN_PRIMARY = (f"background:{C['teal']};color:white;border:none;"
               f"border-radius:4px;padding:6px 14px;{FONT_BODY}font-weight:bold;")
BTN_SECONDARY = (f"background:{C['bg_input']};color:{C['fg']};border:1px solid {C['border_light']};"
                 f"border-radius:4px;padding:6px 14px;{FONT_BODY}")
BTN_DANGER = (f"background:{C['danger']};color:white;border:none;"
              f"border-radius:4px;padding:6px 14px;{FONT_BODY}font-weight:bold;")
BTN_TOOLBAR = (f"background:{C['teal']};color:white;border:none;"
               f"border-radius:4px;padding:6px 14px;{FONT_BODY}font-weight:bold;")
BTN_GHOST = (f"background:transparent;color:{C['teal']};border:none;"
             f"{FONT_SMALL}text-decoration:underline;")
BTN_CHAT_SEND = (f"background:{C['teal']};color:white;border:none;"
                 f"border-radius:10px;font-weight:600;padding:8px 20px;{FONT_CHAT}")
BTN_CHAT_STOP = (f"background:{C['bg_input']};color:{C['fg']};border:1px solid {C['border_light']};"
                 f"border-radius:10px;padding:8px 20px;{FONT_CHAT}")

PANEL_HEADER_STYLE = (
    f"background: {C['bg']}; border-bottom: 1px solid {C['border']};"
    f" min-height: 36px; max-height: 40px;")

# =============================================================================
# Working Set — prioritized file context with token budget
# =============================================================================

@dataclass
class WorkingSetEntry:
    """A single file in the working set with its priority and content."""
    filepath: str          # absolute path
    rel_path: str          # relative to project root
    priority: int          # 0=active tab, 1=AI-edited, 2=user-opened, 3=project file
    content: str
    token_estimate: int    # len(content) // 4 approximation


@dataclass
class WorkingSet:
    """Manages which project files the AI sees, constrained by a token budget.
    High-priority files (active tab, AI-edited) are always included.
    Lower-priority files are included until the budget is exhausted."""
    entries: dict = field(default_factory=dict)   # rel_path -> WorkingSetEntry
    budget: int = 12_000                          # max tokens for file content

    def add(self, filepath, rel_path, priority, content):
        """Add or update a file in the working set."""
        est = len(content) // 4
        self.entries[rel_path] = WorkingSetEntry(filepath, rel_path, priority, content, est)

    def remove(self, rel_path):
        """Remove a file from the working set."""
        self.entries.pop(rel_path, None)

    def clear(self):
        """Remove all entries."""
        self.entries.clear()

    def build_context(self, project_name, project_path, tree_str):
        """Build context string fitting within token budget.
        High-priority files are included first; overflow gets a one-line stub."""
        sorted_entries = sorted(self.entries.values(), key=lambda e: e.priority)
        included = []
        stubs = []
        used = 0
        for entry in sorted_entries:
            if used + entry.token_estimate <= self.budget or entry.priority == 0:
                included.append(entry)
                used += entry.token_estimate
            else:
                size_chars = len(entry.content)
                stubs.append(
                    f"[FILE: {entry.rel_path} — {size_chars} chars, not included (budget)]")
        parts = [
            f"[PROJECT: {project_name}]",
            f"[DIRECTORY: {project_path}]",
            "",
            "[PROJECT STRUCTURE]",
            tree_str,
            "",
        ]
        if included:
            parts.append(
                f"[Included {len(included)} file(s), {len(stubs)} excluded by budget]")
            parts.append("")
            for e in included:
                label = "ACTIVE FILE" if e.priority == 0 else "FILE"
                parts.append(f"========== {label}: {e.rel_path} ==========")
                parts.append(e.content)
                parts.append(f"========== END: {e.rel_path} ==========\n")
        if stubs:
            parts.extend(stubs)
        return "\n".join(parts)

    @property
    def total_tokens(self):
        """Total estimated tokens across all entries."""
        return sum(e.token_estimate for e in self.entries.values())

    @property
    def included_count(self):
        """Number of files that would fit within the budget."""
        sorted_entries = sorted(self.entries.values(), key=lambda e: e.priority)
        used = 0
        count = 0
        for e in sorted_entries:
            if used + e.token_estimate <= self.budget or e.priority == 0:
                used += e.token_estimate
                count += 1
        return count


# =============================================================================
# AI turn result — typed container for one model response
# =============================================================================

@dataclass
class ProposedEdit:
    """A single edit parsed from AI output."""
    edit_type: str       # "edit" or "file"
    filename: str
    old_text: str        # None for "file" type
    new_text: str

@dataclass
class AIWorkResult:
    """Structured result of one AI turn. Populated by response parsing;
    consumed by apply/review logic. Future features (compile diagnostics,
    agent commands, rationale) attach here instead of ad-hoc side channels."""
    assistant_text: str = ""
    proposed_edits: list = field(default_factory=list)   # list[ProposedEdit]
    requested_reads: list = field(default_factory=list)  # list[str] — filenames (future)
    request_compile: bool = False                        # (future)
    warnings: list = field(default_factory=list)         # list[str]
    metadata: dict = field(default_factory=dict)


def _make_panel_header(title_text=""):
    """Create a standardized panel header bar. Returns (widget, title_label, layout).
    Callers can add buttons to the layout on the right side."""
    header = QWidget()
    header.setStyleSheet(PANEL_HEADER_STYLE)
    header.setFixedHeight(40)
    hl = QHBoxLayout(header)
    hl.setContentsMargins(10, 0, 10, 0)
    hl.setSpacing(8)
    title = QLabel(title_text)
    title.setStyleSheet(f"color: {C['fg_head']}; {FONT_TITLE}")
    hl.addWidget(title)
    hl.addStretch()
    return header, title, hl


OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "teensy-coder"
DEFAULT_FQBN = "teensy:avr:teensy40"

# Unified application config file
CONFIG_FILE = os.path.expanduser("~/.teensy_ide_config.json")

def _load_config():
    """Load application config from disk. Returns dict with defaults for missing keys."""
    defaults = {
        "project_path": None,
        "ollama_model": "teensy-coder",
        "board_fqbn": DEFAULT_FQBN,
        "port": "",
        "window_geometry": None,  # [x, y, width, height]
    }
    try:
        with open(CONFIG_FILE, "r") as f:
            saved = json.load(f)
        for k, v in saved.items():
            if k in defaults:
                defaults[k] = v
        return defaults
    except (FileNotFoundError, json.JSONDecodeError):
        return defaults

def _save_config(data):
    """Save application config to disk."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

# Board FQBN → friendly display name mapping
BOARD_DISPLAY = {
    "teensy:avr:teensy40": "Teensy 4.0",
    "teensy:avr:teensy41": "Teensy 4.1",
    "teensy:avr:teensy36": "Teensy 3.6",
    "teensy:avr:teensy32": "Teensy 3.2",
    "teensy:avr:teensyLC": "Teensy LC",
}
WINDOW_TITLE = "Teensy Ollama IDE"

# File extensions recognized as project files (used by AI context and file scanner)
PROJECT_EXTENSIONS = {".ino", ".cpp", ".c", ".h", ".hpp", ".md", ".txt", ".json", ".yaml", ".yml", ".cfg", ".ini"}
PROJECT_SKIP_DIRS = {'.git', '__pycache__', 'build', 'node_modules', '.venv', 'venv'}

SYSTEM_PROMPT = """You are an expert embedded C/C++ developer for Teensy microcontrollers (PJRC), running inside an IDE.
You write clean, efficient code for real-time applications.
You understand hardware registers, interrupts, DMA, timers, and peripheral configuration.

IMPORTANT CONTEXT: You can see the ENTIRE project — every file and the full directory structure are provided automatically with every message. You have complete project knowledge.

CRITICAL: You are running inside a code editor IDE. You CAN and SHOULD write code directly.
The IDE will parse your output and apply changes to the files. NEVER refuse to write code.
ALWAYS provide concrete code when the user asks for changes.

To replace existing code in a file, output this exact format:
<<<EDIT path/to/filename.ext
<<<OLD
(exact lines to find and replace — must match the file EXACTLY)
>>>NEW
(replacement lines)
>>>END

To write or rewrite an entire file (also used for CREATING NEW files):
<<<FILE path/to/filename.ext
(complete file contents)
>>>FILE

Rules:
- Use the RELATIVE PATH as shown in the directory tree (e.g., src/helper.cpp, not just helper.cpp).
- For files in the project root, just use the filename (e.g., sketch.ino).
- The OLD block must match existing code EXACTLY (including whitespace/indentation).
- You can include multiple EDIT or FILE blocks in one response.
- STRONGLY PREFER <<<EDIT over <<<FILE for ALL changes to existing files. <<<EDIT is safer because it only replaces what you specify. <<<FILE replaces THE ENTIRE FILE — any code you don't include will be DELETED.
- ONLY use <<<FILE for: (a) creating brand new files, or (b) completely rewriting a file from scratch when more than 50% of the code changes.
- For adding code (comments, functions, includes), use <<<EDIT with enough OLD context to find the insertion point.
- NEVER use <<<FILE just to add a comment or make a small change — use <<<EDIT.
- You can create files in new subdirectories — the IDE will create the directories.
- You can edit and create .ino, .cpp, .c, .h, .hpp, .md, .txt, .json, and other project files.
- Keep explanations brief and focused.
- ALWAYS provide code. Never say you cannot modify files — the IDE does that for you.
- Edit the CORRECT file. If the user says "add a comment to audio_init.h", edit audio_init.h — not any other file.
- NEVER use unified diff format (diff --git, @@, +/- lines). The IDE does NOT understand diffs. ONLY use <<<EDIT or <<<FILE format.

Example — editing an existing file:
<<<EDIT sketch.ino
<<<OLD
void setup() {
  Serial.begin(115200);
}
>>>NEW
void blinkLED(int pin, int ms) {
  digitalWrite(pin, HIGH);
  delay(ms);
  digitalWrite(pin, LOW);
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
}
>>>END

Example — creating a new file:
<<<FILE src/utils.h
#ifndef UTILS_H
#define UTILS_H
// Utility functions
void initPins();
#endif
>>>FILE"""

# =============================================================================
# Stylesheet
# =============================================================================
STYLESHEET = f"""
QMainWindow {{ background-color: {C['bg']}; }}
QWidget {{ background-color: {C['bg']}; color: {C['fg']}; {FONT_BODY} }}

QToolBar {{
    background-color: {C['bg']};
    border-bottom: 1px solid {C['border']};
    padding: 6px 16px; spacing: 10px;
    min-height: 44px;
}}
QToolBar QLabel {{ color: {C['fg_dim']}; {FONT_SMALL} margin: 0 2px; background: transparent; border: none; }}
QToolBar QComboBox {{
    background-color: {C['bg_input']}; color: {C['fg']};
    border: 1px solid {C['border_light']}; border-radius: 4px;
    padding: 4px 24px 4px 8px; {FONT_BODY} min-height: 22px;
}}
QToolBar QComboBox QAbstractItemView {{
    background-color: {C['bg_input']}; color: {C['fg']};
    selection-background-color: {C['teal']};
}}
QToolBar::separator {{
    width: 1px; height: 24px; margin: 0 4px;
    background-color: {C['border_light']};
}}

QToolBar QPushButton {{
    background-color: transparent; color: {C['fg_head']};
    border: 1px solid {C['border_light']}; border-radius: 4px;
    padding: 6px 12px; {FONT_BODY}
}}
QToolBar QPushButton:hover {{ background-color: {C['bg_input']}; border-color: {C['border_light']}; }}
QToolBar QPushButton:pressed {{ background-color: {C['teal']}; color: white; }}

/* File tabs across top — wider, left-aligned text */
QTabWidget#fileTabs::pane {{ border: none; }}
QTabBar#fileTabBar {{ background-color: {C['bg_dark']}; }}
QTabBar#fileTabBar::tab {{
    background-color: {C['bg_dark']}; color: {C['fg_dim']};
    border: none; border-right: 1px solid {C['border']};
    padding: 8px 20px 8px 16px; min-width: 120px;
    text-align: left;
}}
QTabBar#fileTabBar::tab:selected {{
    background-color: {C['bg']}; color: {C['fg_head']};
    border-bottom: 2px solid {C['teal']};
}}
QTabBar#fileTabBar::tab:hover:!selected {{
    background-color: {C['bg_hover']}; color: {C['fg']};
}}
QTabBar#fileTabBar::close-button {{
    subcontrol-position: right;
    padding: 2px;
    margin-right: 6px;
}}

/* Bottom panel tabs */
QTabWidget#bottomTabs::pane {{ border: none; background-color: {C['bg_dark']}; }}
QTabWidget#bottomTabs > QTabBar::tab {{
    background-color: {C['bg_dark']}; color: {C['fg_dim']};
    border: none; border-right: 1px solid {C['border']};
    padding: 6px 14px; min-width: 80px;
}}
QTabWidget#bottomTabs > QTabBar::tab:selected {{
    background-color: {C['bg']}; color: {C['fg_head']};
    border-bottom: 2px solid {C['teal']};
}}
QTabWidget#bottomTabs > QTabBar::tab:hover:!selected {{
    background-color: {C['bg_hover']};
}}

QTreeView {{
    background-color: {C['bg']}; color: {C['fg']};
    border: 1px solid {C['border']}; border-radius: 4px;
    {FONT_BODY}
}}
QTreeView::item {{ padding: 4px 6px; }}
QTreeView::item:selected {{ background-color: {C['teal']}; color: white; }}
QTreeView::item:hover:!selected {{ background-color: {C['bg_hover']}; }}
QTreeView::branch {{ background-color: {C['bg']}; }}

QSplitter::handle {{ background-color: {C['border']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

QPlainTextEdit, QTextEdit {{
    background-color: {C['bg_dark']}; color: {C['fg']};
    border: none; {FONT_CODE} padding: 6px;
}}
QLineEdit {{
    background-color: {C['bg_input']}; color: {C['fg']};
    border: 1px solid {C['border']}; border-radius: 4px;
    padding: 6px 8px; {FONT_BODY}
}}
QLineEdit:focus {{ border-color: {C['teal']}; }}

QPushButton {{
    background-color: {C['bg_input']}; color: {C['fg']};
    border: 1px solid {C['border']}; border-radius: 4px;
    padding: 4px 10px; {FONT_BODY}
}}
QPushButton:hover {{ background-color: {C['bg_hover']}; border-color: {C['teal']}; }}

QGroupBox {{
    background: transparent;
    border: 1px solid {C['border_light']}; border-radius: 6px;
    margin-top: 8px; padding-top: 12px;
    font-weight: bold; color: {C['fg_head']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: {C['fg_head']};
}}

QComboBox {{
    background-color: {C['bg_input']}; color: {C['fg']};
    border: 1px solid {C['border_light']}; border-radius: 4px;
    padding: 4px 24px 4px 8px; {FONT_BODY}
}}
QComboBox:hover, QComboBox:focus {{ border-color: {C['teal']}; }}
QComboBox::drop-down {{
    border: none; width: 20px;
    subcontrol-origin: padding; subcontrol-position: right center;
}}
QComboBox::down-arrow {{
    width: 0; height: 0;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 6px solid {C['fg_dim']};
}}
QComboBox:hover::down-arrow {{ border-top-color: {C['fg']}; }}
QComboBox QAbstractItemView {{
    background-color: {C['bg_input']}; color: {C['fg']};
    selection-background-color: {C['teal']};
    selection-color: white;
}}

QScrollBar:vertical {{
    background: {C['bg']}; width: 8px; border: none;
}}
QScrollBar::handle:vertical {{
    background: {C['border_light']}; border-radius: 4px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {C['fg_muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {C['bg']}; height: 8px; border: none;
}}
QScrollBar::handle:horizontal {{
    background: {C['border_light']}; border-radius: 4px; min-width: 20px;
}}

QMenu {{
    background-color: {C['bg_input']};
    color: {C['fg']};
    border: 1px solid {C['border_light']};
    border-radius: 6px;
    padding: 4px 0px;
    {FONT_BODY}
}}
QMenu::item {{
    padding: 6px 14px 6px 14px;
    margin: 0px 4px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {C['teal']};
    color: white;
}}
QMenu::item:disabled {{
    color: {C['fg_muted']};
}}
QMenu::separator {{
    height: 1px;
    background-color: {C['border_light']};
    margin: 4px 12px;
}}
QMenu::right-arrow {{
    width: 8px;
    height: 8px;
}}

/* Settings panel tabs */
QTabWidget#settingsTabs::pane {{ border: none; background-color: {C['bg']}; }}
QTabWidget#settingsTabs > QTabBar::tab {{
    background-color: {C['bg_dark']}; color: {C['fg_dim']};
    border: none; border-right: 1px solid {C['border']};
    padding: 6px 16px; min-width: 90px;
}}
QTabWidget#settingsTabs > QTabBar::tab:selected {{
    background-color: {C['bg']}; color: {C['fg_head']};
    border-bottom: 2px solid {C['teal']};
}}
QTabWidget#settingsTabs > QTabBar::tab:hover:!selected {{
    background-color: {C['bg_hover']};
}}

QListWidget {{
    background-color: {C['bg']}; color: {C['fg']};
    border: 1px solid {C['border']}; border-radius: 4px;
    {FONT_BODY} outline: none;
}}
QListWidget::item {{ padding: 4px 6px; }}
QListWidget::item:selected {{ background-color: {C['teal']}; color: white; }}
QListWidget::item:hover:!selected {{ background-color: {C['bg_hover']}; }}
"""


# =============================================================================
# Left Sidebar Icon Button
# =============================================================================

class SidebarButton(QPushButton):
    """Icon button for the left sidebar, drawn with simple Unicode/text."""
    def __init__(self, icon_text, tooltip, parent=None):
        super().__init__(icon_text, parent)
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setFixedSize(40, 40)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {C['fg_muted']};
                border: none; {FONT_ICON} border-radius: 6px;
            }}
            QPushButton:hover {{ color: {C['fg_dim']}; background-color: {C['bg_hover']}; }}
            QPushButton:checked {{
                color: white; background-color: {C['bg_hover']};
            }}
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        # Draw teal accent bar on left when checked
        if self.isChecked():
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(C['teal']))
            p.drawRoundedRect(0, 8, 3, self.height() - 16, 2, 2)
            p.end()


class GitSidebarButton(SidebarButton):
    """Sidebar button with a custom-painted Git branch icon."""
    def __init__(self, tooltip, parent=None):
        super().__init__("", tooltip, parent)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = QColor(C['fg']) if self.isChecked() or self.underMouse() else QColor(C['fg_dim'])
        p.setPen(QPen(col, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = self.width() / 2, self.height() / 2
        # Main vertical line (trunk) — 16px icon
        p.drawLine(int(cx), int(cy - 8), int(cx), int(cy + 8))
        # Branch line forking off to the right
        p.drawLine(int(cx), int(cy - 1), int(cx + 7), int(cy - 7))
        # Dots at the nodes (commits)
        p.setBrush(col)
        r = 2
        p.drawEllipse(int(cx - r), int(cy + 8 - r), r * 2, r * 2)     # bottom
        p.drawEllipse(int(cx - r), int(cy - 8 - r), r * 2, r * 2)     # top
        p.drawEllipse(int(cx + 7 - r), int(cy - 7 - r), r * 2, r * 2) # branch tip
        p.end()


class FileSidebarButton(SidebarButton):
    """Sidebar button with a custom-painted folder icon."""
    def __init__(self, tooltip, parent=None):
        super().__init__("", tooltip, parent)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = QColor(C['fg']) if self.isChecked() or self.underMouse() else QColor(C['fg_dim'])
        p.setPen(QPen(col, 1.5))
        cx, cy = self.width() / 2, self.height() / 2
        # Folder body (20×12)
        p.setBrush(Qt.BrushStyle.NoBrush)
        body_l, body_t = int(cx - 10), int(cy - 3)
        p.drawRect(body_l, body_t, 20, 12)
        # Folder tab on top-left
        p.drawLine(body_l, body_t, body_l, int(cy - 7))
        p.drawLine(body_l, int(cy - 7), int(cx - 3), int(cy - 7))
        p.drawLine(int(cx - 3), int(cy - 7), int(cx - 1), body_t)
        p.end()


class SettingsSidebarButton(SidebarButton):
    """Sidebar button with a custom-painted gear icon (larger than unicode)."""
    def __init__(self, tooltip, parent=None):
        super().__init__("", tooltip, parent)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = QColor(C['fg']) if self.isChecked() or self.underMouse() else QColor(C['fg_dim'])
        p.setPen(QPen(col, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = self.width() / 2, self.height() / 2
        p.translate(cx, cy)
        # Gear: 8 teeth (16×16 icon area)
        teeth = 8
        outer_r, inner_r = 8, 5
        tooth_half = math.pi / teeth * 0.45
        path = QPainterPath()
        points = []
        for i in range(teeth):
            a = 2 * math.pi * i / teeth
            # Outer tooth corners
            points.append(QPointF(outer_r * math.cos(a - tooth_half),
                                  outer_r * math.sin(a - tooth_half)))
            points.append(QPointF(outer_r * math.cos(a + tooth_half),
                                  outer_r * math.sin(a + tooth_half)))
            # Inner valley between teeth
            a2 = 2 * math.pi * (i + 0.5) / teeth
            points.append(QPointF(inner_r * math.cos(a2 - tooth_half),
                                  inner_r * math.sin(a2 - tooth_half)))
            points.append(QPointF(inner_r * math.cos(a2 + tooth_half),
                                  inner_r * math.sin(a2 + tooth_half)))
        path.addPolygon(QPolygonF(points))
        path.closeSubpath()
        p.drawPath(path)
        # Center hole
        p.drawEllipse(-3, -3, 6, 6)
        p.end()


class SpinnerWidget(QWidget):
    """Animated spinning gear indicator for AI activity."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._active = False
        self.hide()

    def start(self):
        self._active = True
        self._angle = 0
        self.show()
        self._timer.start(40)

    def stop(self):
        self._active = False
        self._timer.stop()
        self.hide()

    def _rotate(self):
        self._angle = (self._angle + 15) % 360
        self.update()

    def paintEvent(self, event):
        if not self._active:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(12, 12)
        p.rotate(self._angle)
        col = QColor(C['teal'])
        # Draw gear teeth
        pen = QPen(col, 2.0)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        teeth = 8
        outer_r, inner_r = 9, 5
        for i in range(teeth):
            angle = math.radians(i * 360 / teeth)
            x1, y1 = inner_r * math.cos(angle), inner_r * math.sin(angle)
            x2, y2 = outer_r * math.cos(angle), outer_r * math.sin(angle)
            p.drawLine(int(x1), int(y1), int(x2), int(y2))
        # Center circle
        p.setBrush(QColor(C["bg_dark"]))
        p.drawEllipse(-3, -3, 6, 6)
        p.setBrush(col)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(-2, -2, 4, 4)
        p.end()


# =============================================================================
# Ollama Worker
# =============================================================================

class OllamaWorker(QObject):
    token_received = pyqtSignal(str)
    response_complete = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.messages = []
        self._stop = False

    def stop(self): self._stop = True

    def run(self):
        self._stop = False
        try:
            resp = requests.post(OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "messages": self.messages, "stream": True},
                stream=True, timeout=(5, 120))
            resp.raise_for_status()
            for line in resp.iter_lines():
                if self._stop:
                    resp.close()
                    break
                if line:
                    try:
                        chunk = json.loads(line)
                        t = chunk.get("message", {}).get("content", "")
                        if t: self.token_received.emit(t)
                        if chunk.get("done"): break
                    except json.JSONDecodeError:
                        continue
        except requests.exceptions.ConnectionError:
            if not self._stop:
                self.error_occurred.emit("Cannot connect to Ollama. Is 'ollama serve' running?")
        except Exception as e:
            if not self._stop:
                self.error_occurred.emit(str(e))
        finally:
            if not self._stop:
                self.response_complete.emit()


# =============================================================================
# AI Context Menu Actions
# =============================================================================

DEFAULT_AI_ACTIONS = [
    ("Explain This Code",
     "Explain what the following code does in clear, concise terms. "
     "Mention any Teensy/Arduino-specific details:\n\n```cpp\n{code}\n```"),
    ("Fix / Improve",
     "Review the following code for bugs, issues, or improvements. "
     "Suggest fixes using the <<<EDIT format:\n\n```cpp\n{code}\n```"),
    ("Refactor",
     "Refactor the following code to be cleaner, more readable, and more efficient "
     "while preserving exact behavior. Use the <<<EDIT format:\n\n```cpp\n{code}\n```"),
    ("Add Comments",
     "Add clear, useful inline comments to the following code. "
     "Use the <<<EDIT format to show the commented version:\n\n```cpp\n{code}\n```"),
    ("Find Bugs",
     "Carefully analyze the following code for potential bugs, memory issues, "
     "race conditions, undefined behavior, or Teensy-specific pitfalls:\n\n```cpp\n{code}\n```"),
    ("Optimize for Teensy",
     "Optimize the following code specifically for Teensy performance: "
     "minimize memory usage, use DMA/hardware features where possible, "
     "reduce latency. Use the <<<EDIT format:\n\n```cpp\n{code}\n```"),
    ("Generate Test",
     "Write a simple test or validation sketch that exercises the following code. "
     "Include Serial output to verify correct behavior:\n\n```cpp\n{code}\n```"),
    None,  # separator
    ("Ask AI About This...",  None),  # special: opens a prompt dialog
]

AI_ACTIONS = list(DEFAULT_AI_ACTIONS)
AI_ACTIONS_FILE = os.path.expanduser("~/.teensy_ide_ai_actions.json")

def _load_ai_actions():
    """Load AI actions from config file, or use defaults."""
    global AI_ACTIONS
    try:
        with open(AI_ACTIONS_FILE, "r") as f:
            data = json.load(f)
        actions = []
        for entry in data.get("actions", []):
            if entry is None:
                actions.append(None)
            else:
                actions.append((entry["label"], entry.get("template")))
        # Ensure "Ask AI About This..." is always last
        has_ask = any(e is not None and e[0] == "Ask AI About This..." for e in actions)
        if not has_ask:
            actions.append(("Ask AI About This...", None))
        AI_ACTIONS[:] = actions
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        AI_ACTIONS[:] = list(DEFAULT_AI_ACTIONS)

def _save_ai_actions():
    """Persist current AI_ACTIONS to config file."""
    entries = []
    for entry in AI_ACTIONS:
        if entry is None:
            entries.append(None)
        else:
            entries.append({"label": entry[0], "template": entry[1]})
    try:
        with open(AI_ACTIONS_FILE, "w") as f:
            json.dump({"version": 1, "actions": entries}, f, indent=2)
    except Exception:
        pass


# =============================================================================
# Curated Models for Pull Model browser
# =============================================================================

CURATED_MODELS = [
    {"name": "llama3.2:latest",       "size": "2.0 GB",  "desc": "Meta Llama 3.2 — fast, general purpose"},
    {"name": "llama3.2:1b",           "size": "1.3 GB",  "desc": "Llama 3.2 1B — ultra-lightweight"},
    {"name": "llama3.1:8b",           "size": "4.7 GB",  "desc": "Meta Llama 3.1 8B — strong all-rounder"},
    {"name": "codellama:7b",          "size": "3.8 GB",  "desc": "Code-specialized Llama for programming"},
    {"name": "codellama:13b",         "size": "7.4 GB",  "desc": "Larger Code Llama — better code quality"},
    {"name": "deepseek-coder-v2:16b", "size": "8.9 GB",  "desc": "DeepSeek Coder V2 — strong coding model"},
    {"name": "qwen2.5-coder:7b",     "size": "4.7 GB",  "desc": "Alibaba Qwen 2.5 — excellent at code"},
    {"name": "qwen2.5-coder:1.5b",   "size": "1.0 GB",  "desc": "Qwen 2.5 Coder tiny — fast code assistant"},
    {"name": "mistral:7b",            "size": "4.1 GB",  "desc": "Mistral 7B — efficient general model"},
    {"name": "mixtral:8x7b",          "size": "26 GB",   "desc": "Mixtral MoE — mixture of experts"},
    {"name": "phi3:mini",             "size": "2.3 GB",  "desc": "Microsoft Phi-3 Mini — small but capable"},
    {"name": "phi3:medium",           "size": "7.9 GB",  "desc": "Microsoft Phi-3 Medium — balanced"},
    {"name": "gemma2:2b",             "size": "1.6 GB",  "desc": "Google Gemma 2 2B — compact"},
    {"name": "gemma2:9b",             "size": "5.4 GB",  "desc": "Google Gemma 2 9B — strong mid-size"},
    {"name": "starcoder2:3b",         "size": "1.7 GB",  "desc": "StarCoder2 3B — code completion"},
    {"name": "starcoder2:7b",         "size": "4.0 GB",  "desc": "StarCoder2 7B — better code generation"},
    {"name": "nomic-embed-text",      "size": "274 MB",  "desc": "Nomic text embeddings model"},
    {"name": "tinyllama:1.1b",        "size": "638 MB",  "desc": "TinyLlama — extremely lightweight"},
]


# =============================================================================
# Code Editor
# =============================================================================

def _build_ai_context_menu(editor_widget, menu, selected_text):
    """Add AI actions to a context menu. Returns list of (action, prompt_template) pairs."""
    from PyQt6.QtWidgets import QMenu
    if not selected_text.strip():
        return []
    ai_menu = QMenu("  AI Tools", menu)
    pairs = []
    for entry in AI_ACTIONS:
        if entry is None:
            ai_menu.addSeparator()
            continue
        label, template = entry
        a = QAction(label, editor_widget)
        ai_menu.addAction(a)
        pairs.append((a, template))
    menu.addSeparator()
    menu.addMenu(ai_menu)
    return pairs


if HAS_QSCINTILLA:
    class CodeEditor(QsciScintilla):
        ai_action_requested = pyqtSignal(str)  # emits the full prompt

        def __init__(self, parent=None):
            super().__init__(parent)
            self._current_file = None
            font = QFont("Menlo", 13)
            font.setStyleHint(QFont.StyleHint.Monospace)
            self.setFont(font)
            self.setPaper(QColor(C["bg"]))
            self.setColor(QColor(C["fg"]))
            self.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
            self.setMarginWidth(0, "00000")
            self.setMarginsForegroundColor(QColor(C["fg_dim"]))
            self.setMarginsBackgroundColor(QColor(C["bg"]))
            self.setCaretLineVisible(True)
            self.setCaretLineBackgroundColor(QColor(C["bg_input"]))
            self.setCaretForegroundColor(QColor(C["fg"]))
            self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
            self.setMatchedBraceBackgroundColor(QColor(C["border_light"]))
            self.setMatchedBraceForegroundColor(QColor(C["fg"]))
            self.setAutoIndent(True)
            self.setIndentationGuides(True)
            self.setIndentationGuidesBackgroundColor(QColor(C["border"]))
            self.setIndentationGuidesForegroundColor(QColor(C['border_light']))
            self.setTabWidth(2)
            self.setIndentationsUseTabs(False)
            self.setEdgeMode(QsciScintilla.EdgeMode.EdgeNone)
            self.setFolding(QsciScintilla.FoldStyle.BoxedTreeFoldStyle)
            self.setFoldMarginColors(QColor(C["bg"]), QColor(C["bg"]))
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self._show_context_menu)
            # Lexer
            lexer = QsciLexerCPP(self)
            lexer.setFont(font)
            lexer.setDefaultPaper(QColor(C["bg"]))
            lexer.setDefaultColor(QColor(C["fg"]))
            for i in range(20): lexer.setPaper(QColor(C["bg"]), i)
            lexer.setColor(QColor(C["fg"]),      QsciLexerCPP.Default)
            lexer.setColor(QColor(C["syn_cmt"]), QsciLexerCPP.Comment)
            lexer.setColor(QColor(C["syn_cmt"]), QsciLexerCPP.CommentLine)
            lexer.setColor(QColor(C["syn_cmt"]), QsciLexerCPP.CommentDoc)
            lexer.setColor(QColor(C["syn_kw"]),  QsciLexerCPP.Keyword)
            lexer.setColor(QColor(C["syn_str"]), QsciLexerCPP.DoubleQuotedString)
            lexer.setColor(QColor(C["syn_str"]), QsciLexerCPP.SingleQuotedString)
            lexer.setColor(QColor(C["syn_num"]), QsciLexerCPP.Number)
            lexer.setColor(QColor(C["syn_pp"]),  QsciLexerCPP.PreProcessor)
            lexer.setColor(QColor(C["syn_type"]),QsciLexerCPP.GlobalClass)
            lexer.setColor(QColor(C["fg"]),      QsciLexerCPP.Operator)
            lexer.setColor(QColor(C["fg"]),      QsciLexerCPP.Identifier)
            try: lexer.setKeywords(1, "setup loop pinMode digitalWrite digitalRead analogWrite analogRead Serial delay millis micros attachInterrupt digitalWriteFast IntervalTimer AudioStream AudioConnection AudioMemory Wire SPI INPUT OUTPUT HIGH LOW volatile")
            except: pass
            self.setLexer(lexer)

        def _show_context_menu(self, pos):
            from PyQt6.QtWidgets import QMenu, QInputDialog
            menu = QMenu(self)
            # Standard editing actions with keyboard shortcuts
            if self.hasSelectedText():
                a_cut = QAction("Cut", self)
                a_cut.setShortcut(QKeySequence("Ctrl+X"))
                a_cut.triggered.connect(self.cut)
                menu.addAction(a_cut)
                a_copy = QAction("Copy", self)
                a_copy.setShortcut(QKeySequence("Ctrl+C"))
                a_copy.triggered.connect(self.copy)
                menu.addAction(a_copy)
            a_paste = QAction("Paste", self)
            a_paste.setShortcut(QKeySequence("Ctrl+V"))
            a_paste.triggered.connect(self.paste)
            menu.addAction(a_paste)
            menu.addSeparator()
            a_all = QAction("Select All", self)
            a_all.setShortcut(QKeySequence("Ctrl+A"))
            a_all.triggered.connect(self.selectAll)
            menu.addAction(a_all)

            sel = self.selectedText()
            pairs = _build_ai_context_menu(self, menu, sel)

            chosen = menu.exec(self.mapToGlobal(pos))
            if not chosen:
                return
            for a, template in pairs:
                if chosen == a:
                    if template is None:
                        # "Ask AI About This..." — show input dialog
                        question, ok = QInputDialog.getText(
                            self, "Ask AI", "What do you want to know about this code?")
                        if ok and question.strip():
                            prompt = f"{question.strip()}\n\n```cpp\n{sel}\n```"
                            self.ai_action_requested.emit(prompt)
                    else:
                        self.ai_action_requested.emit(template.format(code=sel))
                    break

        def load_file(self, fp):
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f: self.setText(f.read())
                self._current_file = fp; return True
            except: return False

        def save_file(self, fp=None):
            p = fp or self._current_file
            if not p: return False
            try:
                with open(p, "w", encoding="utf-8") as f: f.write(self.text())
                self._current_file = p; return True
            except: return False

        @property
        def current_file(self): return self._current_file
else:
    class CodeEditor(QPlainTextEdit):
        ai_action_requested = pyqtSignal(str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._current_file = None
            font = QFont("Menlo", 13)
            self.setFont(font)
            self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self._show_context_menu)

        def _show_context_menu(self, pos):
            from PyQt6.QtWidgets import QMenu, QInputDialog
            menu = self.createStandardContextMenu()
            sel = self.textCursor().selectedText()
            pairs = _build_ai_context_menu(self, menu, sel)
            chosen = menu.exec(self.mapToGlobal(pos))
            if not chosen:
                return
            for a, template in pairs:
                if chosen == a:
                    if template is None:
                        question, ok = QInputDialog.getText(
                            self, "Ask AI", "What do you want to know about this code?")
                        if ok and question.strip():
                            prompt = f"{question.strip()}\n\n```cpp\n{sel}\n```"
                            self.ai_action_requested.emit(prompt)
                    else:
                        self.ai_action_requested.emit(template.format(code=sel))
                    break

        def load_file(self, fp):
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f: self.setPlainText(f.read())
                self._current_file = fp; return True
            except: return False
        def save_file(self, fp=None):
            p = fp or self._current_file
            if not p: return False
            try:
                with open(p, "w", encoding="utf-8") as f: f.write(self.toPlainText())
                self._current_file = p; return True
            except: return False
        def text(self): return self.toPlainText()
        @property
        def current_file(self): return self._current_file


# =============================================================================
# Tabbed Editor — file tabs across top like Arduino IDE
# =============================================================================

class TabbedEditor(QWidget):
    file_changed = pyqtSignal(str)
    ai_action_requested = pyqtSignal(str)  # propagated from CodeEditor

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("fileTabs")
        self.tabs.tabBar().setObjectName("fileTabBar")
        self.tabs.setTabsClosable(True)
        self.tabs.tabBar().setExpanding(False)  # Left-justify tabs
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_changed)
        layout.addWidget(self.tabs)

        self._editors = {}

    def open_file(self, filepath):
        filepath = os.path.abspath(filepath)
        if filepath in self._editors:
            self.tabs.setCurrentWidget(self._editors[filepath])
            return True
        editor = CodeEditor()
        editor.ai_action_requested.connect(self.ai_action_requested.emit)
        if editor.load_file(filepath):
            self._editors[filepath] = editor
            idx = self.tabs.addTab(editor, os.path.basename(filepath))
            self.tabs.setCurrentIndex(idx)
            self.file_changed.emit(filepath)
            return True
        return False

    def open_all_project_files(self, project_path):
        """Open root-level project files as tabs, like Arduino IDE.
        Only opens sketch files (.ino, .cpp, .c, .h, .hpp) from the
        project root — the AI context scanner handles deeper scanning."""
        sketch_extensions = {".ino", ".cpp", ".c", ".h", ".hpp"}
        files = []
        for f in sorted(os.listdir(project_path)):
            ext = os.path.splitext(f)[1].lower()
            if ext in sketch_extensions:
                files.append(os.path.join(project_path, f))
        # Open .ino first, then others
        ino_files = [f for f in files if f.endswith(".ino")]
        other_files = [f for f in files if not f.endswith(".ino")]
        for f in ino_files + other_files:
            self.open_file(f)
        # Select the .ino tab
        if ino_files:
            self.tabs.setCurrentWidget(self._editors.get(ino_files[0]))

    def save_current(self):
        e = self.tabs.currentWidget()
        return e.save_file() if e and hasattr(e, 'save_file') else False

    def current_file(self):
        e = self.tabs.currentWidget()
        return e.current_file if e and hasattr(e, 'current_file') else None

    def current_text(self):
        e = self.tabs.currentWidget()
        return e.text() if e and hasattr(e, 'text') else ""

    def _close_tab(self, idx):
        w = self.tabs.widget(idx)
        for fp, ed in list(self._editors.items()):
            if ed == w: del self._editors[fp]; break
        self.tabs.removeTab(idx)

    def close_all(self):
        """Close all editor tabs."""
        self._editors.clear()
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)

    def get_all_files(self):
        """Return dict of {filepath: content} for all open files."""
        result = {}
        for fp, ed in self._editors.items():
            result[fp] = ed.text() if hasattr(ed, 'text') else ed.toPlainText()
        return result

    def set_file_content(self, filepath, content):
        """Set content of an open file by path. Updates editor and saves to disk.
        Returns True if found."""
        if filepath in self._editors:
            ed = self._editors[filepath]
            if hasattr(ed, 'setText'): ed.setText(content)
            else: ed.setPlainText(content)
            # Save to disk so changes persist
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
            except OSError:
                pass  # Editor updated even if disk write fails
            return True
        return False

    def find_file_by_name(self, name):
        """Find full path of an open file by basename or relative path."""
        # Try exact basename match first
        for fp in self._editors:
            if os.path.basename(fp) == name:
                return fp
        # Try relative path suffix match (e.g., "src/helper.cpp")
        for fp in self._editors:
            if fp.endswith("/" + name) or fp.endswith(os.sep + name):
                return fp
        return None

    def _on_changed(self, idx):
        e = self.tabs.widget(idx)
        if e and hasattr(e, 'current_file') and e.current_file:
            self.file_changed.emit(e.current_file)


# =============================================================================
# File Browser
# =============================================================================

class FileBrowser(QWidget):
    """Project file tree with the ability to open files in the editor."""
    file_requested = pyqtSignal(str)  # emits full path when user double-clicks

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tree view (no header bar — tabs above make it redundant)
        self.tree = QTreeView()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tree.setStyleSheet(
            f"QTreeView {{ background:{C['bg_dark']};border:none;{FONT_BODY} }}"
            f"QTreeView::item {{ padding: 4px 6px; }}"
            f"QTreeView::item:selected {{ background:{C['teal']};color:white; }}"
            f"QTreeView::item:hover:!selected {{ background:{C['bg_hover']}; }}")
        self.tree.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.tree)

        self._model = QStandardItemModel()
        self.tree.setModel(self._model)
        self._root_path = None

    def set_root(self, path):
        self._root_path = path
        self._refresh()

    def _refresh(self):
        self._model.clear()
        if not self._root_path or not os.path.isdir(self._root_path):
            return
        self._populate(self._model.invisibleRootItem(), self._root_path)
        self.tree.expandAll()

    def _populate(self, parent_item, dir_path):
        """Recursively add files and folders to the tree model."""
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return
        # Folders first, then files
        dirs = [e for e in entries if os.path.isdir(os.path.join(dir_path, e)) and not e.startswith('.')]
        files = [e for e in entries if os.path.isfile(os.path.join(dir_path, e)) and not e.startswith('.')]
        for d in dirs:
            item = QStandardItem(f"📁 {d}")
            item.setForeground(QColor(C["fg_dim"]))
            item.setData(os.path.join(dir_path, d), Qt.ItemDataRole.UserRole)
            item.setData("dir", Qt.ItemDataRole.UserRole + 1)
            parent_item.appendRow(item)
            self._populate(item, os.path.join(dir_path, d))
        for f in files:
            fp = os.path.join(dir_path, f)
            # Color code by extension
            ext = os.path.splitext(f)[1].lower()
            item = QStandardItem(f)
            if ext in ('.ino', '.cpp', '.c'):
                item.setForeground(QColor(C["syn_kw"]))
            elif ext in ('.h', '.hpp'):
                item.setForeground(QColor(C["syn_type"]))
            elif ext in ('.md', '.txt'):
                item.setForeground(QColor(C["fg_dim"]))
            else:
                item.setForeground(QColor(C["fg"]))
            item.setData(fp, Qt.ItemDataRole.UserRole)
            item.setData("file", Qt.ItemDataRole.UserRole + 1)
            parent_item.appendRow(item)

    def _on_double_click(self, index):
        item = self._model.itemFromIndex(index)
        if not item:
            return
        kind = item.data(Qt.ItemDataRole.UserRole + 1)
        if kind == "file":
            fp = item.data(Qt.ItemDataRole.UserRole)
            if fp:
                self.file_requested.emit(fp)


# =============================================================================
# File Manager View — File browser with parent context pane
# =============================================================================

class FileManagerView(QWidget):
    """Full file browser view with parent context pane, file tree, and action bar."""
    file_requested = pyqtSignal(str)  # emits full path to open in editor

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_path = None
        self._current_focus_path = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header, self.project_label, _ = _make_panel_header("Sketchbook")
        layout.addWidget(header)

        # Splitter: parent context (top) + file tree (bottom)
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # Top pane: parent context
        parent_container = QWidget()
        pc_layout = QVBoxLayout(parent_container)
        pc_layout.setContentsMargins(0, 0, 0, 0)
        pc_layout.setSpacing(0)

        parent_label = QLabel("  Parent Folder")
        parent_label.setStyleSheet(
            f"color:{C['fg_dim']};{FONT_SMALL} padding:4px 0px 4px 6px;"
            f"background:{C['bg_dark']};")
        pc_layout.addWidget(parent_label)

        self.parent_tree = QTreeView()
        self.parent_tree.setHeaderHidden(True)
        self.parent_tree.setRootIsDecorated(False)
        self.parent_tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.parent_tree.setStyleSheet(
            f"QTreeView {{ background:{C['bg_dark']};border:none;{FONT_BODY} }}"
            f"QTreeView::item {{ padding: 4px 6px; }}"
            f"QTreeView::item:selected {{ background:{C['teal']};color:white; }}"
            f"QTreeView::item:hover:!selected {{ background:{C['bg_hover']}; }}")
        self._parent_model = QStandardItemModel()
        self.parent_tree.setModel(self._parent_model)
        self.parent_tree.doubleClicked.connect(self._on_parent_double_click)
        pc_layout.addWidget(self.parent_tree)

        self.splitter.addWidget(parent_container)

        # Bottom pane: main file tree (reuse FileBrowser)
        self.file_browser = FileBrowser()
        self.file_browser.file_requested.connect(self.file_requested.emit)
        self.file_browser.tree.clicked.connect(self._on_tree_item_clicked)
        self.splitter.addWidget(self.file_browser)

        self.splitter.setSizes([120, 400])
        layout.addWidget(self.splitter)

        # Bottom action bar
        btns = QWidget()
        btns.setStyleSheet(f"background: {C['bg']}; border-top: 1px solid {C['border']};")
        bl = QHBoxLayout(btns)
        bl.setContentsMargins(16, 6, 16, 6)
        bl.setSpacing(8)

        new_file_btn = QPushButton("+ New File")
        new_file_btn.setStyleSheet(BTN_SECONDARY)
        new_file_btn.clicked.connect(self._new_file)
        bl.addWidget(new_file_btn)

        new_folder_btn = QPushButton("+ New Folder")
        new_folder_btn.setStyleSheet(BTN_SECONDARY)
        new_folder_btn.clicked.connect(self._new_folder)
        bl.addWidget(new_folder_btn)

        bl.addStretch()

        new_sketch_btn = QPushButton("New Sketch")
        new_sketch_btn.setStyleSheet(BTN_PRIMARY)
        new_sketch_btn.clicked.connect(self._new_sketch)
        bl.addWidget(new_sketch_btn)

        layout.addWidget(btns)

    def set_project(self, path):
        """Set root project path and refresh views."""
        self._project_path = path
        self.project_label.setText(os.path.basename(path) if path else "Sketchbook")
        self.file_browser.set_root(path)
        self._current_focus_path = path
        self._refresh_parent_context(path)

    def _on_tree_item_clicked(self, index):
        """When an item is clicked in the main tree, update parent context."""
        item = self.file_browser._model.itemFromIndex(index)
        if not item:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        kind = item.data(Qt.ItemDataRole.UserRole + 1)
        if kind == "dir":
            self._current_focus_path = path
        else:
            self._current_focus_path = os.path.dirname(path)
        self._refresh_parent_context(self._current_focus_path)

    def _refresh_parent_context(self, folder_path):
        """Show the parent directory contents in the top pane."""
        self._parent_model.clear()
        if not folder_path:
            return
        parent = os.path.dirname(folder_path)
        if not parent or not os.path.isdir(parent):
            return
        try:
            entries = sorted(os.listdir(parent))
        except PermissionError:
            return
        dirs = [e for e in entries if os.path.isdir(os.path.join(parent, e))
                and not e.startswith('.')]
        files = [e for e in entries if os.path.isfile(os.path.join(parent, e))
                 and not e.startswith('.')]
        for d in dirs:
            full = os.path.join(parent, d)
            item = QStandardItem(f"\U0001F4C1 {d}")
            item.setData(full, Qt.ItemDataRole.UserRole)
            item.setData("dir", Qt.ItemDataRole.UserRole + 1)
            if full == folder_path:
                item.setForeground(QColor(C["teal"]))
                f = item.font(); f.setBold(True); item.setFont(f)
            else:
                item.setForeground(QColor(C["fg_dim"]))
            self._parent_model.appendRow(item)
        for fname in files:
            fp = os.path.join(parent, fname)
            item = QStandardItem(fname)
            ext = os.path.splitext(fname)[1].lower()
            if ext in ('.ino', '.cpp', '.c'):
                item.setForeground(QColor(C["syn_kw"]))
            elif ext in ('.h', '.hpp'):
                item.setForeground(QColor(C["syn_type"]))
            elif ext in ('.md', '.txt'):
                item.setForeground(QColor(C["fg_dim"]))
            else:
                item.setForeground(QColor(C["fg"]))
            item.setData(fp, Qt.ItemDataRole.UserRole)
            item.setData("file", Qt.ItemDataRole.UserRole + 1)
            self._parent_model.appendRow(item)

    def _on_parent_double_click(self, index):
        """Handle double-click in parent context pane."""
        item = self._parent_model.itemFromIndex(index)
        if not item:
            return
        kind = item.data(Qt.ItemDataRole.UserRole + 1)
        path = item.data(Qt.ItemDataRole.UserRole)
        if kind == "file":
            self.file_requested.emit(path)
        elif kind == "dir":
            self.file_browser.set_root(path)
            self._current_focus_path = path
            self._refresh_parent_context(path)

    def _new_file(self):
        """Create a new file in the current focus directory."""
        target = self._current_focus_path or self._project_path
        if not target:
            return
        name, ok = QInputDialog.getText(self, "New File", "File name:")
        if ok and name:
            fp = os.path.join(target, name)
            try:
                with open(fp, 'w') as f:
                    f.write("")
                self.file_browser._refresh()
                self._refresh_parent_context(self._current_focus_path)
                self.file_requested.emit(fp)
            except OSError as e:
                QMessageBox.warning(self, "Error", str(e))

    def _new_folder(self):
        """Create a new folder in the current focus directory."""
        target = self._current_focus_path or self._project_path
        if not target:
            return
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            fp = os.path.join(target, name)
            try:
                os.makedirs(fp, exist_ok=True)
                self.file_browser._refresh()
                self._refresh_parent_context(self._current_focus_path)
            except OSError as e:
                QMessageBox.warning(self, "Error", str(e))

    def _new_sketch(self):
        """Create a new Arduino sketch folder with a .ino file."""
        target = self._current_focus_path or self._project_path
        if not target:
            target = os.path.expanduser("~/Documents/Arduino")
            os.makedirs(target, exist_ok=True)
        name, ok = QInputDialog.getText(self, "New Sketch", "Sketch name:")
        if ok and name:
            sketch_dir = os.path.join(target, name)
            ino_file = os.path.join(sketch_dir, f"{name}.ino")
            try:
                os.makedirs(sketch_dir, exist_ok=True)
                with open(ino_file, "w") as f:
                    f.write(f"// {name}.ino\n\nvoid setup() {{\n\n}}\n\nvoid loop() {{\n\n}}\n")
                self.file_browser._refresh()
                self._refresh_parent_context(self._current_focus_path)
                # Signal to open the new sketch file
                self.file_requested.emit(ino_file)
            except OSError as e:
                QMessageBox.warning(self, "Error", str(e))


# =============================================================================
# Chat Panel
# =============================================================================

class ChatPanel(QWidget):
    """AI chat with automatic project context and code-edit application."""
    apply_edit = pyqtSignal(str, str, str)  # filename, old, new
    apply_file = pyqtSignal(str, str)        # filename, full content
    generation_started = pyqtSignal()
    generation_finished = pyqtSignal()
    edits_applied = pyqtSignal()             # emitted after edits are successfully applied
    model_switch_requested = pyqtSignal(str)  # model name — request toolbar combo update

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_path = None
        self._conversation = [{"role": "system", "content": self._build_system_prompt()}]
        self._current_response = ""
        self._error_context = ""
        self._editor_ref = None          # will be set by MainWindow
        self._pending_edits = []         # list of parsed edit operations
        self._working_set = WorkingSet()          # shadow context tracker (Step 2)
        self._ai_edited_files = set()             # rel_paths of files the AI has edited
        self._use_working_set_context = True      # WorkingSet is default; /debug-use-ws off for old path
        self._last_prompt_stats = None            # dict: stats from the last actual prompt sent
        self._last_work_result = None             # AIWorkResult from most recent AI turn
        self._gen_start_time = None               # time.time() when generation started
        self._gen_token_count = 0                  # token count during streaming
        self._stats_widget = None                  # stats row widget during streaming
        self._stats_label = None                   # QLabel showing token/time stats
        self._stats_spinner = None                 # SpinnerWidget in stats row

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Context header — standardized panel header with project info
        ctx_panel, self._chat_title, ctx_hdr = _make_panel_header("AI Chat")
        self._ctx_info = QLabel("")
        self._ctx_info.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        ctx_hdr.insertWidget(1, self._ctx_info)  # After title, before stretch
        self.toggle_files_btn = QPushButton("Show Files")
        self.toggle_files_btn.setStyleSheet(BTN_GHOST)
        self.toggle_files_btn.clicked.connect(self._toggle_file_list)
        self.toggle_files_btn.hide()
        ctx_hdr.addWidget(self.toggle_files_btn)
        layout.addWidget(ctx_panel)

        # Expandable context (below the fixed header)
        self._ctx_detail = QWidget()
        self._ctx_detail.setStyleSheet(
            f"background: {C['bg_dark']}; border-bottom: 1px solid {C['border']};")
        ctx_layout = QVBoxLayout(self._ctx_detail)
        ctx_layout.setContentsMargins(10, 4, 10, 4)
        ctx_layout.setSpacing(2)

        self.path_label = QLabel("")
        self.path_label.setStyleSheet(f"color: {C['fg_dim']}; {FONT_SMALL}")
        ctx_layout.addWidget(self.path_label)

        self.file_list_widget = QLabel("")
        self.file_list_widget.setWordWrap(True)
        self.file_list_widget.setStyleSheet(
            f"color: {C['teal']}; {FONT_SMALL} padding: 4px 0px;")
        self.file_list_widget.hide()
        ctx_layout.addWidget(self.file_list_widget)

        self._ctx_detail.hide()
        layout.addWidget(self._ctx_detail)

        # Chat display — widget-based bubbles (Claude desktop style)
        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setStyleSheet(f"""
            QScrollArea {{ background-color: {C['bg_dark']}; border: none; }}
            QScrollBar:vertical {{ background: {C['bg_dark']}; width: 8px; }}
            QScrollBar::handle:vertical {{ background: {C['border_light']}; border-radius: 4px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)
        self._chat_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Outer container fills scroll area; inner column is centered & max-width
        outer_container = QWidget()
        outer_container.setStyleSheet(f"background:{C['bg_dark']};")
        outer_layout = QHBoxLayout(outer_container)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addStretch()
        chat_container = QWidget()
        chat_container.setStyleSheet(f"background:{C['bg_dark']};")
        chat_container.setMaximumWidth(800)
        chat_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._chat_layout = QVBoxLayout(chat_container)
        self._chat_layout.setContentsMargins(8, 16, 8, 16)
        self._chat_layout.setSpacing(20)
        self._chat_layout.addStretch()
        outer_layout.addWidget(chat_container)
        outer_layout.addStretch()
        self._chat_scroll.setWidget(outer_container)
        self._current_ai_widget = None
        layout.addWidget(self._chat_scroll)

        # Apply bar — shows after AI suggests edits
        self.apply_bar = QWidget()
        self.apply_bar.setStyleSheet(f"background:{C['bg']};border-top:1px solid {C['border']};")
        ab_layout = QHBoxLayout(self.apply_bar)
        ab_layout.setContentsMargins(16, 8, 16, 8)
        self.apply_label = QLabel("")
        self.apply_label.setStyleSheet(f"color:{C['fg']};{FONT_BODY}")
        ab_layout.addWidget(self.apply_label)
        ab_layout.addStretch()
        self.apply_all_btn = QPushButton("Apply All Changes")
        self.apply_all_btn.setStyleSheet(BTN_PRIMARY)
        self.apply_all_btn.clicked.connect(self._apply_all_edits)
        ab_layout.addWidget(self.apply_all_btn)
        self.dismiss_btn = QPushButton("Dismiss")
        self.dismiss_btn.setStyleSheet(BTN_SECONDARY)
        self.dismiss_btn.clicked.connect(self._dismiss_edits)
        ab_layout.addWidget(self.dismiss_btn)
        self.apply_bar.hide()
        layout.addWidget(self.apply_bar)

        # Input area
        inp = QWidget()
        inp.setStyleSheet(f"background:{C['bg']};border-top:1px solid {C['border']};")
        il = QHBoxLayout(inp); il.setContentsMargins(16, 10, 16, 10); il.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask about your code...")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {C['bg_input']}; color: {C['fg']};
                border: 1px solid {C['border_light']}; border-radius: 10px;
                padding: 8px 14px; {FONT_CHAT}
            }}
            QLineEdit:focus {{ border-color: {C['teal']}; }}
        """)
        self.input_field.returnPressed.connect(self.send_message)
        self.input_field.textChanged.connect(self._on_input_text_changed)
        self.input_field.installEventFilter(self)
        il.addWidget(self.input_field)

        # Slash command autocomplete popup
        self._slash_popup = QListWidget()
        self._slash_popup.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._slash_popup.setStyleSheet(f"""
            QListWidget {{
                background: {C['bg_input']};
                border: 1px solid {C['border_light']};
                border-radius: 6px;
                color: {C['fg']};
                {FONT_CHAT}
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 6px 10px;
                border-radius: 4px;
            }}
            QListWidget::item:selected {{
                background: {C['bg_hover']};
            }}
        """)
        self._slash_popup.setMaximumHeight(240)
        self._slash_popup.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._slash_popup.hide()
        self._slash_popup.itemClicked.connect(self._on_slash_selected)

        self.send_btn = QPushButton("Send")
        self.send_btn.setMinimumWidth(72)
        self.send_btn.setStyleSheet(BTN_CHAT_SEND)
        self.send_btn.clicked.connect(self.send_message)
        il.addWidget(self.send_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setMinimumWidth(72)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(BTN_CHAT_STOP)
        self.stop_btn.clicked.connect(self.stop_generation)
        il.addWidget(self.stop_btn)

        layout.addWidget(inp)

        # Bottom buttons — ghost-style
        btns = QWidget()
        btns.setStyleSheet(f"background:{C['bg_dark']};")
        bl = QHBoxLayout(btns); bl.setContentsMargins(16, 4, 16, 4)
        bl.setSpacing(8)
        self.send_errors_btn = QPushButton("Attach Errors")
        self.send_errors_btn.setCheckable(True)
        self.send_errors_btn.setStyleSheet(BTN_GHOST)
        bl.addWidget(self.send_errors_btn)
        clr = QPushButton("Clear Chat")
        clr.setStyleSheet(BTN_GHOST)
        clr.clicked.connect(self.clear_chat)
        bl.addWidget(clr)
        bl.addStretch()
        layout.addWidget(btns)

        # Worker thread
        self._setup_worker_thread()

    def set_editor(self, editor):
        """Link to the TabbedEditor so we can read/write project files."""
        self._editor_ref = editor

    def set_project_path(self, path):
        """Set the project directory path for context."""
        self._project_path = path
        # Reset working set and edit tracking for new project
        self._working_set.clear()
        self._ai_edited_files.clear()
        # Update system prompt (picks up .aide_prompt if present)
        if self._conversation and self._conversation[0]["role"] == "system":
            self._conversation[0]["content"] = self._build_system_prompt()

    def set_error_context(self, e):
        self._error_context = e

    def _build_system_prompt(self):
        """Build system prompt, prepending project-level .aide_prompt if found."""
        base = SYSTEM_PROMPT
        proj = getattr(self, '_project_path', None) or ""
        if proj:
            custom_file = os.path.join(proj, ".aide_prompt")
            if os.path.isfile(custom_file):
                try:
                    with open(custom_file, 'r', encoding='utf-8') as f:
                        custom = f.read().strip()
                    if custom:
                        return custom + "\n\n" + base
                except OSError:
                    pass
        return base

    def _scan_project_files(self, project_path):
        """Recursively scan project directory and return dict of {relative_path: content}.
        Skips hidden dirs, build artifacts, and binary files."""
        if not project_path or not os.path.isdir(project_path):
            return {}
        result = {}
        max_file_size = 256_000  # Skip files > 256KB
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in PROJECT_SKIP_DIRS]
            for fname in sorted(files):
                if fname.startswith('.'):
                    continue
                ext = os.path.splitext(fname)[1].lower()
                if ext not in PROJECT_EXTENSIONS:
                    continue
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, project_path)
                try:
                    size = os.path.getsize(full_path)
                    if size > max_file_size:
                        continue
                    with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                        result[rel_path] = f.read()
                except (OSError, UnicodeDecodeError):
                    continue
        return result

    @staticmethod
    def _fmt_size(size_bytes):
        """Format file size as human-readable string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _build_directory_tree(self, project_path):
        """Build a text directory tree listing with file sizes for AI context."""
        if not project_path or not os.path.isdir(project_path):
            return ""
        lines = [os.path.basename(project_path) + "/"]

        def _walk(dir_path, prefix=""):
            try:
                entries = sorted(os.listdir(dir_path))
            except PermissionError:
                return
            dirs = [e for e in entries if os.path.isdir(os.path.join(dir_path, e))
                    and not e.startswith('.') and e not in PROJECT_SKIP_DIRS]
            files = [e for e in entries if os.path.isfile(os.path.join(dir_path, e))
                     and not e.startswith('.')]
            items = [(d, True) for d in dirs] + [(f, False) for f in files]
            for i, (name, is_dir) in enumerate(items):
                connector = "\u2514\u2500\u2500 " if i == len(items) - 1 else "\u251c\u2500\u2500 "
                if is_dir:
                    lines.append(f"{prefix}{connector}{name}/")
                    extension = "    " if i == len(items) - 1 else "\u2502   "
                    _walk(os.path.join(dir_path, name), prefix + extension)
                else:
                    try:
                        sz = os.path.getsize(os.path.join(dir_path, name))
                        size_str = f"  ({self._fmt_size(sz)})"
                    except OSError:
                        size_str = ""
                    lines.append(f"{prefix}{connector}{name}{size_str}")

        _walk(project_path)
        return "\n".join(lines)

    def _resolve_file_path(self, filename):
        """Resolve a filename from AI output to an absolute path."""
        if os.path.isabs(filename):
            return filename
        proj = getattr(self, '_project_path', None) or ""
        if proj:
            return os.path.join(proj, filename)
        return os.path.abspath(filename)

    def _build_file_context(self):
        """Build file context string for AI prompts. Uses WorkingSet with token budget
        by default. Hidden fallback to full-context via /debug-use-ws off."""
        proj = getattr(self, '_project_path', None) or ""

        if not proj:
            # No project path: include all open editor files directly
            self._working_set.clear()
            if not self._editor_ref:
                return ""
            files = self._editor_ref.get_all_files()
            if not files:
                return ""
            names = []
            for fp, content in files.items():
                basename = os.path.basename(fp)
                names.append(basename)
                self._working_set.add(fp, basename, 2, content)
            self._update_context_display("unknown", "", names)
            context = self._working_set.build_context("unknown", "", "")
            self._last_prompt_stats = {
                "mode": "WorkingSet",
                "file_count": len(names),
                "excluded_count": 0,
                "tokens": len(context) // 4,
                "active_included": True,
                "ai_edited_included": True,
                "warnings": [],
            }
            return context

        proj_name = os.path.basename(proj)
        tree = self._build_directory_tree(proj)
        all_files = self._scan_project_files(proj)

        # Populate working set with priorities
        # 0=active tab, 1=AI-edited, 2=open-but-not-active, 3=other project file
        self._working_set.clear()
        active_file = self._editor_ref.current_file() if self._editor_ref else None
        open_files = self._editor_ref.get_all_files() if self._editor_ref else {}
        open_paths = {os.path.normpath(fp) for fp in open_files}
        for rel_path, content in all_files.items():
            abs_path = os.path.join(proj, rel_path)
            norm_path = os.path.normpath(abs_path)
            if active_file and norm_path == os.path.normpath(active_file):
                priority = 0
            elif rel_path in self._ai_edited_files:
                priority = 1
            elif norm_path in open_paths:
                priority = 2
            else:
                priority = 3
            self._working_set.add(abs_path, rel_path, priority, content)

        # Safety net: if active file wasn't found by scanner (wrong extension,
        # too large, etc.), inject it directly from the editor content
        if active_file:
            active_norm = os.path.normpath(active_file)
            found_active = False
            for rel_path in all_files:
                if os.path.normpath(os.path.join(proj, rel_path)) == active_norm:
                    found_active = True
                    break
            if not found_active:
                # Read directly from editor
                content = self._editor_ref.current_text() if self._editor_ref else ""
                if content:
                    rel = os.path.relpath(active_file, proj)
                    all_files[rel] = content
                    self._working_set.add(active_file, rel, 0, content)

        self._update_context_display(proj_name, proj, sorted(all_files.keys()))

        # Debug fallback: old full-context (all files, no budget)
        if not self._use_working_set_context:
            parts = [
                f"[PROJECT: {proj_name}]", f"[DIRECTORY: {proj}]", "",
                "[PROJECT STRUCTURE]", tree, "",
                f"[The following {len(all_files)} files are in the project. "
                f"This is the COMPLETE content of each file.]", "",
            ]
            for rel_path, content in sorted(all_files.items()):
                parts.append(f"========== FILE: {rel_path} ==========\n{content}\n========== END: {rel_path} ==========\n")
            old_context = "\n".join(parts)
            self._last_prompt_stats = {
                "mode": "old full-context",
                "file_count": len(all_files),
                "excluded_count": 0,
                "tokens": len(old_context) // 4,
                "active_included": True,
                "ai_edited_included": True,
                "warnings": [],
            }
            return old_context

        # Primary path: WorkingSet with token budget
        context = self._working_set.build_context(proj_name, proj, tree)
        included = set()
        excluded = set()
        sorted_entries = sorted(self._working_set.entries.values(), key=lambda e: e.priority)
        used = 0
        for e in sorted_entries:
            if used + e.token_estimate <= self._working_set.budget or e.priority == 0:
                included.add(e.rel_path)
                used += e.token_estimate
            else:
                excluded.add(e.rel_path)

        active_ok = any(e.priority == 0 and e.rel_path in included
                        for e in self._working_set.entries.values())
        edited_ok = all(f in included for f in self._ai_edited_files) if self._ai_edited_files else True
        warnings = self._check_working_set_safety(included)

        self._last_prompt_stats = {
            "mode": "WorkingSet",
            "file_count": len(included),
            "excluded_count": len(excluded),
            "tokens": len(context) // 4,
            "active_included": active_ok,
            "ai_edited_included": edited_ok,
            "warnings": warnings,
        }
        return context

    def _check_working_set_safety(self, included_files):
        """Check that WorkingSet includes critical files. Returns list of warning strings.
        Also emits debug warnings to chat if problems are found."""
        warnings = []
        # Check active file
        active_entry = None
        for e in self._working_set.entries.values():
            if e.priority == 0:
                active_entry = e
                break
        if active_entry and active_entry.rel_path not in included_files:
            msg = f"[debug] WARNING: active file '{active_entry.rel_path}' excluded by budget!"
            warnings.append(msg)
            self._add_info_msg(msg, C['fg_err'])
        # Check AI-edited files
        for rel_path in self._ai_edited_files:
            if rel_path not in included_files:
                msg = f"[debug] WARNING: AI-edited file '{rel_path}' excluded by budget!"
                warnings.append(msg)
                self._add_info_msg(msg, C['fg_err'])
        return warnings

    def _build_git_context(self):
        """Build git status context for the AI (branch, recent commits, diff stat)."""
        proj = getattr(self, '_project_path', None) or ""
        if not proj or not os.path.isdir(os.path.join(proj, ".git")):
            return ""

        def _git(args):
            try:
                r = subprocess.run(
                    ["git"] + args, cwd=proj,
                    capture_output=True, text=True, timeout=5)
                return r.stdout.strip() if r.returncode == 0 else ""
            except Exception:
                return ""

        branch = _git(["branch", "--show-current"])
        if not branch:
            return ""

        parts = ["[GIT STATUS]", f"Branch: {branch}"]

        log = _git(["log", "--oneline", "-5"])
        if log:
            parts.append("Last commits:")
            for line in log.split("\n"):
                parts.append(f"  {line}")

        diff_stat = _git(["diff", "--stat"])
        if diff_stat:
            parts.append(f"Uncommitted changes:\n{diff_stat}")

        untracked = _git(["ls-files", "--others", "--exclude-standard"])
        if untracked:
            files = [f.strip() for f in untracked.split("\n") if f.strip()]
            if files:
                parts.append("Untracked: " + ", ".join(files[:10]))

        return "\n".join(parts)

    # ---- Slash Commands ----

    SLASH_COMMANDS = {
        "clear":   "Clear conversation history",
        "model":   "Switch AI model — /model <name>",
        "compact": "Summarize and compress conversation history",
        "help":    "Show available slash commands",
        "context": "Show what the AI sees (file list, git status, context size)",
    }

    def _on_input_text_changed(self, text):
        """Show/hide/filter slash command autocomplete popup."""
        if not text.startswith("/"):
            self._slash_popup.hide()
            return
        query = text[1:].lower()
        self._slash_popup.clear()
        for cmd, desc in self.SLASH_COMMANDS.items():
            if not query or cmd.startswith(query):
                item = QListWidgetItem(f"/{cmd}  \u2014  {desc}")
                item.setData(Qt.ItemDataRole.UserRole, cmd)
                self._slash_popup.addItem(item)
        if self._slash_popup.count() == 0:
            self._slash_popup.hide()
            return
        # Position popup above the input field
        global_pos = self.input_field.mapToGlobal(
            self.input_field.rect().topLeft())
        row_h = self._slash_popup.sizeHintForRow(0) if self._slash_popup.count() else 28
        popup_h = min(row_h * self._slash_popup.count() + 10, 240)
        self._slash_popup.setFixedWidth(min(self.input_field.width(), 400))
        self._slash_popup.setFixedHeight(popup_h)
        self._slash_popup.move(global_pos.x(), global_pos.y() - popup_h - 4)
        self._slash_popup.show()
        if self._slash_popup.count() > 0:
            self._slash_popup.setCurrentRow(0)

    def _on_slash_selected(self, item):
        """User clicked a slash command in the popup."""
        cmd = item.data(Qt.ItemDataRole.UserRole)
        self.input_field.setText(f"/{cmd} ")
        self.input_field.setFocus()
        self._slash_popup.hide()

    def eventFilter(self, obj, event):
        """Handle keyboard navigation for slash command popup."""
        if obj == self.input_field and hasattr(self, '_slash_popup') and self._slash_popup.isVisible():
            from PyQt6.QtCore import QEvent
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                if key == Qt.Key.Key_Up:
                    row = self._slash_popup.currentRow()
                    if row > 0:
                        self._slash_popup.setCurrentRow(row - 1)
                    return True
                elif key == Qt.Key.Key_Down:
                    row = self._slash_popup.currentRow()
                    if row < self._slash_popup.count() - 1:
                        self._slash_popup.setCurrentRow(row + 1)
                    return True
                elif key == Qt.Key.Key_Tab:
                    item = self._slash_popup.currentItem()
                    if item:
                        self._on_slash_selected(item)
                    return True
                elif key == Qt.Key.Key_Escape:
                    self._slash_popup.hide()
                    return True
                elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    # If popup is showing and text is just a partial command,
                    # select the item; otherwise let send_message handle it
                    text = self.input_field.text().strip()
                    matched_cmd = None
                    for cmd in self.SLASH_COMMANDS:
                        if text == f"/{cmd}" or text.startswith(f"/{cmd} "):
                            matched_cmd = cmd
                            break
                    if not matched_cmd:
                        item = self._slash_popup.currentItem()
                        if item:
                            self._on_slash_selected(item)
                            return True
                    # Full command typed — let send_message handle it
                    self._slash_popup.hide()
        return super().eventFilter(obj, event)

    def send_message(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self._slash_popup.hide()
        if text.startswith("/"):
            self._handle_slash_command(text)
            return
        self._send_prompt(text, display_text=text)

    def _handle_slash_command(self, text):
        """Parse and dispatch a /command."""
        self._add_user_msg(text)
        self.input_field.clear()
        parts = text.split(None, 1)
        cmd = parts[0][1:].lower()  # strip leading /
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "clear":
            self.clear_chat()
            self._add_info_msg("Conversation cleared.", C['fg_ok'])
        elif cmd == "model":
            self._cmd_model(args)
        elif cmd == "compact":
            self._cmd_compact()
        elif cmd == "help":
            self._cmd_help()
        elif cmd == "context":
            self._cmd_context()
        elif cmd == "debug-ws":
            self._cmd_debug_working_set()
        elif cmd == "debug-use-ws":
            self._cmd_debug_use_ws(args)
        else:
            self._add_info_msg(
                f"Unknown command: /{cmd} — type /help for available commands.",
                C['fg_warn'])

    def _cmd_model(self, args):
        """Switch the active Ollama model."""
        global OLLAMA_MODEL
        name = args.strip()
        if not name:
            self._add_info_msg(
                f"Current model: {OLLAMA_MODEL}\nUsage: /model <name>", C['fg'])
            return
        OLLAMA_MODEL = name
        self.model_switch_requested.emit(name)
        self._add_info_msg(f"Switched to model: {name}", C['fg_ok'])

    def _cmd_compact(self):
        """Summarize conversation to free context window space."""
        if len(self._conversation) < 4:
            self._add_info_msg(
                "Conversation too short to compact.", C['fg_warn'])
            return
        old_len = len(self._conversation)
        self._add_info_msg("Compacting conversation...", C['fg_dim'])
        self.input_field.setEnabled(False)

        # Build summary request from conversation history
        history_text = ""
        for msg in self._conversation[1:]:  # skip system prompt
            role = msg["role"]
            content = msg["content"]
            # Truncate very long messages for the summary request
            if len(content) > 500:
                content = content[:500] + "..."
            history_text += f"{role}: {content}\n\n"

        summary_prompt = (
            "Summarize the key points of this conversation in a concise paragraph. "
            "Include: what files were discussed, what changes were made, what issues remain. "
            "Return ONLY the summary, nothing else.\n\n" + history_text
        )

        # One-shot Ollama request in a background thread
        class CompactWorker(QThread):
            finished = pyqtSignal(str)
            error = pyqtSignal(str)

            def run(self_w):
                try:
                    resp = requests.post(
                        OLLAMA_URL.replace("/api/chat", "/api/generate"),
                        json={"model": OLLAMA_MODEL, "prompt": summary_prompt,
                              "stream": False},
                        timeout=(5, 60))
                    resp.raise_for_status()
                    data = resp.json()
                    self_w.finished.emit(data.get("response", "").strip())
                except Exception as e:
                    self_w.error.emit(str(e))

        self._compact_worker = CompactWorker()

        def _on_summary(summary):
            sys_prompt = self._build_system_prompt()
            last_msgs = self._conversation[-2:] if len(self._conversation) >= 2 else []
            self._conversation = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"[CONVERSATION SUMMARY]\n{summary}"},
                {"role": "assistant", "content":
                    "Understood. I have the context from our previous discussion."},
            ] + last_msgs
            self._add_info_msg(
                f"Compacted: {old_len} messages \u2192 {len(self._conversation)} messages",
                C['fg_ok'])
            self.input_field.setEnabled(True)
            self.input_field.setFocus()

        def _on_error(err):
            self._add_info_msg(f"Compact failed: {err}", C['fg_err'])
            self.input_field.setEnabled(True)

        self._compact_worker.finished.connect(_on_summary)
        self._compact_worker.error.connect(_on_error)
        self._compact_worker.start()

    def _cmd_help(self):
        """Show available slash commands."""
        lines = ["Available commands:"]
        for cmd, desc in self.SLASH_COMMANDS.items():
            lines.append(f"  /{cmd}  —  {desc}")
        self._add_info_msg("\n".join(lines), C['fg'])

    def _cmd_context(self):
        """Show the full AI context preview."""
        file_ctx = self._build_file_context()
        git_ctx = self._build_git_context()
        total = file_ctx + ("\n" + git_ctx if git_ctx else "")
        # Count files
        file_count = total.count("========== FILE:")
        size_chars = len(total)
        summary = f"Context: {file_count} files, {size_chars:,} chars"
        if git_ctx:
            # Extract branch from git context
            for line in git_ctx.split("\n"):
                if line.startswith("Branch:"):
                    summary += f", git: {line.split(':', 1)[1].strip()}"
                    break
        # Show truncated preview
        preview = total[:2000]
        if len(total) > 2000:
            preview += f"\n... ({len(total) - 2000:,} more chars)"
        self._add_info_msg(f"{summary}\n\n{preview}", C['fg_dim'])

    def _cmd_debug_working_set(self):
        """Debug command: dump WorkingSet contents and last prompt stats."""
        PRIORITY_LABELS = {0: "active-tab", 1: "ai-edited", 2: "open-tab", 3: "project"}
        ws = self._working_set
        if not ws.entries:
            self._add_info_msg(
                "[debug] WorkingSet is empty.\n"
                "Send a message first to populate it.",
                C['fg_dim'])
            return

        # Summary counts by priority
        counts = {}
        for e in ws.entries.values():
            label = PRIORITY_LABELS.get(e.priority, f"p{e.priority}")
            counts[label] = counts.get(label, 0) + 1

        live_mode = "WorkingSet (default)" if self._use_working_set_context else "old full-context (debug fallback)"
        lines = [
            f"[debug] WorkingSet — {len(ws.entries)} entries, "
            f"~{ws.total_tokens:,} tokens total, budget={ws.budget:,}",
            f"  LIVE MODE: {live_mode}",
            f"  would include: {ws.included_count} files",
            f"  breakdown: {', '.join(f'{v} {k}' for k, v in sorted(counts.items()))}",
            f"  ai_edited_files: {sorted(self._ai_edited_files) if self._ai_edited_files else '(none)'}",
            "",
        ]
        # Per-file listing sorted by priority then path
        sorted_entries = sorted(ws.entries.values(), key=lambda e: (e.priority, e.rel_path))
        for e in sorted_entries:
            label = PRIORITY_LABELS.get(e.priority, f"p{e.priority}")
            in_budget = "✓" if self._entry_in_budget(e) else "✗"
            lines.append(f"  {in_budget} [{label}] {e.rel_path}  (~{e.token_estimate:,} tok)")

        # Last actual prompt stats
        lps = self._last_prompt_stats
        if lps:
            lines.append("")
            lines.append("--- last prompt ---")
            lines.append(f"  mode: {lps['mode']}")
            lines.append(f"  files: {lps['file_count']} included" +
                         (f", {lps['excluded_count']} excluded" if lps['excluded_count'] else ""))
            lines.append(f"  tokens: ~{lps['tokens']:,}")
            lines.append(f"  active file included: {'yes' if lps['active_included'] else 'NO'}")
            lines.append(f"  all AI-edited included: {'yes' if lps['ai_edited_included'] else 'NO'}")
            if lps['warnings']:
                lines.append(f"  warnings ({len(lps['warnings'])}):")
                for w in lps['warnings']:
                    lines.append(f"    {w}")
        else:
            lines.append("")
            lines.append("--- last prompt: (none sent yet) ---")

        self._add_info_msg("\n".join(lines), C['fg_dim'])

    def _entry_in_budget(self, target_entry):
        """Check if a specific entry would be included within the token budget."""
        sorted_entries = sorted(self._working_set.entries.values(), key=lambda e: e.priority)
        used = 0
        for e in sorted_entries:
            if used + e.token_estimate <= self._working_set.budget or e.priority == 0:
                used += e.token_estimate
                if e.rel_path == target_entry.rel_path:
                    return True
            else:
                if e.rel_path == target_entry.rel_path:
                    return False
        return False

    def _cmd_debug_use_ws(self, args):
        """Debug toggle: switch between WorkingSet (default) and old full-context (fallback)."""
        arg = args.strip().lower()
        if arg == "on":
            self._use_working_set_context = True
            self._add_info_msg(
                "[debug] Live context: WorkingSet (default, budget-constrained)\n"
                "This is the normal default mode.",
                C['fg_ok'])
        elif arg == "off":
            self._use_working_set_context = False
            self._add_info_msg(
                "[debug] Live context: old full-context (debug fallback)\n"
                "All project files will be included. Use /debug-use-ws on to restore default.",
                C['fg_warn'])
        else:
            mode = "WorkingSet (default)" if self._use_working_set_context else "old full-context (debug fallback)"
            self._add_info_msg(
                f"[debug] Current live context mode: {mode}\n"
                f"Usage: /debug-use-ws on | off",
                C['fg_dim'])

    def send_ai_action(self, prompt):
        """Called from the right-click AI context menu in the code editor."""
        # Parse tool name and code block from the formatted prompt
        lines = prompt.split("\n")
        tool_name = lines[0].rstrip(":").strip()
        code_lines, in_code = [], False
        for line in lines[1:]:
            if line.startswith("```") and not in_code:
                in_code = True; continue
            if line.startswith("```") and in_code:
                break
            if in_code:
                code_lines.append(line)
        code = "\n".join(code_lines).rstrip()
        self._send_prompt(prompt, display_text=tool_name, display_code=code)

    def _send_prompt(self, text, display_text=None, display_code=None):
        """Core send method used by both manual chat and AI actions."""
        # Build the full message with automatic file + git context
        msg = self._build_file_context()
        git_ctx = self._build_git_context()
        if git_ctx:
            msg += f"\n{git_ctx}\n"
        if self.send_errors_btn.isChecked() and self._error_context:
            msg += f"\n[COMPILER ERRORS:]\n```\n{self._error_context}\n```\n\n"
            self.send_errors_btn.setChecked(False)
        msg += (
            "\n[REMINDER: You are inside an IDE. You CAN and MUST edit files directly. "
            "Use <<<EDIT path\\n<<<OLD\\n...\\n>>>NEW\\n...\\n>>>END to modify files. "
            "NEVER say you cannot edit files. ALWAYS output code edits when asked. "
            "Edit the file the USER mentions, NOT the active file unless they ask for it.]\n"
            f"\n[USER REQUEST:]\n{text}"
        )

        # Show user message bubble (right-aligned)
        show = display_text or text
        self._add_user_msg(show, code=display_code)

        self._conversation.append({"role": "user", "content": msg})
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._current_response = ""
        self.apply_bar.hide()
        self._pending_edits = []

        # Create AI response widget (left-aligned, no bubble)
        self._add_ai_msg()

        # Create stats row with spinner + live token counter
        self._gen_start_time = time.time()
        self._gen_token_count = 0
        stats_wrapper = QWidget()
        stats_wrapper.setStyleSheet("background: transparent;")
        stats_hl = QHBoxLayout(stats_wrapper)
        stats_hl.setContentsMargins(2, 4, 0, 4)
        stats_hl.setSpacing(6)
        spinner = SpinnerWidget()
        spinner.start()
        stats_hl.addWidget(spinner)
        stats_lbl = QLabel("0 tokens")
        stats_lbl.setStyleSheet(
            f"color:{C['fg_dim']};{FONT_SMALL}background:transparent;border:none;")
        stats_hl.addWidget(stats_lbl)
        stats_hl.addStretch()
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, stats_wrapper)
        self._stats_widget = stats_wrapper
        self._stats_label = stats_lbl
        self._stats_spinner = spinner

        self.worker.messages = list(self._conversation)
        if self.thread.isRunning():
            self.worker.stop()
            self.thread.quit()
            if not self.thread.wait(2000):
                self.thread.terminate()
                self.thread.wait(1000)
                self._setup_worker_thread()
        self.generation_started.emit()
        self.thread.start()

    def stop_generation(self):
        self.worker.stop()
        if self.thread.isRunning():
            self.thread.quit()
            if not self.thread.wait(2000):
                self.thread.terminate()
                self.thread.wait(1000)
                self._setup_worker_thread()
        self._finalize_stats(suffix=" (stopped)")
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.input_field.setFocus()
        self.generation_finished.emit()

    def _on_token(self, t):
        self._current_response += t
        if self._current_ai_widget:
            cur = self._current_ai_widget.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.End)
            cur.insertText(t)
            self._current_ai_widget.setTextCursor(cur)
        # Update live stats
        self._gen_token_count += 1
        if self._stats_label and self._gen_start_time:
            elapsed = time.time() - self._gen_start_time
            self._stats_label.setText(
                f"{self._gen_token_count} tokens \u00b7 {elapsed:.1f}s")
        self._scroll_to_bottom()

    # Styles for code blocks and edit blocks in AI responses (QTextEdit HTML)
    _CODE_BLOCK_STYLE = (
        f'background:{C["bg_input"]};'
        f'border:1px solid {C["border_light"]};'
        f'padding:10px;margin:6px 0;'
        f'font-family:Menlo,Monaco,Courier New,monospace;font-size:13px;')
    _EDIT_BLOCK_STYLE = (
        f'background:{C["bg_input"]};'
        f'border:1px solid {C["border_light"]};'
        f'border-left:3px solid {C["teal"]};'
        f'padding:10px;margin:6px 0;'
        f'font-family:Menlo,Monaco,Courier New,monospace;font-size:13px;')
    _EDIT_HEADER_STYLE = (
        f'color:{C["teal"]};font-size:12px;font-weight:bold;margin-bottom:4px;')

    def _render_formatted_response(self):
        """Re-render the completed AI response with styled code blocks and edit blocks."""
        if not self._current_ai_widget or not self._current_response:
            return
        text = self._current_response
        # Only render if there are code fences or edit blocks
        if "```" not in text and "<<<" not in text:
            return
        html_parts = []
        in_code = False
        in_edit = False
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            # <<<EDIT or <<<FILE block start
            if not in_code and not in_edit and (
                    line.startswith("<<<EDIT ") or line.startswith("<<<FILE ")):
                kind = "EDIT" if line.startswith("<<<EDIT") else "FILE"
                filename = line.split(None, 1)[1].strip() if " " in line else ""
                html_parts.append(f'<div style="{self._EDIT_BLOCK_STYLE}">')
                label = f"{kind}: {html.escape(filename)}" if filename else kind
                html_parts.append(
                    f'<div style="{self._EDIT_HEADER_STYLE}">{label}</div>')
                html_parts.append('<pre style="margin:0;white-space:pre-wrap;">')
                in_edit = True
                i += 1
                continue
            # <<<OLD / >>>NEW / >>>END / >>>FILE markers inside edit blocks
            if in_edit:
                if line.startswith(">>>END") or line.startswith(">>>FILE"):
                    html_parts.append("</pre></div>")
                    in_edit = False
                    i += 1
                    continue
                elif line.startswith("<<<OLD"):
                    html_parts.append(
                        f'<div style="color:{C["fg_dim"]};font-size:11px;'
                        f'margin:4px 0 2px 0;">\u2500 OLD \u2500</div>')
                    i += 1
                    continue
                elif line.startswith(">>>NEW"):
                    html_parts.append(
                        f'<div style="color:{C["teal"]};font-size:11px;'
                        f'margin:4px 0 2px 0;">\u2500 NEW \u2500</div>')
                    i += 1
                    continue
                else:
                    html_parts.append(html.escape(line) + "\n")
                    i += 1
                    continue
            # Fenced code block start
            if line.startswith("```") and not in_code:
                lang = line[3:].strip()
                html_parts.append(f'<div style="{self._CODE_BLOCK_STYLE}">')
                if lang:
                    html_parts.append(
                        f'<div style="color:{C["fg_dim"]};font-size:11px;'
                        f'margin-bottom:4px;">{html.escape(lang)}</div>')
                html_parts.append('<pre style="margin:0;white-space:pre-wrap;">')
                in_code = True
                i += 1
                continue
            # Fenced code block end
            if line.startswith("```") and in_code:
                html_parts.append("</pre></div>")
                in_code = False
                i += 1
                continue
            # Inside code block
            if in_code:
                html_parts.append(html.escape(line) + "\n")
                i += 1
                continue
            # Regular text
            html_parts.append(html.escape(line) + "<br>")
            i += 1
        # Close any unclosed blocks
        if in_code or in_edit:
            html_parts.append("</pre></div>")
        self._current_ai_widget.setHtml("".join(html_parts))

    def _on_complete(self):
        if self.thread.isRunning():
            self.thread.quit()
        if self._current_response:
            self._conversation.append({"role": "assistant", "content": self._current_response})
            self._render_formatted_response()
            result = AIWorkResult(assistant_text=self._current_response)
            self._parse_edits(self._current_response, result)
            self._last_work_result = result
        # Finalize stats — stop spinner, show final stats
        self._finalize_stats()
        self._current_ai_widget = None
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.input_field.setFocus()
        self.generation_finished.emit()

    def _finalize_stats(self, suffix=""):
        """Stop spinner and show final token/time stats."""
        if self._stats_spinner:
            self._stats_spinner.stop()
            self._stats_spinner.hide()
        if self._stats_label and self._gen_start_time:
            elapsed = time.time() - self._gen_start_time
            tok_s = self._gen_token_count / elapsed if elapsed > 0 else 0
            self._stats_label.setText(
                f"{self._gen_token_count} tokens \u00b7 {elapsed:.1f}s"
                f" \u00b7 {tok_s:.1f} tok/s{suffix}")
            self._stats_label.setStyleSheet(
                f"color:{C['fg_muted']};{FONT_SMALL}background:transparent;border:none;")
        self._stats_widget = None
        self._stats_label = None
        self._stats_spinner = None
        self._gen_start_time = None

    def _on_error(self, m):
        self._finalize_stats(suffix=" (error)")
        # Show error with "Error" speaker label
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(wrapper)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)
        speaker = QLabel("Error")
        speaker.setStyleSheet(
            f"color:{C['fg_err']};{FONT_CHAT_BOLD}"
            f"padding-left:2px;background:transparent;border:none;")
        vl.addWidget(speaker)
        err_label = QLabel(m)
        err_label.setWordWrap(True)
        err_label.setTextFormat(Qt.TextFormat.PlainText)
        err_label.setStyleSheet(
            f"color:{C['fg_err_text']};{FONT_CHAT}"
            f"background:transparent;border:none;padding-left:2px;")
        err_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        vl.addWidget(err_label)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, wrapper)
        self._scroll_to_bottom()
        self._current_ai_widget = None
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.generation_finished.emit()

    def _setup_worker_thread(self):
        """Create a fresh worker/thread pair (used after forced termination)."""
        self.worker = OllamaWorker()
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.worker.token_received.connect(self._on_token)
        self.worker.response_complete.connect(self._on_complete)
        self.worker.error_occurred.connect(self._on_error)
        self.thread.started.connect(self.worker.run)

    def _parse_edits(self, response, result=None):
        """Parse <<<EDIT and <<<FILE blocks from the AI response.
        Populates result.proposed_edits if an AIWorkResult is provided."""
        edits = []

        # Parse <<<EDIT filename\n<<<OLD\n...\n>>>NEW\n...\n>>>END
        edit_pat = re.compile(
            r'<<<EDIT\s+(\S+)\s*\n<<<OLD\n(.*?)\n>>>NEW\n(.*?)\n>>>END',
            re.DOTALL)
        for m in edit_pat.finditer(response):
            edits.append(("edit", m.group(1), m.group(2), m.group(3)))

        # Parse <<<FILE filename\n...\n>>>FILE
        file_pat = re.compile(
            r'<<<FILE\s+(\S+)\s*\n(.*?)\n>>>FILE',
            re.DOTALL)
        for m in file_pat.finditer(response):
            edits.append(("file", m.group(1), None, m.group(2)))

        # Populate typed result object
        if result is not None:
            for edit_type, filename, old, new in edits:
                result.proposed_edits.append(
                    ProposedEdit(edit_type, filename, old, new))

        if edits:
            self._pending_edits = edits
            n = len(edits)
            files_touched = set(e[1] for e in edits)
            self.apply_label.setText(
                f"{n} change{'s' if n > 1 else ''} in {', '.join(files_touched)}")
            self.apply_bar.show()
            self._add_info_msg(
                f'Found {n} code edit{"s" if n > 1 else ""} — '
                f'use the Apply bar below to apply.', C['fg_ok'])
        # Fallback: parse unified diff format (diff --git a/file b/file)
        # Some small models output this despite being told not to.
        if not edits:
            edits = self._parse_unified_diffs(response)
            if edits:
                if result is not None:
                    for edit_type, filename, old, new in edits:
                        result.proposed_edits.append(
                            ProposedEdit(edit_type, filename, old, new))
                self._pending_edits = edits
                n = len(edits)
                files_touched = set(e[1] for e in edits)
                self.apply_label.setText(
                    f"{n} change{'s' if n > 1 else ''} in {', '.join(files_touched)}")
                self.apply_bar.show()
                self._add_info_msg(
                    f'Found {n} code edit{"s" if n > 1 else ""} (from diff) — '
                    f'use the Apply bar below to apply.', C['fg_ok'])

    def _parse_unified_diffs(self, response):
        """Parse unified diff format as fallback when model ignores <<<EDIT instructions.
        Returns list of (edit_type, filename, old_text, new_text) tuples."""
        edits = []
        # Strip code fences so diff content is exposed
        stripped = re.sub(r'```\w*\n', '', response).replace('```', '')
        # Match diff --git blocks with hunks
        diff_pat = re.compile(
            r'diff\s+--git\s+a/(\S+)\s+b/\S+.*?\n'
            r'(?:.*?\n)*?'
            r'(@@[^\n]*\n(?:[+ \-].*\n?)*)',
            re.MULTILINE)
        for m in diff_pat.finditer(stripped):
            filename = m.group(1)
            hunk_text = m.group(2)
            old_lines = []
            new_lines = []
            for line in hunk_text.splitlines():
                if line.startswith('@@'):
                    continue
                if line.startswith('-'):
                    old_lines.append(line[1:])
                elif line.startswith('+'):
                    new_lines.append(line[1:])
                elif line.startswith(' '):
                    old_lines.append(line[1:])
                    new_lines.append(line[1:])
            if old_lines or new_lines:
                edits.append(("edit", filename,
                              "\n".join(old_lines), "\n".join(new_lines)))
        return edits

    def _track_ai_edited_file(self, filename):
        """Record that the AI edited this file (for working set priority)."""
        proj = getattr(self, '_project_path', None) or ""
        if not proj:
            return
        abs_path = self._resolve_file_path(filename)
        try:
            rel = os.path.relpath(abs_path, proj)
            self._ai_edited_files.add(rel)
        except ValueError:
            pass  # abs_path not under proj

    def _apply_all_edits(self):
        """Apply all parsed edits to the editor. Supports creating new files."""
        if not self._editor_ref or not self._pending_edits:
            return
        applied = 0
        errors = []

        for edit_type, filename, old, new in self._pending_edits:
            # Try to find file in open tabs
            fp = self._editor_ref.find_file_by_name(filename)

            if not fp and edit_type == "file":
                # NEW FILE CREATION: file not open and it's a <<<FILE block
                abs_path = self._resolve_file_path(filename)
                parent_dir = os.path.dirname(abs_path)
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                    with open(abs_path, 'w', encoding='utf-8') as f:
                        f.write(new)
                    # Open the new file in the editor
                    self._editor_ref.open_file(abs_path)
                    applied += 1
                    self._track_ai_edited_file(filename)
                    continue
                except OSError as e:
                    errors.append(f"Could not create {filename}: {e}")
                    continue

            if not fp and edit_type == "edit":
                # For EDIT blocks, try to find file on disk even if not open
                abs_path = self._resolve_file_path(filename)
                if os.path.isfile(abs_path):
                    self._editor_ref.open_file(abs_path)
                    fp = abs_path
                else:
                    errors.append(f"File not found: {filename}")
                    continue

            if not fp:
                errors.append(f"File not found: {filename}")
                continue

            if edit_type == "file":
                # Full file replacement
                if self._editor_ref.set_file_content(fp, new):
                    applied += 1
                    self._track_ai_edited_file(filename)
                else:
                    errors.append(f"Could not write: {filename}")
            elif edit_type == "edit":
                # Search & replace
                files = self._editor_ref.get_all_files()
                content = files.get(fp, "")
                if old in content:
                    new_content = content.replace(old, new, 1)
                    if self._editor_ref.set_file_content(fp, new_content):
                        applied += 1
                        self._track_ai_edited_file(filename)
                    else:
                        errors.append(f"Could not write: {filename}")
                else:
                    errors.append(f"Could not find matching code in {filename}")

        status = f"Applied {applied} change{'s' if applied != 1 else ''}."
        if errors:
            status += " Errors: " + "; ".join(errors)
        self._add_info_msg(status,
                           C['fg_ok'] if not errors else C['fg_warn'])
        self.apply_bar.hide()
        self._pending_edits = []

        # Notify MainWindow to refresh file browser after creates/edits
        if applied > 0:
            self.edits_applied.emit()

    def _dismiss_edits(self):
        self.apply_bar.hide()
        self._pending_edits = []

    def clear_chat(self):
        # Remove all message widgets from the chat layout (keep the stretch)
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._current_ai_widget = None
        self._conversation = [{"role": "system", "content": self._build_system_prompt()}]
        self.apply_bar.hide()
        self._pending_edits = []
        self._ai_edited_files.clear()
        self._working_set.clear()
        self._update_context_bar()

    def _update_context_display(self, proj_name, proj_path, names):
        """Update the context panel with project info and file list."""
        self._ctx_info.setText(f"{proj_name} \u2014 {len(names)} files")
        self.path_label.setText(proj_path)
        # Show abbreviated paths for long lists
        display_names = names[:20]
        if len(names) > 20:
            display_names.append(f"... and {len(names) - 20} more")
        self.file_list_widget.setText("  \u2022  ".join(display_names))
        self._ctx_detail.show()
        self.toggle_files_btn.show()

    def _toggle_file_list(self):
        """Toggle visibility of the file list."""
        if self.file_list_widget.isVisible():
            self.file_list_widget.hide()
            self.toggle_files_btn.setText("Show Files")
        else:
            self.file_list_widget.show()
            self.toggle_files_btn.setText("Hide Files")

    def _update_context_bar(self):
        proj = getattr(self, '_project_path', None) or ""
        if proj and os.path.isdir(proj):
            proj_name = os.path.basename(proj)
            all_files = self._scan_project_files(proj)
            names = sorted(all_files.keys())
            self._update_context_display(proj_name, proj, names)
            return
        if self._editor_ref:
            files = self._editor_ref.get_all_files()
            if files:
                proj_name = os.path.basename(proj) if proj else "unknown"
                names = [os.path.basename(fp) for fp in files]
                self._update_context_display(proj_name, proj, names)
                return
        self._ctx_info.setText("")
        self.path_label.setText("")
        self.file_list_widget.setText("")
        self._ctx_detail.hide()
        self.toggle_files_btn.hide()

    def _add_user_msg(self, text, code=None):
        """Add a right-aligned user message bubble with 'You' label."""
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(wrapper)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)
        # Speaker label "You" — right-aligned
        speaker = QLabel("You")
        speaker.setAlignment(Qt.AlignmentFlag.AlignRight)
        speaker.setStyleSheet(
            f"color:{C['fg_link']};{FONT_CHAT_BOLD}"
            f"padding-right:8px;background:transparent;border:none;")
        vl.addWidget(speaker)
        # Bubble row
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 12, 0)
        row.addStretch()
        bubble = QFrame()
        bubble.setMinimumWidth(200)
        bubble.setMaximumWidth(600)
        bubble.setStyleSheet(
            f"QFrame {{ background-color:{C['bg_input']}; border-radius:14px; }}")
        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(16, 12, 16, 12)
        bl.setSpacing(8)
        # Text label
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setTextFormat(Qt.TextFormat.PlainText)
        text_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        text_label.setStyleSheet(
            f"color:{C['fg_head']};{FONT_CHAT}background:transparent;border:none;")
        text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        bl.addWidget(text_label)
        if code:
            # Code block inside the bubble
            code_label = QLabel(code)
            code_label.setWordWrap(True)
            code_label.setStyleSheet(
                f"background-color:{C['bg']};color:{C['fg']};{FONT_CODE}"
                f"border-radius:8px;padding:8px;")
            code_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            bl.addWidget(code_label)
        row.addWidget(bubble)
        vl.addLayout(row)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, wrapper)
        self._scroll_to_bottom()

    def _add_ai_msg(self):
        """Add a left-aligned AI message area with model name label."""
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        wrapper.setMaximumWidth(700)
        vl = QVBoxLayout(wrapper)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)
        # Speaker label — model name, teal, bold
        speaker = QLabel(OLLAMA_MODEL)
        speaker.setStyleSheet(
            f"color:{C['teal']};{FONT_CHAT_BOLD}"
            f"padding-left:2px;background:transparent;border:none;")
        vl.addWidget(speaker)
        # AI text area — transparent, no bubble
        ai_text = QTextEdit()
        ai_text.setReadOnly(True)
        ai_text.setStyleSheet(
            f"QTextEdit {{ background:transparent;color:{C['fg']};"
            f"border:none;{FONT_CHAT}padding:0;margin:0;"
            f"selection-background-color:{C['teal']}; }}")
        ai_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ai_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Auto-resize as content grows
        ai_text.document().contentsChanged.connect(
            lambda: ai_text.setFixedHeight(
                max(24, int(ai_text.document().size().height()) + 4)))
        ai_text.setFixedHeight(24)
        vl.addWidget(ai_text)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, wrapper)
        self._current_ai_widget = ai_text
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """Scroll chat to bottom."""
        QTimer.singleShot(10, lambda: self._chat_scroll.verticalScrollBar().setValue(
            self._chat_scroll.verticalScrollBar().maximum()))

    def _add_info_msg(self, text, color=None):
        """Add a small info/status message (e.g. 'Found 2 edits')."""
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        wl = QHBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {color or C['fg_ok']}; {FONT_CHAT} padding-left: 2px;")
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        wl.addWidget(label)
        wl.addStretch()
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, wrapper)
        self._scroll_to_bottom()

    @staticmethod
    def _esc(t):
        return (t.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace("\n", "<br>"))


# =============================================================================
# Compiler Output
# =============================================================================

class CompilerOutput(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Compiler output will appear here...")

    def append_output(self, text, color=None):
        cur = self.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color or C["fg"]))
        cur.insertText(text + "\n", fmt)
        self.setTextCursor(cur); self.ensureCursorVisible()

    def clear_output(self): self.clear()


# =============================================================================
# Serial Monitor
# =============================================================================

class SerialMonitor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)

        self.display = QPlainTextEdit()
        self.display.setReadOnly(True)
        self.display.setPlaceholderText("Serial output will appear here...")
        layout.addWidget(self.display)

        ctrl = QWidget()
        ctrl.setStyleSheet(f"background: {C['bg']}; border-top: 1px solid {C['border']};")
        cl = QHBoxLayout(ctrl); cl.setContentsMargins(8, 4, 8, 4)
        cl.setSpacing(8)
        port_lbl = QLabel("Port:")
        port_lbl.setStyleSheet(f"color:{C['fg']};{FONT_BODY}background:transparent;border:none;")
        cl.addWidget(port_lbl)
        self.port_combo = QComboBox(); self.port_combo.setEditable(True); self.port_combo.setMinimumWidth(140)
        cl.addWidget(self.port_combo)
        baud_lbl = QLabel("Baud:")
        baud_lbl.setStyleSheet(f"color:{C['fg']};{FONT_BODY}background:transparent;border:none;")
        cl.addWidget(baud_lbl)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600","19200","38400","57600","115200","250000","500000","1000000"])
        self.baud_combo.setCurrentText("9600")
        cl.addWidget(self.baud_combo)
        self.start_btn = QPushButton("Start")
        self.start_btn.setStyleSheet(BTN_PRIMARY)
        self.start_btn.clicked.connect(self._toggle)
        cl.addWidget(self.start_btn)
        clr = QPushButton("Clear")
        clr.setStyleSheet(BTN_GHOST)
        clr.clicked.connect(self.display.clear)
        cl.addWidget(clr)
        self.send_input = QLineEdit(); self.send_input.setPlaceholderText("Send...")
        self.send_input.setFixedWidth(140); self.send_input.returnPressed.connect(self._send)
        cl.addWidget(self.send_input); cl.addStretch()
        layout.addWidget(ctrl)
        self._running = False

    def refresh_ports(self):
        self.port_combo.clear()
        for pat in ["/dev/cu.usbmodem*", "/dev/ttyACM*", "/dev/cu.usbserial*"]:
            for p in glob.glob(pat): self.port_combo.addItem(p)

    def _toggle(self):
        if self._running: self._stop()
        else: self._start()

    def _start(self):
        port = self.port_combo.currentText().strip()
        baud = self.baud_combo.currentText().strip()
        if not port: return
        try:
            import serial
            self._serial = serial.Serial(port, int(baud), timeout=0.1)
            self._running = True
            self.start_btn.setText("Stop")
            self.start_btn.setStyleSheet(BTN_DANGER)
            self._timer = QTimer(); self._timer.timeout.connect(self._read); self._timer.start(50)
        except ImportError: self.display.appendPlainText("pyserial not installed. Run: pip install pyserial")
        except Exception as e: self.display.appendPlainText(f"Error: {e}")

    def _stop(self):
        self._running = False
        if hasattr(self, '_timer'): self._timer.stop()
        if hasattr(self, '_serial') and self._serial.is_open: self._serial.close()
        self.start_btn.setText("Start")
        self.start_btn.setStyleSheet(BTN_PRIMARY)

    def _read(self):
        if hasattr(self, '_serial') and self._serial.is_open:
            try:
                d = self._serial.read(self._serial.in_waiting or 1)
                if d: self.display.appendPlainText(d.decode("utf-8", errors="replace").rstrip())
            except: pass

    def _send(self):
        if hasattr(self, '_serial') and self._serial.is_open:
            try: self._serial.write((self.send_input.text() + "\n").encode()); self.send_input.clear()
            except: pass


# =============================================================================
# Settings Panel — AI Tools Tab
# =============================================================================

class AIToolsTab(QWidget):
    """CRUD editor for the right-click AI context menu actions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # -- Button bar --
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(4)

        add_btn = QPushButton("Add"); add_btn.setStyleSheet(BTN_PRIMARY)
        add_btn.clicked.connect(self._add_action); btn_bar.addWidget(add_btn)
        edit_btn = QPushButton("Edit"); edit_btn.setStyleSheet(BTN_SECONDARY)
        edit_btn.clicked.connect(self._edit_action); btn_bar.addWidget(edit_btn)
        del_btn = QPushButton("Delete"); del_btn.setStyleSheet(BTN_DANGER)
        del_btn.clicked.connect(self._delete_action); btn_bar.addWidget(del_btn)
        sep_btn = QPushButton("Add Separator"); sep_btn.setStyleSheet(BTN_SECONDARY)
        sep_btn.clicked.connect(self._add_separator); btn_bar.addWidget(sep_btn)

        btn_bar.addSpacing(12)
        up_btn = QPushButton("\u25B2"); up_btn.setStyleSheet(BTN_SECONDARY); up_btn.setFixedWidth(30)
        up_btn.setToolTip("Move Up"); up_btn.clicked.connect(self._move_up); btn_bar.addWidget(up_btn)
        down_btn = QPushButton("\u25BC"); down_btn.setStyleSheet(BTN_SECONDARY); down_btn.setFixedWidth(30)
        down_btn.setToolTip("Move Down"); down_btn.clicked.connect(self._move_down); btn_bar.addWidget(down_btn)

        btn_bar.addStretch()
        reset_btn = QPushButton("Reset to Defaults"); reset_btn.setStyleSheet(BTN_SECONDARY)
        reset_btn.clicked.connect(self._reset_defaults); btn_bar.addWidget(reset_btn)
        layout.addLayout(btn_bar)

        # -- Action list --
        self.action_list = QListWidget()
        self.action_list.doubleClicked.connect(self._edit_action)
        layout.addWidget(self.action_list, stretch=1)

        # -- Inline editor --
        self.edit_group = QGroupBox("Edit Action")
        eg_layout = QVBoxLayout(self.edit_group)
        eg_layout.setSpacing(6)

        lbl_row = QHBoxLayout()
        lbl_row.addWidget(QLabel("Label:"))
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Menu item text, e.g. 'Explain This Code'")
        lbl_row.addWidget(self.label_edit)
        eg_layout.addLayout(lbl_row)

        hint = QLabel("Prompt template — use {code} where selected code should be inserted:")
        hint.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        eg_layout.addWidget(hint)
        self.template_edit = QPlainTextEdit()
        self.template_edit.setMaximumHeight(120)
        self.template_edit.setPlaceholderText(
            'e.g. "Explain what the following code does:\\n\\n```cpp\\n{code}\\n```"')
        eg_layout.addWidget(self.template_edit)

        save_row = QHBoxLayout()
        save_edit_btn = QPushButton("Save Changes"); save_edit_btn.setStyleSheet(BTN_PRIMARY)
        save_edit_btn.clicked.connect(self._save_current_edit); save_row.addWidget(save_edit_btn)
        cancel_btn = QPushButton("Cancel"); cancel_btn.setStyleSheet(BTN_SECONDARY)
        cancel_btn.clicked.connect(self._cancel_edit); save_row.addWidget(cancel_btn)
        save_row.addStretch()
        eg_layout.addLayout(save_row)

        self.edit_group.hide()
        layout.addWidget(self.edit_group)

        # -- Status --
        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        layout.addWidget(self.status)

        self._editing_index = -1
        self._populate_list()

    def _populate_list(self):
        self.action_list.clear()
        for entry in AI_ACTIONS:
            if entry is None:
                item = QListWidgetItem("\u2500\u2500\u2500\u2500  separator  \u2500\u2500\u2500\u2500")
                item.setForeground(QColor(C['fg_dim']))
                item.setData(Qt.ItemDataRole.UserRole, "separator")
            else:
                label, template = entry
                if template is None:
                    text = f"{label}  (built-in)"
                else:
                    preview = template[:60].replace("\n", " ")
                    text = f"{label}  \u2014  {preview}..."
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, "action")
            self.action_list.addItem(item)

    def _add_action(self):
        # Insert before "Ask AI About This..." (always last)
        insert_idx = len(AI_ACTIONS) - 1
        # Find last non-None, non-special entry
        for i in range(len(AI_ACTIONS) - 1, -1, -1):
            if AI_ACTIONS[i] is not None and AI_ACTIONS[i][1] is None:
                insert_idx = i
                break
        AI_ACTIONS.insert(insert_idx, ("New Action", "Your prompt here. Use {code} for selected code.\n\n```cpp\n{code}\n```"))
        self._persist()
        self._populate_list()
        self.action_list.setCurrentRow(insert_idx)
        self._edit_action()

    def _edit_action(self):
        row = self.action_list.currentRow()
        if row < 0 or row >= len(AI_ACTIONS):
            return
        entry = AI_ACTIONS[row]
        if entry is None:
            self.status.setText("Cannot edit a separator. Delete it and add a new one.")
            self.status.setStyleSheet(f"color:{C['fg_warn']};{FONT_SMALL}")
            return
        label, template = entry
        if template is None:
            self.status.setText("'Ask AI About This...' is a built-in action and cannot be edited.")
            self.status.setStyleSheet(f"color:{C['fg_warn']};{FONT_SMALL}")
            return
        self._editing_index = row
        self.label_edit.setText(label)
        self.template_edit.setPlainText(template)
        self.edit_group.show()
        self.label_edit.setFocus()

    def _save_current_edit(self):
        if self._editing_index < 0:
            return
        label = self.label_edit.text().strip()
        template = self.template_edit.toPlainText()
        if not label:
            self.status.setText("Label cannot be empty.")
            self.status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")
            return
        AI_ACTIONS[self._editing_index] = (label, template)
        self._persist()
        self._populate_list()
        self.edit_group.hide()
        self._editing_index = -1
        self.status.setText("Action saved.")
        self.status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")

    def _cancel_edit(self):
        self.edit_group.hide()
        self._editing_index = -1

    def _delete_action(self):
        row = self.action_list.currentRow()
        if row < 0 or row >= len(AI_ACTIONS):
            return
        entry = AI_ACTIONS[row]
        if entry is not None and entry[1] is None:
            self.status.setText("Cannot delete 'Ask AI About This...' — it is always available.")
            self.status.setStyleSheet(f"color:{C['fg_warn']};{FONT_SMALL}")
            return
        del AI_ACTIONS[row]
        self._persist()
        self._populate_list()
        self.status.setText("Action deleted.")
        self.status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")

    def _add_separator(self):
        row = self.action_list.currentRow()
        insert_at = row + 1 if row >= 0 else len(AI_ACTIONS) - 1
        # Don't insert after "Ask AI About This..."
        if insert_at >= len(AI_ACTIONS):
            insert_at = len(AI_ACTIONS) - 1
        AI_ACTIONS.insert(insert_at, None)
        self._persist()
        self._populate_list()

    def _move_up(self):
        row = self.action_list.currentRow()
        if row <= 0:
            return
        AI_ACTIONS[row], AI_ACTIONS[row - 1] = AI_ACTIONS[row - 1], AI_ACTIONS[row]
        self._persist()
        self._populate_list()
        self.action_list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.action_list.currentRow()
        if row < 0 or row >= len(AI_ACTIONS) - 2:
            return  # Can't move past second-to-last (before "Ask AI...")
        AI_ACTIONS[row], AI_ACTIONS[row + 1] = AI_ACTIONS[row + 1], AI_ACTIONS[row]
        self._persist()
        self._populate_list()
        self.action_list.setCurrentRow(row + 1)

    def _reset_defaults(self):
        if QMessageBox.question(
            self, "Reset AI Tools",
            "Reset all AI actions to defaults?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        AI_ACTIONS[:] = list(DEFAULT_AI_ACTIONS)
        self._persist()
        self._populate_list()
        self.edit_group.hide()
        self.status.setText("Reset to defaults.")
        self.status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")

    def _persist(self):
        _save_ai_actions()


# =============================================================================
# Settings Panel — Models Tab
# =============================================================================

class ModelsTab(QWidget):
    model_changed = pyqtSignal()
    BASE = "http://localhost:11434"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        QTimer.singleShot(500, self.refresh_models)

    def _setup_ui(self):
        layout = QHBoxLayout(self); layout.setContentsMargins(4, 4, 4, 4)

        # ========== LEFT COLUMN: Manage Models (installed + pull) ==========
        left = QVBoxLayout()

        # Header: title + Refresh button
        hdr = QHBoxLayout()
        models_title = QLabel("Manage Models")
        models_title.setStyleSheet(f"color:{C['fg_head']};{FONT_TITLE}")
        hdr.addWidget(models_title)
        hdr.addStretch()
        rb = QPushButton("Refresh"); rb.setStyleSheet(BTN_SECONDARY)
        rb.clicked.connect(self.refresh_models)
        hdr.addWidget(rb); left.addLayout(hdr)

        # Installed models tree
        self.model_list = QTreeView()
        self.model_list.setHeaderHidden(False); self.model_list.setRootIsDecorated(False)
        self._lm = QStandardItemModel()
        self._lm.setHorizontalHeaderLabels(["Model", "Size", "Modified"])
        self.model_list.setModel(self._lm)
        self.model_list.clicked.connect(self._on_select)
        left.addWidget(self.model_list, stretch=3)

        # Model action buttons
        model_btns = QHBoxLayout()
        model_btns.setSpacing(4)
        self.load_btn = QPushButton("Load")
        self.load_btn.setStyleSheet(BTN_PRIMARY)
        self.load_btn.setToolTip("Load model into memory for fast responses")
        self.load_btn.clicked.connect(self._load_selected)
        model_btns.addWidget(self.load_btn)
        self.unload_btn = QPushButton("Unload")
        self.unload_btn.setStyleSheet(BTN_SECONDARY)
        self.unload_btn.setToolTip("Unload model from memory to free resources")
        self.unload_btn.clicked.connect(self._unload_selected)
        model_btns.addWidget(self.unload_btn)
        db = QPushButton("Delete")
        db.setStyleSheet(BTN_DANGER); db.clicked.connect(self._delete)
        model_btns.addWidget(db)
        model_btns.addStretch()
        left.addLayout(model_btns)

        self.model_status = QLabel("")
        self.model_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        left.addWidget(self.model_status)

        # -- Pull Model section (in left column, below installed models) --
        pull_label = QLabel("Pull Model")
        pull_label.setStyleSheet(f"color:{C['fg_head']};{FONT_SECTION} padding-top: 8px;")
        left.addWidget(pull_label)

        self.pull_filter = QLineEdit()
        self.pull_filter.setPlaceholderText("Filter models...")
        self.pull_filter.textChanged.connect(self._filter_curated)
        left.addWidget(self.pull_filter)

        self.curated_list = QTreeView()
        self.curated_list.setHeaderHidden(False)
        self.curated_list.setRootIsDecorated(False)
        self.curated_list.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self._curated_model = QStandardItemModel()
        self._curated_model.setHorizontalHeaderLabels(["Model", "Size", "Description"])
        self.curated_list.setModel(self._curated_model)
        left.addWidget(self.curated_list, stretch=2)

        pull_row = QHBoxLayout()
        pull_row.setSpacing(4)
        pull_btn = QPushButton("Pull Selected")
        pull_btn.setStyleSheet(BTN_PRIMARY)
        pull_btn.clicked.connect(self._pull_curated)
        pull_row.addWidget(pull_btn)
        pull_row.addStretch()
        left.addLayout(pull_row)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(4)
        custom_row.addWidget(QLabel("Or pull any:"))
        self.custom_pull_name = QLineEdit()
        self.custom_pull_name.setPlaceholderText("e.g. mistral:7b")
        self.custom_pull_name.returnPressed.connect(self._pull_custom)
        custom_row.addWidget(self.custom_pull_name)
        pull_custom_btn = QPushButton("Pull")
        pull_custom_btn.setStyleSheet(BTN_SECONDARY)
        pull_custom_btn.clicked.connect(self._pull_custom)
        custom_row.addWidget(pull_custom_btn)
        left.addLayout(custom_row)

        self.pull_status = QLabel("")
        self.pull_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        left.addWidget(self.pull_status)

        lw = QWidget(); lw.setLayout(left); lw.setMinimumWidth(280)

        # ========== RIGHT COLUMN: Model Details + Create/Edit ==========
        right = QVBoxLayout()

        dg = QGroupBox("Model Details")
        dl = QVBoxLayout(dg)
        self.details = QPlainTextEdit(); self.details.setReadOnly(True)
        self.details.setMaximumHeight(120); self.details.setPlaceholderText("Select a model...")
        dl.addWidget(self.details)

        # Editable description with save
        desc_row = QHBoxLayout()
        desc_row.addWidget(QLabel("Description:"))
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Short description (shown in toolbar)")
        desc_row.addWidget(self.desc_edit)
        save_desc_btn = QPushButton("Save")
        save_desc_btn.setStyleSheet(BTN_PRIMARY)
        save_desc_btn.clicked.connect(self._save_desc)
        desc_row.addWidget(save_desc_btn)
        gen_desc_btn = QPushButton("Auto-Generate")
        gen_desc_btn.setStyleSheet(BTN_SECONDARY)
        gen_desc_btn.clicked.connect(self._auto_gen_desc)
        desc_row.addWidget(gen_desc_btn)
        dl.addLayout(desc_row)
        right.addWidget(dg)

        cg = QGroupBox("Create / Edit Model")
        cl = QVBoxLayout(cg)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Name:")); self.name_in = QLineEdit(); self.name_in.setPlaceholderText("e.g. teensy-coder-v2")
        r1.addWidget(self.name_in); cl.addLayout(r1)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Base:")); self.base_cb = QComboBox(); self.base_cb.setEditable(True); self.base_cb.setMinimumWidth(180)
        r2.addWidget(self.base_cb)
        r2.addWidget(QLabel("Ctx:")); self.ctx_cb = QComboBox()
        self.ctx_cb.addItems(["4096","8192","16384","32768","65536"]); self.ctx_cb.setCurrentText("16384"); self.ctx_cb.setEditable(True)
        r2.addWidget(self.ctx_cb)
        r2.addWidget(QLabel("Temp:")); self.temp_in = QLineEdit("0.7"); self.temp_in.setFixedWidth(45)
        r2.addWidget(self.temp_in); cl.addLayout(r2)

        cl.addWidget(QLabel("System Prompt:"))
        self.sys_in = QPlainTextEdit()
        self.sys_in.setPlaceholderText("e.g. You are an expert embedded systems developer...")
        cl.addWidget(self.sys_in)

        r3 = QHBoxLayout()
        pb = QPushButton("Preview"); pb.setStyleSheet(BTN_SECONDARY); pb.clicked.connect(self._preview); r3.addWidget(pb)
        cb = QPushButton("Create Model")
        cb.setStyleSheet(BTN_PRIMARY)
        cb.clicked.connect(self._create); r3.addWidget(cb); r3.addStretch()
        cl.addLayout(r3)

        self.mf_preview = QPlainTextEdit(); self.mf_preview.setReadOnly(True)
        self.mf_preview.setMaximumHeight(90); self.mf_preview.setPlaceholderText("Preview...")
        cl.addWidget(self.mf_preview)
        self.status = QLabel(""); cl.addWidget(self.status)

        right.addWidget(cg)

        # Wrap right column in scroll area
        rw = QWidget(); rw.setLayout(right)
        right_scroll = QScrollArea()
        right_scroll.setWidget(rw)
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {C['bg']}; }}")

        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.addWidget(lw); sp.addWidget(right_scroll); sp.setSizes([320, 440])
        layout.addWidget(sp)

        self._populate_curated_list()

    def _build_mf(self):
        lines = [f"FROM {self.base_cb.currentText().strip()}"]
        ctx = self.ctx_cb.currentText().strip()
        if ctx: lines.append(f"PARAMETER num_ctx {ctx}")
        t = self.temp_in.text().strip()
        if t: lines.append(f"PARAMETER temperature {t}")
        s = self.sys_in.toPlainText().strip()
        if s: lines.append(f'SYSTEM """{s}"""')
        return "\n".join(lines)

    def _preview(self): self.mf_preview.setPlainText(self._build_mf())

    def _create(self):
        name = self.name_in.text().strip()
        if not name: self.status.setText("Enter a name."); self.status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}"); return
        mf = self._build_mf()
        self.status.setText(f"Creating '{name}'..."); self.status.setStyleSheet(f"color:{C['fg_link']};{FONT_SMALL}")
        def go():
            try:
                r = requests.post(f"{self.BASE}/api/create", json={"name": name, "modelfile": mf}, stream=True, timeout=300)
                st = ""
                for l in r.iter_lines():
                    if l:
                        try: st = json.loads(l).get("status","")
                        except: pass
                ok = "success" in st.lower()
                QTimer.singleShot(0, lambda: self._done(name if ok else st, ok))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._done(str(e), False))
        threading.Thread(target=go, daemon=True).start()

    def _done(self, m, ok):
        if ok:
            self.status.setText(f"'{m}' created!"); self.status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
            self.refresh_models(); self.model_changed.emit()
        else:
            self.status.setText(f"Error: {m}"); self.status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def refresh_models(self):
        self._lm.removeRows(0, self._lm.rowCount()); self.base_cb.clear()
        try:
            r = requests.get(f"{self.BASE}/api/tags", timeout=5)
            if r.status_code == 200:
                for m in r.json().get("models", []):
                    n = m.get("name",""); sz = m.get("size",0)
                    ss = f"{sz/(1024**3):.1f}GB" if sz > 1024**3 else f"{sz/(1024**2):.0f}MB"
                    d = m.get("modified_at","")[:10]
                    row = [QStandardItem(n), QStandardItem(ss), QStandardItem(d)]
                    for i in row: i.setEditable(False)
                    self._lm.appendRow(row); self.base_cb.addItem(n)
                self.model_list.resizeColumnToContents(0)
        except Exception as e: self.details.setPlainText(f"Ollama error: {e}")

    # Shared cache path for model descriptions
    DESC_FILE = os.path.expanduser("~/.teensy_ide_model_descs.json")

    def _load_descs(self):
        try:
            with open(self.DESC_FILE, "r") as f: return json.load(f)
        except: return {}

    def _save_descs_dict(self, d):
        try:
            with open(self.DESC_FILE, "w") as f: json.dump(d, f, indent=2)
        except: pass

    def _on_select(self, idx):
        ni = self._lm.item(idx.row(), 0)
        if not ni: return
        name = ni.text(); self.name_in.setText(name)
        # Load cached description
        descs = self._load_descs()
        self.desc_edit.setText(descs.get(name, ""))
        try:
            r = requests.post(f"{self.BASE}/api/show", json={"name": name}, timeout=10)
            if r.status_code == 200:
                d = r.json(); info = d.get("model_info", {})
                det = [f"Model: {name}"]
                if info:
                    arch = info.get("general.architecture","?")
                    det.append(f"Arch: {arch}")
                    pc = info.get("general.parameter_count","")
                    if pc: det.append(f"Params: {int(pc)/1e9:.1f}B")
                    cl = info.get(f"{arch}.context_length","")
                    if cl: det.append(f"Max Ctx: {cl}")
                p = d.get("parameters","")
                if p: det.append(f"\nParams:\n{p}")
                self.details.setPlainText("\n".join(det))
                # Extract system prompt from the 'system' field or modelfile
                sys_prompt = d.get("system", "")
                mf = d.get("modelfile","")
                if mf:
                    self.mf_preview.setPlainText(mf)
                    if not sys_prompt:
                        if 'SYSTEM """' in mf:
                            try: sys_prompt = mf[mf.index('SYSTEM """')+10:mf.index('"""', mf.index('SYSTEM """')+10)].strip()
                            except: pass
                        elif 'SYSTEM "' in mf:
                            try:
                                start = mf.index('SYSTEM "') + 8
                                sys_prompt = mf[start:mf.index('"', start)].strip()
                            except: pass
                    for l in mf.splitlines():
                        if l.startswith("FROM "): self.base_cb.setCurrentText(l[5:].strip())
                        if "num_ctx" in l.lower(): self.ctx_cb.setCurrentText(l.split()[-1])
                        if "temperature" in l.lower(): self.temp_in.setText(l.split()[-1])
                if sys_prompt:
                    self.sys_in.setPlainText(sys_prompt)
        except Exception as e: self.details.setPlainText(f"Error: {e}")

    def _save_desc(self):
        """Save the user-edited description to the persistent cache."""
        name = self.name_in.text().strip()
        if not name: return
        descs = self._load_descs()
        descs[name] = self.desc_edit.text().strip()
        self._save_descs_dict(descs)
        self.status.setText("Description saved.")
        self.status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")

    def _auto_gen_desc(self):
        """Ask the model to generate its own description, then save it."""
        name = self.name_in.text().strip()
        if not name:
            return
        self.desc_edit.setText("Generating...")
        self.status.setText("Asking model to describe itself...")
        self.status.setStyleSheet(f"color:{C['teal']};{FONT_SMALL}")
        def gen():
            desc = ""
            try:
                # Get technical info
                r = requests.post(f"{self.BASE}/api/show", json={"name": name}, timeout=5)
                tech = ""
                if r.status_code == 200:
                    info = r.json().get("model_info", {})
                    arch = info.get("general.architecture", "")
                    pc = info.get("general.parameter_count", "")
                    parts = []
                    if arch: parts.append(arch)
                    if pc:
                        try: parts.append(f"{int(pc)/1e9:.1f}B")
                        except: pass
                    tech = ", ".join(parts)
                # Ask the model itself
                r2 = requests.post(
                    OLLAMA_URL,
                    json={
                        "model": name,
                        "messages": [{"role": "user", "content":
                            "In EXACTLY 6 words or fewer, describe what you specialize in. "
                            "Reply with ONLY the description, nothing else. "
                            "Example: 'Teensy embedded systems and audio'"}],
                        "stream": False
                    }, timeout=60)
                if r2.status_code == 200:
                    ai_desc = r2.json().get("message", {}).get("content", "").strip()
                    ai_desc = ai_desc.split("\n")[0].strip().rstrip(".")
                    if ai_desc and len(ai_desc) < 60:
                        desc = f"{ai_desc} ({tech})" if tech else ai_desc
                if not desc:
                    desc = tech
            except Exception as e:
                desc = f"Error: {e}"

            def apply():
                self.desc_edit.setText(desc)
                if desc and not desc.startswith("Error"):
                    descs = self._load_descs()
                    descs[name] = desc
                    self._save_descs_dict(descs)
                    self.status.setText("Description generated and saved.")
                    self.status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
                else:
                    self.status.setText(desc)
                    self.status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")
            QTimer.singleShot(0, apply)
        threading.Thread(target=gen, daemon=True).start()

    def _delete(self):
        idxs = self.model_list.selectedIndexes()
        if not idxs: return
        name = self._lm.item(idxs[0].row(), 0).text()
        if QMessageBox.question(self, "Delete", f"Delete '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                r = requests.delete(f"{self.BASE}/api/delete", json={"name": name}, timeout=30)
                if r.status_code == 200:
                    self.status.setText(f"Deleted."); self.status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
                    self.refresh_models(); self.model_changed.emit()
            except Exception as e:
                self.status.setText(str(e)); self.status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    # ---- Load / Unload Model methods ----

    def _load_selected(self):
        """Load the selected model into Ollama memory."""
        idxs = self.model_list.selectedIndexes()
        if not idxs:
            self.model_status.setText("Select a model to load.")
            self.model_status.setStyleSheet(f"color:{C['fg_warn']};{FONT_SMALL}")
            return
        name = self._lm.item(idxs[0].row(), 0).text()
        self.load_btn.setEnabled(False)
        self.load_btn.setText("Loading...")
        self.model_status.setText(f"Loading {name}...")
        self.model_status.setStyleSheet(f"color:{C['fg_link']};{FONT_SMALL}")

        def do_load():
            try:
                requests.post(f"{self.BASE}/api/generate",
                    json={"model": name, "prompt": " ", "keep_alive": "10m",
                          "options": {"num_predict": 1}},
                    timeout=120)
                QTimer.singleShot(0, lambda: self._on_load_done(name, True))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_load_done(name, False, str(e)))
        threading.Thread(target=do_load, daemon=True).start()

    def _on_load_done(self, name, success, error=""):
        self.load_btn.setEnabled(True)
        self.load_btn.setText("Load")
        if success:
            self.model_status.setText(f"{name} loaded into memory.")
            self.model_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
        else:
            self.model_status.setText(f"Failed to load {name}: {error}")
            self.model_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _unload_selected(self):
        """Unload the selected model from Ollama memory."""
        idxs = self.model_list.selectedIndexes()
        if not idxs:
            self.model_status.setText("Select a model to unload.")
            self.model_status.setStyleSheet(f"color:{C['fg_warn']};{FONT_SMALL}")
            return
        name = self._lm.item(idxs[0].row(), 0).text()
        self.unload_btn.setEnabled(False)
        self.unload_btn.setText("Unloading...")
        self.model_status.setText(f"Unloading {name}...")
        self.model_status.setStyleSheet(f"color:{C['fg_link']};{FONT_SMALL}")

        def do_unload():
            try:
                requests.post(f"{self.BASE}/api/generate",
                    json={"model": name, "prompt": "", "keep_alive": "0"},
                    timeout=30)
                QTimer.singleShot(0, lambda: self._on_unload_done(name, True))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_unload_done(name, False, str(e)))
        threading.Thread(target=do_unload, daemon=True).start()

    def _on_unload_done(self, name, success, error=""):
        self.unload_btn.setEnabled(True)
        self.unload_btn.setText("Unload")
        if success:
            self.model_status.setText(f"{name} unloaded from memory.")
            self.model_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
        else:
            self.model_status.setText(f"Failed to unload {name}: {error}")
            self.model_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    # ---- Pull Model methods ----

    def _get_installed_names(self):
        """Return set of installed model names."""
        names = set()
        for row in range(self._lm.rowCount()):
            item = self._lm.item(row, 0)
            if item:
                names.add(item.text())
        return names

    def _populate_curated_list(self, filter_text=""):
        self._curated_model.removeRows(0, self._curated_model.rowCount())
        installed = self._get_installed_names()
        ft = filter_text.lower()
        for m in CURATED_MODELS:
            name, size, desc = m["name"], m["size"], m["desc"]
            if ft and ft not in name.lower() and ft not in desc.lower():
                continue
            is_installed = name in installed
            row = [
                QStandardItem(f"{name}  (installed)" if is_installed else name),
                QStandardItem(size),
                QStandardItem(desc),
            ]
            for item in row:
                item.setEditable(False)
                if is_installed:
                    item.setForeground(QColor(C["fg_dim"]))
            self._curated_model.appendRow(row)
        self.curated_list.resizeColumnToContents(0)
        self.curated_list.resizeColumnToContents(1)

    def _filter_curated(self, text):
        self._populate_curated_list(text)

    def _pull_curated(self):
        idxs = self.curated_list.selectedIndexes()
        if not idxs:
            self.pull_status.setText("Select a model from the list first.")
            self.pull_status.setStyleSheet(f"color:{C['fg_warn']};{FONT_SMALL}")
            return
        name = self._curated_model.item(idxs[0].row(), 0).text()
        name = name.replace("  (installed)", "").strip()
        self._pull_model(name)

    def _pull_custom(self):
        name = self.custom_pull_name.text().strip()
        if not name:
            self.pull_status.setText("Enter a model name.")
            self.pull_status.setStyleSheet(f"color:{C['fg_warn']};{FONT_SMALL}")
            return
        self._pull_model(name)

    def _pull_model(self, name):
        self.pull_status.setText(f"Pulling '{name}'...")
        self.pull_status.setStyleSheet(f"color:{C['teal']};{FONT_SMALL}")

        def go():
            try:
                r = requests.post(
                    f"{self.BASE}/api/pull",
                    json={"name": name}, stream=True, timeout=(10, 600))
                last_status = ""
                for line in r.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            status = chunk.get("status", "")
                            completed = chunk.get("completed", 0)
                            total = chunk.get("total", 0)
                            if total and completed:
                                pct = int(completed / total * 100)
                                msg = f"{status} — {pct}%"
                            else:
                                msg = status
                            last_status = status
                            QTimer.singleShot(0, lambda m=msg: self._on_pull_progress(m))
                        except json.JSONDecodeError:
                            continue
                ok = "success" in last_status.lower()
                QTimer.singleShot(0, lambda: self._on_pull_done(name, ok))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_pull_done(str(e), False))
        threading.Thread(target=go, daemon=True).start()

    def _on_pull_progress(self, msg):
        self.pull_status.setText(msg)

    def _on_pull_done(self, name, success):
        if success:
            self.pull_status.setText(f"'{name}' pulled successfully!")
            self.pull_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
            self.refresh_models()
            self._populate_curated_list(self.pull_filter.text())
            self.model_changed.emit()
        else:
            self.pull_status.setText(f"Pull failed: {name}")
            self.pull_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")


# =============================================================================
# Settings Panel — Container
# =============================================================================

class SettingsPanel(QWidget):
    """Settings panel with AI Tools and Models tabs."""
    model_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar — standardized
        header, _, _ = _make_panel_header("Settings")
        layout.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("settingsTabs")
        self.tabs.tabBar().setExpanding(False)

        self.models_tab = ModelsTab()
        self.models_tab.model_changed.connect(self.model_changed.emit)
        self.tabs.addTab(self.models_tab, "Models")

        self.ai_tools_tab = AIToolsTab()
        self.tabs.addTab(self.ai_tools_tab, "AI Tools")

        layout.addWidget(self.tabs)

    def refresh_models(self):
        """Convenience method for external callers."""
        self.models_tab.refresh_models()


# =============================================================================
# Git Panel
# =============================================================================

class GitPanel(QWidget):
    """Git GUI with graphical branch/tag manager and console output."""
    branch_changed = pyqtSignal()  # emitted after checkout so MainWindow can reload files

    _BTN = BTN_SECONDARY
    _BTN_PRIMARY = BTN_PRIMARY
    _BTN_DANGER = BTN_DANGER

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Header bar — standardized
        header, self.branch_label, header_layout = _make_panel_header("Branch: —")
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(self._BTN_PRIMARY)
        refresh_btn.clicked.connect(self.refresh_status)
        header_layout.addWidget(refresh_btn)
        init_btn = QPushButton("Init Repo")
        init_btn.setStyleSheet(self._BTN)
        init_btn.clicked.connect(self._init_repo)
        header_layout.addWidget(init_btn)
        layout.addWidget(header)

        # ===== Top half: graphical branch/tag manager =====
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(10, 6, 10, 6)
        top_layout.setSpacing(8)

        # -- Branches & Tags side by side --
        lists_row = QHBoxLayout()

        # Branches panel
        br_box = QWidget()
        br_layout = QVBoxLayout(br_box)
        br_layout.setContentsMargins(0, 0, 0, 0)
        br_layout.setSpacing(4)
        br_hdr = QLabel("Branches")
        br_hdr.setStyleSheet(f"color:{C['teal']};{FONT_SECTION}")
        br_layout.addWidget(br_hdr)

        self.branch_list = QTreeView()
        self.branch_list.setHeaderHidden(True)
        self.branch_list.setRootIsDecorated(False)
        self.branch_list.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.branch_list.setStyleSheet(
            f"QTreeView {{ background:{C['bg']};border:1px solid {C['border']};"
            f"border-radius:4px;{FONT_BODY} }} "
            f"QTreeView::item {{ padding: 4px 6px; }} "
            f"QTreeView::item:selected {{ background:{C['teal']};color:white; }}"
            f"QTreeView::item:hover:!selected {{ background:{C['bg_hover']}; }}")
        self._branch_model = QStandardItemModel()
        self.branch_list.setModel(self._branch_model)
        self.branch_list.clicked.connect(self._on_branch_clicked)
        br_layout.addWidget(self.branch_list)

        br_btns = QHBoxLayout()
        br_btns.setSpacing(4)
        self.checkout_btn = QPushButton("Checkout")
        self.checkout_btn.setStyleSheet(self._BTN_PRIMARY)
        self.checkout_btn.clicked.connect(self._checkout_branch)
        br_btns.addWidget(self.checkout_btn)
        self.new_branch_btn = QPushButton("New Branch")
        self.new_branch_btn.setStyleSheet(self._BTN)
        self.new_branch_btn.clicked.connect(self._new_branch)
        br_btns.addWidget(self.new_branch_btn)
        self.merge_btn = QPushButton("Merge Into Current")
        self.merge_btn.setStyleSheet(self._BTN)
        self.merge_btn.clicked.connect(self._merge_branch)
        br_btns.addWidget(self.merge_btn)
        self.del_branch_btn = QPushButton("Delete")
        self.del_branch_btn.setStyleSheet(self._BTN_DANGER)
        self.del_branch_btn.clicked.connect(self._delete_branch)
        br_btns.addWidget(self.del_branch_btn)
        br_btns.addStretch()
        br_layout.addLayout(br_btns)
        lists_row.addWidget(br_box, stretch=3)

        # Tags panel
        tag_box = QWidget()
        tag_layout = QVBoxLayout(tag_box)
        tag_layout.setContentsMargins(0, 0, 0, 0)
        tag_layout.setSpacing(4)
        tag_hdr = QLabel("Tags")
        tag_hdr.setStyleSheet(f"color:{C['teal']};{FONT_SECTION}")
        tag_layout.addWidget(tag_hdr)

        self.tag_list = QTreeView()
        self.tag_list.setHeaderHidden(True)
        self.tag_list.setRootIsDecorated(False)
        self.tag_list.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tag_list.setStyleSheet(
            f"QTreeView {{ background:{C['bg']};border:1px solid {C['border']};"
            f"border-radius:4px;{FONT_BODY} }} "
            f"QTreeView::item {{ padding: 4px 6px; }} "
            f"QTreeView::item:selected {{ background:{C['teal']};color:white; }}"
            f"QTreeView::item:hover:!selected {{ background:{C['bg_hover']}; }}")
        self._tag_model = QStandardItemModel()
        self.tag_list.setModel(self._tag_model)
        self.tag_list.clicked.connect(self._on_tag_clicked)
        tag_layout.addWidget(self.tag_list)

        tag_btns = QHBoxLayout()
        tag_btns.setSpacing(4)
        self.new_tag_btn = QPushButton("New Tag")
        self.new_tag_btn.setStyleSheet(self._BTN)
        self.new_tag_btn.clicked.connect(self._new_tag)
        tag_btns.addWidget(self.new_tag_btn)
        self.checkout_tag_btn = QPushButton("Checkout")
        self.checkout_tag_btn.setStyleSheet(self._BTN)
        self.checkout_tag_btn.clicked.connect(self._checkout_tag)
        tag_btns.addWidget(self.checkout_tag_btn)
        self.del_tag_btn = QPushButton("Delete")
        self.del_tag_btn.setStyleSheet(self._BTN_DANGER)
        self.del_tag_btn.clicked.connect(self._delete_tag)
        tag_btns.addWidget(self.del_tag_btn)
        tag_btns.addStretch()
        tag_layout.addLayout(tag_btns)
        lists_row.addWidget(tag_box, stretch=2)

        top_layout.addLayout(lists_row)

        # Filter indicator
        self.filter_label = QLabel("")
        self.filter_label.setStyleSheet(
            f"color:{C['teal']};{FONT_SMALL}font-style:italic;padding:2px 0;")
        self.filter_label.hide()
        top_layout.addWidget(self.filter_label)

        # -- Commit row --
        commit_row = QHBoxLayout()
        commit_row.setSpacing(6)
        self.commit_msg = QLineEdit()
        self.commit_msg.setPlaceholderText("Commit message...")
        commit_row.addWidget(self.commit_msg)
        commit_btn = QPushButton("Commit All")
        commit_btn.setStyleSheet(self._BTN_PRIMARY)
        commit_btn.clicked.connect(self._commit)
        commit_row.addWidget(commit_btn)
        push_btn = QPushButton("Push")
        push_btn.setStyleSheet(self._BTN)
        push_btn.clicked.connect(self._push)
        commit_row.addWidget(push_btn)
        pull_btn = QPushButton("Pull")
        pull_btn.setStyleSheet(self._BTN)
        pull_btn.clicked.connect(self._pull)
        commit_row.addWidget(pull_btn)
        top_layout.addLayout(commit_row)

        splitter.addWidget(top)

        # ===== Bottom half: console output =====
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet(
            f"background:{C['bg']};color:{C['fg']};"
            f"border:none;border-top:1px solid {C['border']};")
        splitter.addWidget(self.output)

        splitter.setSizes([400, 250])
        layout.addWidget(splitter)

        self._project_path = None
        self._selected_branch_name = None
        self._selected_tag_name = None
        self._all_branches_data = []

    # ---- Helpers ----

    def set_project(self, path):
        self._project_path = path
        self.refresh_status()

    def _run_git(self, args, silent=False):
        if not self._project_path:
            if not silent:
                self._log("No project open.")
            return ""
        try:
            r = subprocess.run(
                ["git"] + args, cwd=self._project_path,
                capture_output=True, text=True, timeout=30)
            out = (r.stdout or "") + (r.stderr or "")
            return out.strip()
        except FileNotFoundError:
            return "git not found. Install git first."
        except Exception as e:
            return str(e)

    def _log(self, text):
        """Append to the console output."""
        self.output.appendPlainText(text)
        self.output.verticalScrollBar().setValue(
            self.output.verticalScrollBar().maximum())

    def _is_repo(self):
        check = self._run_git(["rev-parse", "--is-inside-work-tree"], silent=True)
        return "true" in check.lower()

    def _selected_branch(self):
        idxs = self.branch_list.selectedIndexes()
        if not idxs:
            return None
        item = self._branch_model.itemFromIndex(idxs[0])
        if not item:
            return None
        name = item.text()
        # Strip leading "* " for current branch
        if name.startswith("* "):
            name = name[2:]
        return name.strip()

    def _selected_tag(self):
        idxs = self.tag_list.selectedIndexes()
        if not idxs:
            return None
        item = self._tag_model.itemFromIndex(idxs[0])
        return item.text().strip() if item else None

    # ---- Refresh ----

    def refresh_status(self):
        if not self._project_path:
            self.branch_label.setText("Branch: —")
            self._branch_model.clear()
            self._tag_model.clear()
            self.output.setPlainText("No project open.")
            return

        if not self._is_repo():
            self.branch_label.setText("Not a git repository")
            self._branch_model.clear()
            self._tag_model.clear()
            self.output.setPlainText(
                "Not a git repository.\n"
                "Click 'Init Repo' to initialize one.")
            return

        # Current branch
        current = self._run_git(["branch", "--show-current"], silent=True)
        self.branch_label.setText(f"Branch: {current or '(detached)'}")

        # Reset filter state
        self._selected_branch_name = None
        self._selected_tag_name = None
        self.filter_label.hide()

        # Populate branches
        self._branch_model.clear()
        self._all_branches_data = []
        raw = self._run_git(["branch", "-a"], silent=True)
        for line in raw.splitlines():
            name = line.strip()
            if not name or "HEAD" in name:
                continue
            item = QStandardItem(name)
            if name.startswith("* "):
                item.setForeground(QColor(C["teal"]))
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            elif name.startswith("remotes/"):
                item.setForeground(QColor(C["fg_dim"]))
            self._branch_model.appendRow(item)
            self._all_branches_data.append({
                'name': name.lstrip("* ").strip(),
                'display': name
            })

        # Populate tags — only those reachable from the current branch
        self._refresh_tags_for(current or "HEAD")

        # Console: status + recent log
        status = self._run_git(["status", "--short"], silent=True)
        log = self._run_git(["log", "--oneline", "-15"], silent=True)
        text = f"--- Status ---\n{status or '(clean)'}\n\n--- Recent Commits ---\n{log or '(none)'}"
        self.output.setPlainText(text)

    def _refresh_tags_for(self, branch_ref):
        """Show only tags that are ancestors of the given branch/ref."""
        self._tag_model.clear()
        # Get all tags, then filter to those merged into branch_ref
        raw = self._run_git(["tag", "-l", "--sort=-creatordate",
                             "--merged", branch_ref], silent=True)
        if not raw:
            # Fallback: if --merged fails (detached HEAD, etc), show all tags
            raw = self._run_git(["tag", "-l", "--sort=-creatordate"], silent=True)
        for line in raw.splitlines():
            name = line.strip()
            if name:
                self._tag_model.appendRow(QStandardItem(name))

    def _on_branch_clicked(self, idx):
        """When a branch is clicked, filter tags. Click again to deselect."""
        name = self._selected_branch()
        if not name:
            return
        # Click-to-deselect
        if name == self._selected_branch_name:
            self._selected_branch_name = None
            self.branch_list.clearSelection()
            current = self._run_git(["branch", "--show-current"], silent=True)
            self._refresh_tags_for(current or "HEAD")
            self.filter_label.hide()
            return
        self._selected_branch_name = name
        self._selected_tag_name = None
        self.tag_list.clearSelection()
        ref = name
        self._refresh_tags_for(ref)
        self.filter_label.setText(f"Filtering tags by branch: {name}")
        self.filter_label.show()
        log = self._run_git(["log", "--oneline", "-10", ref], silent=True)
        self._log(f"\n--- Commits on '{name}' ---\n{log or '(none)'}")

    def _on_tag_clicked(self, idx):
        """When a tag is clicked, filter branches to those containing it.
        Click again to deselect."""
        tag_name = self._selected_tag()
        if not tag_name:
            return
        # Click-to-deselect
        if tag_name == self._selected_tag_name:
            self._selected_tag_name = None
            self.tag_list.clearSelection()
            self._refresh_all_branches()
            self.filter_label.hide()
            return
        self._selected_tag_name = tag_name
        self._selected_branch_name = None
        self.branch_list.clearSelection()
        # Find branches containing this tag
        raw = self._run_git(["branch", "-a", "--contains", tag_name], silent=True)
        matching = set()
        for line in raw.splitlines():
            name = line.strip()
            if name and "HEAD" not in name:
                matching.add(name.lstrip("* ").strip())
        # Filter branch list
        self._branch_model.clear()
        for bd in self._all_branches_data:
            if bd['name'] in matching:
                item = QStandardItem(bd['display'])
                if bd['display'].startswith("* "):
                    item.setForeground(QColor(C["teal"]))
                    f = item.font(); f.setBold(True); item.setFont(f)
                elif bd['display'].startswith("remotes/"):
                    item.setForeground(QColor(C["fg_dim"]))
                self._branch_model.appendRow(item)
        self.filter_label.setText(f"Filtering branches by tag: {tag_name}")
        self.filter_label.show()
        self._log(f"\n--- Tag '{tag_name}' is on {len(matching)} branch(es) ---")

    def _refresh_all_branches(self):
        """Repopulate branch list with all branches (clear any filter)."""
        self._branch_model.clear()
        for bd in self._all_branches_data:
            item = QStandardItem(bd['display'])
            if bd['display'].startswith("* "):
                item.setForeground(QColor(C["teal"]))
                f = item.font(); f.setBold(True); item.setFont(f)
            elif bd['display'].startswith("remotes/"):
                item.setForeground(QColor(C["fg_dim"]))
            self._branch_model.appendRow(item)

    # ---- Branch operations ----

    def _confirm(self, title, message):
        """Show a Yes/No confirmation dialog. Returns True if user clicks Yes."""
        return QMessageBox.question(
            self, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes

    # ---- Branch operations ----

    def _checkout_branch(self):
        name = self._selected_branch()
        if not name:
            QMessageBox.information(self, "Git", "Select a branch first.")
            return
        if not self._confirm("Checkout Branch",
                f"Switch to branch '{name}'?\n\nUnsaved changes may be lost."):
            return
        if name.startswith("remotes/origin/"):
            local = name[len("remotes/origin/"):]
            result = self._run_git(["checkout", "-b", local, name])
        else:
            result = self._run_git(["checkout", name])
        self._log(result)
        self.refresh_status()
        self.branch_changed.emit()

    def _new_branch(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Branch", "Branch name:")
        if ok and name.strip():
            if not self._confirm("Create Branch",
                    f"Create and switch to new branch '{name.strip()}'?"):
                return
            result = self._run_git(["checkout", "-b", name.strip()])
            self._log(result)
            self.refresh_status()
            self.branch_changed.emit()

    def _merge_branch(self):
        name = self._selected_branch()
        if not name:
            QMessageBox.information(self, "Git", "Select a branch to merge.")
            return
        current = self._run_git(["branch", "--show-current"], silent=True)
        if not self._confirm("Merge Branch",
                f"Merge '{name}' into '{current}'?\n\n"
                f"This may modify your files and cannot be easily undone."):
            return
        result = self._run_git(["merge", name])
        self._log(result)
        self.refresh_status()
        self.branch_changed.emit()

    def _delete_branch(self):
        name = self._selected_branch()
        if not name:
            QMessageBox.information(self, "Git", "Select a branch first.")
            return
        if name.startswith("* "):
            QMessageBox.warning(self, "Git", "Cannot delete the current branch.")
            return
        if not self._confirm("Delete Branch",
                f"Are you sure you want to delete branch '{name}'?\n\n"
                f"This cannot be undone."):
            return
        result = self._run_git(["branch", "-d", name])
        self._log(result)
        self.refresh_status()

    # ---- Tag operations ----

    def _new_tag(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Tag", "Tag name (e.g. v1.0):")
        if ok and name.strip():
            msg, ok2 = QInputDialog.getText(
                self, "Tag Message", "Message (optional, leave blank for lightweight tag):")
            if ok2:
                if msg.strip():
                    result = self._run_git(["tag", "-a", name.strip(), "-m", msg.strip()])
                else:
                    result = self._run_git(["tag", name.strip()])
                self._log(result or f"Tag '{name.strip()}' created.")
                self.refresh_status()

    def _checkout_tag(self):
        name = self._selected_tag()
        if not name:
            QMessageBox.information(self, "Git", "Select a tag first.")
            return
        if not self._confirm("Checkout Tag",
                f"Switch to tag '{name}'?\n\n"
                f"This will put you in 'detached HEAD' state.\n"
                f"Unsaved changes may be lost."):
            return
        result = self._run_git(["checkout", name])
        self._log(result)
        self.refresh_status()
        self.branch_changed.emit()

    def _delete_tag(self):
        name = self._selected_tag()
        if not name:
            QMessageBox.information(self, "Git", "Select a tag first.")
            return
        if not self._confirm("Delete Tag",
                f"Are you sure you want to delete tag '{name}'?\n\n"
                f"This cannot be undone."):
            return
        result = self._run_git(["tag", "-d", name])
        self._log(result)
        self.refresh_status()

    # ---- Commit / Push / Pull / Init ----

    def _commit(self):
        msg = self.commit_msg.text().strip()
        if not msg:
            QMessageBox.warning(self, "No Message", "Enter a commit message.")
            return
        # Show what will be committed
        status = self._run_git(["status", "--short"], silent=True)
        if not self._confirm("Commit All Changes",
                f"Commit all changes with message:\n\n\"{msg}\"\n\n"
                f"Files to commit:\n{status or '(no changes)'}"):
            return
        self._run_git(["add", "-A"])
        result = self._run_git(["commit", "-m", msg])
        self._log(result)
        self.commit_msg.clear()
        self.refresh_status()

    def _push(self):
        current = self._run_git(["branch", "--show-current"], silent=True)
        if not self._confirm("Push",
                f"Push branch '{current}' to remote?"):
            return
        result = self._run_git(["push"])
        self._log(result or "Push complete.")
        self.refresh_status()

    def _pull(self):
        current = self._run_git(["branch", "--show-current"], silent=True)
        if not self._confirm("Pull",
                f"Pull latest changes into '{current}' from remote?\n\n"
                f"This may modify your local files."):
            return
        result = self._run_git(["pull"])
        self._log(result or "Pull complete.")
        self.refresh_status()
        self.branch_changed.emit()

    def _init_repo(self):
        if not self._project_path:
            self._log("No project open.")
            return
        if not self._confirm("Initialize Repository",
                f"Initialize a new git repository in:\n\n"
                f"{self._project_path}\n\n"
                f"Are you sure?"):
            return
        result = self._run_git(["init"])
        self._log(result)
        self.refresh_status()


class MainWindow(QMainWindow):
    def __init__(self, project_path=None, config=None):
        super().__init__()
        self._config = config or {}
        self.setWindowTitle(WINDOW_TITLE)
        # Size to 75% of screen so it fits any display; fully resizable
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            w = min(int(avail.width() * 0.75), 1200)
            h = min(int(avail.height() * 0.80), 850)
            self.resize(w, h)
            self.move(avail.x() + (avail.width() - w) // 2,
                      avail.y() + (avail.height() - h) // 2)
        else:
            self.resize(900, 650)
        self.setMinimumSize(700, 450)
        self.project_path = project_path
        self._compiler_errors = ""

        self._setup_ui()
        self._setup_toolbar()
        self._setup_menubar()
        self._setup_statusbar()

        # Restore saved window geometry (validated against visible screens)
        geom = self._config.get("window_geometry")
        if geom and len(geom) == 4:
            from PyQt6.QtGui import QGuiApplication
            x, y, gw, gh = geom
            for scr in QGuiApplication.screens():
                sg = scr.availableGeometry()
                if sg.contains(x, y):
                    self.setGeometry(x, y, gw, gh)
                    break

        # Restore board selection
        saved_fqbn = self._config.get("board_fqbn")
        if saved_fqbn and hasattr(self, 'board_combo'):
            idx = self.board_combo.findData(saved_fqbn)
            if idx >= 0:
                self.board_combo.setCurrentIndex(idx)

        # Restore port selection
        saved_port = self._config.get("port")
        if saved_port and hasattr(self, 'port_combo'):
            idx = self.port_combo.findText(saved_port)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)

        if project_path:
            self._open_project(project_path)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---- Left icon sidebar ----
        sidebar = QWidget()
        sidebar.setFixedWidth(48)
        sidebar.setStyleSheet(f"background-color: {C['bg_sidebar']}; border-right: 1px solid {C['border']};")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(4, 6, 4, 6)
        sb_layout.setSpacing(2)

        self.btn_code = SidebarButton("</>", "Code Editor")
        self.btn_code.setChecked(True)
        self.btn_chat = SidebarButton("AI", "AI Chat")
        self.btn_files = FileSidebarButton("Files")
        self.btn_git = GitSidebarButton("Git")
        self.btn_settings = SettingsSidebarButton("Settings")

        self.btn_code.clicked.connect(lambda: self._switch_view(0))
        self.btn_chat.clicked.connect(lambda: self._switch_view(1))
        self.btn_files.clicked.connect(lambda: self._switch_view(2))
        self.btn_settings.clicked.connect(lambda: self._switch_view(3))
        self.btn_git.clicked.connect(lambda: self._switch_view(4))

        sb_layout.addWidget(self.btn_code)
        sb_layout.addWidget(self.btn_chat)
        sb_layout.addWidget(self.btn_files)
        sb_layout.addWidget(self.btn_git)
        sb_layout.addStretch()
        sb_layout.addWidget(self.btn_settings)

        main_layout.addWidget(sidebar)

        # ---- Main content stack ----
        self.view_stack = QStackedWidget()

        # View 0: Code editor view
        code_view = QWidget()
        cv_layout = QVBoxLayout(code_view)
        cv_layout.setContentsMargins(0, 0, 0, 0)
        cv_layout.setSpacing(0)

        v_splitter = QSplitter(Qt.Orientation.Vertical)

        self.editor = TabbedEditor()
        self.editor.file_changed.connect(self._on_editor_file_changed)
        self.editor.ai_action_requested.connect(self._on_ai_action)
        v_splitter.addWidget(self.editor)

        # Bottom panel
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setObjectName("bottomTabs")
        self.bottom_tabs.tabBar().setExpanding(False)
        self.compiler_output = CompilerOutput()
        self.bottom_tabs.addTab(self.compiler_output, "Output")
        self.serial_monitor = SerialMonitor()
        self.bottom_tabs.addTab(self.serial_monitor, "Serial Monitor")

        v_splitter.addWidget(self.bottom_tabs)
        v_splitter.setSizes([675, 225])

        cv_layout.addWidget(v_splitter)
        self.view_stack.addWidget(code_view)

        # View 1: Chat view (full panel)
        self.chat_panel = ChatPanel()
        self.chat_panel.set_editor(self.editor)
        self.chat_panel.generation_started.connect(lambda: self.ai_spinner.start())
        self.chat_panel.generation_finished.connect(lambda: self.ai_spinner.stop())
        self.chat_panel.edits_applied.connect(self._on_edits_applied)
        self.chat_panel.model_switch_requested.connect(self._on_model_switch)
        self.view_stack.addWidget(self.chat_panel)

        # View 2: File Manager (full panel)
        self.file_manager = FileManagerView()
        self.file_manager.file_requested.connect(
            lambda fp: (self.editor.open_file(fp), self._switch_view(0)))
        self.view_stack.addWidget(self.file_manager)

        # View 3: Settings (full panel)
        self.settings_panel = SettingsPanel()
        self.settings_panel.model_changed.connect(self._refresh_models)
        self.view_stack.addWidget(self.settings_panel)

        # View 4: Git panel (full panel)
        self.git_panel = GitPanel()
        self.git_panel.branch_changed.connect(self._on_branch_changed)
        self.view_stack.addWidget(self.git_panel)

        main_layout.addWidget(self.view_stack)

    def _switch_view(self, idx):
        self.view_stack.setCurrentIndex(idx)
        for i, btn in enumerate([self.btn_code, self.btn_chat, self.btn_files,
                                 self.btn_settings, self.btn_git]):
            btn.setChecked(i == idx)
        if idx == 4:
            self.git_panel.refresh_status()

    def _setup_statusbar(self):
        sb = QStatusBar()
        sb.setStyleSheet(
            f"QStatusBar {{ background: {C['bg_sidebar']}; color: {C['fg_dim']};"
            f" border-top: 1px solid {C['border']}; {FONT_SMALL} }}"
            f" QStatusBar::item {{ border: none; }}")
        sb.setFixedHeight(26)
        self.setStatusBar(sb)
        # Left: teal dot + board/port connection info
        dot = QLabel("\u25cf")
        dot.setStyleSheet(f"color:{C['teal']};{FONT_SMALL} padding: 0 0 0 8px;")
        sb.addWidget(dot)
        self._status_board = QLabel("")
        self._status_board.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL} padding: 0 8px;")
        sb.addWidget(self._status_board)
        self._update_status_board()
        # Right: model name + cursor position
        self._status_model = QLabel(OLLAMA_MODEL)
        self._status_model.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL} padding: 0 8px;")
        sb.addPermanentWidget(self._status_model)
        self._status_cursor = QLabel("Ln 1, Col 1")
        self._status_cursor.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL} padding: 0 8px;")
        sb.addPermanentWidget(self._status_cursor)
        # Connect board/port combo changes to status bar
        if hasattr(self, 'board_combo'):
            self.board_combo.currentTextChanged.connect(lambda: self._update_status_board())
        if hasattr(self, 'port_combo'):
            self.port_combo.currentTextChanged.connect(lambda: self._update_status_board())
        # Connect tab changes to re-wire cursor signal
        self.editor.tabs.currentChanged.connect(self._connect_cursor_signal)
        # Wire up initial editor if any
        QTimer.singleShot(100, lambda: self._connect_cursor_signal(self.editor.tabs.currentIndex()))

    def _connect_cursor_signal(self, idx):
        """Connect cursor position signal from current editor tab."""
        w = self.editor.tabs.widget(idx)
        if w is None:
            return
        if HAS_QSCINTILLA and isinstance(w, QsciScintilla):
            try: w.cursorPositionChanged.disconnect(self._update_cursor_pos_sci)
            except: pass
            w.cursorPositionChanged.connect(self._update_cursor_pos_sci)
            line, col = w.getCursorPosition()
            self._status_cursor.setText(f"Ln {line + 1}, Col {col + 1}")
        elif isinstance(w, QPlainTextEdit):
            try: w.cursorPositionChanged.disconnect(self._update_cursor_pos_plain)
            except: pass
            w.cursorPositionChanged.connect(self._update_cursor_pos_plain)
            cursor = w.textCursor()
            self._status_cursor.setText(
                f"Ln {cursor.blockNumber() + 1}, Col {cursor.columnNumber() + 1}")

    def _update_cursor_pos_sci(self, line, col):
        self._status_cursor.setText(f"Ln {line + 1}, Col {col + 1}")

    def _update_cursor_pos_plain(self):
        w = self.editor.tabs.currentWidget()
        if w and isinstance(w, QPlainTextEdit):
            cursor = w.textCursor()
            self._status_cursor.setText(
                f"Ln {cursor.blockNumber() + 1}, Col {cursor.columnNumber() + 1}")

    def _current_fqbn(self):
        """Get the actual FQBN from board combo (stored as item data)."""
        if hasattr(self, 'board_combo'):
            data = self.board_combo.currentData()
            return data if data else self.board_combo.currentText()
        return DEFAULT_FQBN

    def _update_status_board(self):
        board = self._current_fqbn()
        port = self.port_combo.currentText() if hasattr(self, 'port_combo') else ""
        board_display = BOARD_DISPLAY.get(board, board)
        if port:
            self._status_board.setText(f"{board_display} on {port}")
        else:
            self._status_board.setText(f"{board_display}")

    def _setup_toolbar(self):
        toolbar = QToolBar("Build")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.addToolBar(toolbar)

        # Verify/Upload buttons
        tb_primary = (f"QPushButton {{ {BTN_TOOLBAR} }}"
                      f"QPushButton:hover {{ background:{C['teal_hover']}; }}")

        verify_btn = QPushButton("\u2713 Verify")
        verify_btn.setToolTip("Compile sketch (Ctrl+B)")
        verify_btn.setStyleSheet(tb_primary)
        verify_btn.clicked.connect(self._compile)
        toolbar.addWidget(verify_btn)

        upload_btn = QPushButton("\u27A4 Upload")
        upload_btn.setToolTip("Upload to Teensy (Ctrl+U)")
        upload_btn.setStyleSheet(tb_primary)
        upload_btn.clicked.connect(self._upload)
        toolbar.addWidget(upload_btn)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel("Board"))
        self.board_combo = QComboBox()
        fqbns = ["teensy:avr:teensy40", "teensy:avr:teensy41",
                 "teensy:avr:teensy36", "teensy:avr:teensy32", "teensy:avr:teensyLC"]
        for fqbn in fqbns:
            self.board_combo.addItem(BOARD_DISPLAY.get(fqbn, fqbn), fqbn)
        self.board_combo.setCurrentIndex(0)
        self.board_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.board_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.board_combo.setMinimumWidth(100)
        toolbar.addWidget(self.board_combo)

        toolbar.addWidget(QLabel("Port"))
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.port_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.port_combo.setMinimumWidth(100)
        self._refresh_ports()
        toolbar.addWidget(self.port_combo)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel("AI"))
        self.model_combo = QComboBox()
        self.model_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.model_combo.setMinimumWidth(140)
        self._refresh_models()
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        toolbar.addWidget(self.model_combo)

        self.model_desc_label = QLabel("")
        self.model_desc_label.setStyleSheet(
            f"color:{C['fg_dim']};{FONT_SMALL}font-style:italic;"
            f"background:transparent;border:none;margin-left:4px;")
        toolbar.addWidget(self.model_desc_label)
        self._update_model_desc()

        # Load model button — pre-loads model into memory
        self.load_model_btn = QPushButton("Load")
        self.load_model_btn.setToolTip("Pre-load model into memory")
        self.load_model_btn.setStyleSheet(tb_primary)
        self.load_model_btn.clicked.connect(self._load_model)
        toolbar.addWidget(self.load_model_btn)

        # Spacer to push spinner to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer.setStyleSheet("background:transparent;border:none;")
        toolbar.addWidget(spacer)

        # Animated spinner — visible when AI is generating
        self.ai_spinner = SpinnerWidget()
        toolbar.addWidget(self.ai_spinner)

    # ---- Model descriptions (persistent cache) ----

    MODEL_DESC_FILE = os.path.expanduser("~/.teensy_ide_model_descs.json")

    def _load_model_descs(self):
        """Load cached model descriptions from disk."""
        try:
            with open(self.MODEL_DESC_FILE, "r") as f:
                return json.load(f)
        except:
            return {}

    def _save_model_descs(self, descs):
        """Save model descriptions to disk."""
        try:
            with open(self.MODEL_DESC_FILE, "w") as f:
                json.dump(descs, f, indent=2)
        except:
            pass

    def _update_model_desc(self):
        name = self.model_combo.currentText()
        if not name:
            self.model_desc_label.setText("")
            return

        # 1. Check persistent cache
        descs = self._load_model_descs()
        if name in descs and descs[name]:
            self.model_desc_label.setText(descs[name])
            return

        # 2. Try quick metadata lookup first (no AI call)
        self.model_desc_label.setText("")
        def generate():
            try:
                desc = self._generate_model_desc(name)
                if desc:
                    descs = self._load_model_descs()
                    descs[name] = desc
                    self._save_model_descs(descs)
                QTimer.singleShot(0, lambda d=desc: self.model_desc_label.setText(d or ""))
            except Exception:
                QTimer.singleShot(0, lambda: self.model_desc_label.setText(""))
        threading.Thread(target=generate, daemon=True).start()

    def _generate_model_desc(self, name):
        """Build a short description from Ollama API metadata, or ask the model itself."""
        try:
            r = requests.post(
                "http://localhost:11434/api/show",
                json={"name": name}, timeout=5)
            if r.status_code != 200:
                return ""
            d = r.json()
            info = d.get("model_info", {})
            system = d.get("system", "")
            arch = info.get("general.architecture", "")
            pc = info.get("general.parameter_count", "")
            ctx = ""
            if arch:
                ctx_key = f"{arch}.context_length"
                ctx = str(info.get(ctx_key, ""))

            # Build a technical summary
            parts = []
            if arch:
                parts.append(arch)
            if pc:
                try:
                    parts.append(f"{int(pc)/1e9:.1f}B params")
                except:
                    parts.append(f"{pc} params")
            if ctx:
                parts.append(f"ctx {ctx}")

            tech = ", ".join(parts)

            # If the model has a custom system prompt, summarize its specialty
            if system and len(system) > 20:
                # Ask the model itself for a 6-word self-description
                try:
                    r2 = requests.post(
                        OLLAMA_URL,
                        json={
                            "model": name,
                            "messages": [{
                                "role": "user",
                                "content": (
                                    "In EXACTLY 6 words or fewer, describe what you specialize in. "
                                    "Reply with ONLY the description, nothing else. "
                                    "Example: 'Teensy embedded systems and audio'")
                            }],
                            "stream": False
                        },
                        timeout=15)
                    if r2.status_code == 200:
                        ai_desc = r2.json().get("message", {}).get("content", "").strip()
                        # Clean up — take first line, limit length
                        ai_desc = ai_desc.split("\n")[0].strip().rstrip(".")
                        if ai_desc and len(ai_desc) < 60:
                            return f"{ai_desc} ({tech})" if tech else ai_desc
                except:
                    pass

            # Fallback: just use the technical info
            return tech
        except:
            return ""

    def _make_action(self, text, slot, shortcut=None):
        a = QAction(text, self); a.triggered.connect(slot)
        if shortcut: a.setShortcut(QKeySequence(shortcut))
        return a

    def _setup_menubar(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")
        fm.addAction(self._make_action("Open Project...", self._open_project_dialog, "Ctrl+O"))
        fm.addAction(self._make_action("Save", self._save_file, "Ctrl+S"))
        fm.addSeparator()
        fm.addAction(self._make_action("Quit", self.close, "Ctrl+Q"))

        bm = mb.addMenu("Build")
        bm.addAction(self._make_action("Verify/Compile", self._compile, "Ctrl+B"))
        bm.addAction(self._make_action("Upload", self._upload, "Ctrl+U"))

        am = mb.addMenu("AI")
        am.addAction(self._make_action("Open AI Chat", lambda: self._switch_view(1), "Ctrl+Shift+A"))
        am.addAction(self._make_action("Send Errors to AI", self._send_errors_to_ai, "Ctrl+Shift+E"))
        am.addAction(self._make_action("Clear Chat", self.chat_panel.clear_chat))

        vm = mb.addMenu("View")
        vm.addAction(self._make_action("Code Editor", lambda: self._switch_view(0), "Ctrl+1"))
        vm.addAction(self._make_action("AI Chat", lambda: self._switch_view(1), "Ctrl+2"))
        vm.addAction(self._make_action("Files", lambda: self._switch_view(2), "Ctrl+3"))
        vm.addAction(self._make_action("Settings", lambda: self._switch_view(3), "Ctrl+4"))
        vm.addAction(self._make_action("Git", lambda: self._switch_view(4), "Ctrl+5"))

    # ---- File operations ----
    def _open_project_dialog(self):
        p = QFileDialog.getExistingDirectory(self, "Open", os.path.expanduser("~/Documents/Arduino"))
        if p: self._open_project(p)

    def _open_project(self, path):
        self.project_path = path
        self.serial_monitor.refresh_ports()
        self.setWindowTitle(f"{WINDOW_TITLE} — {os.path.basename(path)}")
        self.editor.open_all_project_files(path)
        self.chat_panel.set_project_path(path)
        self.chat_panel._update_context_bar()
        self.git_panel.set_project(path)
        self.file_manager.set_project(path)

    def _on_branch_changed(self):
        """Reload all project files after a git checkout/merge."""
        if not self.project_path:
            return
        # Close all tabs and reopen from disk (files now reflect new branch)
        self.editor.close_all()
        self.editor.open_all_project_files(self.project_path)
        self.chat_panel._update_context_bar()

    def _on_ai_action(self, prompt):
        """Handle AI right-click action from the code editor."""
        self._switch_view(1)
        self.chat_panel.send_ai_action(prompt)

    def _on_edits_applied(self):
        """Refresh file browser and context after AI creates/edits files."""
        if self.project_path:
            self.file_manager.file_browser._refresh()
        self.chat_panel._update_context_bar()

    def _on_model_switch(self, model_name):
        """Handle /model command — update toolbar combo and status bar."""
        global OLLAMA_MODEL
        OLLAMA_MODEL = model_name
        if hasattr(self, 'model_combo'):
            # Try to find and select the model in the combo box
            idx = self.model_combo.findText(model_name)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            else:
                # Model not in list — add it
                self.model_combo.addItem(model_name)
                self.model_combo.setCurrentText(model_name)
        if hasattr(self, '_status_model'):
            self._status_model.setText(model_name)

    def _on_editor_file_changed(self, fp):
        self.setWindowTitle(f"{WINDOW_TITLE} — {os.path.basename(fp)}")
        self.chat_panel._update_context_bar()

    def _save_file(self):
        self.editor.save_current()

    # ---- Build ----
    def _compile(self):
        if not self.project_path:
            QMessageBox.warning(self, "No Project", "Open a project first."); return
        self._save_file(); self.compiler_output.clear_output()
        self._switch_view(0); self.bottom_tabs.setCurrentWidget(self.compiler_output)
        self.compiler_output.append_output("Compiling...", C["fg_link"])
        self._run_cli(["compile", "--fqbn", self._current_fqbn(), self.project_path])

    def _upload(self):
        if not self.project_path:
            QMessageBox.warning(self, "No Project", "Open a project first."); return
        port = self.port_combo.currentText().strip()
        if not port:
            QMessageBox.warning(self, "No Port", "Select a port first."); return
        self._save_file(); self.compiler_output.clear_output()
        self._switch_view(0); self.bottom_tabs.setCurrentWidget(self.compiler_output)
        self.compiler_output.append_output("Compiling and uploading...", C["fg_link"])
        self._run_cli(["compile","--upload","--fqbn",self._current_fqbn(),"--port",port,self.project_path])

    def _run_cli(self, args):
        self._compiler_errors = ""
        def go():
            try:
                r = subprocess.run(["arduino-cli"]+args, capture_output=True, text=True, timeout=120)
                if r.stdout:
                    for l in r.stdout.splitlines():
                        QTimer.singleShot(0, lambda l=l: self.compiler_output.append_output(l))
                if r.stderr:
                    self._compiler_errors = r.stderr
                    for l in r.stderr.splitlines():
                        c = C["fg_err"] if "error" in l.lower() else C["fg_warn"] if "warning" in l.lower() else C["fg"]
                        QTimer.singleShot(0, lambda l=l,c=c: self.compiler_output.append_output(l,c))
                if r.returncode == 0:
                    QTimer.singleShot(0, lambda: self.compiler_output.append_output("\nDone compiling.", C["fg_ok"]))
                else:
                    QTimer.singleShot(0, lambda: self.compiler_output.append_output("\nCompilation failed.", C["fg_err"]))
                    QTimer.singleShot(0, lambda: self.chat_panel.set_error_context(self._compiler_errors))
            except FileNotFoundError:
                QTimer.singleShot(0, lambda: self.compiler_output.append_output("arduino-cli not found.", C["fg_err"]))
            except subprocess.TimeoutExpired:
                QTimer.singleShot(0, lambda: self.compiler_output.append_output("Timed out.", C["fg_err"]))
        threading.Thread(target=go, daemon=True).start()

    def _refresh_ports(self):
        self.port_combo.clear()
        try:
            r = subprocess.run(["arduino-cli","board","list","--format","json"], capture_output=True, text=True, timeout=10)
            if r.stdout:
                d = json.loads(r.stdout)
                pts = d if isinstance(d, list) else d.get("detected_ports", [])
                for pi in pts:
                    a = pi.get("port",{}).get("address","")
                    if a: self.port_combo.addItem(a)
        except: pass
        for pat in ["/dev/cu.usbmodem*","/dev/ttyACM*"]:
            for p in glob.glob(pat):
                if self.port_combo.findText(p)==-1: self.port_combo.addItem(p)

    def _refresh_models(self):
        global OLLAMA_MODEL
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            if r.status_code == 200:
                for m in r.json().get("models",[]):
                    n = m.get("name","")
                    if n: self.model_combo.addItem(n)
                idx = self.model_combo.findText(OLLAMA_MODEL)
                if idx >= 0:
                    self.model_combo.setCurrentIndex(idx)
                elif self.model_combo.count() > 0:
                    self.model_combo.setCurrentIndex(0)
        except:
            self.model_combo.addItem(OLLAMA_MODEL)
        self.model_combo.blockSignals(False)
        # Always sync the global to whatever is actually selected
        current = self.model_combo.currentText()
        if current:
            OLLAMA_MODEL = current

    def _on_model_changed(self, name):
        global OLLAMA_MODEL
        if name:
            OLLAMA_MODEL = name
            self._update_model_desc()
            if hasattr(self, '_status_model'):
                self._status_model.setText(name)

    def _load_model(self):
        """Pre-load the selected model into Ollama memory."""
        model = OLLAMA_MODEL
        if not model:
            return
        self.load_model_btn.setEnabled(False)
        self.load_model_btn.setText("Loading...")
        self.ai_spinner.active = True
        self.ai_spinner.update()
        if hasattr(self, '_status_model'):
            self._status_model.setText(f"Loading {model}...")

        def do_load():
            try:
                requests.post("http://localhost:11434/api/generate",
                    json={"model": model, "prompt": " ", "keep_alive": "10m",
                          "options": {"num_predict": 1}},
                    timeout=120)
                QTimer.singleShot(0, lambda: self._on_model_loaded(model, True))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_model_loaded(model, False, str(e)))
        threading.Thread(target=do_load, daemon=True).start()

    def _on_model_loaded(self, model, success, error=""):
        """Callback when model loading completes."""
        self.load_model_btn.setEnabled(True)
        self.load_model_btn.setText("Load")
        self.ai_spinner.active = False
        self.ai_spinner.update()
        if success:
            if hasattr(self, '_status_model'):
                self._status_model.setText(f"{model} (loaded)")
        else:
            if hasattr(self, '_status_model'):
                self._status_model.setText(f"{model} (failed)")

    def _send_errors_to_ai(self):
        if self._compiler_errors:
            self.chat_panel.set_error_context(self._compiler_errors)
            self.chat_panel.send_errors_btn.setChecked(True)
            self._switch_view(1); self.chat_panel.input_field.setFocus()

    def closeEvent(self, event):
        # Save application state before closing
        config = {
            "project_path": self.project_path,
            "ollama_model": OLLAMA_MODEL,
            "board_fqbn": self._current_fqbn(),
            "port": self.port_combo.currentText() if hasattr(self, 'port_combo') else "",
            "window_geometry": [
                self.geometry().x(), self.geometry().y(),
                self.geometry().width(), self.geometry().height()
            ],
        }
        _save_config(config)
        # Thread cleanup
        if self.chat_panel.thread.isRunning():
            self.chat_panel.worker.stop(); self.chat_panel.thread.quit(); self.chat_panel.thread.wait(2000)
        event.accept()


# =============================================================================
# Entry Point
# =============================================================================

def _ensure_ollama():
    """Start Ollama if it isn't already running."""
    try:
        requests.get("http://localhost:11434/api/tags", timeout=2)
        return  # already running
    except Exception:
        pass
    # Try macOS app first, then CLI
    if os.path.isdir("/Applications/Ollama.app"):
        subprocess.Popen(["open", "-a", "Ollama"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    elif os.path.isfile("/usr/local/bin/ollama"):
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    else:
        return  # not installed
    # Wait briefly for it to come up
    import time
    for _ in range(10):
        time.sleep(1)
        try:
            requests.get("http://localhost:11434/api/tags", timeout=2)
            return
        except Exception:
            pass


def _ensure_app_bundle():
    """Auto-create ArduinoAIDE.app if it doesn't exist (macOS Finder launch)."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(script_dir, "ArduinoAIDE.app")
    if os.path.isdir(app_dir):
        return  # already exists
    create_script = os.path.join(script_dir, "create_app.sh")
    if os.path.isfile(create_script):
        try:
            subprocess.run(["bash", create_script], cwd=script_dir,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=10)
        except Exception:
            pass  # non-critical — app still works from terminal


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(WINDOW_TITLE)
    # Set explicit font to avoid macOS -apple-system lookup warning
    app_font = QFont("Helvetica Neue", 13)
    app_font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(app_font)
    app.setStyleSheet(STYLESHEET)
    # Auto-create .app bundle for Finder launch (if missing)
    _ensure_app_bundle()
    # Ensure Ollama is running
    _ensure_ollama()
    # Load persisted configs
    _load_ai_actions()
    config = _load_config()
    # CLI arg takes precedence over saved project path
    project_path = None
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        project_path = os.path.abspath(sys.argv[1])
    elif config.get("project_path") and os.path.isdir(config["project_path"]):
        project_path = config["project_path"]
    # Set the global model from config before window creation
    global OLLAMA_MODEL
    OLLAMA_MODEL = config.get("ollama_model", "teensy-coder")
    w = MainWindow(project_path, config=config)
    w.show()
    # Auto-preload the AI model after UI is visible
    QTimer.singleShot(500, w._load_model)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
