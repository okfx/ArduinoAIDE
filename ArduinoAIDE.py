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
    QScrollArea, QFrame, QInputDialog, QStatusBar, QProgressBar,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QAbstractItemView, QGridLayout, QHeaderView, QSpinBox
)
from PyQt6.QtCore import (
    Qt, QDir, QModelIndex, pyqtSignal, QObject, QThread,
    QTimer, QSize, QPoint, QPointF
)
from PyQt6.QtGui import (
    QFont, QColor, QAction, QKeySequence, QTextCursor,
    QTextCharFormat, QPalette, QFileSystemModel,
    QStandardItemModel, QStandardItem, QPainter, QPen,
    QPainterPath, QPolygonF, QPixmap, QIcon, QShortcut
)

try:
    from PyQt6.Qsci import QsciScintilla, QsciScintillaBase, QsciLexerCPP, QsciAPIs
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

# Settings panel shared styles
BTN_SM_PRIMARY   = (f"background:{C['teal']};color:white;border:none;"
                    f"border-radius:4px;padding:4px 10px;font-size:11px;font-weight:600;")
BTN_SM_SECONDARY = (f"background:{C['bg_input']};color:{C['fg']};"
                    f"border:1px solid {C['border_light']};border-radius:4px;"
                    f"padding:4px 10px;font-size:11px;")
BTN_SM_GHOST     = (f"background:transparent;color:{C['fg_dim']};"
                    f"border:1px solid {C['border_light']};border-radius:4px;"
                    f"padding:4px 10px;font-size:11px;")
BTN_SM_DANGER    = (f"background:{C['danger']};color:white;border:none;"
                    f"border-radius:4px;padding:4px 10px;font-size:11px;font-weight:600;")
SETTINGS_STITLE  = (f"color:{C['teal']};font-size:11px;font-weight:600;"
                    f"border-bottom:1px solid {C['bg_hover']};padding-bottom:4px;")
SETTINGS_CARD    = (f"QFrame{{background:{C['bg']};border:1px solid {C['border']};"
                    f"border-radius:8px;}}")
SETTINGS_INPUT   = (f"background:{C['bg_input']};color:{C['fg']};"
                    f"border:1px solid {C['border_light']};border-radius:6px;"
                    f"padding:6px 10px;font-size:13px;")
SETTINGS_COMBO   = (f"QComboBox{{background:{C['bg_input']};color:{C['fg']};"
                    f"border:1px solid {C['border_light']};border-radius:6px;"
                    f"padding:4px 8px;font-size:13px;}}"
                    f"QComboBox::drop-down{{border:none;}}"
                    f"QComboBox QAbstractItemView{{background:{C['bg_input']};"
                    f"color:{C['fg']};border:1px solid {C['border']};}}")
SETTINGS_TABLE   = (f"QTableWidget{{background:{C['bg_dark']};color:{C['fg']};"
                    f"border:1px solid {C['border']};border-radius:6px;"
                    f"gridline-color:{C['border']};}}"
                    f"QTableWidget::item{{padding:4px 8px;border:none;}}"
                    f"QTableWidget::item:selected{{background:{C['bg_hover']};"
                    f"color:{C['fg']};}}"
                    f"QTableWidget::item:hover:!selected{{background:{C['bg_hover']};}}")
SETTINGS_TBL_HDR = (f"QHeaderView::section{{background:{C['bg_input']};color:{C['fg_dim']};"
                    f"font-size:11px;font-weight:600;border:none;"
                    f"padding:4px 8px;border-right:1px solid {C['border']};}}")

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
                f"=== FILES IN YOUR CONTEXT ({len(included)} files — you can read and edit these directly) ===")
            if stubs:
                parts.append(f"[{len(stubs)} additional file(s) excluded by budget]")
            parts.append("")
            for e in included:
                label = "ACTIVE FILE" if e.priority == 0 else "FILE"
                parts.append(f"========== {label}: {e.rel_path} ==========")
                parts.append(e.content)
                parts.append(f"========== END: {e.rel_path} ==========\n")
            parts.append("=== END OF FILE CONTEXT ===")
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
    edit_type: str       # "edit" or "file" (from parser)
    filename: str
    old_text: str        # None for "file" type
    new_text: str
    operation: str = ""           # "create_file", "replace_file", "search_replace"
    warnings: list = field(default_factory=list)  # validation warnings
    blocked: bool = False         # if True, skip during apply
    resolved_path: str = ""       # cached absolute path after resolution
    matched_text: str = ""        # actual text matched in file (for normalized matches)

@dataclass
class SymbolEntry:
    """A single indexed symbol (function, global, type) in the project."""
    name: str
    rel_path: str       # relative path to source file
    line: int           # 1-based line number
    kind: str           # "function", "global", "type"
    signature: str = "" # e.g. "void digitalWrite(uint8_t pin, uint8_t val)"

@dataclass
class StructuredDiagnostic:
    """A single compiler diagnostic parsed from gcc/arduino-cli output."""
    file: str
    line: int
    column: int
    severity: str      # "error", "warning", "note"
    message: str

@dataclass
class AIWorkResult:
    """Structured result of one AI turn. Populated by response parsing;
    consumed by apply/review logic. Future features (compile diagnostics,
    agent commands, rationale) attach here instead of ad-hoc side channels."""
    assistant_text: str = ""
    proposed_edits: list = field(default_factory=list)   # list[ProposedEdit]
    requested_reads: list = field(default_factory=list)  # list[str] — filenames (future)
    request_compile: bool = False                        # (future)
    diagnostics: list = field(default_factory=list)      # list[StructuredDiagnostic]
    warnings: list = field(default_factory=list)         # list[str]
    metadata: dict = field(default_factory=dict)


def _diag_key(d):
    """Identity key for a StructuredDiagnostic, ignoring line numbers
    (which shift when code is edited). Matches on file + severity + message."""
    return (os.path.basename(d.file), d.severity, d.message)

def _diff_diagnostics(prev, curr):
    """Compare two diagnostic lists. Returns (resolved, remaining, new) counts.
    Uses file+severity+message matching (line numbers ignored)."""
    from collections import Counter
    prev_counts = Counter(_diag_key(d) for d in prev)
    curr_counts = Counter(_diag_key(d) for d in curr)
    all_keys = set(prev_counts) | set(curr_counts)
    resolved = 0
    remaining = 0
    new = 0
    for k in all_keys:
        p = prev_counts.get(k, 0)
        c = curr_counts.get(k, 0)
        matched = min(p, c)
        remaining += matched
        resolved += p - matched
        new += c - matched
    return resolved, remaining, new

_GCC_DIAG_RE = re.compile(
    r'^(.+?):(\d+):(?:(\d+):)?\s*(error|warning|note):\s*(.+)$')
_LINKER_RE = re.compile(
    r"(undefined reference to|multiple definition of)\s+[`'](.+?)[`']")
_INCLUDE_RE = re.compile(
    r'^In file included from (.+?):(\d+)[,:]')
_BARE_DIAG_RE = re.compile(
    r'^\s*(error|warning):\s*(.+)$')
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

def _normalize_ws(text):
    """Normalize whitespace for fuzzy anchor matching.
    - Strips leading/trailing whitespace from each line
    - Collapses runs of spaces/tabs within each line to a single space
    - Preserves line boundaries (newlines)
    Returns the normalized string."""
    lines = text.splitlines()
    out = []
    for line in lines:
        # Strip leading/trailing, collapse internal whitespace runs
        out.append(re.sub(r'[ \t]+', ' ', line.strip()))
    return '\n'.join(out)


def _find_normalized_matches(content, anchor):
    """Find regions in content that match anchor under whitespace normalization.
    Returns list of (start, end) index pairs into the original content."""
    norm_anchor = _normalize_ws(anchor)
    if not norm_anchor:
        return []
    # Build a normalized version of content with index mapping
    # For each line in content, record its start/end in original and its normalized form
    content_lines = content.splitlines(True)  # keep line endings
    matches = []
    anchor_lines = norm_anchor.split('\n')
    n_anchor = len(anchor_lines)
    # Normalize each content line (strip + collapse whitespace)
    norm_content_lines = [re.sub(r'[ \t]+', ' ', ln.rstrip('\n\r').strip())
                          for ln in content_lines]
    # Sliding window search
    for i in range(len(norm_content_lines) - n_anchor + 1):
        window = norm_content_lines[i:i + n_anchor]
        if window == anchor_lines:
            # Found a match — compute original byte range
            start = sum(len(ln) for ln in content_lines[:i])
            end = sum(len(ln) for ln in content_lines[:i + n_anchor])
            matches.append((start, end))
    return matches


def _parse_compiler_diagnostics(stderr_text):
    """Parse gcc/arduino-cli stderr into StructuredDiagnostic objects.
    Returns (list[StructuredDiagnostic], raw_text). Raw text is always preserved."""
    diags = []
    cleaned = _ANSI_RE.sub('', stderr_text)
    for line in cleaned.splitlines():
        stripped = line.strip()
        # Pattern A/B — gcc-style with optional column
        m = _GCC_DIAG_RE.match(stripped)
        if m:
            diags.append(StructuredDiagnostic(
                file=m.group(1),
                line=int(m.group(2)),
                column=int(m.group(3)) if m.group(3) else 0,
                severity=m.group(4),
                message=m.group(5).strip(),
            ))
            continue
        # Pattern C — "In file included from path:line"
        m = _INCLUDE_RE.match(stripped)
        if m:
            diags.append(StructuredDiagnostic(
                file=m.group(1), line=int(m.group(2)), column=0,
                severity="note", message="In file included from here",
            ))
            continue
        # Linker errors
        m = _LINKER_RE.search(stripped)
        if m:
            diags.append(StructuredDiagnostic(
                file="<linker>", line=0, column=0,
                severity="error", message=stripped,
            ))
            continue
        # Pattern D — standalone error/warning with no file
        m = _BARE_DIAG_RE.match(stripped)
        if m:
            diags.append(StructuredDiagnostic(
                file="", line=0, column=0,
                severity=m.group(1), message=m.group(2).strip(),
            ))
    return diags, stderr_text


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


OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "teensy-coder"
AI_BACKEND = "ollama"        # "ollama" or "lmstudio"
LMSTUDIO_URL = "http://localhost:1234"
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
        "recent_projects": [],
        "editor_font_size": 13,
        "tab_width": 2,
        "ollama_url": "http://localhost:11434",
        "ai_backend": "ollama",
        "lmstudio_url": "http://localhost:1234",
        "arduino_cli_path": "arduino-cli",
        "additional_board_urls": [],
        "context_budget": 12000,
        "verbose_compile": False,
        "compiler_warnings": "default",
    }
    try:
        with open(CONFIG_FILE, "r") as f:
            saved = json.load(f)
        # Merge saved values over defaults (preserves all keys)
        defaults.update(saved)
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

# Ollama inference options — tuned for Qwen3 non-thinking mode
OLLAMA_CHAT_OPTIONS = {
    "enable_thinking": False,
    "temperature": 0.3,
    "top_p": 0.8,
    "top_k": 20,
    "repeat_penalty": 1.1,
    "num_predict": 4096,
}

# Stop sequences to catch format leakage
OLLAMA_STOP_SEQUENCES = ["```", "<|im_start|>", "<|im_end|>", "<think>"]

# Persist custom rules to disk
_RULES_FILE = os.path.expanduser("~/.teensy_ide_rules.txt")

def _load_custom_rules():
    """Load custom system prompt rules from disk, or return None if no custom rules."""
    try:
        with open(_RULES_FILE, "r", encoding="utf-8") as f:
            text = f.read().strip()
        return text if text else None
    except (FileNotFoundError, OSError):
        return None

def _save_custom_rules(text):
    """Save custom rules to disk. Pass empty string to delete."""
    try:
        if not text.strip():
            if os.path.exists(_RULES_FILE):
                os.remove(_RULES_FILE)
            return
        with open(_RULES_FILE, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
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
TARGET_EXTENSIONS = {".ino", ".cpp", ".c", ".h", ".hpp"}  # code extensions for file-targeting detection
PROJECT_SKIP_DIRS = {'.git', '__pycache__', 'build', 'node_modules', '.venv', 'venv'}

# ── Arduino/Teensy calltip signatures for built-in functions ──
ARDUINO_CALLTIPS = {
    "pinMode": "void pinMode(uint8_t pin, uint8_t mode)",
    "digitalWrite": "void digitalWrite(uint8_t pin, uint8_t val)",
    "digitalRead": "int digitalRead(uint8_t pin)",
    "analogRead": "int analogRead(uint8_t pin)",
    "analogWrite": "void analogWrite(uint8_t pin, int val)",
    "delay": "void delay(unsigned long ms)",
    "delayMicroseconds": "void delayMicroseconds(unsigned int us)",
    "millis": "unsigned long millis()",
    "micros": "unsigned long micros()",
    "attachInterrupt": "void attachInterrupt(uint8_t pin, void(*fn)(void), int mode)",
    "Serial.begin": "void Serial.begin(unsigned long baud)",
    "Serial.print": "size_t Serial.print(val) / Serial.print(val, format)",
    "Serial.println": "size_t Serial.println(val) / Serial.println(val, format)",
    "Serial.write": "size_t Serial.write(uint8_t byte) / Serial.write(buf, len)",
    "Serial.read": "int Serial.read()",
    "Serial.available": "int Serial.available()",
    "Serial.readString": "String Serial.readString()",
    "tone": "void tone(uint8_t pin, unsigned int freq, unsigned long dur=0)",
    "noTone": "void noTone(uint8_t pin)",
    "map": "long map(long val, long fromLow, long fromHigh, long toLow, long toHigh)",
    "constrain": "x constrain(x, a, b)",
    "shiftOut": "void shiftOut(uint8_t dataPin, uint8_t clockPin, uint8_t bitOrder, uint8_t val)",
    "pulseIn": "unsigned long pulseIn(uint8_t pin, uint8_t state, unsigned long timeout=1000000)",
    "Wire.begin": "void Wire.begin() / Wire.begin(uint8_t addr)",
    "Wire.beginTransmission": "void Wire.beginTransmission(uint8_t addr)",
    "Wire.write": "size_t Wire.write(uint8_t val) / Wire.write(buf, len)",
    "Wire.endTransmission": "uint8_t Wire.endTransmission(bool stop=true)",
    "Wire.requestFrom": "uint8_t Wire.requestFrom(uint8_t addr, uint8_t qty)",
    "Wire.read": "int Wire.read()",
    "SPI.begin": "void SPI.begin()",
    "SPI.transfer": "uint8_t SPI.transfer(uint8_t val)",
    "SPI.beginTransaction": "void SPI.beginTransaction(SPISettings settings)",
    "SPI.endTransaction": "void SPI.endTransaction()",
    "digitalWriteFast": "void digitalWriteFast(uint8_t pin, uint8_t val)",
    "digitalReadFast": "int digitalReadFast(uint8_t pin)",
    "analogReadResolution": "void analogReadResolution(unsigned int bits)",
    "analogWriteResolution": "void analogWriteResolution(unsigned int bits)",
    "analogWriteFrequency": "void analogWriteFrequency(uint8_t pin, float freq)",
}

SYSTEM_PROMPT = """You are ArduinoAIDE, an embedded firmware coding assistant for Teensy/Arduino C/C++ projects. The IDE already provides the project files and relevant context. Act on them directly.

DEFAULT MODE
- If the user asks to change, fix, add, remove, refactor, implement, replace, or resolve errors: output edits immediately.
- If the user asks to explain, review, summarize, or analyze: answer in plain text only.
- If compiler or build errors are shown: fix them immediately using edits.
- Do not ask for files, paths, snippets, or pasted code that should already be in context.
- Ask at most one short clarifying question only when a safe edit is impossible without it.

OUTPUT RULES
- Be brief.
- For edit requests, output only the edit block(s). No preface. No afterword.
- Never say you can help, would you like me to, here is the fix, or similar filler.
- Never output markdown fences.
- Never output unified diffs.
- Never output XML, JSON, YAML, LaTeX, role labels, special tokens, or chat wrappers.
- Never output <think>, </think>, <|im_start|>, <|im_end|>, assistant:, or similar tokens anywhere.
- Plain text only unless emitting the edit syntax below.

EDIT SYNTAX

Replace code:
<<<EDIT path/to/file.ext
<<<OLD
exact existing text
>>>NEW
replacement text
>>>END

Write full file:
<<<FILE path/to/file.ext
complete file contents
>>>FILE

Insert before anchor:
<<<INSERT_BEFORE path/to/file.ext
<<<ANCHOR
exact anchor text
>>>ANCHOR
<<<CONTENT
inserted text
>>>CONTENT

Insert after anchor:
<<<INSERT_AFTER path/to/file.ext
<<<ANCHOR
exact anchor text
>>>ANCHOR
<<<CONTENT
inserted text
>>>CONTENT

SELECTION MODE
If the input contains:
<<<SELECTED>>>
...
>>>SELECTED>>>
then output only:
<<<REPLACEMENT>>>
replacement code only
>>>REPLACEMENT>>>
No explanation. No edit blocks. No markdown. No extra text.

EDIT DECISION RULES
- Prefer <<<EDIT for existing files.
- Use <<<FILE only for new files or true full rewrites.
- For small or moderate changes, do not use <<<FILE.
- Use relative paths exactly as shown by the IDE.
- OLD must match the existing file exactly, including whitespace.
- Never invent OLD content.
- If exact OLD cannot be trusted, use INSERT_BEFORE or INSERT_AFTER with a real anchor from context.
- Do not guess missing file content.
- Preserve unrelated code.

PRIORITY ORDER
1. Correct syntax and markers
2. Exact OLD or exact anchor
3. Smallest safe edit
4. No commentary

GOOD EXAMPLES

User: Fix the compile error from missing include for millis().
Assistant:
<<<INSERT_BEFORE src/main.cpp
<<<ANCHOR
void setup() {
>>>ANCHOR
<<<CONTENT
#include <Arduino.h>
>>>CONTENT

User: Rename loop counter i to channel in the selected code.
Assistant:
<<<REPLACEMENT>>>
for (int channel = 0; channel < 8; ++channel) {
  readMux(channel);
}
>>>REPLACEMENT>>>

User: Add a helper to clamp PWM duty and use it in setFanDuty().
Assistant:
<<<INSERT_BEFORE src/fan.cpp
<<<ANCHOR
void setFanDuty(uint8_t duty) {
>>>ANCHOR
<<<CONTENT
static inline uint8_t clampDuty(uint8_t duty) {
  return duty > 100 ? 100 : duty;
}
>>>CONTENT

<<<EDIT src/fan.cpp
<<<OLD
void setFanDuty(uint8_t duty) {
  analogWrite(FAN_PIN, duty);
}
>>>NEW
void setFanDuty(uint8_t duty) {
  analogWrite(FAN_PIN, clampDuty(duty));
}
>>>END

BAD EXAMPLE (never do this)

User: Fix the bug.
Assistant: Sure, I can help with that. Please provide the file path and confirm whether you want a full rewrite.
```diff
@@ -old
+new
```
This change should solve the issue.

A Teensy quick reference is appended below. A comprehensive API reference may also be in your file context — consult it for pin mappings, peripheral APIs, and library usage."""

# Load Teensy quick reference (appended to system prompt at startup)
_quick_ref_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'docs', 'TEENSY_QUICK_REF.md')
try:
    with open(_quick_ref_path, 'r', encoding='utf-8') as _f:
        _TEENSY_QUICK_REF = _f.read().strip()
except (FileNotFoundError, OSError):
    _TEENSY_QUICK_REF = ""
if _TEENSY_QUICK_REF:
    SYSTEM_PROMPT += "\n\n--- TEENSY QUICK REFERENCE ---\n" + _TEENSY_QUICK_REF

# Snapshot default prompt before custom rules override
# _DEFAULT_SYSTEM_PROMPT includes Teensy ref (for full runtime use)
# _DEFAULT_RULES_TEXT excludes Teensy ref (for editor display)
_DEFAULT_SYSTEM_PROMPT = SYSTEM_PROMPT
_DEFAULT_RULES_TEXT = SYSTEM_PROMPT.split(
    "\n\n--- TEENSY QUICK REFERENCE ---\n")[0] if _TEENSY_QUICK_REF else SYSTEM_PROMPT

# Load custom rules if they exist (overrides default prompt)
_custom_rules = _load_custom_rules()
if _custom_rules:
    SYSTEM_PROMPT = _custom_rules
    if _TEENSY_QUICK_REF and _TEENSY_QUICK_REF not in SYSTEM_PROMPT:
        SYSTEM_PROMPT += "\n\n--- TEENSY QUICK REFERENCE ---\n" + _TEENSY_QUICK_REF

# Path to full Teensy API reference (included in WorkingSet for .ino projects)
_TEENSY_API_REF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     'docs', 'TEENSY_API_REFERENCE.md')
_REF_DOCS_FILE = os.path.expanduser("~/.teensy_ide_ref_docs.json")

def _load_ref_docs():
    """Load reference documents list from config. Returns list of abs paths."""
    if os.path.exists(_REF_DOCS_FILE):
        try:
            with open(_REF_DOCS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    # First run: seed with Teensy API reference if it exists
    docs = []
    if os.path.exists(_TEENSY_API_REF_PATH):
        docs.append(_TEENSY_API_REF_PATH)
    _save_ref_docs(docs)
    return docs

def _save_ref_docs(docs):
    """Persist reference documents list."""
    try:
        with open(_REF_DOCS_FILE, 'w') as f:
            json.dump(docs, f, indent=2)
    except OSError:
        pass

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
QTabBar#fileTabBar {{ background-color: {C['bg_dark']}; alignment: left; }}
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
QTabWidget#bottomTabs > QTabBar {{ alignment: left; }}
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
QTabWidget#settingsTabs > QTabBar {{ alignment: left; }}
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


class SerialSidebarButton(SidebarButton):
    """Sidebar button with a custom-painted terminal/serial icon."""
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
        # Terminal screen outline (20×14)
        p.drawRoundedRect(int(cx - 10), int(cy - 7), 20, 14, 2, 2)
        # Prompt cursor ">" inside
        p.setPen(QPen(col, 1.8))
        p.drawLine(int(cx - 5), int(cy - 1), int(cx - 1), int(cy + 2))
        p.drawLine(int(cx - 1), int(cy + 2), int(cx - 5), int(cy + 5))
        # Cursor underscore
        p.drawLine(int(cx + 1), int(cy + 5), int(cx + 6), int(cy + 5))
        p.end()


class LibrarySidebarButton(SidebarButton):
    """Sidebar button with book icon for Library Manager."""
    def __init__(self, tooltip, parent=None):
        super().__init__("", tooltip, parent)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = QColor(C['fg']) if self.isChecked() or self.underMouse() else QColor(C['fg_dim'])
        p.setPen(QPen(col, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = self.width() // 2, self.height() // 2
        # Book spine + pages
        p.drawLine(cx, cy - 7, cx, cy + 7)
        p.drawRect(cx - 9, cy - 7, 8, 14)
        p.drawRect(cx + 1, cy - 7, 8, 14)
        p.end()


class BoardSidebarButton(SidebarButton):
    """Sidebar button with chip icon for Board Manager."""
    def __init__(self, tooltip, parent=None):
        super().__init__("", tooltip, parent)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = QColor(C['fg']) if self.isChecked() or self.underMouse() else QColor(C['fg_dim'])
        p.setPen(QPen(col, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = self.width() // 2, self.height() // 2
        # Chip body
        p.drawRect(cx - 6, cy - 6, 12, 12)
        # Pins on all 4 sides
        for offset in [-4, 0, 4]:
            p.drawLine(cx - 9, cy + offset, cx - 6, cy + offset)
            p.drawLine(cx + 6, cy + offset, cx + 9, cy + offset)
            p.drawLine(cx + offset, cy - 9, cx + offset, cy - 6)
            p.drawLine(cx + offset, cy + 6, cx + offset, cy + 9)
        p.end()


class PlotterSidebarButton(SidebarButton):
    """Sidebar button with a line-chart icon for Serial Plotter."""
    def __init__(self, tooltip, parent=None):
        super().__init__("", tooltip, parent)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = QColor(C['fg']) if self.isChecked() or self.underMouse() else QColor(C['fg_dim'])
        p.setPen(QPen(col, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = self.width() // 2, self.height() // 2
        # Axes
        p.drawLine(cx - 9, cy - 8, cx - 9, cy + 8)
        p.drawLine(cx - 9, cy + 8, cx + 9, cy + 8)
        # Line chart polyline
        p.setPen(QPen(QColor(C['teal']), 1.8))
        points = [QPointF(cx - 7, cy + 4), QPointF(cx - 3, cy - 2),
                  QPointF(cx + 1, cy + 1), QPointF(cx + 5, cy - 6),
                  QPointF(cx + 8, cy - 3)]
        p.drawPolyline(QPolygonF(points))
        p.end()


class NavBadge(QLabel):
    """Small circular count badge overlaid on a sidebar icon button."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        self.hide()
        self._update_style(C['fg_err'])

    def _update_style(self, bg_color):
        self.setStyleSheet(
            f"background:{bg_color};color:white;border-radius:8px;"
            f"font-size:9px;font-weight:bold;border:none;")

    def set_count(self, errors, warnings):
        if errors > 0:
            self._update_style(C['fg_err'])
            self.setText("9+" if errors > 9 else str(errors))
            self.show()
        elif warnings > 0:
            self._update_style(C['fg_warn'])
            self.setText("9+" if warnings > 9 else str(warnings))
            self.show()
        else:
            self.hide()

    def reposition(self):
        if self.parentWidget():
            pw = self.parentWidget().width()
            self.move(pw - 10, -2)


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
            if AI_BACKEND == "lmstudio":
                self._run_openai()
            else:
                self._run_ollama()
        except requests.exceptions.ConnectionError:
            if not self._stop:
                backend_name = "LM Studio" if AI_BACKEND == "lmstudio" else "Ollama"
                self.error_occurred.emit(
                    f"Cannot connect to {backend_name}. Is it running?")
        except Exception as e:
            if not self._stop:
                self.error_occurred.emit(str(e))
        finally:
            if not self._stop:
                self.response_complete.emit()

    def _run_ollama(self):
        resp = requests.post(f"{OLLAMA_URL}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": self.messages,
                  "stream": True,
                  "options": OLLAMA_CHAT_OPTIONS,
                  "stop": OLLAMA_STOP_SEQUENCES},
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

    def _run_openai(self):
        # Don't pass Ollama-specific stop sequences to OpenAI-compatible APIs —
        # tokens like <|im_end|> are chat template internals that cause
        # immediate termination on backends like LM Studio MLX.
        payload = {
            "model": OLLAMA_MODEL,
            "messages": self.messages,
            "stream": True,
            "temperature": OLLAMA_CHAT_OPTIONS.get("temperature", 0.3),
            "top_p": OLLAMA_CHAT_OPTIONS.get("top_p", 0.8),
            "max_tokens": OLLAMA_CHAT_OPTIONS.get("num_predict", 4096),
        }
        resp = requests.post(f"{LMSTUDIO_URL}/v1/chat/completions",
            json=payload, stream=True, timeout=(5, 120))
        resp.raise_for_status()
        for line in resp.iter_lines():
            if self._stop:
                resp.close()
                break
            if not line:
                continue
            text = line.decode("utf-8", errors="replace")
            # SSE prefix: handle both "data: " (with space) and "data:" (without)
            if text.startswith("data: "):
                text = text[6:]
            elif text.startswith("data:"):
                text = text[5:]
            text = text.strip()
            if not text:
                continue
            if text == "[DONE]":
                break
            try:
                chunk = json.loads(text)
                # Detect error responses (non-streaming JSON error objects)
                if "error" in chunk:
                    err_msg = chunk["error"]
                    if isinstance(err_msg, dict):
                        err_msg = err_msg.get("message", str(err_msg))
                    self.error_occurred.emit(f"LM Studio: {err_msg}")
                    return
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                t = delta.get("content", "")
                if t: self.token_received.emit(t)
                if chunk.get("choices", [{}])[0].get("finish_reason"):
                    break
            except json.JSONDecodeError:
                continue


# =============================================================================
# Code Editor
# =============================================================================

if HAS_QSCINTILLA:
    # Marker numbers for QScintilla gutter (0-31 available)
    _MARKER_ERROR = 8
    _MARKER_WARNING = 9

    class CodeEditor(QsciScintilla):
        ask_llm_requested = pyqtSignal()

        def __init__(self, parent=None, chat_panel=None):
            super().__init__(parent)
            self._current_file = None
            self._chat_panel = chat_panel
            font = QFont("Menlo", 13)
            font.setStyleHint(QFont.StyleHint.Monospace)
            self.setFont(font)
            self.setPaper(QColor(C["bg"]))
            self.setColor(QColor(C["fg"]))
            self.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
            self.setMarginWidth(0, "00000")
            self.setMarginsForegroundColor(QColor(C["fg_dim"]))
            self.setMarginsBackgroundColor(QColor(C["bg"]))
            # Margin 1: diagnostic markers (error/warning symbols)
            self.setMarginType(1, QsciScintilla.MarginType.SymbolMargin)
            self.setMarginWidth(1, 16)
            self.setMarginMarkerMask(1, (1 << _MARKER_ERROR) | (1 << _MARKER_WARNING))
            self.markerDefine(QsciScintilla.MarkerSymbol.Circle, _MARKER_ERROR)
            self.setMarkerForegroundColor(QColor(C["fg_err"]), _MARKER_ERROR)
            self.setMarkerBackgroundColor(QColor(C["fg_err"]), _MARKER_ERROR)
            self.markerDefine(QsciScintilla.MarkerSymbol.Circle, _MARKER_WARNING)
            self.setMarkerForegroundColor(QColor("#e5c07b"), _MARKER_WARNING)
            self.setMarkerBackgroundColor(QColor("#e5c07b"), _MARKER_WARNING)
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
            # Diagnostic hover tooltips via Scintilla dwell
            self._line_diagnostics = {}  # {0-indexed line: [StructuredDiagnostic, ...]}
            self.SendScintilla(QsciScintillaBase.SCI_SETMOUSEDWELLTIME, 400)
            self.SCN_DWELLSTART.connect(self._on_dwell)
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

            # ── Code Intelligence ──
            # Autocomplete via QsciAPIs
            self.setAutoCompletionSource(QsciScintilla.AutoCompletionSource.AcsAPIs)
            self.setAutoCompletionThreshold(3)
            self.setAutoCompletionCaseSensitivity(True)
            self.setAutoCompletionReplaceWord(True)
            self.setAutoCompletionUseSingle(
                QsciScintilla.AutoCompletionUseSingle.AcusNever)
            self._rebuild_api_list()

            # Calltip colors (dark theme)
            self.SendScintilla(QsciScintillaBase.SCI_CALLTIPSETBACK,
                               int(QColor("#2d2d2d").rgb() & 0xFFFFFF))
            self.SendScintilla(QsciScintillaBase.SCI_CALLTIPSETFORE,
                               int(QColor("#d4d4d4").rgb() & 0xFFFFFF))

            # Calltip trigger on ( and ) characters
            self.SCN_CHARADDED.connect(self._on_char_added)

            # Ctrl+Click indicator (blue underline)
            self._ctrl_indicator = 0
            self.SendScintilla(QsciScintillaBase.SCI_INDICSETSTYLE,
                               self._ctrl_indicator, 1)  # INDIC_PLAIN
            self.SendScintilla(QsciScintillaBase.SCI_INDICSETFORE,
                               self._ctrl_indicator,
                               int(QColor("#569cd6").rgb() & 0xFFFFFF))
            self._ctrl_held = False

            # F12 → Go to Definition
            from PyQt6.QtWidgets import QShortcut
            QShortcut(QKeySequence("F12"), self).activated.connect(
                self._goto_definition)

        # ── Code Intelligence Methods ──

        def _rebuild_api_list(self):
            """Rebuild QsciAPIs word list from keywords + project symbols."""
            apis = QsciAPIs(self.lexer())
            # C++ built-in keywords
            for kw in ("int", "float", "double", "char", "bool", "void",
                        "long", "short", "unsigned", "signed", "const",
                        "static", "extern", "volatile", "struct", "class",
                        "enum", "typedef", "union", "namespace", "template",
                        "typename", "return", "if", "else", "for", "while",
                        "do", "switch", "case", "break", "continue",
                        "default", "sizeof", "new", "delete", "true",
                        "false", "nullptr", "this", "public", "private",
                        "protected", "virtual", "override", "inline", "auto"):
                apis.add(kw)
            # Arduino/Teensy keywords
            for kw in ("setup", "loop", "pinMode", "digitalWrite",
                        "digitalRead", "analogWrite", "analogRead",
                        "Serial", "delay", "millis", "micros",
                        "attachInterrupt", "noInterrupts", "interrupts",
                        "map", "constrain", "min", "max", "abs", "pow",
                        "sqrt", "sin", "cos", "tan", "randomSeed", "random",
                        "INPUT", "OUTPUT", "INPUT_PULLUP", "HIGH", "LOW",
                        "LED_BUILTIN", "byte", "word", "boolean", "String",
                        "bitRead", "bitWrite", "bitSet", "bitClear", "bit",
                        "highByte", "lowByte", "tone", "noTone", "shiftOut",
                        "shiftIn", "pulseIn", "Wire", "SPI",
                        "digitalWriteFast", "digitalReadFast",
                        "IntervalTimer", "elapsedMillis", "elapsedMicros",
                        "AudioStream", "AudioConnection", "AudioMemory"):
                apis.add(kw)
            # Project symbols from symbol index
            if self._chat_panel and hasattr(self._chat_panel, '_symbol_index'):
                for name, entries in self._chat_panel._symbol_index.items():
                    # For functions with signatures, add with params hint
                    func_entries = [e for e in entries if e.kind == "function" and e.signature]
                    if func_entries:
                        sig = func_entries[0].signature
                        # Extract params from signature: "type name(params)" → "name(params)"
                        paren = sig.find('(')
                        if paren >= 0:
                            apis.add(f"{name}{sig[paren:]}")
                        else:
                            apis.add(name)
                    else:
                        apis.add(name)
            apis.prepare()
            self._apis = apis

        def _on_char_added(self, char_code):
            """Show/hide calltips on ( and ) characters."""
            ch = chr(char_code) if char_code > 0 else ""
            if ch == "(":
                word = self._word_before_paren()
                if not word:
                    return
                # Look up in project calltip map first, then Arduino built-ins
                tip = None
                if self._chat_panel and hasattr(self._chat_panel, '_calltip_map'):
                    tip = self._chat_panel._calltip_map.get(word)
                if not tip:
                    tip = ARDUINO_CALLTIPS.get(word)
                if tip:
                    line, col = self.getCursorPosition()
                    pos = self.positionFromLineIndex(line, col)
                    self.SendScintilla(
                        QsciScintillaBase.SCI_CALLTIPSHOW, pos,
                        tip.encode("utf-8"))
            elif ch == ")":
                self.SendScintilla(QsciScintillaBase.SCI_CALLTIPCANCEL)

        def _word_before_paren(self):
            """Get the word immediately before the cursor (before the just-typed '(')."""
            line, col = self.getCursorPosition()
            if col < 2:
                return ""
            # col-1 is where '(' was inserted, so look at col-2 for end of word
            text = self.text(line)
            end = col - 1  # position of '('
            # Skip back over the word
            start = end
            while start > 0 and (text[start - 1].isalnum() or text[start - 1] in ('_', '.')):
                start -= 1
            return text[start:end] if start < end else ""

        def _goto_definition(self):
            """Jump to the definition of the symbol under cursor."""
            if not self._chat_panel:
                return
            # Get word under cursor
            if self.hasSelectedText():
                word = self.selectedText().strip()
            else:
                line, col = self.getCursorPosition()
                word = self.wordAtLineIndex(line, col)
            if not word:
                return
            sym_index = getattr(self._chat_panel, '_symbol_index', {})
            entries = sym_index.get(word, [])
            if not entries:
                # Flash status bar
                mw = self.window()
                if mw and hasattr(mw, 'statusBar'):
                    mw.statusBar().showMessage(
                        f"No definition found for '{word}'", 3000)
                return
            editor_ref = getattr(self._chat_panel, '_editor_ref', None)
            if not editor_ref:
                return
            proj = getattr(self._chat_panel, '_project_path', None) or ""
            if len(entries) == 1:
                e = entries[0]
                abs_path = os.path.join(proj, e.rel_path) if proj else e.rel_path
                editor_ref.goto_line(abs_path, e.line)
            else:
                # Multiple matches — show popup menu
                from PyQt6.QtWidgets import QMenu
                menu = QMenu(self)
                menu.setStyleSheet(
                    f"QMenu{{background:{C['bg_input']};color:{C['fg']};"
                    f"border:1px solid {C['border_light']};border-radius:4px;padding:4px;}}"
                    f"QMenu::item{{padding:4px 16px;}}"
                    f"QMenu::item:selected{{background:{C['teal']};color:#fff;}}")
                for e in entries:
                    label = f"{e.kind} {e.name} \u2014 {e.rel_path}:{e.line}"
                    abs_path = os.path.join(proj, e.rel_path) if proj else e.rel_path
                    action = menu.addAction(label)
                    action.triggered.connect(
                        lambda checked, p=abs_path, ln=e.line: editor_ref.goto_line(p, ln))
                # Show at cursor position
                line, col = self.getCursorPosition()
                pos_x = self.SendScintilla(
                    QsciScintillaBase.SCI_POINTXFROMPOSITION, 0,
                    self.positionFromLineIndex(line, col))
                pos_y = self.SendScintilla(
                    QsciScintillaBase.SCI_POINTYFROMPOSITION, 0,
                    self.positionFromLineIndex(line, col))
                menu.exec(self.mapToGlobal(QPoint(pos_x, pos_y + 20)))

        def mousePressEvent(self, event):
            """Ctrl+Click → Go to Definition."""
            if (event.modifiers() & Qt.KeyboardModifier.ControlModifier
                    and event.button() == Qt.MouseButton.LeftButton):
                # Set cursor position at click, then go to definition
                super().mousePressEvent(event)
                self._goto_definition()
                return
            super().mousePressEvent(event)

        def mouseMoveEvent(self, event):
            """Ctrl+hover: underline word under mouse with indicator."""
            ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            if ctrl != self._ctrl_held:
                self._ctrl_held = ctrl
                if ctrl:
                    self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
                else:
                    self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
                    # Clear all indicators
                    length = self.length()
                    self.SendScintilla(
                        QsciScintillaBase.SCI_SETINDICATORCURRENT,
                        self._ctrl_indicator)
                    self.SendScintilla(
                        QsciScintillaBase.SCI_INDICATORCLEARRANGE, 0, length)
            if ctrl:
                # Underline word under mouse
                pos = self.SendScintilla(
                    QsciScintillaBase.SCI_POSITIONFROMPOINT,
                    int(event.position().x()), int(event.position().y()))
                if pos >= 0:
                    word_start = self.SendScintilla(
                        QsciScintillaBase.SCI_WORDSTARTPOSITION, pos, True)
                    word_end = self.SendScintilla(
                        QsciScintillaBase.SCI_WORDENDPOSITION, pos, True)
                    if word_end > word_start:
                        length = self.length()
                        self.SendScintilla(
                            QsciScintillaBase.SCI_SETINDICATORCURRENT,
                            self._ctrl_indicator)
                        self.SendScintilla(
                            QsciScintillaBase.SCI_INDICATORCLEARRANGE,
                            0, length)
                        self.SendScintilla(
                            QsciScintillaBase.SCI_INDICATORFILLRANGE,
                            word_start, word_end - word_start)
            super().mouseMoveEvent(event)

        def _show_context_menu(self, pos):
            from PyQt6.QtWidgets import QMenu
            menu = QMenu(self)
            menu.setStyleSheet(
                f"QMenu{{background:{C['bg_input']};color:{C['fg']};"
                f"border:1px solid {C['border_light']};border-radius:4px;padding:4px;}}"
                f"QMenu::item{{padding:4px 20px;border-radius:2px;}}"
                f"QMenu::item:selected{{background:{C['teal']};color:#fff;}}"
                f"QMenu::separator{{height:1px;background:{C['border_light']};"
                f"margin:4px 8px;}}")
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
            if self.hasSelectedText():
                menu.addSeparator()
                a_llm = QAction("Ask LLM", self)
                a_llm.triggered.connect(self.ask_llm_requested.emit)
                menu.addAction(a_llm)
            menu.exec(self.mapToGlobal(pos))

        def clear_diagnostics(self):
            """Remove all error/warning markers and tooltip data."""
            self.markerDeleteAll(_MARKER_ERROR)
            self.markerDeleteAll(_MARKER_WARNING)
            self._line_diagnostics.clear()

        def set_diagnostics(self, diags):
            """Set gutter markers and tooltip data from StructuredDiagnostic list.
            Lines are 1-indexed in diagnostics, 0-indexed in QScintilla."""
            self.clear_diagnostics()
            for d in diags:
                line_0 = d.line - 1
                if line_0 < 0:
                    continue
                self._line_diagnostics.setdefault(line_0, []).append(d)
                marker = _MARKER_ERROR if d.severity == "error" else _MARKER_WARNING
                self.markerAdd(line_0, marker)

        def _on_dwell(self, pos, x, y):
            """Show tooltip with diagnostic messages when hovering over a marked line."""
            if pos < 0 or not self._line_diagnostics:
                return
            line = self.SendScintilla(QsciScintillaBase.SCI_LINEFROMPOSITION, pos)
            diags = self._line_diagnostics.get(line)
            if not diags:
                return
            parts = []
            for d in diags:
                sev = d.severity.upper()
                parts.append(f"[{sev}] {d.message}")
            tip = "\n".join(parts)
            from PyQt6.QtWidgets import QToolTip
            QToolTip.showText(self.mapToGlobal(QPoint(x, y)), tip, self)

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
        ask_llm_requested = pyqtSignal()

        def __init__(self, parent=None, chat_panel=None):
            super().__init__(parent)
            self._current_file = None
            font = QFont("Menlo", 13)
            self.setFont(font)
            self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self._show_context_menu)

        def _show_context_menu(self, pos):
            from PyQt6.QtWidgets import QMenu
            menu = self.createStandardContextMenu()
            menu.setStyleSheet(
                f"QMenu{{background:{C['bg_input']};color:{C['fg']};"
                f"border:1px solid {C['border_light']};border-radius:4px;padding:4px;}}"
                f"QMenu::item{{padding:4px 20px;border-radius:2px;}}"
                f"QMenu::item:selected{{background:{C['teal']};color:#fff;}}"
                f"QMenu::separator{{height:1px;background:{C['border_light']};"
                f"margin:4px 8px;}}")
            if self.textCursor().hasSelection():
                menu.addSeparator()
                a_llm = QAction("Ask LLM", self)
                a_llm.triggered.connect(self.ask_llm_requested.emit)
                menu.addAction(a_llm)
            menu.exec(self.mapToGlobal(pos))

        def clear_diagnostics(self): pass  # No gutter in QPlainTextEdit
        def set_diagnostics(self, diags): pass

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
    ask_llm_requested = pyqtSignal()        # propagated from CodeEditor
    editor_opened = pyqtSignal(object)      # emits CodeEditor widget when a new tab is created

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
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_changed)
        layout.addWidget(self.tabs)

        self._editors = {}
        self._chat_panel = None  # set by MainWindow after chat_panel is created

    def open_file(self, filepath):
        filepath = os.path.abspath(filepath)
        if filepath in self._editors:
            self.tabs.setCurrentWidget(self._editors[filepath])
            return True
        editor = CodeEditor(chat_panel=self._chat_panel)
        editor.ask_llm_requested.connect(self.ask_llm_requested.emit)
        if editor.load_file(filepath):
            self._editors[filepath] = editor
            idx = self.tabs.addTab(editor, os.path.basename(filepath))
            self.tabs.setCurrentIndex(idx)
            self.file_changed.emit(filepath)
            self.editor_opened.emit(editor)
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
        if e and hasattr(e, 'save_file'):
            result = e.save_file()
            if result:
                if hasattr(e, 'setModified'):
                    e.setModified(False)
                fp = e.current_file if hasattr(e, 'current_file') else None
                if fp:
                    self._mark_tab_clean(fp)
            return result
        return False

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

    def set_file_content(self, filepath, content, save_to_disk=True):
        """Set content of an open file by path. Updates editor buffer.
        Writes to disk only if save_to_disk=True.  Returns True if found."""
        if filepath in self._editors:
            ed = self._editors[filepath]
            if hasattr(ed, 'setText'): ed.setText(content)
            else: ed.setPlainText(content)
            if save_to_disk:
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    if hasattr(ed, 'setModified'):
                        ed.setModified(False)
                except OSError:
                    pass
            else:
                # Mark as modified so the dirty indicator shows
                if hasattr(ed, 'setModified'):
                    ed.setModified(True)
                self._mark_tab_dirty(filepath)
            return True
        return False

    def _mark_tab_dirty(self, filepath):
        """Add a • dirty indicator to the tab title."""
        if filepath not in self._editors:
            return
        ed = self._editors[filepath]
        idx = self.tabs.indexOf(ed)
        if idx < 0:
            return
        title = self.tabs.tabText(idx)
        if not title.endswith(' •'):
            self.tabs.setTabText(idx, title + ' •')

    def _mark_tab_clean(self, filepath):
        """Remove the • dirty indicator from the tab title."""
        if filepath not in self._editors:
            return
        ed = self._editors[filepath]
        idx = self.tabs.indexOf(ed)
        if idx < 0:
            return
        title = self.tabs.tabText(idx)
        if title.endswith(' •'):
            self.tabs.setTabText(idx, title[:-2])

    def save_all(self):
        """Save all modified editor buffers to disk."""
        for fp, ed in self._editors.items():
            is_modified = (ed.isModified() if hasattr(ed, 'isModified')
                           else False)
            if is_modified:
                if hasattr(ed, 'save_file'):
                    ed.save_file()
                if hasattr(ed, 'setModified'):
                    ed.setModified(False)
                self._mark_tab_clean(fp)

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

    def apply_diagnostics(self, diagnostics, project_path=""):
        """Apply gutter markers to open editors based on StructuredDiagnostic list.
        Groups diagnostics by file path, resolves to open editors."""
        # Group diagnostics by absolute file path
        by_file = {}
        for d in diagnostics:
            if d.file == "<linker>" or d.line == 0:
                continue
            if os.path.isabs(d.file):
                abs_path = d.file
            elif project_path:
                abs_path = os.path.join(project_path, d.file)
            else:
                abs_path = os.path.abspath(d.file)
            abs_path = os.path.normpath(abs_path)
            by_file.setdefault(abs_path, []).append(d)
        # Apply to open editors
        for fp, ed in self._editors.items():
            norm_fp = os.path.normpath(fp)
            if norm_fp in by_file:
                ed.set_diagnostics(by_file[norm_fp])

    def clear_diagnostics(self):
        """Clear all diagnostic markers from all open editors."""
        for ed in self._editors.values():
            ed.clear_diagnostics()

    def goto_line(self, filepath, line):
        """Open file (if not already) and scroll to line (1-indexed)."""
        filepath = os.path.abspath(filepath)
        if filepath not in self._editors:
            if not self.open_file(filepath):
                return
        self.tabs.setCurrentWidget(self._editors[filepath])
        ed = self._editors[filepath]
        if HAS_QSCINTILLA:
            ed.setCursorPosition(max(0, line - 1), 0)
            ed.ensureLineVisible(max(0, line - 1))
        else:
            cursor = ed.textCursor()
            block = ed.document().findBlockByLineNumber(max(0, line - 1))
            cursor.setPosition(block.position())
            ed.setTextCursor(cursor)
            ed.ensureCursorVisible()

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

    @staticmethod
    def _flat_folder_icon():
        """Create a flat folder icon matching the dark theme."""
        if not hasattr(FileBrowser, '_cached_folder_icon'):
            px = QPixmap(16, 16)
            px.fill(QColor(0, 0, 0, 0))
            p = QPainter(px)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            # Tab portion
            p.setBrush(QColor(C['teal']))
            p.drawRoundedRect(1, 2, 6, 3, 1, 1)
            # Body
            p.drawRoundedRect(1, 4, 14, 10, 2, 2)
            p.end()
            FileBrowser._cached_folder_icon = QIcon(px)
        return FileBrowser._cached_folder_icon

    def _populate(self, parent_item, dir_path):
        """Recursively add files and folders to the tree model."""
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return
        # Folders first, then files
        dirs = [e for e in entries if os.path.isdir(os.path.join(dir_path, e)) and not e.startswith('.')]
        files = [e for e in entries if os.path.isfile(os.path.join(dir_path, e)) and not e.startswith('.')]
        folder_icon = self._flat_folder_icon()
        for d in dirs:
            item = QStandardItem(d)
            item.setIcon(folder_icon)
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
        default_dir = self._current_focus_path or self._project_path
        if not default_dir or not os.path.isdir(default_dir):
            default_dir = os.path.expanduser("~/Documents/Arduino")
        os.makedirs(default_dir, exist_ok=True)
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Create New Sketch",
            os.path.join(default_dir, "new_sketch"),
            "Arduino Sketch (*.ino)")
        if not filepath:
            return
        if not filepath.endswith(".ino"):
            filepath += ".ino"
        sketch_name = os.path.splitext(os.path.basename(filepath))[0]
        chosen_dir = os.path.dirname(filepath)
        sketch_dir = os.path.join(chosen_dir, sketch_name)
        ino_file = os.path.join(sketch_dir, f"{sketch_name}.ino")
        if os.path.exists(sketch_dir):
            QMessageBox.warning(self, "Exists",
                                f"Folder '{sketch_name}' already exists.")
            return
        try:
            os.makedirs(sketch_dir, exist_ok=True)
            with open(ino_file, "w") as f:
                f.write(f"// {sketch_name}.ino\n\nvoid setup() {{\n\n}}\n\nvoid loop() {{\n\n}}\n")
            self.file_browser._refresh()
            self._refresh_parent_context(self._current_focus_path)
            self.file_requested.emit(ino_file)
        except OSError as e:
            QMessageBox.warning(self, "Error", str(e))


# =============================================================================
# Library Manager Panel
# =============================================================================

class LibraryManagerPanel(QWidget):
    """Search, install, update, and remove Arduino libraries via arduino-cli."""
    include_requested = pyqtSignal(str)  # library name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._installed_libs = []  # list of dicts from arduino-cli
        self._search_results = []
        self._filter_mode = 0  # 0=installed, 1=search, 2=updatable
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header, _, _ = _make_panel_header("Library Manager")
        layout.addWidget(header)

        body = QWidget()
        body.setStyleSheet(f"background:{C['bg_dark']};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 12, 16, 12)
        bl.setSpacing(10)

        # Search row
        search_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search libraries...")
        self._search_input.setStyleSheet(SETTINGS_INPUT)
        self._search_input.returnPressed.connect(self._search)
        search_row.addWidget(self._search_input, stretch=1)
        search_btn = QPushButton("Search")
        search_btn.setStyleSheet(BTN_SM_PRIMARY)
        search_btn.clicked.connect(self._search)
        search_row.addWidget(search_btn)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(BTN_SM_GHOST)
        refresh_btn.clicked.connect(self._refresh_installed)
        search_row.addWidget(refresh_btn)
        bl.addLayout(search_row)

        # Filter combo
        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["Installed", "Search Results", "Updatable"])
        self._filter_combo.setStyleSheet(SETTINGS_COMBO)
        self._filter_combo.currentIndexChanged.connect(self._apply_filter)
        bl.addWidget(self._filter_combo)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Library", "Version", "Status"])
        self._table.horizontalHeader().setStyleSheet(SETTINGS_TBL_HDR)
        self._table.setStyleSheet(SETTINGS_TABLE)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(1, 100)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(2, 120)
        bl.addWidget(self._table, stretch=1)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        install_btn = QPushButton("Install")
        install_btn.setStyleSheet(BTN_SM_PRIMARY)
        install_btn.clicked.connect(self._install)
        btn_row.addWidget(install_btn)
        update_btn = QPushButton("Update")
        update_btn.setStyleSheet(BTN_SM_SECONDARY)
        update_btn.clicked.connect(self._update)
        btn_row.addWidget(update_btn)
        remove_btn = QPushButton("Remove")
        remove_btn.setStyleSheet(BTN_SM_DANGER)
        remove_btn.clicked.connect(self._remove)
        btn_row.addWidget(remove_btn)
        include_btn = QPushButton("Include in Sketch")
        include_btn.setStyleSheet(BTN_SM_GHOST)
        include_btn.clicked.connect(self._include_library)
        btn_row.addWidget(include_btn)
        btn_row.addStretch()
        bl.addLayout(btn_row)

        # Status
        self._status = QLabel("")
        self._status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        bl.addWidget(self._status)

        layout.addWidget(body, stretch=1)
        QTimer.singleShot(500, self._refresh_installed)

    def _selected_name(self):
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.text() if item else None

    def _refresh_installed(self):
        self._status.setText("Loading installed libraries...")
        self._status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")

        def go():
            try:
                r = subprocess.run(
                    ["arduino-cli", "lib", "list", "--format", "json"],
                    capture_output=True, text=True, timeout=30)
                data = json.loads(r.stdout) if r.stdout.strip() else []
                if isinstance(data, dict):
                    data = data.get("installed_libraries", [])
                QTimer.singleShot(0, lambda: self._on_installed(data))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_error(str(e)))
        threading.Thread(target=go, daemon=True).start()

    def _on_installed(self, data):
        self._installed_libs = data
        self._filter_combo.setCurrentIndex(0)
        self._show_installed()

    def _on_error(self, msg):
        self._status.setText(f"Error: {msg}")
        self._status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _show_installed(self):
        self._table.setRowCount(0)
        for item in self._installed_libs:
            lib = item.get("library", item)
            name = lib.get("name", "?")
            ver = lib.get("version", "?")
            release = item.get("release", {})
            latest = release.get("version", ver)
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(name))
            self._table.setItem(row, 1, QTableWidgetItem(ver))
            if latest and latest != ver:
                st = QTableWidgetItem(f"Update → {latest}")
                st.setForeground(QColor(C['fg_warn']))
            else:
                st = QTableWidgetItem("Installed")
                st.setForeground(QColor(C['fg_ok']))
            self._table.setItem(row, 2, st)
        self._status.setText(f"{self._table.rowCount()} installed libraries")
        self._status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")

    def _show_search_results(self):
        self._table.setRowCount(0)
        installed_names = set()
        for item in self._installed_libs:
            lib = item.get("library", item)
            installed_names.add(lib.get("name", ""))
        for lib in self._search_results:
            name = lib.get("name", "?")
            ver = lib.get("latest", lib.get("version", "?"))
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(name))
            self._table.setItem(row, 1, QTableWidgetItem(str(ver)))
            if name in installed_names:
                st = QTableWidgetItem("Installed")
                st.setForeground(QColor(C['fg_ok']))
            else:
                st = QTableWidgetItem("Available")
                st.setForeground(QColor(C['fg_dim']))
            self._table.setItem(row, 2, st)
        self._status.setText(f"{self._table.rowCount()} results")
        self._status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")

    def _show_updatable(self):
        self._table.setRowCount(0)
        for item in self._installed_libs:
            lib = item.get("library", item)
            name = lib.get("name", "?")
            ver = lib.get("version", "?")
            release = item.get("release", {})
            latest = release.get("version", ver)
            if latest and latest != ver:
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, 0, QTableWidgetItem(name))
                self._table.setItem(row, 1, QTableWidgetItem(ver))
                st = QTableWidgetItem(f"Update → {latest}")
                st.setForeground(QColor(C['fg_warn']))
                self._table.setItem(row, 2, st)
        self._status.setText(f"{self._table.rowCount()} updatable")
        self._status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")

    def _apply_filter(self, idx):
        self._filter_mode = idx
        if idx == 0:
            self._show_installed()
        elif idx == 1:
            self._show_search_results()
        elif idx == 2:
            self._show_updatable()

    def _search(self):
        query = self._search_input.text().strip()
        if not query:
            return
        self._status.setText(f"Searching '{query}'...")
        self._status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")

        def go():
            try:
                r = subprocess.run(
                    ["arduino-cli", "lib", "search", query, "--format", "json"],
                    capture_output=True, text=True, timeout=30)
                data = json.loads(r.stdout) if r.stdout.strip() else {}
                libs = data.get("libraries", data) if isinstance(data, dict) else data
                if not isinstance(libs, list):
                    libs = []
                QTimer.singleShot(0, lambda: self._on_search(libs))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_error(str(e)))
        threading.Thread(target=go, daemon=True).start()

    def _on_search(self, libs):
        self._search_results = libs
        self._filter_combo.setCurrentIndex(1)

    def _install(self):
        name = self._selected_name()
        if not name:
            return
        self._status.setText(f"Installing {name}...")
        self._status.setStyleSheet(f"color:{C['fg_link']};{FONT_SMALL}")

        def go():
            try:
                r = subprocess.run(
                    ["arduino-cli", "lib", "install", name],
                    capture_output=True, text=True, timeout=120)
                if r.returncode == 0:
                    QTimer.singleShot(0, lambda: self._on_action_done(
                        f"Installed {name}", True))
                else:
                    QTimer.singleShot(0, lambda: self._on_action_done(
                        r.stderr.strip() or "Install failed", False))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_action_done(str(e), False))
        threading.Thread(target=go, daemon=True).start()

    def _update(self):
        self._install()  # installing latest = update

    def _remove(self):
        name = self._selected_name()
        if not name:
            return
        reply = QMessageBox.question(
            self, "Remove Library",
            f"Remove library '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._status.setText(f"Removing {name}...")
        self._status.setStyleSheet(f"color:{C['fg_link']};{FONT_SMALL}")

        def go():
            try:
                r = subprocess.run(
                    ["arduino-cli", "lib", "uninstall", name],
                    capture_output=True, text=True, timeout=60)
                if r.returncode == 0:
                    QTimer.singleShot(0, lambda: self._on_action_done(
                        f"Removed {name}", True))
                else:
                    QTimer.singleShot(0, lambda: self._on_action_done(
                        r.stderr.strip() or "Remove failed", False))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_action_done(str(e), False))
        threading.Thread(target=go, daemon=True).start()

    def _on_action_done(self, msg, success):
        self._status.setText(msg)
        self._status.setStyleSheet(
            f"color:{C['fg_ok'] if success else C['fg_err']};{FONT_SMALL}")
        if success:
            self._refresh_installed()

    def _include_library(self):
        name = self._selected_name()
        if name:
            self.include_requested.emit(name)


# =============================================================================
# Board Manager Panel
# =============================================================================

class BoardManagerPanel(QWidget):
    """Search, install, update, and remove platform cores via arduino-cli."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._installed_cores = []
        self._search_results = []
        self._filter_mode = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header, _, _ = _make_panel_header("Board Manager")
        layout.addWidget(header)

        body = QWidget()
        body.setStyleSheet(f"background:{C['bg_dark']};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 12, 16, 12)
        bl.setSpacing(10)

        # Search + index row
        search_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search boards/platforms...")
        self._search_input.setStyleSheet(SETTINGS_INPUT)
        self._search_input.returnPressed.connect(self._search)
        search_row.addWidget(self._search_input, stretch=1)
        search_btn = QPushButton("Search")
        search_btn.setStyleSheet(BTN_SM_PRIMARY)
        search_btn.clicked.connect(self._search)
        search_row.addWidget(search_btn)
        index_btn = QPushButton("Update Index")
        index_btn.setStyleSheet(BTN_SM_GHOST)
        index_btn.clicked.connect(self._update_index)
        search_row.addWidget(index_btn)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(BTN_SM_GHOST)
        refresh_btn.clicked.connect(self._refresh_installed)
        search_row.addWidget(refresh_btn)
        bl.addLayout(search_row)

        # Filter combo
        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["Installed", "Search Results", "Updatable"])
        self._filter_combo.setStyleSheet(SETTINGS_COMBO)
        self._filter_combo.currentIndexChanged.connect(self._apply_filter)
        bl.addWidget(self._filter_combo)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(
            ["Platform", "ID", "Version", "Status"])
        self._table.horizontalHeader().setStyleSheet(SETTINGS_TBL_HDR)
        self._table.setStyleSheet(SETTINGS_TABLE)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(1, 140)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(2, 80)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(3, 120)
        bl.addWidget(self._table, stretch=1)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        install_btn = QPushButton("Install")
        install_btn.setStyleSheet(BTN_SM_PRIMARY)
        install_btn.clicked.connect(self._install)
        btn_row.addWidget(install_btn)
        update_btn = QPushButton("Update")
        update_btn.setStyleSheet(BTN_SM_SECONDARY)
        update_btn.clicked.connect(self._update)
        btn_row.addWidget(update_btn)
        remove_btn = QPushButton("Remove")
        remove_btn.setStyleSheet(BTN_SM_DANGER)
        remove_btn.clicked.connect(self._remove)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        bl.addLayout(btn_row)

        # Status
        self._status = QLabel("")
        self._status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        bl.addWidget(self._status)

        layout.addWidget(body, stretch=1)
        QTimer.singleShot(500, self._refresh_installed)

    def _selected_id(self):
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 1)
        return item.text() if item else None

    def _refresh_installed(self):
        self._status.setText("Loading installed platforms...")
        self._status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")

        def go():
            try:
                r = subprocess.run(
                    ["arduino-cli", "core", "list", "--format", "json"],
                    capture_output=True, text=True, timeout=30)
                data = json.loads(r.stdout) if r.stdout.strip() else []
                if isinstance(data, dict):
                    data = data.get("platforms", [])
                QTimer.singleShot(0, lambda: self._on_installed(data))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_error(str(e)))
        threading.Thread(target=go, daemon=True).start()

    def _on_installed(self, data):
        self._installed_cores = data
        self._filter_combo.setCurrentIndex(0)
        self._show_installed()

    def _on_error(self, msg):
        self._status.setText(f"Error: {msg}")
        self._status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _show_installed(self):
        self._table.setRowCount(0)
        for item in self._installed_cores:
            name = item.get("name", item.get("Name", "?"))
            pid = item.get("id", item.get("ID", "?"))
            ver = item.get("installed", item.get("installed_version",
                           item.get("Installed", "?")))
            latest = item.get("latest", item.get("latest_version",
                              item.get("Latest", ver)))
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(str(name)))
            self._table.setItem(row, 1, QTableWidgetItem(str(pid)))
            self._table.setItem(row, 2, QTableWidgetItem(str(ver)))
            if latest and str(latest) != str(ver):
                st = QTableWidgetItem(f"Update → {latest}")
                st.setForeground(QColor(C['fg_warn']))
            else:
                st = QTableWidgetItem("Installed")
                st.setForeground(QColor(C['fg_ok']))
            self._table.setItem(row, 3, st)
        self._status.setText(f"{self._table.rowCount()} installed platforms")
        self._status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")

    def _show_search_results(self):
        self._table.setRowCount(0)
        installed_ids = {item.get("id", item.get("ID", ""))
                         for item in self._installed_cores}
        for item in self._search_results:
            name = item.get("name", item.get("Name", "?"))
            pid = item.get("id", item.get("ID", "?"))
            ver = item.get("latest", item.get("latest_version",
                           item.get("Latest", "?")))
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(str(name)))
            self._table.setItem(row, 1, QTableWidgetItem(str(pid)))
            self._table.setItem(row, 2, QTableWidgetItem(str(ver)))
            if pid in installed_ids:
                st = QTableWidgetItem("Installed")
                st.setForeground(QColor(C['fg_ok']))
            else:
                st = QTableWidgetItem("Available")
                st.setForeground(QColor(C['fg_dim']))
            self._table.setItem(row, 3, st)
        self._status.setText(f"{self._table.rowCount()} results")
        self._status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")

    def _show_updatable(self):
        self._table.setRowCount(0)
        for item in self._installed_cores:
            name = item.get("name", item.get("Name", "?"))
            pid = item.get("id", item.get("ID", "?"))
            ver = item.get("installed", item.get("installed_version",
                           item.get("Installed", "?")))
            latest = item.get("latest", item.get("latest_version",
                              item.get("Latest", ver)))
            if latest and str(latest) != str(ver):
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, 0, QTableWidgetItem(str(name)))
                self._table.setItem(row, 1, QTableWidgetItem(str(pid)))
                self._table.setItem(row, 2, QTableWidgetItem(str(ver)))
                st = QTableWidgetItem(f"Update → {latest}")
                st.setForeground(QColor(C['fg_warn']))
                self._table.setItem(row, 3, st)
        self._status.setText(f"{self._table.rowCount()} updatable")
        self._status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")

    def _apply_filter(self, idx):
        self._filter_mode = idx
        if idx == 0:
            self._show_installed()
        elif idx == 1:
            self._show_search_results()
        elif idx == 2:
            self._show_updatable()

    def _search(self):
        query = self._search_input.text().strip()
        if not query:
            return
        self._status.setText(f"Searching '{query}'...")
        self._status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")

        def go():
            try:
                r = subprocess.run(
                    ["arduino-cli", "core", "search", query,
                     "--format", "json"],
                    capture_output=True, text=True, timeout=30)
                data = json.loads(r.stdout) if r.stdout.strip() else {}
                platforms = data.get("platforms", data) if isinstance(
                    data, dict) else data
                if not isinstance(platforms, list):
                    platforms = []
                QTimer.singleShot(0, lambda: self._on_search(platforms))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_error(str(e)))
        threading.Thread(target=go, daemon=True).start()

    def _on_search(self, platforms):
        self._search_results = platforms
        self._filter_combo.setCurrentIndex(1)

    def _install(self):
        pid = self._selected_id()
        if not pid:
            return
        self._status.setText(f"Installing {pid}...")
        self._status.setStyleSheet(f"color:{C['fg_link']};{FONT_SMALL}")

        def go():
            try:
                r = subprocess.run(
                    ["arduino-cli", "core", "install", pid],
                    capture_output=True, text=True, timeout=300)
                if r.returncode == 0:
                    QTimer.singleShot(0, lambda: self._on_action_done(
                        f"Installed {pid}", True))
                else:
                    QTimer.singleShot(0, lambda: self._on_action_done(
                        r.stderr.strip() or "Install failed", False))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_action_done(
                    str(e), False))
        threading.Thread(target=go, daemon=True).start()

    def _update(self):
        self._install()

    def _remove(self):
        pid = self._selected_id()
        if not pid:
            return
        reply = QMessageBox.question(
            self, "Remove Platform",
            f"Remove platform '{pid}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._status.setText(f"Removing {pid}...")
        self._status.setStyleSheet(f"color:{C['fg_link']};{FONT_SMALL}")

        def go():
            try:
                r = subprocess.run(
                    ["arduino-cli", "core", "uninstall", pid],
                    capture_output=True, text=True, timeout=60)
                if r.returncode == 0:
                    QTimer.singleShot(0, lambda: self._on_action_done(
                        f"Removed {pid}", True))
                else:
                    QTimer.singleShot(0, lambda: self._on_action_done(
                        r.stderr.strip() or "Remove failed", False))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_action_done(
                    str(e), False))
        threading.Thread(target=go, daemon=True).start()

    def _on_action_done(self, msg, success):
        self._status.setText(msg)
        self._status.setStyleSheet(
            f"color:{C['fg_ok'] if success else C['fg_err']};{FONT_SMALL}")
        if success:
            self._refresh_installed()

    def _update_index(self):
        self._status.setText("Updating board index...")
        self._status.setStyleSheet(f"color:{C['fg_link']};{FONT_SMALL}")

        def go():
            try:
                r = subprocess.run(
                    ["arduino-cli", "core", "update-index"],
                    capture_output=True, text=True, timeout=60)
                if r.returncode == 0:
                    QTimer.singleShot(0, lambda: self._on_action_done(
                        "Board index updated", True))
                else:
                    QTimer.singleShot(0, lambda: self._on_action_done(
                        r.stderr.strip() or "Update failed", False))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_action_done(
                    str(e), False))
        threading.Thread(target=go, daemon=True).start()


# =============================================================================
# Serial Plotter
# =============================================================================

PLOT_COLORS = ["#50fa7b", "#ff79c6", "#8be9fd", "#ffb86c", "#bd93f9",
               "#f1fa8c", "#ff5555", "#6272a4"]


class PlotWidget(QWidget):
    """Custom QPainter-based line chart widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._data = []          # list of deques, one per channel
        self._channel_names = []
        self._auto_scale = True
        self._y_min = 0.0
        self._y_max = 100.0
        self._mouse_pos = None   # for crosshair
        self._margin_left = 60
        self._margin_right = 16
        self._margin_top = 16
        self._margin_bottom = 30

    def set_data(self, data, names):
        self._data = data
        self._channel_names = names

    def set_y_range(self, auto, y_min=0.0, y_max=100.0):
        self._auto_scale = auto
        self._y_min = y_min
        self._y_max = y_max

    def mouseMoveEvent(self, event):
        self._mouse_pos = event.pos()
        self.update()

    def leaveEvent(self, event):
        self._mouse_pos = None
        self.update()

    def paintEvent(self, event):
        from collections import deque
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(C['bg_dark']))

        ml, mr, mt, mb = self._margin_left, self._margin_right, self._margin_top, self._margin_bottom
        plot_w = w - ml - mr
        plot_h = h - mt - mb
        if plot_w < 10 or plot_h < 10:
            p.end()
            return

        # Compute Y range
        y_min, y_max = self._y_min, self._y_max
        if self._auto_scale and self._data:
            all_vals = []
            for d in self._data:
                all_vals.extend(d)
            if all_vals:
                y_min = min(all_vals)
                y_max = max(all_vals)
                margin = (y_max - y_min) * 0.1 or 1.0
                y_min -= margin
                y_max += margin
            else:
                y_min, y_max = 0.0, 100.0
        if y_max == y_min:
            y_max = y_min + 1.0

        max_samples = max((len(d) for d in self._data), default=0)

        # Grid lines
        grid_pen = QPen(QColor(C['border']))
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        p.setPen(grid_pen)
        n_grid_y = 5
        for i in range(n_grid_y + 1):
            gy = mt + plot_h - (i / n_grid_y) * plot_h
            p.drawLine(int(ml), int(gy), int(ml + plot_w), int(gy))
        n_grid_x = min(5, max_samples - 1) if max_samples > 1 else 0
        if n_grid_x > 0:
            for i in range(n_grid_x + 1):
                gx = ml + (i / n_grid_x) * plot_w
                p.drawLine(int(gx), int(mt), int(gx), int(mt + plot_h))

        # Axis labels
        label_font = QFont("monospace", 9)
        p.setFont(label_font)
        p.setPen(QColor(C['fg_muted']))
        for i in range(n_grid_y + 1):
            val = y_min + (i / n_grid_y) * (y_max - y_min)
            gy = mt + plot_h - (i / n_grid_y) * plot_h
            p.drawText(2, int(gy - 6), ml - 6, 12,
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{val:.1f}")
        # X-axis: sample numbers
        if max_samples > 0 and n_grid_x > 0:
            for i in range(n_grid_x + 1):
                gx = ml + (i / n_grid_x) * plot_w
                sample_idx = int(i / n_grid_x * (max_samples - 1)) if max_samples > 1 else 0
                p.drawText(int(gx - 20), int(mt + plot_h + 4), 40, 16,
                           Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                           str(sample_idx))

        # Draw data lines
        for ch_idx, d in enumerate(self._data):
            if len(d) < 2:
                continue
            color = QColor(PLOT_COLORS[ch_idx % len(PLOT_COLORS)])
            pen = QPen(color, 2)
            p.setPen(pen)
            points = []
            data_list = list(d)
            for i, val in enumerate(data_list):
                x = ml + (i / (max_samples - 1)) * plot_w if max_samples > 1 else ml
                y = mt + plot_h - ((val - y_min) / (y_max - y_min)) * plot_h
                points.append(QPointF(x, y))
            if len(points) >= 2:
                p.drawPolyline(QPolygonF(points))

        # Crosshair + tooltip
        if self._mouse_pos and self._data and max_samples > 1:
            mx, my = self._mouse_pos.x(), self._mouse_pos.y()
            if ml <= mx <= ml + plot_w and mt <= my <= mt + plot_h:
                cross_pen = QPen(QColor(C['fg_dim']))
                cross_pen.setStyle(Qt.PenStyle.DashLine)
                p.setPen(cross_pen)
                p.drawLine(mx, mt, mx, mt + plot_h)
                p.drawLine(ml, my, ml + plot_w, my)
                # Determine sample index
                frac = (mx - ml) / plot_w
                sample_idx = int(frac * (max_samples - 1))
                sample_idx = max(0, min(sample_idx, max_samples - 1))
                # Build tooltip
                tip_lines = [f"Sample {sample_idx}"]
                for ch_idx, d in enumerate(self._data):
                    data_list = list(d)
                    if sample_idx < len(data_list):
                        name = self._channel_names[ch_idx] if ch_idx < len(self._channel_names) else f"ch{ch_idx}"
                        tip_lines.append(f"  {name}: {data_list[sample_idx]:.2f}")
                tip_text = "\n".join(tip_lines)
                # Draw tooltip box
                tip_font = QFont("monospace", 9)
                p.setFont(tip_font)
                fm = p.fontMetrics()
                tip_w = max(fm.horizontalAdvance(l) for l in tip_lines) + 12
                tip_h = fm.height() * len(tip_lines) + 8
                tx = min(mx + 10, w - tip_w - 4)
                ty = max(my - tip_h - 10, mt)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(C['bg']))
                p.drawRect(tx, ty, tip_w, tip_h)
                p.setPen(QColor(C['fg']))
                p.drawText(tx + 6, ty + 4, tip_w - 12, tip_h - 8,
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                           tip_text)

        # Legend (top-right)
        if self._channel_names:
            legend_font = QFont("monospace", 9)
            p.setFont(legend_font)
            fm = p.fontMetrics()
            lx = ml + plot_w - 10
            ly = mt + 6
            for ch_idx, name in enumerate(self._channel_names):
                color = QColor(PLOT_COLORS[ch_idx % len(PLOT_COLORS)])
                tw = fm.horizontalAdvance(name)
                rx = lx - tw - 14
                # Background
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(C['bg']))
                p.drawRect(rx - 2, ly - 2, tw + 18, fm.height() + 4)
                # Color dot
                p.setBrush(color)
                p.drawEllipse(rx, ly + 3, 8, 8)
                # Label
                p.setPen(QColor(C['fg_dim']))
                p.drawText(rx + 12, ly, tw + 4, fm.height(),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           name)
                ly += fm.height() + 4

        p.end()


class SerialPlotterPanel(QWidget):
    """Real-time serial plotter with QPainter line charts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from collections import deque
        self._deque_cls = deque
        self._data = []            # list of deques
        self._channel_count = 0
        self._channel_names = []
        self._sample_count = 0
        self._paused = False
        self._dirty = False
        self._header_detected = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header, _, hl = _make_panel_header("SERIAL PLOTTER")
        layout.addWidget(header)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet(
            f"background:{C['bg']};border-bottom:1px solid {C['border']};")
        toolbar.setFixedHeight(36)
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(8, 2, 8, 2)
        tb.setSpacing(6)

        self._ch_label = QLabel("Channels: 0")
        self._ch_label.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        tb.addWidget(self._ch_label)

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setCheckable(True)
        self._pause_btn.setStyleSheet(BTN_SM_SECONDARY)
        self._pause_btn.clicked.connect(self._toggle_pause)
        tb.addWidget(self._pause_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(BTN_SM_GHOST)
        clear_btn.clicked.connect(self._clear)
        tb.addWidget(clear_btn)

        tb.addWidget(QLabel("|"))

        self._auto_scale_btn = QPushButton("Auto Y")
        self._auto_scale_btn.setCheckable(True)
        self._auto_scale_btn.setChecked(True)
        self._auto_scale_btn.setStyleSheet(BTN_SM_SECONDARY)
        self._auto_scale_btn.clicked.connect(self._on_auto_scale_changed)
        tb.addWidget(self._auto_scale_btn)

        ymin_lbl = QLabel("Min:")
        ymin_lbl.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        tb.addWidget(ymin_lbl)
        self._y_min_spin = self._make_double_spin(-1e6, 1e6, 0.0)
        self._y_min_spin.setEnabled(False)
        tb.addWidget(self._y_min_spin)

        ymax_lbl = QLabel("Max:")
        ymax_lbl.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        tb.addWidget(ymax_lbl)
        self._y_max_spin = self._make_double_spin(-1e6, 1e6, 100.0)
        self._y_max_spin.setEnabled(False)
        tb.addWidget(self._y_max_spin)

        tb.addWidget(QLabel("|"))

        pts_lbl = QLabel("Points:")
        pts_lbl.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        tb.addWidget(pts_lbl)
        self._max_points_spin = self._make_int_spin(100, 10000, 500)
        self._max_points_spin.valueChanged.connect(self._on_max_points_changed)
        tb.addWidget(self._max_points_spin)

        tb.addStretch()

        export_btn = QPushButton("Export CSV")
        export_btn.setStyleSheet(BTN_SM_GHOST)
        export_btn.clicked.connect(self._export_csv)
        tb.addWidget(export_btn)

        layout.addWidget(toolbar)

        # Plot area
        self._plot_widget = PlotWidget()
        layout.addWidget(self._plot_widget, stretch=1)

        # Refresh timer (~16 FPS)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(60)
        self._refresh_timer.timeout.connect(self._on_refresh_tick)
        self._refresh_timer.start()

    @staticmethod
    def _make_double_spin(lo, hi, val):
        from PyQt6.QtWidgets import QDoubleSpinBox
        sb = QDoubleSpinBox()
        sb.setRange(lo, hi)
        sb.setValue(val)
        sb.setDecimals(1)
        sb.setFixedWidth(72)
        sb.setStyleSheet(
            f"QDoubleSpinBox{{background:{C['bg_input']};color:{C['fg']};"
            f"border:1px solid {C['border_light']};border-radius:3px;"
            f"padding:1px 4px;{FONT_SMALL}}}")
        return sb

    @staticmethod
    def _make_int_spin(lo, hi, val):
        sb = QSpinBox()
        sb.setRange(lo, hi)
        sb.setValue(val)
        sb.setFixedWidth(64)
        sb.setStyleSheet(
            f"QSpinBox{{background:{C['bg_input']};color:{C['fg']};"
            f"border:1px solid {C['border_light']};border-radius:3px;"
            f"padding:1px 4px;{FONT_SMALL}}}")
        return sb

    # ── Data handling ──────────────────────────────────────────────────────

    def on_serial_line(self, line):
        """Called for every serial line. Parse and append to data model."""
        values = self._parse_serial_line(line)
        if values is None:
            return
        if self._channel_count == 0 or len(values) != self._channel_count:
            self._reset_channels(len(values))
        for i, v in enumerate(values):
            self._data[i].append(v)
        self._sample_count += 1
        self._dirty = True

    def on_connection_changed(self, connected):
        """Reset plot data when serial connection starts."""
        if connected:
            self._reset_channels(0)
            self._header_detected = False
            self._plot_widget.update()

    def _parse_serial_line(self, line):
        """Parse a serial line into a list of floats, or None."""
        line = line.strip()
        if not line:
            return None
        # Try splitting: comma, tab, then whitespace
        for sep in [',', '\t', None]:
            tokens = line.split(sep) if sep else line.split()
            if len(tokens) >= 1:
                values = []
                all_numeric = True
                for t in tokens:
                    t = t.strip()
                    if not t:
                        continue
                    try:
                        values.append(float(t))
                    except ValueError:
                        all_numeric = False
                        break
                if all_numeric and values:
                    return values
        # Check if it's a label header (non-numeric first line)
        if not self._header_detected and self._channel_count == 0:
            for sep in [',', '\t', None]:
                tokens = line.split(sep) if sep else line.split()
                labels = [t.strip() for t in tokens if t.strip()]
                if len(labels) >= 1 and all(not self._is_numeric(l) for l in labels):
                    self._channel_names = labels
                    self._header_detected = True
                    return None
        return None

    @staticmethod
    def _is_numeric(s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    def _reset_channels(self, count):
        """Reset data model for new channel count."""
        max_pts = self._max_points_spin.value()
        self._channel_count = count
        self._data = [self._deque_cls(maxlen=max_pts) for _ in range(count)]
        if not self._header_detected or len(self._channel_names) != count:
            self._channel_names = [f"ch{i}" for i in range(count)]
        self._sample_count = 0
        self._plot_widget.set_data(self._data, self._channel_names)
        self._update_channel_label()

    def _update_channel_label(self):
        self._ch_label.setText(f"Channels: {self._channel_count}")

    # ── UI actions ─────────────────────────────────────────────────────────

    def _toggle_pause(self):
        self._paused = self._pause_btn.isChecked()
        self._pause_btn.setText("Resume" if self._paused else "Pause")

    def _clear(self):
        self._reset_channels(0)
        self._header_detected = False
        self._plot_widget.update()

    def _on_auto_scale_changed(self):
        auto = self._auto_scale_btn.isChecked()
        self._y_min_spin.setEnabled(not auto)
        self._y_max_spin.setEnabled(not auto)
        self._update_y_range()

    def _on_max_points_changed(self):
        max_pts = self._max_points_spin.value()
        new_data = []
        for d in self._data:
            nd = self._deque_cls(d, maxlen=max_pts)
            new_data.append(nd)
        self._data = new_data
        self._plot_widget.set_data(self._data, self._channel_names)
        self._dirty = True

    def _update_y_range(self):
        auto = self._auto_scale_btn.isChecked()
        self._plot_widget.set_y_range(auto, self._y_min_spin.value(), self._y_max_spin.value())
        self._dirty = True

    def _on_refresh_tick(self):
        if self._dirty and not self._paused:
            self._update_y_range()
            self._plot_widget.update()
            self._dirty = False

    def _export_csv(self):
        if not self._data:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Plot Data", "", "CSV (*.csv)")
        if not path:
            return
        max_len = max((len(d) for d in self._data), default=0)
        with open(path, 'w') as f:
            f.write(",".join(self._channel_names) + "\n")
            for i in range(max_len):
                row = []
                for d in self._data:
                    data_list = list(d)
                    row.append(str(data_list[i]) if i < len(data_list) else "")
                f.write(",".join(row) + "\n")


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
    recompile_requested = pyqtSignal()       # emitted when user clicks Recompile after apply
    model_switch_requested = pyqtSignal(str)  # model name — request toolbar combo update
    fix_triggered = pyqtSignal()             # emitted when /fix or continuation fix is invoked
    chat_cleared = pyqtSignal()              # emitted when conversation is cleared

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_path = None
        self._conversation = [{"role": "system", "content": self._build_system_prompt()}]
        self._current_response = ""
        self._error_context = ""
        self._error_diagnostics = []     # list[StructuredDiagnostic]
        self._editor_ref = None          # will be set by MainWindow
        self._pending_edits = []         # list[ProposedEdit]
        self._file_acceptance = {}       # {filename: True (accepted) | False (rejected)}
        self._apply_snapshot = {}        # {abs_path: original_content} for undo
        budget = _load_config().get("context_budget", 12000)
        self._working_set = WorkingSet(budget=budget)
        self._ai_edited_files = set()             # rel_paths of files the AI has edited
        self._use_working_set_context = True      # WorkingSet is default; /debug-use-ws off for old path
        self._last_prompt_stats = None            # dict: stats from the last actual prompt sent
        self._target_override = None              # str: rel_path of file detected in user message (per-prompt only)
        self._symbol_index = {}                   # {name: [SymbolEntry, ...]} across all project files
        self._calltip_map = {}                    # {func_name: signature_string}
        self._last_work_result = None             # AIWorkResult from most recent AI turn
        self._selection_mode = False              # True when using selection-based edit flow
        self._selection_edit = None               # dict with selection coords for selection mode
        self._selection_prefilled = False         # True when pre-fill was used for selection prompt
        self._captured_selection = None            # snapshot of editor selection (survives focus loss)
        self._gen_start_time = None               # time.time() when generation started
        self._gen_token_count = 0                  # token count during streaming
        self._stats_widget = None                  # stats row widget during streaming
        self._stats_label = None                   # QLabel showing token/time stats
        self._stats_spinner = None                 # SpinnerWidget in stats row
        self._in_think_block = False              # True while streaming inside <think>...</think>

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Style right-click context menus (QTextEdit default menus inherit this)
        self.setStyleSheet(
            f"ChatPanel QMenu{{background:{C['bg_input']};color:{C['fg']};"
            f"border:1px solid {C['border_light']};border-radius:4px;padding:4px;}}"
            f"ChatPanel QMenu::item{{padding:4px 20px;border-radius:2px;}}"
            f"ChatPanel QMenu::item:selected{{background:{C['teal']};color:#fff;}}"
            f"ChatPanel QMenu::separator{{height:1px;background:{C['border_light']};"
            f"margin:4px 8px;}}")

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
        # Outer container fills scroll area width; inner column centered at 800px
        outer_container = QWidget()
        outer_container.setStyleSheet(f"background:{C['bg_dark']};")
        outer_lay = QHBoxLayout(outer_container)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(0)
        outer_lay.addStretch()
        chat_column = QWidget()
        chat_column.setMaximumWidth(1200)
        chat_column.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._chat_layout = QVBoxLayout(chat_column)
        self._chat_layout.setContentsMargins(12, 12, 12, 12)
        self._chat_layout.setSpacing(20)
        self._chat_layout.addStretch()
        outer_lay.addWidget(chat_column)
        outer_lay.addStretch()
        self._chat_scroll.setWidget(outer_container)
        self._current_ai_widget = None
        self._current_ai_wrapper = None
        layout.addWidget(self._chat_scroll)

        # Apply bar — shows after AI suggests edits
        self.apply_bar = QWidget()
        self.apply_bar.setStyleSheet(f"background:{C['bg']};border-top:1px solid {C['border']};")
        ab_outer = QVBoxLayout(self.apply_bar)
        ab_outer.setContentsMargins(16, 8, 16, 8)
        ab_outer.setSpacing(4)
        # Header row: summary + intent badge
        ab_header = QHBoxLayout()
        self.apply_label = QLabel("")
        self.apply_label.setStyleSheet(f"color:{C['fg']};{FONT_BODY}")
        ab_header.addWidget(self.apply_label)
        self._intent_badge = QLabel("BUILD FIX")
        self._intent_badge.setStyleSheet(
            f"background:{C['teal']};color:white;border-radius:3px;"
            f"padding:1px 6px;{FONT_SMALL}")
        self._intent_badge.hide()
        ab_header.addWidget(self._intent_badge)
        ab_header.addStretch()
        ab_outer.addLayout(ab_header)
        # File detail rows (populated dynamically)
        self._apply_file_rows = QWidget()
        self._apply_file_rows_layout = QVBoxLayout(self._apply_file_rows)
        self._apply_file_rows_layout.setContentsMargins(24, 0, 0, 0)
        self._apply_file_rows_layout.setSpacing(2)
        ab_outer.addWidget(self._apply_file_rows)
        # Button row
        ab_btns = QHBoxLayout()
        ab_btns.addStretch()
        self.apply_all_btn = QPushButton("Replace")
        self.apply_all_btn.setStyleSheet(BTN_PRIMARY)
        self.apply_all_btn.clicked.connect(self._apply_all_edits)
        ab_btns.addWidget(self.apply_all_btn)
        self._apply_compile_btn = QPushButton("\u25b6 Apply \u0026 Compile")
        self._apply_compile_btn.setStyleSheet(
            f"background:#007a7f;color:white;border:none;border-radius:4px;"
            f"padding:4px 12px;{FONT_BODY}")
        self._apply_compile_btn.clicked.connect(self._apply_and_compile)
        ab_btns.addWidget(self._apply_compile_btn)
        self.dismiss_btn = QPushButton("Dismiss")
        self.dismiss_btn.setStyleSheet(BTN_SECONDARY)
        self.dismiss_btn.clicked.connect(self._dismiss_edits)
        ab_btns.addWidget(self.dismiss_btn)
        ab_outer.addLayout(ab_btns)
        self.apply_bar.hide()
        layout.addWidget(self.apply_bar)

        # Recompile bar — shown after applying edits when diagnostics exist
        self.recompile_bar = QWidget()
        self.recompile_bar.setStyleSheet(f"background:{C['bg']};border-top:1px solid {C['border']};")
        rc_layout = QHBoxLayout(self.recompile_bar)
        rc_layout.setContentsMargins(16, 8, 16, 8)
        self._recompile_label = QLabel("Edits applied. Recompile to check?")
        self._recompile_label.setStyleSheet(f"color:{C['fg']};{FONT_BODY}")
        rc_layout.addWidget(self._recompile_label)
        rc_layout.addStretch()
        self._undo_btn = QPushButton("\u21a9 Undo Last Apply")
        self._undo_btn.setStyleSheet(BTN_GHOST)
        self._undo_btn.clicked.connect(self._undo_last_apply)
        self._undo_btn.hide()
        rc_layout.addWidget(self._undo_btn)
        recompile_btn = QPushButton("Recompile")
        recompile_btn.setStyleSheet(BTN_PRIMARY)
        recompile_btn.clicked.connect(self._on_recompile_clicked)
        rc_layout.addWidget(recompile_btn)
        rc_dismiss = QPushButton("Dismiss")
        rc_dismiss.setStyleSheet(BTN_SECONDARY)
        rc_dismiss.clicked.connect(lambda: self.recompile_bar.hide())
        rc_layout.addWidget(rc_dismiss)
        self.recompile_bar.hide()
        layout.addWidget(self.recompile_bar)

        # Fix continuation bar — shown when compile-after-AI-edits still fails
        self.fix_continuation_bar = QWidget()
        self.fix_continuation_bar.setStyleSheet(
            f"background:{C['bg_dark']};border-top:2px solid {C['fg_warn']};")
        fc_outer = QVBoxLayout(self.fix_continuation_bar)
        fc_outer.setContentsMargins(16, 8, 16, 8)
        fc_outer.setSpacing(6)
        # Top row: status label + primary action buttons
        fc_top = QHBoxLayout()
        self._fix_continuation_label = QLabel("Errors remain after applying changes.")
        self._fix_continuation_label.setStyleSheet(f"color:{C['fg_warn']};{FONT_BODY}")
        self._fix_continuation_label.setWordWrap(True)
        fc_top.addWidget(self._fix_continuation_label, stretch=1)
        self._fix_retry_btn = QPushButton("Fix Remaining Errors")
        self._fix_retry_btn.setStyleSheet(BTN_PRIMARY)
        self._fix_retry_btn.clicked.connect(self._on_fix_continuation_clicked)
        fc_top.addWidget(self._fix_retry_btn)
        fc_dismiss = QPushButton("Dismiss")
        fc_dismiss.setStyleSheet(BTN_SECONDARY)
        fc_dismiss.clicked.connect(self.fix_continuation_bar.hide)
        fc_top.addWidget(fc_dismiss)
        fc_outer.addLayout(fc_top)
        # Escalation row: alternative actions shown when stalled
        self._escalation_row = QWidget()
        esc_layout = QHBoxLayout(self._escalation_row)
        esc_layout.setContentsMargins(0, 0, 0, 0)
        esc_layout.setSpacing(6)
        esc_label = QLabel("Try a different approach:")
        esc_label.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        esc_layout.addWidget(esc_label)
        btn_explain = QPushButton("Explain Errors")
        btn_explain.setStyleSheet(BTN_SECONDARY)
        btn_explain.setToolTip("Ask AI to explain the errors without fixing")
        btn_explain.clicked.connect(self._on_fix_explain)
        esc_layout.addWidget(btn_explain)
        btn_focus = QPushButton("Focus One File")
        btn_focus.setStyleSheet(BTN_SECONDARY)
        btn_focus.setToolTip("Fix only the first file with errors")
        btn_focus.clicked.connect(self._on_fix_focus)
        esc_layout.addWidget(btn_focus)
        btn_narrow = QPushButton("Narrower Fix")
        btn_narrow.setStyleSheet(BTN_SECONDARY)
        btn_narrow.setToolTip("Ask for the smallest possible change")
        btn_narrow.clicked.connect(self._on_fix_narrow)
        esc_layout.addWidget(btn_narrow)
        esc_layout.addStretch()
        self._escalation_row.hide()
        fc_outer.addWidget(self._escalation_row)
        self.fix_continuation_bar.hide()
        layout.addWidget(self.fix_continuation_bar)

        # Code workspace panel — shows full captured selection with actions
        self._workspace_panel = QFrame()
        self._workspace_panel.setStyleSheet(
            f"QFrame#workspacePanel{{"
            f"background:{C['bg_dark']};border:1px solid {C['teal']};"
            f"border-radius:8px;margin:4px 16px;}}")
        self._workspace_panel.setObjectName("workspacePanel")
        self._workspace_panel.setMaximumHeight(200)
        wp_layout = QVBoxLayout(self._workspace_panel)
        wp_layout.setContentsMargins(0, 0, 0, 0)
        wp_layout.setSpacing(0)

        # Header row
        ws_header = QWidget()
        ws_header.setStyleSheet(
            f"background:{C['bg']};border-top-left-radius:8px;"
            f"border-top-right-radius:8px;")
        wsh_layout = QHBoxLayout(ws_header)
        wsh_layout.setContentsMargins(12, 6, 8, 6)
        wsh_layout.setSpacing(6)
        self._workspace_header = QLabel("")
        self._workspace_header.setStyleSheet(
            f"color:{C['fg_dim']};{FONT_SMALL}background:transparent;border:none;")
        wsh_layout.addWidget(self._workspace_header)
        wsh_layout.addStretch()
        ws_close = QPushButton("✕")
        ws_close.setFixedSize(20, 20)
        ws_close.setStyleSheet(
            f"QPushButton{{color:{C['fg_dim']};background:transparent;"
            f"border:none;{FONT_SMALL}font-weight:bold;}}"
            f"QPushButton:hover{{color:{C['fg']};}}")
        ws_close.clicked.connect(self._clear_captured_selection)
        wsh_layout.addWidget(ws_close)
        wp_layout.addWidget(ws_header)

        # Code display
        self._workspace_code = QPlainTextEdit()
        self._workspace_code.setReadOnly(True)
        self._workspace_code.setMaximumHeight(120)
        self._workspace_code.setStyleSheet(
            f"QPlainTextEdit{{background:#111111;color:{C['fg']};"
            f"border:none;padding:6px 12px;"
            f"font-family:Menlo,Monaco,Consolas,monospace;font-size:12px;}}")
        self._workspace_code.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        wp_layout.addWidget(self._workspace_code)

        # Quick action buttons row
        ws_actions = QWidget()
        ws_actions.setStyleSheet(
            f"background:{C['bg_dark']};border-bottom-left-radius:8px;"
            f"border-bottom-right-radius:8px;")
        wsa_layout = QHBoxLayout(ws_actions)
        wsa_layout.setContentsMargins(12, 4, 12, 4)
        wsa_layout.setSpacing(6)
        _WS_BTN = (
            f"QPushButton{{color:{C['teal']};background:transparent;"
            f"border:none;{FONT_SMALL}padding:3px 8px;}}"
            f"QPushButton:hover{{color:{C['fg']};background:{C['bg_hover']};"
            f"border-radius:4px;}}")
        for label, key in [("Explain", "explain"), ("Fix / Improve", "fix"),
                           ("Refactor", "refactor"), ("Optimize", "optimize")]:
            btn = QPushButton(label)
            btn.setStyleSheet(_WS_BTN)
            btn.clicked.connect(lambda checked, k=key: self._on_workspace_action(k))
            wsa_layout.addWidget(btn)
        wsa_layout.addStretch()
        wp_layout.addWidget(ws_actions)

        self._workspace_panel.hide()
        layout.addWidget(self._workspace_panel)

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
        # Connect tab changes to clear captured selection
        editor.tabs.currentChanged.connect(self._on_editor_tab_changed)
        # Connect selectionChanged for all existing editors
        for fp, ed in editor._editors.items():
            self._connect_editor_signals(ed)
        # Auto-connect future editors
        editor.editor_opened.connect(self._connect_editor_signals)

    def _connect_editor_signals(self, editor_widget):
        """Connect selectionChanged and textChanged for selection capture."""
        if hasattr(editor_widget, 'selectionChanged'):
            editor_widget.selectionChanged.connect(
                self._on_editor_selection_changed)
        sig = 'textChanged' if hasattr(editor_widget, 'textChanged') else None
        if sig:
            getattr(editor_widget, sig).connect(
                self._on_editor_text_changed)

    def _on_editor_selection_changed(self):
        """Snapshot the editor selection when it changes (survives focus loss)."""
        editor_widget = self.sender()
        if not editor_widget or not hasattr(editor_widget, 'hasSelectedText'):
            return
        if editor_widget.hasSelectedText():
            sel_text = editor_widget.selectedText()
            lf, cf, lt, ct = editor_widget.getSelection()
            # Resolve file path for this editor widget
            file_path = None
            if self._editor_ref:
                for fp, ed in self._editor_ref._editors.items():
                    if ed is editor_widget:
                        file_path = fp
                        break
            if sel_text.strip() and file_path:
                self._captured_selection = {
                    'text': sel_text,
                    'line_from': lf, 'col_from': cf,
                    'line_to': lt, 'col_to': ct,
                    'file_path': file_path,
                }
                self._update_workspace()
        # Do NOT clear when selection is empty — might just be focus loss

    def _on_editor_tab_changed(self, index):
        """Clear captured selection when the user switches to a different file tab."""
        self._clear_captured_selection()

    def _on_editor_text_changed(self):
        """Clear captured selection if the editor text changed and no selection remains."""
        editor_widget = self.sender()
        if not editor_widget:
            return
        if hasattr(editor_widget, 'hasSelectedText') and not editor_widget.hasSelectedText():
            self._clear_captured_selection()

    def _clear_captured_selection(self):
        """Clear the captured selection and hide the workspace panel."""
        self._captured_selection = None
        self._update_workspace()

    def _update_workspace(self):
        """Show or hide the workspace panel based on _captured_selection."""
        if self._captured_selection:
            sel = self._captured_selection
            basename = os.path.basename(sel['file_path'])
            line_range = f"lines {sel['line_from'] + 1}\u2013{sel['line_to'] + 1}"
            self._workspace_header.setText(f"{basename} : {line_range}")
            self._workspace_code.setPlainText(sel['text'])
            self._workspace_panel.show()
        else:
            self._workspace_panel.hide()

    def _on_workspace_action(self, action_name):
        """Send a quick action prompt through the selection flow (or chat for explain)."""
        prompts = {
            'explain': 'Explain this code briefly. Mention any Teensy/Arduino-specific details.',
            'fix': 'Review this code for bugs and improvements. Fix any issues found.',
            'refactor': 'Refactor this code to be cleaner and more readable.',
            'optimize': ('Optimize this code for Teensy performance. '
                         'Minimize memory, use hardware features where possible.'),
        }
        prompt = prompts.get(action_name, action_name)
        if self._captured_selection:
            sel = self._captured_selection
            if action_name == 'explain':
                # Explain uses regular chat path — no selection-edit flow
                basename = os.path.basename(sel['file_path'])
                line_range = f"lines {sel['line_from']+1}\u2013{sel['line_to']+1}"
                explain_prompt = (
                    f"Explain this code from {basename} ({line_range}):\n"
                    f"```\n{sel['text']}\n```\n{prompt}")
                self._captured_selection = None
                self._update_workspace()
                self._send_prompt(explain_prompt, display_text="Explain")
            else:
                self._send_selection_prompt(
                    prompt, sel['text'],
                    sel['line_from'], sel['col_from'],
                    sel['line_to'], sel['col_to'],
                    sel['file_path'],
                    display_text=action_name.replace('_', ' ').title(),
                )

    def set_project_path(self, path):
        """Set the project directory path for context."""
        self._project_path = path
        # Reset working set and edit tracking for new project
        self._working_set.clear()
        self._ai_edited_files.clear()
        # Discard any pending edits from the previous project
        self._pending_edits = []
        self._file_acceptance = {}
        self._clear_apply_file_rows()
        self.apply_bar.hide()
        self.recompile_bar.hide()
        self.fix_continuation_bar.hide()
        # Update system prompt (picks up .aide_prompt if present)
        if self._conversation and self._conversation[0]["role"] == "system":
            self._conversation[0]["content"] = self._build_system_prompt()
        # Build symbol index after event loop returns (non-blocking)
        self._symbol_index = {}
        QTimer.singleShot(0, self._build_symbol_index)

    def set_error_context(self, e, diagnostics=None):
        self._error_context = e
        self._error_diagnostics = diagnostics or []
        # If the apply bar is open, refresh its intent badge with updated diagnostics
        if self._pending_edits:
            self._refresh_apply_summary()

    def _build_diagnostic_context(self):
        """Build structured diagnostic context for the AI prompt.
        Includes a summary table plus targeted code excerpts around error lines.
        Falls back to raw compiler text if no structured diagnostics are available."""
        raw = self._error_context
        diags = self._error_diagnostics

        if not diags:
            # No structured diagnostics — send raw text only
            return (f"[COMPILER ERRORS — produce <<<EDIT blocks to fix these:]\n"
                    f"```\n{raw}\n```\n")

        # --- Diagnostic summary table ---
        parts = ["[COMPILER ERRORS — produce <<<EDIT blocks to fix these:]", ""]
        for i, d in enumerate(diags[:15]):  # Cap at 15 to avoid prompt bloat
            loc = f"{d.file}:{d.line}"
            if d.column:
                loc += f":{d.column}"
            parts.append(f"  {i+1}. [{d.severity}] {loc} — {d.message}")
        if len(diags) > 15:
            parts.append(f"  ... and {len(diags) - 15} more")
        parts.append("")

        # --- Code excerpts for diagnostic locations ---
        # Group diagnostics by file, read each file once, show context window
        proj = getattr(self, '_project_path', None) or ""
        file_lines_cache = {}  # abs_path -> list of lines
        seen_files = {}        # rel_path -> set of diagnostic line numbers

        for d in diags[:15]:
            if d.file == "<linker>" or d.line == 0:
                continue
            # Resolve to absolute path
            if os.path.isabs(d.file):
                abs_path = d.file
            elif proj:
                abs_path = os.path.join(proj, d.file)
            else:
                abs_path = os.path.abspath(d.file)
            # Try to get a relative path for display
            rel = os.path.relpath(abs_path, proj) if proj else d.file
            if rel not in seen_files:
                seen_files[rel] = set()
            seen_files[rel].add(d.line)
            # Cache the file contents
            if abs_path not in file_lines_cache:
                try:
                    with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                        file_lines_cache[abs_path] = f.readlines()
                except OSError:
                    file_lines_cache[abs_path] = None

        # Build excerpts — max 3 files to keep context bounded
        excerpt_count = 0
        for rel, line_nums in sorted(seen_files.items()):
            if excerpt_count >= 3:
                parts.append(f"[... excerpts for remaining files omitted]")
                break
            # Find the cached content
            abs_path = os.path.join(proj, rel) if proj else os.path.abspath(rel)
            lines = file_lines_cache.get(abs_path)
            if not lines:
                continue

            # Merge nearby line ranges (5 lines above/below each diagnostic)
            WINDOW = 5
            ranges = []
            for ln in sorted(line_nums):
                start = max(1, ln - WINDOW)
                end = min(len(lines), ln + WINDOW)
                if ranges and start <= ranges[-1][1] + 2:
                    # Merge with previous range
                    ranges[-1] = (ranges[-1][0], end)
                else:
                    ranges.append((start, end))

            parts.append(f"[CODE EXCERPT: {rel}]")
            for rng_start, rng_end in ranges:
                for i in range(rng_start, rng_end + 1):
                    marker = " >>>" if i in line_nums else "    "
                    parts.append(f"{marker} {i:4d} | {lines[i-1].rstrip()}")
                if rng_end < len(lines):
                    parts.append("    ...")
            parts.append("")
            excerpt_count += 1

        # Append raw output for human/model reference
        parts.append("[RAW COMPILER OUTPUT:]")
        parts.append(f"```\n{raw}\n```")

        return "\n".join(parts) + "\n"

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
        """Resolve a filename from AI output to an absolute path.
        Uses a multi-strategy approach:
          a) Exact match (original logic)
          b) Case-insensitive exact match against project files
          c) Case-insensitive substring match against WorkingSet context files
          d) Extension-based fallback for single-file-in-context scenarios
        """
        if os.path.isabs(filename):
            return filename
        proj = getattr(self, '_project_path', None) or ""

        # --- (a) Exact match: file exists at proj/filename ---
        if proj:
            exact = os.path.join(proj, filename)
            if os.path.isfile(exact):
                return exact

        # --- (b) Case-insensitive exact basename match against open tabs + project ---
        target_lower = os.path.basename(filename).lower()
        # Check open editor tabs
        if self._editor_ref:
            tab_matches = []
            for fp in self._editor_ref.get_all_files():
                if os.path.basename(fp).lower() == target_lower:
                    tab_matches.append(fp)
            if len(tab_matches) == 1:
                print(f"[resolve] case-insensitive tab match: {filename!r} → {tab_matches[0]!r}")
                return tab_matches[0]

        # Check project files on disk
        if proj:
            disk_matches = []
            for root, dirs, files in os.walk(proj):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in PROJECT_SKIP_DIRS]
                for f in files:
                    if f.lower() == target_lower:
                        disk_matches.append(os.path.join(root, f))
            if len(disk_matches) == 1:
                print(f"[resolve] case-insensitive disk match: {filename!r} → {disk_matches[0]!r}")
                return disk_matches[0]

        # --- (c) Substring match against WorkingSet context files ---
        target_stem = os.path.splitext(target_lower)[0]  # e.g. "drumsynth"
        target_ext = os.path.splitext(target_lower)[1]    # e.g. ".ino"
        context_files = []  # list of (abs_path, basename)
        if hasattr(self, '_working_set') and self._working_set.entries:
            for entry in self._working_set.entries.values():
                context_files.append((entry.filepath, os.path.basename(entry.filepath)))

        if target_stem and context_files:
            substr_matches = []
            for abs_path, bname in context_files:
                bname_stem = os.path.splitext(bname)[0].lower()
                bname_ext = os.path.splitext(bname)[1].lower()
                # Extension must match if both have one
                if target_ext and bname_ext and target_ext != bname_ext:
                    continue
                # Check if LLM's stem is a substring of the context file's stem
                if target_stem in bname_stem:
                    substr_matches.append(abs_path)
            if len(substr_matches) == 1:
                print(f"[resolve] context substring match: {filename!r} → {substr_matches[0]!r}")
                return substr_matches[0]

        # --- (d) Extension fallback: single context file with same extension ---
        if target_ext and context_files:
            ext_matches = [fp for fp, bn in context_files
                           if os.path.splitext(bn)[1].lower() == target_ext]
            if len(ext_matches) == 1:
                print(f"[resolve] single-extension fallback: {filename!r} → {ext_matches[0]!r}")
                return ext_matches[0]

        # --- Fallback: construct path (may not exist) ---
        if proj:
            return os.path.join(proj, filename)
        return os.path.abspath(filename)

    def _detect_named_files(self, user_text):
        """Scan user message for filenames with code extensions or known function names.
        Returns the rel_path of the best matching project file, or None.
        Checks filenames first; falls back to symbol index for function names."""
        proj = getattr(self, '_project_path', None) or ""
        if not proj:
            return None
        # Tokenize on whitespace, commas, backticks, quotes, parens
        import re as _re
        tokens = _re.split(r'[\s,`\'"()\[\]]+', user_text)

        # Phase 1: filename detection (existing logic)
        candidates = []
        for tok in tokens:
            tok = tok.strip('.!?;:')
            if not tok:
                continue
            ext = os.path.splitext(tok)[1].lower()
            if ext in TARGET_EXTENSIONS:
                candidates.append(tok)
        if candidates:
            all_files = self._scan_project_files(proj)
            for cand in candidates:
                if cand in all_files:
                    return cand
                cand_base = os.path.basename(cand)
                matches = [rp for rp in all_files if os.path.basename(rp) == cand_base]
                if len(matches) == 1:
                    return matches[0]
                if len(matches) > 1:
                    return min(matches, key=len)

        # Phase 2: function-name detection via symbol index
        if self._symbol_index:
            # Look for tokens that match a known function name
            # Prefer "function" kind over "global"/"type"
            for tok in tokens:
                tok = tok.strip('.!?;:()').rstrip('(')
                if not tok or len(tok) < 2:
                    continue
                entries = self._symbol_index.get(tok)
                if not entries:
                    continue
                func_entries = [e for e in entries if e.kind == "function"]
                if func_entries:
                    # If all function entries point to the same file, use it
                    files = list({e.rel_path for e in func_entries})
                    if len(files) == 1:
                        return files[0]
                    # Multiple files — prefer the one with the shortest path
                    return min(files, key=len)

        return None

    def _build_symbol_index(self):
        """Walk all project files and extract function definitions, globals, and type
        definitions using conservative regex patterns. Updates self._symbol_index.
        Called after project open and after edits are applied. Non-blocking (fast scan).
        Files that fail to parse are silently skipped."""
        import re as _re
        proj = getattr(self, '_project_path', None) or ""
        if not proj:
            self._symbol_index = {}
            return

        # Only index code files — skip .md/.json/etc.
        CODE_EXTS = {".ino", ".cpp", ".c", ".h", ".hpp"}
        all_files = self._scan_project_files(proj)
        index = {}  # name -> list[SymbolEntry]

        # Conservative patterns — prefer false negatives over false positives
        # Function definitions: return-type name(args) NOT ending in ; or pure declarations
        RE_FUNC = _re.compile(
            r'^[a-zA-Z_][\w\s\*&:<>]+\s+(\w+)\s*\([^;{]*\)\s*(?:const\s*)?(?:override\s*)?(?:noexcept\s*)?[{]',
            _re.MULTILINE)
        # Global variables at file scope (not inside a block): type name = / type name;
        RE_GLOBAL = _re.compile(
            r'^(?:(?:static|extern|volatile|const)\s+)*[a-zA-Z_]\w+(?:\s*\*+)?\s+(\w+)\s*(?:=|;)',
            _re.MULTILINE)
        # Type definitions: struct/enum/typedef name
        RE_TYPE = _re.compile(
            r'^(?:struct|enum|typedef|class)\s+(\w+)', _re.MULTILINE)

        for rel_path, content in all_files.items():
            ext = os.path.splitext(rel_path)[1].lower()
            if ext not in CODE_EXTS:
                continue
            try:
                # Pre-compute line start offsets for O(1) line-number lookup
                line_starts = [0]
                for ch in content:
                    if ch == '\n':
                        line_starts.append(line_starts[-1] + 1)
                    else:
                        line_starts[-1] += 1
                # Rebuild as cumulative byte offsets
                offsets = [0]
                pos = 0
                for line_content in content.split('\n'):
                    pos += len(line_content) + 1
                    offsets.append(pos)

                def offset_to_line(match_start):
                    # Binary search for line number
                    lo, hi = 0, len(offsets) - 1
                    while lo < hi:
                        mid = (lo + hi + 1) // 2
                        if offsets[mid] <= match_start:
                            lo = mid
                        else:
                            hi = mid - 1
                    return lo + 1  # 1-based

                for m in RE_FUNC.finditer(content):
                    name = m.group(1)
                    if name in ('if', 'for', 'while', 'switch', 'return', 'else'):
                        continue
                    # Capture signature: strip trailing { and whitespace
                    sig = m.group(0).rstrip().rstrip('{').strip()
                    entry = SymbolEntry(name, rel_path, offset_to_line(m.start()),
                                        "function", signature=sig)
                    index.setdefault(name, []).append(entry)

                for m in RE_TYPE.finditer(content):
                    name = m.group(1)
                    entry = SymbolEntry(name, rel_path, offset_to_line(m.start()), "type")
                    index.setdefault(name, []).append(entry)

                for m in RE_GLOBAL.finditer(content):
                    name = m.group(1)
                    # Skip names already indexed as functions or common keywords
                    if name in index or name in ('if', 'for', 'while', 'return',
                                                  'else', 'case', 'break', 'continue'):
                        continue
                    entry = SymbolEntry(name, rel_path, offset_to_line(m.start()), "global")
                    index.setdefault(name, []).append(entry)
            except Exception:
                continue  # silently skip files that fail to parse

        self._symbol_index = index

        # Build calltip map: function name → signature string
        calltip_map = {}
        for name, entries in index.items():
            sigs = [e.signature for e in entries
                    if e.kind == "function" and e.signature]
            if sigs:
                calltip_map[name] = "\n".join(sigs)
        self._calltip_map = calltip_map

        # Refresh autocomplete API lists on all open editors
        if self._editor_ref:
            for ed in self._editor_ref._editors.values():
                if HAS_QSCINTILLA and hasattr(ed, '_rebuild_api_list'):
                    ed._rebuild_api_list()

        # Refresh outline panel if MainWindow is available
        mw = self.window()
        if mw and hasattr(mw, '_refresh_outline'):
            mw._refresh_outline()

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

        # Overlay editor buffer content onto scanned files.
        # Buffer-only edits (save_to_disk=False) are only in the editor widget,
        # not on disk — the editor buffer is the authoritative source for open files.
        active_file = self._editor_ref.current_file() if self._editor_ref else None
        open_files = self._editor_ref.get_all_files() if self._editor_ref else {}
        for fp, content in open_files.items():
            rel = os.path.relpath(fp, proj)
            all_files[rel] = content  # override disk content with buffer content

        # Populate working set with priorities
        # 0=active tab, 1=AI-edited, 2=open-but-not-active, 3=other project file
        self._working_set.clear()
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

        # Per-prompt target override: promote named file to priority 0,
        # demote active tab to priority 2 (open-tab) if different
        if self._target_override and self._target_override in self._working_set.entries:
            target_entry = self._working_set.entries[self._target_override]
            if target_entry.priority != 0:
                # Demote current priority-0 entry (active tab) to open-tab
                for e in self._working_set.entries.values():
                    if e.priority == 0 and e.rel_path != self._target_override:
                        e.priority = 2
                target_entry.priority = 0

        # Include reference documents at lowest priority for .ino projects
        if any(f.endswith('.ino') for f in all_files):
            for ref_path in _load_ref_docs():
                if os.path.exists(ref_path):
                    try:
                        with open(ref_path, 'r', encoding='utf-8') as _f:
                            ref_content = _f.read()
                        rel_name = f'ref/{os.path.basename(ref_path)}'
                        self._working_set.add(ref_path, rel_name, 3, ref_content)
                    except OSError:
                        pass

        self._update_context_display(proj_name, proj, sorted(all_files.keys()))

        # Debug fallback: old full-context (all files, no budget)
        if not self._use_working_set_context:
            parts = [
                f"[PROJECT: {proj_name}]", f"[DIRECTORY: {proj}]", "",
                "[PROJECT STRUCTURE]", tree, "",
                f"=== FILES IN YOUR CONTEXT ({len(all_files)} files — you can read and edit these directly) ===", "",
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
            "target_override": self._target_override,
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
        "fix":     "Ask AI to fix compile errors using diagnostics",
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
        elif cmd == "fix":
            self._cmd_fix()
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
                    if AI_BACKEND == "lmstudio":
                        resp = requests.post(
                            f"{LMSTUDIO_URL}/v1/chat/completions",
                            json={"model": OLLAMA_MODEL,
                                  "messages": [{"role": "user", "content": summary_prompt}],
                                  "stream": False,
                                  "temperature": 0.3, "max_tokens": 2048},
                            timeout=60)
                        resp.raise_for_status()
                        summary = resp.json()["choices"][0]["message"]["content"].strip()
                    else:
                        resp = requests.post(
                            f"{OLLAMA_URL}/api/generate",
                            json={"model": OLLAMA_MODEL, "prompt": summary_prompt,
                                  "stream": False},
                            timeout=(5, 60))
                        resp.raise_for_status()
                        summary = resp.json().get("response", "").strip()
                    self_w.finished.emit(summary)
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

    def show_fix_continuation(self, n_diags, attempt=0, diff=None, stalled=False):
        """Show the fix continuation bar after compile-after-AI-edits failure.
        diff is an optional (resolved, remaining, new) tuple from _diff_diagnostics.
        stalled=True shows escalation buttons for alternative approaches."""
        attempt_prefix = f"Fix attempt {attempt} \u2014 " if attempt > 0 else ""
        if stalled:
            self._fix_continuation_label.setText(
                f"{attempt_prefix}no progress. Try a different approach?")
            self._escalation_row.show()
        elif diff and attempt > 0:
            resolved, remaining, new_count = diff
            parts = []
            if resolved:
                parts.append(f"\u2713 {resolved} resolved")
            if new_count:
                parts.append(f"\u26a0 {new_count} new")
            parts.append(f"\u2715 {remaining} remain")
            diff_text = " \u00b7 ".join(parts)
            self._fix_continuation_label.setText(
                f"{attempt_prefix}{diff_text}. Fix remaining errors?")
            self._escalation_row.hide()
        else:
            s = "s" if n_diags != 1 else ""
            self._fix_continuation_label.setText(
                f"{attempt_prefix}{n_diags} error{s} remain. Fix remaining errors?")
            self._escalation_row.hide()
        self.fix_continuation_bar.show()

    def _on_fix_continuation_clicked(self):
        """User confirmed continuing the fix cycle."""
        self.fix_continuation_bar.hide()
        self._cmd_fix()

    def _on_fix_explain(self):
        """Escalation: ask AI to explain errors instead of fixing."""
        self.fix_continuation_bar.hide()
        self.fix_triggered.emit()
        self.send_errors_btn.setChecked(True)
        self._send_prompt(
            "Don't fix anything yet. Explain in plain terms what these compiler "
            "errors mean and what's causing them. Be specific about which lines "
            "and what the root cause is.",
            display_text="/fix (explain)")

    def _on_fix_focus(self):
        """Escalation: focus on the first file with errors."""
        self.fix_continuation_bar.hide()
        self.fix_triggered.emit()
        # Find the first diagnostic's file
        target = None
        if self._error_diagnostics:
            target = self._error_diagnostics[0].file
        self.send_errors_btn.setChecked(True)
        if target:
            basename = os.path.basename(target)
            self._send_prompt(
                f"Focus only on {basename}. What specifically needs to change "
                f"to fix the errors in this file? Make the smallest targeted "
                f"edit possible. Ignore errors in other files for now.",
                display_text=f"/fix (focus: {basename})")
        else:
            self._send_prompt(
                "Focus on the first error only. What specifically needs to change? "
                "Make the smallest targeted edit possible.",
                display_text="/fix (focus)")

    def _on_fix_narrow(self):
        """Escalation: ask for the smallest possible change."""
        self.fix_continuation_bar.hide()
        self.fix_triggered.emit()
        self.send_errors_btn.setChecked(True)
        self._send_prompt(
            "The previous fixes haven't resolved these errors. Please make the "
            "smallest possible change — modify as few lines as you can. Do not "
            "rewrite functions or restructure code. Change only the exact lines "
            "that cause the errors.",
            display_text="/fix (narrow)")

    def _cmd_fix(self):
        """Send a compile-fix request using structured diagnostics."""
        if not self._error_context:
            self._add_info_msg(
                "No compile errors to fix. Compile first (Ctrl+R).", C['fg_warn'])
            return
        self.fix_triggered.emit()
        n_diags = len(self._error_diagnostics)
        n_errors = sum(1 for d in self._error_diagnostics if d.severity == "error")
        if n_diags:
            self._add_info_msg(
                f"Sending {n_diags} diagnostics ({n_errors} errors) to AI...",
                C['fg_dim'])
        # Enable error attachment and send a focused fix prompt
        self.send_errors_btn.setChecked(True)
        self._send_prompt(
            "Fix the compile errors shown above. Make minimal, targeted edits. "
            "Do not refactor or change unrelated code. "
            "Explain briefly what you changed and why.",
            display_text="/fix")

    def _cmd_context(self):
        """Show the full AI context preview."""
        file_ctx = self._build_file_context()
        git_ctx = self._build_git_context()
        total = file_ctx + ("\n" + git_ctx if git_ctx else "")
        # Count files
        file_count = total.count("========== FILE:")
        size_chars = len(total)
        budget = self._working_set.budget
        summary = f"Context: {file_count} files, {size_chars:,} chars (budget: {budget:,} tokens)"
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
        # Symbol index summary
        sym_count = sum(len(v) for v in self._symbol_index.values())
        sym_files = len({e.rel_path for entries in self._symbol_index.values()
                         for e in entries})
        sym_summary = (f"{sym_count} symbols across {sym_files} files"
                       if self._symbol_index else "(empty — send a message first)")
        lines = [
            f"[debug] WorkingSet — {len(ws.entries)} entries, "
            f"~{ws.total_tokens:,} tokens total, budget={ws.budget:,}",
            f"  LIVE MODE: {live_mode}",
            f"  would include: {ws.included_count} files",
            f"  breakdown: {', '.join(f'{v} {k}' for k, v in sorted(counts.items()))}",
            f"  ai_edited_files: {sorted(self._ai_edited_files) if self._ai_edited_files else '(none)'}",
            f"  symbol index: {sym_summary}",
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
            tgt = lps.get('target_override')
            if tgt:
                lines.append(f"  target override: {tgt} (detected in user message)")
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

    def _send_prompt(self, text, display_text=None, display_code=None):
        """Core send method used by both manual chat and AI actions."""
        # Guard: reject if a generation is already in progress
        if self.thread.isRunning():
            self._add_info_msg(
                "Please wait — model is currently responding.", C['fg_warn'])
            return

        # Guard: check model is set and backend is reachable
        if not OLLAMA_MODEL or OLLAMA_MODEL.strip() == "":
            self._add_info_msg(
                "No model selected. Choose a model from the toolbar dropdown "
                "or the Models tab in Settings.", C['fg_warn'])
            return
        base_url = LMSTUDIO_URL if AI_BACKEND == "lmstudio" else OLLAMA_URL
        try:
            import urllib.request
            req = urllib.request.Request(base_url, method='HEAD')
            urllib.request.urlopen(req, timeout=2)
        except Exception:
            backend_name = "LM Studio" if AI_BACKEND == "lmstudio" else "Ollama"
            self._add_info_msg(
                f"Cannot reach {backend_name} at {base_url}. "
                f"Make sure {backend_name} is running.", C['fg_warn'])
            return

        # Silently discard any pending edits when sending a new message
        if self._pending_edits and self.apply_bar.isVisible():
            self._pending_edits = []
            self.apply_bar.hide()

        # Selection-based edit flow: use captured selection snapshot
        # (survives focus loss when user clicks chat input)
        if self._captured_selection:
            sel = self._captured_selection
            self._captured_selection = None
            self._update_workspace()
            self._send_selection_prompt(
                text, sel['text'],
                sel['line_from'], sel['col_from'],
                sel['line_to'], sel['col_to'],
                sel['file_path'], display_text=display_text,
                display_code=display_code)
            return

        # Detect named files in user message for per-prompt targeting override
        self._target_override = self._detect_named_files(text)

        # Build the full message with automatic file + git context
        msg = self._build_file_context()
        git_ctx = self._build_git_context()
        if git_ctx:
            msg += f"\n{git_ctx}\n"
        if self.send_errors_btn.isChecked() and self._error_context:
            msg += "\n" + self._build_diagnostic_context() + "\n"
            self.send_errors_btn.setChecked(False)
        # Targeting reminder — stronger when a named file was detected
        if self._target_override:
            target_reminder = (
                f"\n[REMINDER: The project files are above — you already have them. "
                "Respond with <<<EDIT blocks when changes are needed. Do not ask for file paths or permission. "
                "Use <<<EDIT path\\n<<<OLD\\n...\\n>>>NEW\\n...\\n>>>END format.]\n"
                f"(Edit {self._target_override} as requested — not the active file.)\n"
                f"\n[USER REQUEST:]\n{text}"
            )
        else:
            target_reminder = (
                "\n[REMINDER: The project files are above — you already have them. "
                "Respond with <<<EDIT blocks when changes are needed. Do not ask for file paths or permission. "
                "Use <<<EDIT path\\n<<<OLD\\n...\\n>>>NEW\\n...\\n>>>END format. "
                "Edit the file the USER mentions, NOT the active file unless they ask for it.]\n"
                f"\n[USER REQUEST:]\n{text}"
            )
        msg += target_reminder

        # Show user message bubble (right-aligned)
        show = display_text or text
        self._add_user_msg(show, code=display_code)

        self._conversation.append({"role": "user", "content": msg})
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._current_response = ""
        self._in_think_block = False
        self.apply_bar.hide()
        self._pending_edits = []
        self._apply_snapshot.clear()
        self._undo_btn.hide()

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
        # Attach stats to AI message wrapper (not as separate chat item)
        if self._current_ai_wrapper:
            self._current_ai_wrapper.layout().addWidget(stats_wrapper)
        else:
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

    # -- Selection-based edit flow -------------------------------------------

    _SELECTION_SYSTEM_PROMPT = (
        "You are a code editor. The user's file is shown below with a selected "
        "region marked between <<<SELECTED>>> and >>>SELECTED>>>.\n\n"
        "Your response will be inserted directly as code. "
        "Output ONLY the replacement code — nothing else.\n\n"
        "RULES:\n"
        "- Respond with ONLY the replacement text for the selected region.\n"
        "- Do NOT include <<<SELECTED>>> or >>>SELECTED>>> markers.\n"
        "- Do NOT wrap your response in ```code fences```.\n"
        "- Do NOT include any explanation, preamble, or commentary.\n"
        "- Do NOT repeat the rest of the file — ONLY the replacement.\n"
        "- If the user asks to explain or analyze (not change) the code, "
        "respond with a plain text explanation instead.\n"
        "- PRESERVE the syntactic role of the selected code. If the selection "
        "is a comment, your replacement must also be a comment (keep the // or "
        "/* */ prefix). If it is a string literal, keep the quotes. If it is a "
        "function body, keep it as a function body.\n"
        "- Be VERBATIM with the user's replacement text. If the user says to "
        "replace with 'wowser', output exactly 'wowser' — do not capitalize, "
        "add punctuation, or rephrase it.\n"
        "- Match the indentation of the original selection exactly. Count the "
        "leading spaces or tabs and reproduce them.\n"
        "- Be extremely concise. No explanation, no alternatives, no commentary. "
        "If the user asks to 'explain', give a brief explanation (2-3 sentences "
        "max) — not a tutorial.\n"
        "\nEXAMPLES:\n\n"
        "Example 1:\n"
        "User selected: // This is the old comment\n"
        "User request: replace this with hello world\n"
        "Your response:\n"
        "// hello world\n\n"
        "Example 2:\n"
        "User selected: int delay_ms = 100;\n"
        "User request: change the delay to 250\n"
        "Your response:\n"
        "int delay_ms = 250;\n\n"
        "Example 3:\n"
        "User selected:\n"
        "void setup() {\n"
        "  Serial.begin(9600);\n"
        "}\n"
        "User request: add a pin mode setup for pin 13\n"
        "Your response:\n"
        "void setup() {\n"
        "  Serial.begin(9600);\n"
        "  pinMode(13, OUTPUT);\n"
        "}\n\n"
        "Example 4:\n"
        "User selected: // FIRMWARE_VERSION auto-generated from compile date\n"
        "User request: replace this with wowser\n"
        "Your response:\n"
        "// wowser\n\n"
        "Notice: every response is ONLY the replacement code. "
        "No explanation. No markdown fences. No preamble.\n"
    )

    def _send_selection_prompt(self, user_text, selected_text,
                                line_from, col_from, line_to, col_to,
                                file_path, display_text=None,
                                display_code=None):
        """Send a selection-based edit prompt — simpler than <<<EDIT flow.
        The LLM responds with just the replacement text for the selection."""
        # Store selection details for apply time
        self._selection_mode = True
        self._selection_edit = {
            'file_path': file_path,
            'line_from': line_from,
            'col_from': col_from,
            'line_to': line_to,
            'col_to': col_to,
            'original_text': selected_text,
        }

        # Build file content with <<<SELECTED>>> markers
        editor_widget = self._editor_ref.tabs.currentWidget()
        full_content = editor_widget.text() if hasattr(editor_widget, 'text') else ""
        lines = full_content.split('\n')
        marked = []
        for i, line in enumerate(lines):
            if i == line_from:
                marked.append('<<<SELECTED>>>')
            marked.append(line)
            if i == line_to:
                marked.append('>>>SELECTED>>>')
        marked_content = '\n'.join(marked)

        basename = os.path.basename(file_path)
        user_msg = (f"=== WORKING ON: {basename} (lines {line_from+1}\u2013{line_to+1}) ===\n"
                    f"The selected code is marked with <<<SELECTED>>> / >>>SELECTED>>>.\n\n"
                    f"{marked_content}\n\n"
                    f"User request: {user_text}")

        # One-shot conversation with assistant pre-fill to force code output
        messages = [
            {"role": "system", "content": self._SELECTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": "<<<REPLACEMENT>>>\n"},
        ]
        self._selection_prefilled = True

        # Show user bubble with multi-line code preview (up to 3 lines)
        show = display_text or user_text
        preview_lines = selected_text.split('\n')[:3]
        preview_lines = [l[:60] + ('…' if len(l) > 60 else '') for l in preview_lines]
        if len(selected_text.split('\n')) > 3:
            preview_lines.append('…')
        sel_preview = '\n'.join(preview_lines)
        self._add_user_msg(show, code=sel_preview if display_code is None else display_code)

        # Prepare UI for streaming (same as _send_prompt)
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._current_response = ""
        self._in_think_block = False
        self.apply_bar.hide()
        self._pending_edits = []
        self._apply_snapshot.clear()
        self._undo_btn.hide()
        self._add_ai_msg()

        # Stats row
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
        if self._current_ai_wrapper:
            self._current_ai_wrapper.layout().addWidget(stats_wrapper)
        else:
            self._chat_layout.insertWidget(
                self._chat_layout.count() - 1, stats_wrapper)
        self._stats_widget = stats_wrapper
        self._stats_label = stats_lbl
        self._stats_spinner = spinner

        # Send to Ollama with selection-specific messages
        self.worker.messages = messages
        if self.thread.isRunning():
            self.worker.stop()
            self.thread.quit()
            if not self.thread.wait(2000):
                self.thread.terminate()
                self.thread.wait(1000)
                self._setup_worker_thread()
        self.generation_started.emit()
        self.thread.start()

    def _handle_selection_response(self, response_text):
        """Process the LLM response in selection mode.
        Uses pre-fill extraction first, then multi-strategy fallbacks."""
        import re as _re
        text = self._clean_model_artifacts(response_text).strip()
        # Strip thinking blocks — not useful as code replacement
        text = _re.sub(r'<think>.*?</think>', '', text, flags=_re.DOTALL).strip()
        original = self._selection_edit['original_text']
        prefilled = self._selection_prefilled
        self._selection_prefilled = False

        # ── Pre-fill path ──────────────────────────────────────────────
        # When we pre-filled with "<<<REPLACEMENT>>>\n", the streamed
        # response IS the replacement content (possibly followed by the
        # closing >>>REPLACEMENT>>> marker).
        if prefilled:
            # Strip closing delimiter if the model added it
            if '>>>REPLACEMENT>>>' in text:
                text = text[:text.index('>>>REPLACEMENT>>>')].strip()
            # Strip opening delimiter if the model echoed it
            if text.startswith('<<<REPLACEMENT>>>'):
                text = text[len('<<<REPLACEMENT>>>'):].lstrip('\n')
            # Strip trailing code fences
            if text.endswith('```'):
                text = text[:text.rfind('```')].strip()
            # Strip wrapping code fences
            if text.startswith('```'):
                first_nl = text.find('\n')
                if first_nl != -1:
                    text = text[first_nl + 1:]
                if text.endswith('```'):
                    text = text[:text.rfind('```')].strip()

            if text:
                # Run safety filters before creating edit
                if self._selection_is_refusal(text):
                    return
                if self._selection_is_prose(text, original):
                    return
                self._create_selection_edit(text)
                return

        # ── Non-pre-fill fallback path ─────────────────────────────────
        # Strategy 1: Delimiter extraction
        start_marker = '<<<REPLACEMENT>>>'
        end_marker = '>>>REPLACEMENT>>>'
        if start_marker in text and end_marker in text:
            s = text.index(start_marker) + len(start_marker)
            e = text.index(end_marker)
            extracted = text[s:e].strip()
            if extracted:
                self._create_selection_edit(extracted)
                return

        # Strategy 2: Refusal detection
        if self._selection_is_refusal(text):
            return

        # Strategy 3: Single code fence extraction
        fence_matches = _re.findall(r'```(?:\w*)\n(.*?)```', text, _re.DOTALL)
        if len(fence_matches) == 1:
            candidate = fence_matches[0].strip()
            if candidate and len(candidate) < len(original) * 3:
                self._create_selection_edit(candidate)
                return

        # Strategy 4: Strip wrapping code fences
        stripped = text
        if stripped.startswith('```'):
            first_nl = stripped.find('\n')
            if first_nl != -1:
                stripped = stripped[first_nl + 1:]
        if stripped.endswith('```'):
            stripped = stripped[:stripped.rfind('```')].rstrip()
        if stripped != text:
            text = stripped

        # Safety filters on remaining text
        if self._selection_is_prose(text, original):
            return

        # Strategy 5: Short response — probably just the replacement
        original_len = len(original)
        sentence_count = len(_re.findall(r'\.\s+[A-Z]', text))
        has_paragraphs = '\n\n' in text
        is_long = len(text) > original_len * 2
        if not is_long and not has_paragraphs and sentence_count < 2:
            self._create_selection_edit(text)
            return

        # Strategy 6: Conservative code check
        first_line = text.strip().split('\n')[0].strip() if text.strip() else ''
        starts_with_code = any(
            first_line.lower().startswith(s.lower()) for s in self._CODE_STARTERS)
        if starts_with_code and sentence_count < 2 and not has_paragraphs:
            self._create_selection_edit(text)
            return

        # Default: no edit found — response is an explanation (already displayed)

    # Code token prefixes for detecting code vs prose in selection responses
    _CODE_STARTERS = (
        '//', '/*', '#include', '#define', '#pragma', '#if', '#else',
        '#endif', 'void', 'int', 'float', 'char', 'bool', 'const',
        'constexpr', 'static', 'class', 'struct', 'enum', 'if', 'for',
        'while', 'return', 'typedef', 'unsigned', 'signed', 'long',
        'short', 'double', 'auto', 'extern', 'volatile', 'namespace',
        'using', 'template', 'virtual', 'public', 'private', 'protected',
        'switch', 'case', 'break', 'continue', 'do', 'else', 'try',
        'catch', 'throw', '{', '}', '(', '[', 'Serial', 'digital',
        'analog', 'delay', 'pinMode', 'String', 'byte', 'uint',
        'int8', 'int16', 'int32',
    )

    # -- Response cleaning: strip model artifacts and LaTeX ----------------

    import re as _re_cls
    _MODEL_ARTIFACT_RE = _re_cls.compile(
        r'<\|(?:im_start|im_end|endoftext|begin_of_sentence|end_of_sentence)\|>'
        r'|<\uff5c[^\uff5c]*\uff5c>'          # fullwidth bar delimiters (deepseek)
        r'|^(?:Question|Answer|Human|Assistant|User)\s*:\s*'  # role prefixes
        r'|<\|(?:user|assistant|system)\|>',   # chat role markers
        _re_cls.MULTILINE | _re_cls.IGNORECASE
    )
    _LATEX_RE = _re_cls.compile(
        r'\\\(|\\\)'                                          # inline math \( \)
        r'|\\\[|\\\]'                                         # display math \[ \]
        r'|\\frac\{([^}]*)\}\{([^}]*)\}'                     # \frac{a}{b} → a/b
        r'|\\boxed\{([^}]*)\}'                                # \boxed{x} → x
        r'|\\text\{([^}]*)\}'                                 # \text{x} → x
        r'|\\(?:mathbb|mathrm|textbf|textit)\{([^}]*)\}'     # math fonts → content
        r'|\\(?:cdot|times)'                                  # operators
        r'|\\(?:left|right|Big|big)[|()\\\[\]{}]?'            # sizing
        r'|\$\$?'                                             # dollar-sign math
    )
    del _re_cls  # clean up the temporary import

    def _clean_model_artifacts(self, text):
        """Strip special tokens and role markers that leak from various LLMs."""
        return self._MODEL_ARTIFACT_RE.sub('', text)

    def _validate_output_format(self, text):
        """Check for common Qwen format violations. Returns (is_valid, issues)."""
        issues = []
        if '```' in text:
            issues.append("markdown_fence")
        if re.search(r'^@@\s', text, re.MULTILINE):
            issues.append("unified_diff")
        if re.search(r'^[+-]\s+\w', text, re.MULTILINE):
            if '<<<EDIT' not in text and '<<<FILE' not in text and '<<<REPLACEMENT' not in text:
                issues.append("diff_style")
        if '<think>' in text or '</think>' in text:
            issues.append("think_leak")
        if '<|im_start|>' in text or '<|im_end|>' in text:
            issues.append("special_token")
        # Preamble before first edit marker (verbosity detection)
        first_marker = None
        for marker in ['<<<EDIT', '<<<FILE', '<<<INSERT_BEFORE',
                        '<<<INSERT_AFTER', '<<<REPLACEMENT>>>']:
            idx = text.find(marker)
            if idx >= 0 and (first_marker is None or idx < first_marker):
                first_marker = idx
        if first_marker is not None and first_marker > 80:
            preamble = text[:first_marker].strip()
            if preamble:
                issues.append("preamble")
        return (len(issues) == 0, issues)

    def _strip_latex(self, text):
        """Convert common LaTeX formatting to plain text."""
        def _repl(m):
            if m.group(1) is not None and m.group(2) is not None:
                return f"{m.group(1)}/{m.group(2)}"
            for g in (3, 4, 5):
                if m.group(g) is not None:
                    return m.group(g)
            s = m.group(0)
            if s == '\\cdot': return '\u00b7'
            if s == '\\times': return '\u00d7'
            return ''
        return self._LATEX_RE.sub(_repl, text)

    def _selection_is_refusal(self, text):
        """Check if text is an LLM refusal. If so, show info and return True."""
        _refusal_phrases = (
            "i'm sorry", "i can't assist", "i cannot assist",
            "i can't help", "i cannot help", "i apologize",
            "i'm unable to", "i am unable to",
            "as an ai", "as a language model",
            "it seems like you're asking", "it seems like you",
            "without more context", "could you clarify",
            "if you have any other questions", "please provide more",
        )
        text_lower = text.lower()
        if any(phrase in text_lower for phrase in _refusal_phrases):
            self._add_info_msg(
                "AI declined to make the edit.", C['fg_warn'])
            return True
        return False

    def _selection_is_prose(self, text, original):
        """Check if text looks like prose/explanation. If so, show info and return True."""
        import re as _re
        original_len = len(original)
        sentence_count = len(_re.findall(r'\.\s+[A-Z]', text))
        has_list_markers = bool(
            _re.search(r'^\d+[\.\)]\s', text, _re.MULTILINE))
        has_paragraphs = '\n\n' in text
        is_long = len(text) > original_len * 2
        prose_signals = sum([
            sentence_count >= 2,
            is_long,
            has_list_markers,
            has_paragraphs,
        ])
        if prose_signals >= 2:
            return True  # Explanation already displayed via streaming
        return False

    def _create_selection_edit(self, replacement_text):
        """Create a ProposedEdit for a selection replacement and show apply bar."""
        # Safety net: reject refusal/prose that slipped through extraction
        rt_lower = replacement_text.lower()
        if any(p in rt_lower for p in (
                "i'm sorry", "i can't", "i cannot",
                "i apologize", "it seems like")):
            self._add_info_msg(
                "AI declined to make the edit.", C['fg_warn'])
            return

        original = self._selection_edit['original_text']

        # Strip markdown fences if still wrapped
        if replacement_text.strip().startswith('```'):
            lines = replacement_text.strip().split('\n')
            if lines[0].strip().startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            replacement_text = '\n'.join(lines)

        # Preserve trailing newline from original selection
        if original.endswith('\r\n') and not replacement_text.endswith('\r\n'):
            replacement_text = replacement_text.rstrip('\n') + '\r\n'
        elif original.endswith('\n') and not replacement_text.endswith('\n'):
            replacement_text += '\n'

        file_path = self._selection_edit['file_path']
        edit = ProposedEdit(
            edit_type="selection",
            filename=os.path.basename(file_path),
            old_text=original,
            new_text=replacement_text,
            operation="selection_replace",
            resolved_path=file_path,
        )
        self._pending_edits = [edit]
        self._populate_apply_bar([edit])
        self._add_info_msg(
            'Selection edit ready — use the Apply bar to replace the selected text.',
            C['fg_ok'])

    def stop_generation(self):
        self.worker.stop()
        self._selection_mode = False
        self._selection_prefilled = False
        self._in_think_block = False
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
        t = self._clean_model_artifacts(t)
        t = self._strip_latex(t)
        if not t:
            return
        # In selection mode, strip replacement delimiters before display
        if self._selection_mode:
            t = t.replace('<<<REPLACEMENT>>>', '').replace('>>>REPLACEMENT>>>', '')
            if not t:
                return
        self._current_response += t  # keep tags for _render_formatted_response
        # Handle <think> blocks — strip tags from display text, track state
        display_t = t
        if '<think>' in display_t:
            display_t = display_t.replace('<think>', '')
            self._in_think_block = True
        if '</think>' in display_t:
            display_t = display_t.replace('</think>', '')
            self._in_think_block = False
        if self._current_ai_widget and display_t:
            cur = self._current_ai_widget.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.End)
            if self._in_think_block:
                # Style thinking tokens as dim italic
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(C['fg_dim']))
                fmt.setFontItalic(True)
                fmt.setFontPointSize(11)
                cur.insertText(display_t, fmt)
            else:
                cur.insertText(display_t)
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
        f'background:{C["bg_dark"]};'
        f'border:1px solid #333;'
        f'border-radius:6px;'
        f'padding:10px 12px;margin:8px 0;'
        f'font-family:Menlo,Monaco,Consolas,monospace;font-size:12px;')
    _INLINE_CODE_STYLE = (
        f'background:#252525;padding:1px 5px;border-radius:3px;'
        f'font-family:Menlo,Monaco,Consolas,monospace;font-size:12px;'
        f'color:{C["fg_warn"]};')
    _EDIT_BLOCK_STYLE = (
        f'background:{C["bg_input"]};'
        f'border:1px solid {C["border_light"]};'
        f'border-left:3px solid {C["teal"]};'
        f'padding:10px;margin:12px 0;'
        f'font-family:Menlo,Monaco,Courier New,monospace;font-size:13px;')
    _EDIT_HEADER_STYLE = (
        f'color:{C["teal"]};font-size:12px;font-weight:bold;margin-bottom:4px;')

    def _render_formatted_response(self):
        """Re-render the completed AI response with styled code blocks and edit blocks."""
        import re
        if not self._current_ai_widget or not self._current_response:
            return
        text = self._current_response
        # Only render if there's markdown-like content worth processing
        if ("```" not in text and "<<<" not in text
                and "`" not in text and "<think>" not in text
                and "**" not in text and "\n#" not in text
                and "\n- " not in text and "\n* " not in text
                and "\n1." not in text):
            return
        html_parts = []
        in_code = False
        in_edit = False
        in_think = False
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            # <think> block start
            if '<think>' in line and not in_code and not in_edit:
                line = line.replace('<think>', '')
                in_think = True
                if not line.strip():
                    i += 1
                    continue
            # </think> block end
            if '</think>' in line:
                line = line.replace('</think>', '')
                in_think = False
                if line.strip():
                    escaped_line = html.escape(line)
                    html_parts.append(
                        f'<span style="color:{C["fg_dim"]};font-style:italic;'
                        f'font-size:11px;">{escaped_line}</span><br>')
                i += 1
                continue
            # Inside think block — render as dim italic
            if in_think:
                escaped_line = html.escape(line)
                html_parts.append(
                    f'<span style="color:{C["fg_dim"]};font-style:italic;'
                    f'font-size:11px;">{escaped_line}</span><br>')
                i += 1
                continue
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
            # Regular text — markdown rendering
            line = self._strip_latex(line)

            # Empty line = paragraph break
            if not line.strip():
                html_parts.append('<div style="height:8px;"></div>')
                i += 1
                continue

            escaped_line = html.escape(line)

            # Headings: ## or ### at start of line
            heading_match = re.match(r'^(#{1,4})\s+(.+)$', escaped_line)
            if heading_match:
                level = len(heading_match.group(1))
                h_text = heading_match.group(2)
                sizes = {1: '18px', 2: '16px', 3: '15px', 4: '14px'}
                font_size = sizes.get(level, '14px')
                html_parts.append(
                    f'<div style="font-size:{font_size};font-weight:bold;'
                    f'color:{C["fg_head"]};margin:12px 0 4px 0;">{h_text}</div>')
                i += 1
                continue

            # Bullet list items: "- item" or "* item"
            bullet_match = re.match(r'^(\s*)[*\-]\s+(.+)$', escaped_line)
            if bullet_match:
                indent = len(bullet_match.group(1))
                b_text = bullet_match.group(2)
                margin_left = 16 + (indent * 8)
                b_text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', b_text)
                b_text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', b_text)
                b_text = re.sub(
                    r'`([^`]+)`',
                    rf'<code style="{self._INLINE_CODE_STYLE}">\1</code>',
                    b_text)
                html_parts.append(
                    f'<div style="margin-left:{margin_left}px;margin-bottom:2px;">'
                    f'\u2022 {b_text}</div>')
                i += 1
                continue

            # Numbered list items: "1. item", "2. item"
            num_match = re.match(r'^(\s*)(\d+)\.\s+(.+)$', escaped_line)
            if num_match:
                indent = len(num_match.group(1))
                number = num_match.group(2)
                n_text = num_match.group(3)
                margin_left = 16 + (indent * 8)
                n_text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', n_text)
                n_text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', n_text)
                n_text = re.sub(
                    r'`([^`]+)`',
                    rf'<code style="{self._INLINE_CODE_STYLE}">\1</code>',
                    n_text)
                html_parts.append(
                    f'<div style="margin-left:{margin_left}px;margin-bottom:2px;">'
                    f'{number}. {n_text}</div>')
                i += 1
                continue

            # Horizontal rules: --- or ***
            if re.match(r'^[\-\*]{3,}\s*$', escaped_line):
                html_parts.append(
                    f'<hr style="border:none;border-top:1px solid {C["border_light"]};'
                    f'margin:8px 0;">')
                i += 1
                continue

            # Inline formatting: bold, italic, inline code
            escaped_line = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', escaped_line)
            escaped_line = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', escaped_line)
            escaped_line = re.sub(
                r'`([^`]+)`',
                rf'<code style="{self._INLINE_CODE_STYLE}">\1</code>',
                escaped_line)

            html_parts.append(escaped_line + "<br>")
            i += 1
        # Close any unclosed blocks
        if in_code or in_edit:
            html_parts.append("</pre></div>")
        styled_html = (
            f'<div style="color:{C["fg"]};font-family:\'Helvetica Neue\',Helvetica,'
            f'Arial,sans-serif;font-size:14px;line-height:1.5;">'
            + "".join(html_parts)
            + '</div>')
        self._current_ai_widget.setHtml(styled_html)
        self._current_ai_widget.document().adjustSize()
        self._scroll_to_bottom()

    def _on_complete(self):
        if self.thread.isRunning():
            self.thread.quit()
        if self._current_response:
            # Final pass: strip any remaining model artifacts
            self._current_response = self._clean_model_artifacts(
                self._current_response).strip()
            # Validate output format and auto-clean known violations
            _is_valid, _fmt_issues = self._validate_output_format(
                self._current_response)
            if not _is_valid and _fmt_issues:
                cleaned = self._current_response
                if "markdown_fence" in _fmt_issues:
                    cleaned = re.sub(r'```\w*\n?', '', cleaned)
                if "think_leak" in _fmt_issues:
                    cleaned = re.sub(
                        r'<think>.*?</think>', '', cleaned, flags=re.DOTALL)
                if "special_token" in _fmt_issues:
                    cleaned = cleaned.replace(
                        '<|im_start|>', '').replace('<|im_end|>', '')
                self._current_response = cleaned.strip()
            # Selection mode: bypass <<<EDIT parser, handle replacement directly
            if self._selection_mode:
                self._handle_selection_response(self._current_response)
                self._selection_mode = False
            else:
                # Strip think blocks from history — keep only final answer
                _clean_hist = re.sub(
                    r'<think>.*?</think>', '', self._current_response,
                    flags=re.DOTALL).strip()
                self._conversation.append(
                    {"role": "assistant", "content": _clean_hist})
                self._render_formatted_response()
                # Deferred resize to ensure final height is correct after HTML render
                if self._current_ai_widget:
                    QTimer.singleShot(50, lambda w=self._current_ai_widget:
                        w.setFixedHeight(max(30, int(w.document().size().height()) + 20)))
                result = AIWorkResult(assistant_text=self._current_response)
                result.diagnostics = list(self._error_diagnostics)
                self._parse_edits(self._current_response, result)
                self._last_work_result = result
        # Finalize stats — stop spinner, show final stats
        self._finalize_stats()
        self._current_ai_widget = None
        self._current_ai_wrapper = None
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
        self._selection_mode = False
        self._selection_prefilled = False
        self._in_think_block = False
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
        self._current_ai_wrapper = None
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

    def _extract_edit_blocks(self, text):
        """Parse <<<EDIT, <<<FILE, <<<INSERT_BEFORE, and <<<INSERT_AFTER blocks
        using a line-by-line state machine. Handles >>> and <<< inside code
        content, blank lines between markers, and trailing newlines in captured
        sections. Returns list[ProposedEdit]."""
        # Normalize literal \r\n and \n escape sequences to real newlines.
        # Some local models (e.g. deepseek-coder-v2) emit backslash-n instead
        # of actual newline chars. Only trigger when markers are adjacent.
        if '\\r\\n<<<' in text or '\\r\\n>>>' in text:
            text = text.replace('\\r\\n', '\n')
        if '\\n<<<' in text or '\\n>>>' in text:
            text = text.replace('\\n', '\n')

        # Force every recognized marker onto its own line.
        # Some local models put markers on the same line as content,
        # e.g. "<<<EDIT file <<<OLD // code..." — the state machine needs
        # each marker at the start of its own line.
        # Markers that take a filename argument — newline before only
        for m in ['<<<EDIT ', '<<<FILE ',
                   '<<<INSERT_BEFORE ', '<<<INSERT_AFTER ']:
            text = text.replace(m, '\n' + m)
        # Standalone markers — newline before AND after trailing content
        import re as _re
        for m in ['<<<OLD', '>>>NEW', '>>>END', '>>>FILE',
                   '<<<ANCHOR', '>>>ANCHOR',
                   '<<<CONTENT', '>>>CONTENT']:
            # First: if marker has trailing non-whitespace, split it off
            # e.g. "<<<OLD // code" → "<<<OLD\n// code"
            text = _re.sub(_re.escape(m) + r'[ \t]+(\S)', m + '\n\\1', text)
            # Then: ensure marker starts on its own line
            text = text.replace(m, '\n' + m)

        # Strip markdown code fences that some LLMs wrap around old/new content.
        # e.g. <<<OLD\n```cpp\n// code\n```\n>>>NEW
        # Remove lines that are just ``` or ```<lang> inside edit blocks.
        cleaned = []
        for raw_line in text.split('\n'):
            stripped = raw_line.strip()
            if stripped == '```' or (stripped.startswith('```') and
                    len(stripped) < 20 and ' ' not in stripped.lstrip('`')):
                # Could be a code fence — check if we're inside an edit block
                # by scanning backward for the most recent marker
                in_block = False
                for prev in reversed(cleaned):
                    ps = prev.strip()
                    if (ps.startswith('<<<OLD') or ps.startswith('>>>NEW') or
                            ps.startswith('<<<FILE ') or ps.startswith('<<<ANCHOR') or
                            ps.startswith('<<<CONTENT')):
                        in_block = True
                        break
                    if (ps.startswith('>>>END') or ps.startswith('>>>FILE') or
                            ps.startswith('>>>ANCHOR') or ps.startswith('>>>CONTENT') or
                            ps.startswith('<<<EDIT ')):
                        break
                if in_block:
                    continue  # skip this fence line
            cleaned.append(raw_line)

        edits = []
        lines = cleaned
        state = 'idle'
        filename = ''
        old_lines = []
        new_lines = []
        file_lines = []
        insert_type = ''      # "insert_before" or "insert_after"
        anchor_lines = []
        content_lines = []

        for line in lines:
            stripped = line.strip()
            if state == 'idle':
                if stripped.startswith('<<<EDIT') and len(stripped) > 7:
                    filename = stripped[7:].strip()
                    old_lines = []; new_lines = []
                    state = 'expect_old'
                elif stripped.startswith('<<<FILE') and len(stripped) > 7:
                    filename = stripped[7:].strip()
                    file_lines = []
                    state = 'file'
                elif stripped.startswith('<<<INSERT_BEFORE') and len(stripped) > 16:
                    filename = stripped[16:].strip()
                    insert_type = 'insert_before'
                    anchor_lines = []; content_lines = []
                    state = 'insert_expect_anchor'
                elif stripped.startswith('<<<INSERT_AFTER') and len(stripped) > 15:
                    filename = stripped[15:].strip()
                    insert_type = 'insert_after'
                    anchor_lines = []; content_lines = []
                    state = 'insert_expect_anchor'
            elif state == 'expect_old':
                if stripped == '<<<OLD':
                    state = 'old'
                # else: skip any prose between <<<EDIT and <<<OLD
            elif state == 'old':
                if stripped == '>>>NEW':
                    state = 'new'
                else:
                    old_lines.append(line)
            elif state == 'new':
                if stripped == '>>>END':
                    edits.append(ProposedEdit(
                        "edit", filename,
                        '\n'.join(old_lines).rstrip('\n'),
                        '\n'.join(new_lines).rstrip('\n')))
                    state = 'idle'; filename = ''; old_lines = []; new_lines = []
                else:
                    new_lines.append(line)
            elif state == 'file':
                if stripped == '>>>FILE':
                    edits.append(ProposedEdit(
                        "file", filename, None,
                        '\n'.join(file_lines)))
                    state = 'idle'; filename = ''; file_lines = []
                else:
                    file_lines.append(line)
            # INSERT_BEFORE / INSERT_AFTER states
            elif state == 'insert_expect_anchor':
                if stripped == '<<<ANCHOR':
                    state = 'insert_anchor'
            elif state == 'insert_anchor':
                if stripped == '>>>ANCHOR':
                    state = 'insert_expect_content'
                else:
                    anchor_lines.append(line)
            elif state == 'insert_expect_content':
                if stripped == '<<<CONTENT':
                    state = 'insert_content'
            elif state == 'insert_content':
                if stripped == '>>>CONTENT':
                    edits.append(ProposedEdit(
                        insert_type, filename,
                        '\n'.join(anchor_lines).rstrip('\n'),
                        '\n'.join(content_lines).rstrip('\n')))
                    state = 'idle'; filename = ''; insert_type = ''
                    anchor_lines = []; content_lines = []
                else:
                    content_lines.append(line)
        return edits

    def _parse_edits(self, response, result=None):
        """Parse <<<EDIT and <<<FILE blocks from the AI response.
        Populates result.proposed_edits if an AIWorkResult is provided."""
        edits = self._extract_edit_blocks(response)

        if result is not None:
            result.proposed_edits.extend(edits)

        if edits:
            self._pending_edits = edits
            self._classify_edits()
            self._validate_edits()
            n = len(edits)
            self._populate_apply_bar(edits)
            self._add_info_msg(
                f'Found {n} code edit{"s" if n > 1 else ""} — '
                f'use the Apply bar below to apply.', C['fg_ok'])
        # Fallback: parse unified diff format (diff --git a/file b/file)
        # Some small models output this despite being told not to.
        if not edits:
            diff_tuples = self._parse_unified_diffs(response)
            if diff_tuples:
                edits = [ProposedEdit(et, fn, old, new)
                         for et, fn, old, new in diff_tuples]
                if result is not None:
                    result.proposed_edits.extend(edits)
                self._pending_edits = edits
                self._classify_edits()
                self._validate_edits()
                n = len(edits)
                self._populate_apply_bar(edits)
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

    # -- Edit classification and validation ----------------------------------

    def _classify_edits(self):
        """Assign semantic operation to each pending edit and resolve file paths."""
        for edit in self._pending_edits:
            edit.resolved_path = self._resolve_file_path(edit.filename)
            if edit.edit_type in ("insert_before", "insert_after"):
                edit.operation = edit.edit_type
            elif edit.edit_type == "edit":
                edit.operation = "search_replace"
            elif edit.edit_type == "file":
                if os.path.isfile(edit.resolved_path):
                    edit.operation = "replace_file"
                else:
                    edit.operation = "create_file"

    def _validate_edits(self):
        """Run pre-display validation on classified edits.
        Sets warnings and blocked flags on each ProposedEdit."""
        for edit in self._pending_edits:
            edit.warnings = []
            edit.blocked = False
            if edit.operation == "search_replace":
                self._validate_search_replace(edit)
            elif edit.operation in ("insert_before", "insert_after"):
                self._validate_insert(edit)
            elif edit.operation == "replace_file":
                self._validate_replace_file(edit)
            elif edit.operation == "create_file":
                self._validate_create_file(edit)
            self._validate_filename_ambiguity(edit)

    def _validate_search_replace(self, edit):
        """Validate a search_replace edit against current file content.
        Tries exact match first, then normalized whitespace match."""
        content = self._get_file_content_for_validation(edit)
        if content is None:
            edit.blocked = True
            edit.warnings.append(f"file not found: {edit.filename}")
            return
        if not edit.old_text:
            edit.blocked = True
            edit.warnings.append("empty anchor text \u2014 cannot apply search/replace")
            return
        # 1. Try exact match
        count = content.count(edit.old_text)
        if count == 1:
            return  # exact unique match — ideal
        if count > 1:
            edit.warnings.append(
                f"anchor matches {count} locations, will replace first only")
            return
        # 2. Exact match failed (count == 0) — try normalized whitespace
        norm_matches = _find_normalized_matches(content, edit.old_text)
        if len(norm_matches) == 1:
            start, end = norm_matches[0]
            edit.matched_text = content[start:end]
            edit.warnings.append("anchor matched using normalized whitespace")
        elif len(norm_matches) > 1:
            edit.warnings.append(
                f"normalized anchor matches {len(norm_matches)} locations, "
                f"will replace first only")
            start, end = norm_matches[0]
            edit.matched_text = content[start:end]
        else:
            edit.blocked = True
            edit.warnings.append("anchor text not found in file")

    def _validate_insert(self, edit):
        """Validate an insert_before or insert_after edit.
        Uses the same anchor matching as search_replace: exact first, then normalized."""
        content = self._get_file_content_for_validation(edit)
        if content is None:
            edit.blocked = True
            edit.warnings.append(f"file not found: {edit.filename}")
            return
        if not edit.old_text:
            edit.blocked = True
            edit.warnings.append("empty anchor text — cannot locate insertion point")
            return
        # 1. Exact match
        count = content.count(edit.old_text)
        if count == 1:
            return  # unique match
        if count > 1:
            edit.warnings.append(
                f"anchor matches {count} locations, will insert at first only")
            return
        # 2. Normalized whitespace fallback
        norm_matches = _find_normalized_matches(content, edit.old_text)
        if len(norm_matches) == 1:
            start, end = norm_matches[0]
            edit.matched_text = content[start:end]
            edit.warnings.append("anchor matched using normalized whitespace")
        elif len(norm_matches) > 1:
            edit.warnings.append(
                f"normalized anchor matches {len(norm_matches)} locations, "
                f"will insert at first only")
            start, end = norm_matches[0]
            edit.matched_text = content[start:end]
        else:
            edit.blocked = True
            edit.warnings.append("anchor text not found in file")

    def _validate_replace_file(self, edit):
        """Validate a replace_file edit — block if new content is <50% of original
        (likely a truncated snippet masquerading as a full file replacement)."""
        try:
            existing_size = os.path.getsize(edit.resolved_path)
        except OSError:
            return
        new_size = len(edit.new_text.encode('utf-8'))
        if existing_size > 0 and new_size < existing_size * 0.5:
            pct = int((1 - new_size / existing_size) * 100)
            edit.blocked = True
            edit.warnings.append(
                f"blocked: new content is {pct}% smaller than original "
                f"— likely a truncated snippet. Dismiss and ask AI to use <<<EDIT blocks.")

    def _validate_create_file(self, edit):
        """Validate a create_file edit — block path traversal, reclassify if file exists."""
        # Path traversal guard
        proj = getattr(self, '_project_path', None) or ""
        if proj and edit.resolved_path:
            real_resolved = os.path.realpath(edit.resolved_path)
            real_project = os.path.realpath(proj)
            if not real_resolved.startswith(real_project + os.sep) and real_resolved != real_project:
                edit.blocked = True
                edit.warnings.append("BLOCKED: path escapes project directory")
                return
        if os.path.isfile(edit.resolved_path):
            edit.operation = "replace_file"
            edit.warnings.append("file already exists — treating as replace")
            self._validate_replace_file(edit)
            return

    def _validate_filename_ambiguity(self, edit):
        """Block if the edit's filename matches multiple open files — applying to
        the wrong file silently would be worse than blocking."""
        if not self._editor_ref:
            return
        basename = os.path.basename(edit.filename)
        matches = [fp for fp in self._editor_ref._editors
                    if os.path.basename(fp) == basename]
        if len(matches) > 1:
            edit.blocked = True
            edit.warnings.append(
                f"blocked: \"{basename}\" matches {len(matches)} open files "
                f"— specify the full path")

    def _get_file_content_for_validation(self, edit):
        """Get file content for validation: open editors first, then disk.
        Returns content string or None if file not found."""
        if self._editor_ref:
            fp = self._editor_ref.find_file_by_name(edit.filename)
            if fp:
                files = self._editor_ref.get_all_files()
                return files.get(fp, "")
        if os.path.isfile(edit.resolved_path):
            try:
                with open(edit.resolved_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except (OSError, UnicodeDecodeError):
                return None
        return None

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
        """Apply all parsed edits to the editor. Skips blocked and rejected edits.
        Re-validates anchors at apply time (files may have changed since parse)."""
        if not self._editor_ref or not self._pending_edits:
            return
        applied = 0
        skipped = 0
        rejected = 0
        errors = []

        # Snapshot current file contents for undo
        self._apply_snapshot.clear()
        all_editor_files = self._editor_ref.get_all_files()
        for edit in self._pending_edits:
            if edit.blocked or self._file_acceptance.get(edit.filename) is False:
                continue
            fp = self._editor_ref.find_file_by_name(edit.filename)
            if fp and fp not in self._apply_snapshot:
                content = all_editor_files.get(fp)
                if content is not None:
                    self._apply_snapshot[fp] = content

        for edit in self._pending_edits:
            if self._file_acceptance.get(edit.filename) is False:
                rejected += 1
                continue
            if edit.blocked:
                skipped += 1
                continue

            abs_path = edit.resolved_path or self._resolve_file_path(edit.filename)
            fp = self._editor_ref.find_file_by_name(edit.filename)

            if not fp and edit.operation == "create_file":
                # Safety net: block writes outside project directory
                proj = getattr(self, '_project_path', None) or ""
                if proj:
                    real_abs = os.path.realpath(abs_path)
                    real_proj = os.path.realpath(proj)
                    if not real_abs.startswith(real_proj + os.sep) and real_abs != real_proj:
                        errors.append(f"Blocked: {edit.filename} is outside project directory")
                        continue
                parent_dir = os.path.dirname(abs_path)
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                    with open(abs_path, 'w', encoding='utf-8') as f:
                        f.write(edit.new_text)
                    self._editor_ref.open_file(abs_path)
                    applied += 1
                    self._track_ai_edited_file(edit.filename)
                    continue
                except OSError as e:
                    errors.append(f"Could not create {edit.filename}: {e}")
                    continue

            if not fp and edit.operation in ("search_replace", "replace_file",
                                              "insert_before", "insert_after"):
                if os.path.isfile(abs_path):
                    self._editor_ref.open_file(abs_path)
                    fp = abs_path
                else:
                    errors.append(f"✗ File not found: {edit.filename}")
                    continue

            if not fp:
                errors.append(f"✗ File not found: {edit.filename}")
                continue

            if edit.operation == "replace_file":
                if self._editor_ref.set_file_content(fp, edit.new_text,
                                                      save_to_disk=False):
                    applied += 1
                    self._track_ai_edited_file(edit.filename)
                else:
                    errors.append(f"✗ Could not write: {edit.filename}")
            elif edit.operation == "search_replace":
                files = self._editor_ref.get_all_files()
                content = files.get(fp, "")
                # Re-validate anchor at apply time (file may have changed since parse)
                anchor = None
                if edit.matched_text and edit.matched_text in content:
                    anchor = edit.matched_text
                elif edit.old_text and edit.old_text in content:
                    anchor = edit.old_text
                else:
                    # Last-resort: re-run normalized matching
                    norm_matches = _find_normalized_matches(content, edit.old_text)
                    if norm_matches:
                        start, end = norm_matches[0]
                        anchor = content[start:end]
                if anchor is not None:
                    line_num = content[:content.find(anchor)].count('\n') + 1
                    new_content = content.replace(anchor, edit.new_text, 1)
                    if self._editor_ref.set_file_content(fp, new_content,
                                                          save_to_disk=False):
                        applied += 1
                        self._track_ai_edited_file(edit.filename)
                    else:
                        errors.append(f"✗ Could not write {edit.filename}")
                else:
                    errors.append(
                        f"✗ Anchor not found in {edit.filename} — "
                        f"copy the change manually or ask AI to retry")
            elif edit.operation in ("insert_before", "insert_after"):
                files = self._editor_ref.get_all_files()
                content = files.get(fp, "")
                # Re-validate anchor at apply time
                anchor = None
                if edit.matched_text and edit.matched_text in content:
                    anchor = edit.matched_text
                elif edit.old_text and edit.old_text in content:
                    anchor = edit.old_text
                else:
                    norm_matches = _find_normalized_matches(content, edit.old_text)
                    if norm_matches:
                        start, end = norm_matches[0]
                        anchor = content[start:end]
                if anchor is not None:
                    if edit.operation == "insert_before":
                        replacement = edit.new_text + "\n" + anchor
                    else:
                        replacement = anchor + "\n" + edit.new_text
                    new_content = content.replace(anchor, replacement, 1)
                    if self._editor_ref.set_file_content(fp, new_content,
                                                          save_to_disk=False):
                        applied += 1
                        self._track_ai_edited_file(edit.filename)
                    else:
                        errors.append(f"✗ Could not write {edit.filename}")
                else:
                    errors.append(
                        f"✗ Anchor not found in {edit.filename} — "
                        f"copy the change manually or ask AI to retry")
            elif edit.operation == "create_file":
                # create_file but file is already open — replace content
                if self._editor_ref.set_file_content(fp, edit.new_text):
                    applied += 1
                    self._track_ai_edited_file(edit.filename)
                else:
                    errors.append(f"✗ Could not write: {edit.filename}")
            elif edit.operation == "selection_replace":
                # Selection-based edit — replace using stored coordinates
                sel = self._selection_edit
                if sel and fp:
                    editor_w = self._editor_ref.tabs.currentWidget()
                    file_matches = (
                        self._editor_ref.current_file() == sel['file_path'])
                    if editor_w and file_matches and hasattr(editor_w, 'setSelection'):
                        # Safety check: verify text at stored range still matches
                        lf, cf = sel['line_from'], sel['col_from']
                        lt, ct = sel['line_to'], sel['col_to']
                        editor_w.setSelection(lf, cf, lt, ct)
                        current_sel = editor_w.selectedText()
                        if current_sel == sel['original_text']:
                            editor_w.replaceSelectedText(edit.new_text)
                            applied += 1
                            self._track_ai_edited_file(edit.filename)
                            # Mark buffer dirty (disk write on explicit Save)
                            if hasattr(editor_w, 'setModified'):
                                editor_w.setModified(True)
                            self._editor_ref._mark_tab_dirty(fp)
                        else:
                            # Selection shifted — fall back to search_replace
                            files = self._editor_ref.get_all_files()
                            content = files.get(fp, "")
                            if edit.old_text and edit.old_text in content:
                                new_content = content.replace(
                                    edit.old_text, edit.new_text, 1)
                                if self._editor_ref.set_file_content(
                                        fp, new_content,
                                        save_to_disk=False):
                                    applied += 1
                                    self._track_ai_edited_file(edit.filename)
                                else:
                                    errors.append(
                                        f"✗ Could not write {edit.filename}")
                            else:
                                errors.append(
                                    f"✗ Selection changed since prompt was sent. "
                                    f"Copy the replacement manually.")
                    else:
                        # File not active — fall back to search_replace
                        files = self._editor_ref.get_all_files()
                        content = files.get(fp, "")
                        if edit.old_text and edit.old_text in content:
                            new_content = content.replace(
                                edit.old_text, edit.new_text, 1)
                            if self._editor_ref.set_file_content(fp, new_content,
                                                                  save_to_disk=False):
                                applied += 1
                                self._track_ai_edited_file(edit.filename)
                            else:
                                errors.append(
                                    f"✗ Could not write {edit.filename}")
                        else:
                            errors.append(
                                f"✗ Original selection not found in "
                                f"{edit.filename}")
                self._selection_edit = None

        parts = [f"Applied {applied}/{applied + len(errors)} change{'s' if applied != 1 else ''}."]
        if rejected:
            parts.append(f"Rejected {rejected}.")
        if skipped:
            parts.append(f"Skipped {skipped} blocked.")
        if errors:
            parts.extend(errors)
        self._add_info_msg(" ".join(parts),
                           C['fg_ok'] if not errors else C['fg_warn'])
        self.apply_bar.hide()
        self._pending_edits = []
        self._file_acceptance = {}
        self._clear_apply_file_rows()

        # Notify MainWindow to refresh file browser after creates/edits
        if applied > 0:
            self.edits_applied.emit()
            # Rebuild symbol index after edits (non-blocking)
            QTimer.singleShot(0, self._build_symbol_index)
            # Show undo button and recompile bar
            self._undo_btn.setVisible(bool(self._apply_snapshot))
            if self._error_diagnostics:
                self.recompile_bar.show()
            elif self._apply_snapshot:
                # No diagnostics but we have a snapshot — show recompile bar
                # just for the undo button
                self.recompile_bar.show()
        else:
            self._apply_snapshot.clear()

    def _undo_last_apply(self):
        """Revert files to their pre-apply content using the snapshot."""
        if not self._apply_snapshot or not self._editor_ref:
            return
        restored = 0
        for fpath, original in self._apply_snapshot.items():
            if self._editor_ref.set_file_content(fpath, original,
                                                  save_to_disk=False):
                restored += 1
        self._apply_snapshot.clear()
        self._undo_btn.hide()
        self.recompile_bar.hide()
        n = restored
        self._add_info_msg(
            f"Reverted {n} file{'s' if n != 1 else ''} to pre-apply state.",
            C['fg_warn'])

    def _apply_and_compile(self):
        """Apply all edits then trigger a compile."""
        self._apply_all_edits()
        # Defer compile so editor content updates propagate first
        self.recompile_bar.hide()
        QTimer.singleShot(100, self.recompile_requested.emit)

    def _on_recompile_clicked(self):
        """Handle Recompile button click."""
        self.recompile_bar.hide()
        self.recompile_requested.emit()

    def _clear_apply_file_rows(self):
        """Remove dynamic per-file labels from the apply bar."""
        while self._apply_file_rows_layout.count():
            item = self._apply_file_rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _build_edit_diff_html(self, edit):
        """Build an HTML diff view of old_text vs new_text using difflib."""
        import difflib
        if edit.operation in ("create_file", "replace_file"):
            # For file-level ops, show new content as all additions
            lines = []
            for line in (edit.new_text or "").splitlines():
                lines.append(f'<span style="color:#7ee0d8;">+ {html.escape(line)}</span>')
            diff_body = "<br>".join(lines) if lines else "<em>empty</em>"
        else:
            old_lines = (edit.old_text or "").splitlines()
            new_lines = (edit.new_text or "").splitlines()
            diff = difflib.unified_diff(old_lines, new_lines, n=3, lineterm="")
            lines = []
            for line in diff:
                if line.startswith('---') or line.startswith('+++'):
                    continue  # skip file headers
                if line.startswith('@@'):
                    lines.append(
                        f'<span style="color:{C["fg_dim"]};">{html.escape(line)}</span>')
                elif line.startswith('-'):
                    lines.append(
                        f'<span style="color:#f08080;">{html.escape(line)}</span>')
                elif line.startswith('+'):
                    lines.append(
                        f'<span style="color:#7ee0d8;">{html.escape(line)}</span>')
                else:
                    lines.append(
                        f'<span style="color:{C["fg_dim"]};">{html.escape(line)}</span>')
            diff_body = "<br>".join(lines) if lines else "<em>no changes</em>"
        return (f'<div style="font-family:Menlo,Monaco,Courier New,monospace;'
                f'font-size:12px;white-space:pre;line-height:1.4;">'
                f'{diff_body}</div>')

    def _populate_apply_bar(self, edits):
        """Group edits by file, reset acceptance state, and populate the apply bar."""
        self._file_acceptance = {}  # reset on each new set of edits
        self._edit_expanded = {}    # track which edit indices are expanded
        for e in edits:
            e._user_rejected = False  # init per-edit rejection tracking
        self._refresh_apply_summary()
        self._refresh_file_rows()
        self.apply_bar.show()

    def _refresh_apply_summary(self):
        """Update the header summary label and Apply button count."""
        edits = self._pending_edits
        n_total = len(edits)
        n_accepted = sum(1 for e in edits
                         if not e.blocked
                         and self._file_acceptance.get(e.filename) is not False)
        from collections import OrderedDict
        nf = len(OrderedDict((e.filename, None) for e in edits))
        summary = f"{n_total} edit{'s' if n_total != 1 else ''} in {nf} file{'s' if nf != 1 else ''}"
        n_excluded = n_total - n_accepted
        if n_excluded:
            summary += f" ({n_excluded} excluded)"
        self.apply_label.setText(summary)
        # Update Apply button text with count
        self.apply_all_btn.setText(
            f"Replace {n_accepted} of {n_total}" if n_excluded else "Replace")
        self.apply_all_btn.setEnabled(n_accepted > 0)
        self._apply_compile_btn.setEnabled(n_accepted > 0)
        if self._error_diagnostics:
            self._intent_badge.show()
        else:
            self._intent_badge.hide()

    def _refresh_file_rows(self):
        """Rebuild per-file rows with per-edit accept/reject controls."""
        self._clear_apply_file_rows()
        from collections import OrderedDict
        by_file = OrderedDict()
        for i, edit in enumerate(self._pending_edits):
            by_file.setdefault(edit.filename, []).append((i, edit))

        _BTN_SMALL = (f"background:{C['bg_input']};color:{C['fg']};"
                      f"border:1px solid {C['border_light']};border-radius:3px;"
                      f"padding:1px 8px;{FONT_SMALL}")
        _BTN_ACCEPT_ON = (f"background:{C['teal']};color:white;border:none;"
                          f"border-radius:3px;padding:1px 8px;{FONT_SMALL}")
        _BTN_REJECT_ON = (f"background:{C['fg_err']};color:white;border:none;"
                          f"border-radius:3px;padding:1px 8px;{FONT_SMALL}")

        for filename, indexed_edits in by_file.items():
            file_state = self._file_acceptance.get(filename)  # True/False/None
            count = len(indexed_edits)
            has_new = any(e.operation == "create_file" for _, e in indexed_edits)
            has_replace = any(e.operation == "replace_file" for _, e in indexed_edits)

            # File header row: filename + file-level Accept All / Reject All
            file_row = QWidget()
            file_layout = QHBoxLayout(file_row)
            file_layout.setContentsMargins(0, 2, 0, 0)
            file_layout.setSpacing(4)

            label_text = f"{filename} ({count} edit{'s' if count != 1 else ''})"
            if has_new:
                label_text += " \u2014 new file"
            elif has_replace:
                label_text += " \u2014 replace"
            if file_state is True:
                label_text = "\u2713 " + label_text
                label_color = C['fg_ok']
            elif file_state is False:
                label_text = "\u2717 " + label_text
                label_color = C['fg_dim']
            else:
                label_color = C['fg']

            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color:{label_color};{FONT_SMALL}font-weight:bold;")
            file_layout.addWidget(lbl)
            file_layout.addStretch()

            all_blocked_by_validation = all(
                e.blocked and any("blocked:" in w for w in e.warnings)
                for _, e in indexed_edits)
            accept_all = QPushButton("Accept All" if file_state is not True else "\u2713 All")
            accept_all.setStyleSheet(_BTN_ACCEPT_ON if file_state is True else _BTN_SMALL)
            accept_all.setEnabled(not all_blocked_by_validation)
            accept_all.clicked.connect(
                lambda checked, fn=filename: self._on_file_accept(fn))
            file_layout.addWidget(accept_all)

            reject_all = QPushButton("Reject All" if file_state is not False else "\u2717 All")
            reject_all.setStyleSheet(_BTN_REJECT_ON if file_state is False else _BTN_SMALL)
            reject_all.clicked.connect(
                lambda checked, fn=filename: self._on_file_reject(fn))
            file_layout.addWidget(reject_all)

            self._apply_file_rows_layout.addWidget(file_row)

            # Per-edit rows (hidden if entire file is rejected)
            if file_state is not False:
                for idx, edit in indexed_edits:
                    edit_row = QWidget()
                    el = QHBoxLayout(edit_row)
                    el.setContentsMargins(16, 0, 0, 0)  # indent under file
                    el.setSpacing(4)

                    # Description: first line of new_text, truncated
                    if edit.operation == "search_replace" and edit.new_text:
                        first_line = edit.new_text.split('\n', 1)[0].strip()
                        desc = first_line[:60] + ("\u2026" if len(first_line) > 60 else "")
                    elif edit.operation == "create_file":
                        desc = "create file"
                    elif edit.operation == "replace_file":
                        desc = "replace file content"
                    else:
                        desc = edit.edit_type

                    # Blocked by validation vs user-rejected
                    user_rejected = getattr(edit, '_user_rejected', False)
                    validation_blocked = edit.blocked and not user_rejected

                    if user_rejected:
                        prefix = "\u2717"
                        desc_color = C['fg_dim']
                    elif validation_blocked:
                        prefix = "\u26d4"
                        desc_color = C['fg_err']
                    else:
                        prefix = "\u2713"
                        desc_color = C['fg_ok']

                    desc_label = QLabel(f"{prefix} {desc}")
                    desc_label.setStyleSheet(f"color:{desc_color};{FONT_SMALL}")
                    el.addWidget(desc_label)
                    el.addStretch()

                    # Expand toggle for diff view
                    is_expanded = self._edit_expanded.get(idx, False)
                    expand_btn = QPushButton("\u25bc" if is_expanded else "\u25b6")
                    expand_btn.setFixedSize(20, 20)
                    expand_btn.setStyleSheet(
                        f"background:transparent;color:{C['fg_dim']};"
                        f"border:none;font-size:10px;")
                    expand_btn.setToolTip("Show diff" if not is_expanded else "Hide diff")
                    expand_btn.clicked.connect(
                        lambda checked, i=idx: self._toggle_edit_diff(i))
                    el.addWidget(expand_btn)

                    if not validation_blocked:
                        if user_rejected:
                            undo_btn = QPushButton("Accept")
                            undo_btn.setStyleSheet(_BTN_SMALL)
                            undo_btn.clicked.connect(
                                lambda checked, i=idx: self._on_edit_accept(i))
                            el.addWidget(undo_btn)
                        else:
                            rej_btn = QPushButton("Reject")
                            rej_btn.setStyleSheet(_BTN_SMALL)
                            rej_btn.clicked.connect(
                                lambda checked, i=idx: self._on_edit_reject(i))
                            el.addWidget(rej_btn)

                    self._apply_file_rows_layout.addWidget(edit_row)

                    # Inline diff panel (shown when expanded)
                    if is_expanded:
                        diff_widget = QTextEdit()
                        diff_widget.setReadOnly(True)
                        diff_widget.setHtml(self._build_edit_diff_html(edit))
                        diff_widget.setStyleSheet(
                            f"QTextEdit {{ background:{C['bg_input']};"
                            f"border:1px solid {C['border_light']};"
                            f"border-left:3px solid {C['teal']};"
                            f"color:{C['fg']};padding:6px;"
                            f"margin:0 0 0 16px; }}")
                        diff_widget.setVerticalScrollBarPolicy(
                            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                        diff_widget.setHorizontalScrollBarPolicy(
                            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                        diff_widget.setMaximumHeight(200)
                        # Auto-size height to content, up to max
                        doc_h = int(diff_widget.document().size().height()) + 16
                        diff_widget.setFixedHeight(min(doc_h, 200))
                        self._apply_file_rows_layout.addWidget(diff_widget)

                    # Warnings for this edit
                    for warning in edit.warnings:
                        wpre = "\u26d4" if edit.blocked else "\u26a0"
                        wcolor = C['fg_err'] if edit.blocked else C['fg_warn']
                        warn_label = QLabel(f"    {wpre} {warning}")
                        warn_label.setStyleSheet(f"color:{wcolor};{FONT_SMALL}")
                        self._apply_file_rows_layout.addWidget(warn_label)

    def _on_file_accept(self, filename):
        """Accept all edits in a file group."""
        current = self._file_acceptance.get(filename)
        if current is True:
            self._file_acceptance[filename] = None
        else:
            self._file_acceptance[filename] = True
            # Undo any per-edit rejections for this file
            for e in self._pending_edits:
                if e.filename == filename and getattr(e, '_user_rejected', False):
                    e._user_rejected = False
                    e.blocked = False
        self._refresh_apply_summary()
        self._refresh_file_rows()

    def _on_file_reject(self, filename):
        """Reject all edits in a file group."""
        current = self._file_acceptance.get(filename)
        self._file_acceptance[filename] = None if current is False else False
        self._refresh_apply_summary()
        self._refresh_file_rows()

    def _on_edit_reject(self, edit_idx):
        """Reject an individual edit by index."""
        edit = self._pending_edits[edit_idx]
        edit.blocked = True
        edit._user_rejected = True
        self._refresh_apply_summary()
        self._refresh_file_rows()

    def _on_edit_accept(self, edit_idx):
        """Re-accept a previously user-rejected edit."""
        edit = self._pending_edits[edit_idx]
        edit.blocked = False
        edit._user_rejected = False
        self._refresh_apply_summary()
        self._refresh_file_rows()

    def _toggle_edit_diff(self, edit_idx):
        """Toggle inline diff visibility for a specific edit."""
        self._edit_expanded[edit_idx] = not self._edit_expanded.get(edit_idx, False)
        self._refresh_file_rows()

    def _dismiss_edits(self):
        self.apply_bar.hide()
        self._pending_edits = []
        self._file_acceptance = {}
        self._edit_expanded = {}
        self._clear_apply_file_rows()

    def clear_chat(self):
        # Remove all message widgets from the chat layout (keep the stretch)
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._current_ai_widget = None
        self._current_ai_wrapper = None
        self._conversation = [{"role": "system", "content": self._build_system_prompt()}]
        self.apply_bar.hide()
        self.fix_continuation_bar.hide()
        self._pending_edits = []
        self._file_acceptance = {}
        self._selection_mode = False
        self._selection_prefilled = False
        self._selection_edit = None
        self._ai_edited_files.clear()
        self._working_set.clear()
        self._update_context_bar()
        self.chat_cleared.emit()

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
            f"padding-right:6px;background:transparent;border:none;")
        vl.addWidget(speaker)
        # Bubble row
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        left_spacer = QWidget()
        left_spacer.setFixedWidth(80)
        left_spacer.setStyleSheet("background:transparent;border:none;")
        row.addWidget(left_spacer)
        bubble = QFrame()
        bubble.setStyleSheet(
            f"QFrame {{ background-color:{C['bg_input']}; border-radius:14px; }}")
        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(16, 12, 16, 12)
        bl.setSpacing(8)
        # Text label
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setTextFormat(Qt.TextFormat.PlainText)
        text_label.setStyleSheet(
            f"color:{C['fg_head']};{FONT_CHAT}background:transparent;border:none;")
        text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        bl.addWidget(text_label)
        if code:
            # Expandable code block inside the bubble
            code_label = QLabel(code)
            code_label.setWordWrap(False)
            code_label.setStyleSheet(
                f"background-color:{C['bg']};color:{C['fg']};{FONT_CODE}"
                f"padding:8px;border:none;")
            code_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            code_scroll = QScrollArea()
            code_scroll.setWidget(code_label)
            code_scroll.setWidgetResizable(False)
            code_scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll_ss = (
                f"QScrollArea{{background-color:{C['bg']};border-radius:8px;border:none;}}"
                f"QScrollBar:horizontal{{background:{C['bg']};height:6px;}}"
                f"QScrollBar::handle:horizontal{{background:{C['border_light']};"
                f"border-radius:3px;min-width:20px;}}"
                f"QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal"
                f"{{width:0px;}}"
                f"QScrollBar:vertical{{background:{C['bg']};width:6px;}}"
                f"QScrollBar::handle:vertical{{background:{C['border_light']};"
                f"border-radius:3px;min-height:20px;}}"
                f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical"
                f"{{height:0px;}}")
            code_scroll.setStyleSheet(scroll_ss)
            natural_h = code_label.sizeHint().height() + 10
            collapsed_h = 120
            expanded_max = 500
            if natural_h <= collapsed_h:
                # Short code — show at natural height, no toggle needed
                code_scroll.setFixedHeight(natural_h)
                code_scroll.setVerticalScrollBarPolicy(
                    Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                bl.addWidget(code_scroll)
            else:
                # Tall code — start collapsed with expand/collapse toggle
                code_scroll.setFixedHeight(collapsed_h)
                code_scroll.setVerticalScrollBarPolicy(
                    Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                bl.addWidget(code_scroll)
                toggle_btn = QPushButton("Show more")
                toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                toggle_btn.setStyleSheet(
                    f"QPushButton{{color:{C['teal']};background:transparent;"
                    f"border:none;{FONT_SMALL}padding:2px 0px;text-align:left;}}"
                    f"QPushButton:hover{{color:{C['fg_head']};}}")
                toggle_btn.setProperty("_expanded", False)
                def _toggle_code(checked, btn=toggle_btn, scr=code_scroll,
                                 nat=natural_h, col=collapsed_h, mx=expanded_max):
                    expanded = btn.property("_expanded")
                    if expanded:
                        scr.setFixedHeight(col)
                        scr.setVerticalScrollBarPolicy(
                            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                        btn.setText("Show more")
                        btn.setProperty("_expanded", False)
                    else:
                        scr.setFixedHeight(min(nat, mx))
                        scr.setVerticalScrollBarPolicy(
                            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                        btn.setText("Show less")
                        btn.setProperty("_expanded", True)
                toggle_btn.clicked.connect(_toggle_code)
                bl.addWidget(toggle_btn)
        row.addWidget(bubble)
        vl.addLayout(row)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, wrapper)
        self._scroll_to_bottom()

    def _add_ai_msg(self):
        """Add a left-aligned AI message area with model name label."""
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
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
        ai_text.document().setDocumentMargin(2)
        # Auto-resize as content grows — generous padding for QTextEdit internals
        def _resize_ai_text(te=ai_text):
            doc_height = te.document().size().height()
            te.setFixedHeight(max(30, int(doc_height) + 20))
        ai_text.document().contentsChanged.connect(_resize_ai_text)
        ai_text.setFixedHeight(30)
        vl.addWidget(ai_text)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, wrapper)
        self._current_ai_widget = ai_text
        self._current_ai_wrapper = wrapper
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
    jump_to_line = pyqtSignal(str, int)  # (filepath, line_number)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Compiler output will appear here...")
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard)

    def append_output(self, text, color=None):
        cur = self.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color or C["fg"]))
        cur.insertText(text + "\n", fmt)
        self.setTextCursor(cur); self.ensureCursorVisible()

    def clear_output(self): self.clear()

    def mouseDoubleClickEvent(self, event):
        """Double-click a compiler error line to jump to file:line."""
        cursor = self.cursorForPosition(event.pos())
        cursor.select(cursor.SelectionType.LineUnderCursor)
        line_text = cursor.selectedText().strip()
        m = _GCC_DIAG_RE.match(line_text)
        if m:
            self.jump_to_line.emit(m.group(1), int(m.group(2)))
        else:
            super().mouseDoubleClickEvent(event)


# =============================================================================
# Diagnostic Panel — structured compiler error/warning rows
# =============================================================================

class DiagnosticPanel(QWidget):
    """Table of parsed compiler diagnostics with clickable file:line navigation."""
    navigate_requested = pyqtSignal(str, int)  # file path, line number

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._diagnostics = []
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["", "File", "Line", "Message"])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(22)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.resizeSection(0, 24)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(1, 160)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(2, 48)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background:{C['bg_dark']};color:{C['fg']};
                border:1px solid {C['border']};{FONT_BODY}
                gridline-color:{C['border']};
            }}
            QTableWidget::item {{
                padding:2px 4px;border:none;
            }}
            QTableWidget::item:selected {{
                background:{C['bg_hover']};color:{C['fg']};
            }}
            QHeaderView::section {{
                background:{C['bg']};color:{C['fg_dim']};
                {FONT_SMALL}border:none;
                padding:2px 4px;border-right:1px solid {C['border']};
            }}
        """)
        self._table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

    def populate(self, diagnostics):
        """Fill table from list[StructuredDiagnostic]."""
        self._diagnostics = list(diagnostics)
        self._table.setRowCount(0)
        severity_map = {
            "error":   ("\u2715", C['fg_err']),
            "warning": ("\u26a0", C['fg_warn']),
            "note":    ("\u2139", C['fg_dim']),
        }
        for diag in self._diagnostics:
            row = self._table.rowCount()
            self._table.insertRow(row)
            # Column 0: severity icon
            icon_char, icon_color = severity_map.get(
                diag.severity, ("\u00b7", C['fg_dim']))
            icon_item = QTableWidgetItem(icon_char)
            icon_item.setForeground(QColor(icon_color))
            icon_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            icon_item.setFlags(
                icon_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, 0, icon_item)
            # Column 1: file basename
            fname = os.path.basename(diag.file) if diag.file else ""
            file_item = QTableWidgetItem(fname)
            file_item.setForeground(QColor(C['fg']))
            if diag.file:
                file_item.setToolTip(diag.file)
            self._table.setItem(row, 1, file_item)
            # Column 2: line number
            line_str = str(diag.line) if diag.line else ""
            line_item = QTableWidgetItem(line_str)
            line_item.setForeground(QColor(C['fg_dim']))
            line_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 2, line_item)
            # Column 3: message
            msg_item = QTableWidgetItem(diag.message)
            msg_item.setForeground(QColor(C['fg']))
            self._table.setItem(row, 3, msg_item)

    def _on_double_click(self, row, col):
        if row < 0 or row >= len(self._diagnostics):
            return
        diag = self._diagnostics[row]
        if diag.file and diag.line:
            self.navigate_requested.emit(diag.file, diag.line)

    def summary_text(self):
        errors = sum(1 for d in self._diagnostics if d.severity == "error")
        warnings = sum(1 for d in self._diagnostics if d.severity == "warning")
        if not self._diagnostics:
            return ""
        parts = []
        if errors:
            parts.append(f"{errors} error{'s' if errors != 1 else ''}")
        if warnings:
            parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
        return ", ".join(parts)


# =============================================================================
# Serial Monitor
# =============================================================================

class HistoryLineEdit(QLineEdit):
    """QLineEdit with Up/Down arrow command history (terminal-style)."""
    _MAX_HISTORY = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._history_index: int = -1
        self._pending: str = ""

    def add_to_history(self, text: str):
        text = text.strip()
        if not text:
            return
        if self._history and self._history[-1] == text:
            return
        self._history.append(text)
        if len(self._history) > self._MAX_HISTORY:
            self._history.pop(0)
        self._history_index = -1
        self._pending = ""

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Up:
            if not self._history:
                return
            if self._history_index == -1:
                self._pending = self.text()
                self._history_index = len(self._history) - 1
            elif self._history_index > 0:
                self._history_index -= 1
            self.setText(self._history[self._history_index])
            return
        elif event.key() == Qt.Key.Key_Down:
            if self._history_index == -1:
                return
            if self._history_index < len(self._history) - 1:
                self._history_index += 1
                self.setText(self._history[self._history_index])
            else:
                self._history_index = -1
                self.setText(self._pending)
            return
        else:
            if self._history_index != -1:
                self._history_index = -1
            super().keyPressEvent(event)


class SerialReaderThread(QThread):
    """Background thread that reads from serial port and emits data."""
    data_received = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._serial = None
        self._running = False

    def configure(self, port, baud):
        import serial as _serial_mod
        self._serial = _serial_mod.Serial(port, baud, timeout=0.1)
        self._running = True

    def run(self):
        while self._running and self._serial and self._serial.is_open:
            try:
                waiting = self._serial.in_waiting
                if waiting > 0:
                    data = self._serial.read(waiting)
                    if data:
                        self.data_received.emit(data)
                else:
                    self.msleep(20)
            except Exception as e:
                if self._running:
                    self.error_occurred.emit(str(e))
                break

    def stop(self):
        self._running = False
        self.wait(1000)
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None

    def write_data(self, data: bytes):
        if self._serial and self._serial.is_open:
            try:
                self._serial.write(data)
            except Exception as e:
                self.error_occurred.emit(str(e))


class SerialMonitor(QWidget):
    """Full serial monitor panel with threaded reader, toolbar, output, and input row."""
    serial_line_received = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reader = None
        self._connected = False
        self._timestamps = False
        self._hex_mode = False
        self._hex_offset = 0
        self._hex_buffer = b""  # Buffer for incomplete hex lines
        self._auto_scroll = True
        self._line_buffer = ""  # Buffer for incomplete lines
        self._rx_count = 0
        self._tx_count = 0
        self._msg_count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Panel header ---
        header, title, hl = _make_panel_header("SERIAL MONITOR")
        layout.addWidget(header)

        # --- Toolbar row ---
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background:{C['bg']};border-bottom:1px solid {C['border']};")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(10, 6, 10, 6)
        tb_layout.setSpacing(8)

        port_lbl = QLabel("Port")
        port_lbl.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}background:transparent;border:none;")
        tb_layout.addWidget(port_lbl)
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setMinimumWidth(160)
        tb_layout.addWidget(self.port_combo)

        refresh_btn = QPushButton("↻")
        refresh_btn.setToolTip("Refresh ports")
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setStyleSheet(BTN_GHOST)
        refresh_btn.clicked.connect(self.refresh_ports)
        tb_layout.addWidget(refresh_btn)

        baud_lbl = QLabel("Baud")
        baud_lbl.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}background:transparent;border:none;")
        tb_layout.addWidget(baud_lbl)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["300", "1200", "2400", "4800", "9600", "19200",
                                   "38400", "57600", "115200", "250000", "500000", "1000000"])
        self.baud_combo.setCurrentText("115200")
        tb_layout.addWidget(self.baud_combo)

        tb_layout.addSpacing(8)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setStyleSheet(BTN_PRIMARY)
        self.connect_btn.setFixedWidth(90)
        self.connect_btn.clicked.connect(self._toggle_connection)
        tb_layout.addWidget(self.connect_btn)

        tb_layout.addSpacing(8)

        self.ts_check = QPushButton("⏱")
        self.ts_check.setToolTip("Toggle timestamps")
        self.ts_check.setCheckable(True)
        self.ts_check.setFixedSize(28, 28)
        self.ts_check.setStyleSheet(BTN_GHOST)
        self.ts_check.toggled.connect(self._toggle_timestamps)
        tb_layout.addWidget(self.ts_check)

        self.hex_check = QPushButton("Hex")
        self.hex_check.setToolTip("Toggle hex display")
        self.hex_check.setCheckable(True)
        self.hex_check.setFixedHeight(28)
        self.hex_check.setStyleSheet(BTN_GHOST)
        self.hex_check.toggled.connect(self._toggle_hex)
        tb_layout.addWidget(self.hex_check)

        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(BTN_GHOST)
        clear_btn.clicked.connect(self._clear_output)
        tb_layout.addWidget(clear_btn)

        tb_layout.addStretch()

        self._counter_label = QLabel("RX: 0  TX: 0  Msgs: 0")
        self._counter_label.setStyleSheet(
            f"color:{C['fg_muted']};font-family:monospace;font-size:11px;"
            f"background:transparent;border:none;")
        tb_layout.addWidget(self._counter_label)

        layout.addWidget(toolbar)

        # --- Output area ---
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Serial output will appear here...")
        self.output.setStyleSheet(
            f"background:{C['bg_dark']};color:{C['fg']};border:none;{FONT_CODE}padding:8px;")
        self.output.setMaximumBlockCount(10000)
        # Track user scroll position
        self.output.verticalScrollBar().valueChanged.connect(self._on_scroll)
        layout.addWidget(self.output, stretch=1)

        # --- Input row ---
        input_row = QWidget()
        input_row.setStyleSheet(f"background:{C['bg']};border-top:1px solid {C['border']};")
        ir_layout = QHBoxLayout(input_row)
        ir_layout.setContentsMargins(10, 6, 10, 6)
        ir_layout.setSpacing(8)

        self.send_input = HistoryLineEdit()
        self.send_input.setPlaceholderText("Type message to send...")
        self.send_input.returnPressed.connect(self._send)
        ir_layout.addWidget(self.send_input, stretch=1)

        self.line_ending_combo = QComboBox()
        self.line_ending_combo.addItems(["NL", "CR", "CR+NL", "None"])
        self.line_ending_combo.setCurrentText("NL")
        self.line_ending_combo.setFixedWidth(70)
        ir_layout.addWidget(self.line_ending_combo)

        send_btn = QPushButton("Send")
        send_btn.setStyleSheet(BTN_PRIMARY)
        send_btn.clicked.connect(self._send)
        ir_layout.addWidget(send_btn)

        layout.addWidget(input_row)

    def refresh_ports(self):
        """Scan for available serial ports."""
        current = self.port_combo.currentText()
        self.port_combo.clear()
        # Try arduino-cli first for accurate detection
        try:
            r = subprocess.run(["arduino-cli", "board", "list", "--format", "json"],
                               capture_output=True, text=True, timeout=10)
            if r.stdout:
                d = json.loads(r.stdout)
                pts = d if isinstance(d, list) else d.get("detected_ports", [])
                for pi in pts:
                    a = pi.get("port", {}).get("address", "")
                    if a:
                        self.port_combo.addItem(a)
        except Exception:
            pass
        # Fallback: glob for common serial device paths
        for pat in ["/dev/cu.usbmodem*", "/dev/ttyACM*", "/dev/cu.usbserial*"]:
            for p in glob.glob(pat):
                if self.port_combo.findText(p) == -1:
                    self.port_combo.addItem(p)
        # Restore previous selection if still available
        if current:
            idx = self.port_combo.findText(current)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)

    def _toggle_connection(self):
        if self._connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port = self.port_combo.currentText().strip()
        baud = self.baud_combo.currentText().strip()
        if not port:
            self._append_system("No port selected.")
            return
        try:
            self._reader = SerialReaderThread(self)
            self._reader.data_received.connect(self._on_data)
            self._reader.error_occurred.connect(self._on_error)
            self._reader.configure(port, int(baud))
            self._reader.start()
            self._connected = True
            self._line_buffer = ""
            self._hex_buffer = b""
            self._hex_offset = 0
            self._rx_count = 0
            self._tx_count = 0
            self._msg_count = 0
            self._update_counters()
            self.connect_btn.setText("Disconnect")
            self.connect_btn.setStyleSheet(BTN_DANGER)
            self.port_combo.setEnabled(False)
            self.baud_combo.setEnabled(False)
            self._append_system(f"Connected to {port} at {baud} baud")
            self.connection_changed.emit(True)
        except ImportError:
            self._append_system("pyserial not installed. Run: pip install pyserial")
        except Exception as e:
            self._append_system(f"Connection failed: {e}")

    def _disconnect(self):
        if self._reader:
            self._reader.stop()
            self._reader = None
        self._connected = False
        self._line_buffer = ""
        self.connect_btn.setText("Connect")
        self.connect_btn.setStyleSheet(BTN_PRIMARY)
        self.port_combo.setEnabled(True)
        self.baud_combo.setEnabled(True)
        self._append_system("Disconnected")
        self.connection_changed.emit(False)

    def _on_data(self, data: bytes):
        # Update counters
        self._rx_count += len(data)
        self._msg_count += data.count(b'\n')
        self._update_counters()

        if self._hex_mode:
            self._hex_buffer += data
            # Process complete 16-byte rows
            while len(self._hex_buffer) >= 16:
                chunk = self._hex_buffer[:16]
                self._hex_buffer = self._hex_buffer[16:]
                self._append_raw(self._format_hex_line(chunk))
                self._hex_offset += 16
            # Flush partial row on newline boundary
            if self._hex_buffer and b'\n' in data:
                chunk = self._hex_buffer
                self._hex_buffer = b""
                self._append_raw(self._format_hex_line(chunk))
                self._hex_offset += len(chunk)
        else:
            text = data.decode("utf-8", errors="replace")
            # Buffer incomplete lines for timestamp-accurate display
            self._line_buffer += text
            while "\n" in self._line_buffer:
                line, self._line_buffer = self._line_buffer.split("\n", 1)
                self._append_line(line)
            # If buffer has content but no newline yet, show it after a short delay
            if self._line_buffer and "\r" in self._line_buffer:
                line = self._line_buffer.rstrip("\r")
                self._line_buffer = ""
                self._append_line(line)

    def _append_line(self, text):
        self.serial_line_received.emit(text)
        if self._timestamps:
            from datetime import datetime
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.output.appendPlainText(f"[{ts}] {text}")
        else:
            self.output.appendPlainText(text)
        if self._auto_scroll:
            sb = self.output.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _append_system(self, msg):
        self.output.appendPlainText(f"--- {msg} ---")
        if self._auto_scroll:
            sb = self.output.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _on_error(self, msg):
        self._append_system(f"Error: {msg}")
        self._disconnect()

    def _on_scroll(self, value):
        sb = self.output.verticalScrollBar()
        # Auto-scroll if user is near the bottom
        self._auto_scroll = value >= sb.maximum() - 10

    def _toggle_timestamps(self, checked):
        self._timestamps = checked

    def _toggle_hex(self, checked):
        self._hex_mode = checked
        if checked:
            # Flush text buffer when switching to hex
            if self._line_buffer:
                self._append_line(self._line_buffer)
                self._line_buffer = ""
        else:
            # Flush hex buffer when switching to text
            if self._hex_buffer:
                self._append_raw(self._format_hex_line(self._hex_buffer))
                self._hex_offset += len(self._hex_buffer)
                self._hex_buffer = b""

    def _format_hex_line(self, data: bytes) -> str:
        """Format up to 16 bytes as a hex dump line."""
        n = len(data)
        # Offset
        line = f"{self._hex_offset:08X}  "
        # First 8 hex bytes
        hex_parts = []
        for i in range(8):
            hex_parts.append(f"{data[i]:02X}" if i < n else "..")
        line += " ".join(hex_parts) + "  "
        # Next 8 hex bytes
        hex_parts = []
        for i in range(8, 16):
            hex_parts.append(f"{data[i]:02X}" if i < n else "..")
        line += " ".join(hex_parts) + "  "
        # ASCII column
        ascii_str = ""
        for i in range(n):
            b = data[i]
            ascii_str += chr(b) if 0x20 <= b < 0x7F else "."
        ascii_str += "." * (16 - n)
        line += f"|{ascii_str}|"
        return line

    def _append_raw(self, text):
        """Append text to output without timestamp processing."""
        self.output.appendPlainText(text)
        if self._auto_scroll:
            sb = self.output.verticalScrollBar()
            sb.setValue(sb.maximum())

    @staticmethod
    def _format_si(value: int) -> str:
        """Format integer with SI suffixes for readability."""
        if value < 1000:
            return str(value)
        elif value < 1_000_000:
            return f"{value / 1000:.1f}K"
        elif value < 1_000_000_000:
            return f"{value / 1_000_000:.1f}M"
        else:
            return f"{value / 1_000_000_000:.1f}G"

    def _update_counters(self):
        rx = self._format_si(self._rx_count)
        tx = self._format_si(self._tx_count)
        msgs = self._format_si(self._msg_count)
        self._counter_label.setText(f"RX: {rx}  TX: {tx}  Msgs: {msgs}")

    def _clear_output(self):
        self.output.clear()
        self._hex_offset = 0
        self._hex_buffer = b""
        self._rx_count = 0
        self._tx_count = 0
        self._msg_count = 0
        self._update_counters()

    def _send(self):
        if not self._connected or not self._reader:
            return
        text = self.send_input.text()
        if not text:
            return
        ending_map = {"NL": "\n", "CR": "\r", "CR+NL": "\r\n", "None": ""}
        ending = ending_map.get(self.line_ending_combo.currentText(), "\n")
        payload = (text + ending).encode("utf-8")
        self._reader.write_data(payload)
        self._tx_count += len(payload)
        self._update_counters()
        self.send_input.add_to_history(text)
        self.send_input.clear()

    def cleanup(self):
        """Stop reader thread. Call from MainWindow.closeEvent."""
        if self._reader:
            self._reader.stop()
            self._reader = None


# =============================================================================
# Settings Panel — Models Tab
# =============================================================================

class ModelsTab(QWidget):
    model_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        QTimer.singleShot(500, self.refresh_models)

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{C['bg_dark']};}}")

        content = QWidget()
        content.setStyleSheet(f"background:{C['bg_dark']};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ── Backend Selector Row ──────────────────────────────────────────────
        backend_row = QHBoxLayout()
        backend_row.setSpacing(8)
        t_be = QLabel("AI BACKEND"); t_be.setStyleSheet(SETTINGS_STITLE)
        backend_row.addWidget(t_be)

        self._backend_combo = QComboBox()
        self._backend_combo.addItems(["Ollama", "LM Studio (OpenAI-compatible)"])
        self._backend_combo.setCurrentIndex(1 if AI_BACKEND == "lmstudio" else 0)
        self._backend_combo.setStyleSheet(SETTINGS_COMBO)
        self._backend_combo.setFixedWidth(220)
        self._backend_combo.currentIndexChanged.connect(self._on_backend_switch)
        backend_row.addWidget(self._backend_combo)

        self._backend_url = QLineEdit()
        self._backend_url.setStyleSheet(SETTINGS_INPUT)
        self._backend_url.setPlaceholderText("Backend URL")
        self._backend_url.setText(
            LMSTUDIO_URL if AI_BACKEND == "lmstudio" else OLLAMA_URL)
        self._backend_url.editingFinished.connect(self._on_backend_url_changed)
        backend_row.addWidget(self._backend_url, stretch=1)

        test_btn = QPushButton("Test Connection"); test_btn.setStyleSheet(BTN_SM_GHOST)
        test_btn.clicked.connect(self._test_connection)
        backend_row.addWidget(test_btn)

        self._conn_status = QLabel("")
        self._conn_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        backend_row.addWidget(self._conn_status)

        layout.addLayout(backend_row)

        # ── Installed Models ──────────────────────────────────────────────────
        hdr = QHBoxLayout(); hdr.setSpacing(6)
        t_models = QLabel("INSTALLED MODELS"); t_models.setStyleSheet(SETTINGS_STITLE)
        hdr.addWidget(t_models); hdr.addStretch()
        refresh_btn = QPushButton("↻ Refresh"); refresh_btn.setStyleSheet(BTN_SM_GHOST)
        refresh_btn.clicked.connect(self.refresh_models); hdr.addWidget(refresh_btn)
        layout.addLayout(hdr)

        self.model_table = QTableWidget()
        self.model_table.setColumnCount(3)
        self.model_table.setHorizontalHeaderLabels(["Model", "Size", "Modified"])
        self.model_table.horizontalHeader().setStyleSheet(SETTINGS_TBL_HDR)
        self.model_table.setStyleSheet(SETTINGS_TABLE)
        self.model_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.model_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.model_table.setSortingEnabled(True)
        self.model_table.verticalHeader().setVisible(False)
        mhdr = self.model_table.horizontalHeader()
        mhdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        mhdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        mhdr.resizeSection(1, 80)
        mhdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        mhdr.resizeSection(2, 90)
        layout.addWidget(self.model_table)

        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        layout.addWidget(self.status)

        # ── Context Budget ────────────────────────────────────────────────────
        budget_row = QHBoxLayout(); budget_row.setSpacing(8)
        t_budget = QLabel("CONTEXT BUDGET"); t_budget.setStyleSheet(SETTINGS_STITLE)
        budget_row.addWidget(t_budget)

        self._budget_spin = QSpinBox()
        self._budget_spin.setRange(2000, 100000)
        self._budget_spin.setSingleStep(1000)
        self._budget_spin.setSuffix(" tokens")
        self._budget_spin.setValue(_load_config().get("context_budget", 12000))
        self._budget_spin.setStyleSheet(
            f"QSpinBox{{background:{C['bg_input']};color:{C['fg']};"
            f"border:1px solid {C['border_light']};border-radius:3px;padding:4px 8px;}}")
        self._budget_spin.valueChanged.connect(self._on_budget_changed)
        budget_row.addWidget(self._budget_spin)

        budget_hint = QLabel(
            "Lower for small models (4K\u20136K). Higher for large models (8K\u201312K).")
        budget_hint.setStyleSheet(f"color:{C['fg_muted']};{FONT_SMALL}")
        budget_row.addWidget(budget_hint)
        budget_row.addStretch()

        layout.addLayout(budget_row)

        layout.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # -- Backend selector methods -----------------------------------------------

    def _on_backend_switch(self, idx):
        """Handle backend combo change."""
        global AI_BACKEND, OLLAMA_URL, LMSTUDIO_URL
        is_lm = idx == 1
        AI_BACKEND = "lmstudio" if is_lm else "ollama"
        if is_lm:
            self._backend_url.setText(LMSTUDIO_URL)
        else:
            self._backend_url.setText(OLLAMA_URL)
        self._conn_status.setText("")
        cfg = _load_config()
        cfg["ai_backend"] = AI_BACKEND
        _save_config(cfg)
        self.refresh_models()
        self.model_changed.emit()

    def _on_backend_url_changed(self):
        """Handle URL field edit — update the corresponding global."""
        global OLLAMA_URL, LMSTUDIO_URL
        url = self._backend_url.text().strip().rstrip("/")
        if not url:
            return
        cfg = _load_config()
        if AI_BACKEND == "lmstudio":
            LMSTUDIO_URL = url
            cfg["lmstudio_url"] = url
        else:
            OLLAMA_URL = url
            cfg["ollama_url"] = url
        _save_config(cfg)

    def _test_connection(self):
        """Quick GET to verify the backend is reachable."""
        self._conn_status.setText("Testing…")
        self._conn_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        QApplication.processEvents()
        try:
            if AI_BACKEND == "lmstudio":
                url = f"{LMSTUDIO_URL}/v1/models"
            else:
                url = f"{OLLAMA_URL}/api/tags"
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                self._conn_status.setText("Connected")
                self._conn_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
            else:
                self._conn_status.setText(f"HTTP {resp.status_code}")
                self._conn_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")
        except Exception:
            self._conn_status.setText("Not reachable")
            self._conn_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _on_budget_changed(self, value):
        """Save context budget to config and notify."""
        cfg = _load_config()
        cfg["context_budget"] = value
        _save_config(cfg)
        # Update live WorkingSet if MainWindow has set a reference
        if hasattr(self, '_main_window') and hasattr(self._main_window, 'chat_panel'):
            self._main_window.chat_panel._working_set.budget = value

    def refresh_models(self):
        self.model_table.setRowCount(0)
        try:
            if AI_BACKEND == "lmstudio":
                r = requests.get(f"{LMSTUDIO_URL}/v1/models", timeout=5)
                if r.status_code == 200:
                    for m in r.json().get("data", []):
                        n = m.get("id", "")
                        row = self.model_table.rowCount()
                        self.model_table.insertRow(row)
                        self.model_table.setItem(row, 0, QTableWidgetItem(n))
                        self.model_table.setItem(row, 1, QTableWidgetItem("—"))
                        self.model_table.setItem(row, 2, QTableWidgetItem("—"))
            else:
                r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
                if r.status_code == 200:
                    for m in r.json().get("models", []):
                        n = m.get("name", ""); sz = m.get("size", 0)
                        ss = f"{sz/(1024**3):.1f} GB" if sz > 1024**3 else f"{sz/(1024**2):.0f} MB"
                        d = m.get("modified_at", "")[:10]
                        row = self.model_table.rowCount()
                        self.model_table.insertRow(row)
                        self.model_table.setItem(row, 0, QTableWidgetItem(n))
                        self.model_table.setItem(row, 1, QTableWidgetItem(ss))
                        self.model_table.setItem(row, 2, QTableWidgetItem(d))
        except Exception as e:
            backend = "LM Studio" if AI_BACKEND == "lmstudio" else "Ollama"
            self.status.setText(f"{backend} error: {e}")
            self.status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")



# =============================================================================
# Settings Panel — Git Tab
# =============================================================================

class GitTab(QWidget):
    """Lightweight git view inside the Settings panel.
    Branch context bar → Changes → History → Branches & Tags (2-col)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_path = None
        self._setup_ui()

    def set_project_path(self, path):
        self._project_path = path
        self._refresh()

    def _run_git(self, args):
        """Run git in project dir. Returns (stdout, success)."""
        if not self._project_path:
            return "", False
        try:
            res = subprocess.run(
                ["git"] + args, cwd=self._project_path,
                capture_output=True, text=True, timeout=8)
            return res.stdout.strip(), res.returncode == 0
        except Exception:
            return "", False

    def _setup_ui(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{C['bg_dark']};}}")

        content = QWidget(); content.setStyleSheet(f"background:{C['bg_dark']};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(20)

        # ── 1. Branch context bar ─────────────────────────────────────────────
        self._branch_bar = QFrame()
        self._branch_bar.setStyleSheet(SETTINGS_CARD)
        bb = QHBoxLayout(self._branch_bar)
        bb.setContentsMargins(12, 8, 12, 8); bb.setSpacing(8)

        bb_left = QHBoxLayout(); bb_left.setSpacing(8)
        branch_icon = QLabel("⎇")
        branch_icon.setStyleSheet(f"color:{C['teal']};font-size:15px;")
        bb_left.addWidget(branch_icon)
        self._branch_name_lbl = QLabel("—")
        self._branch_name_lbl.setStyleSheet(
            f"color:{C['teal']};font-size:15px;font-weight:600;")
        bb_left.addWidget(self._branch_name_lbl)
        self._ahead_behind_lbl = QLabel("")
        self._ahead_behind_lbl.setStyleSheet(
            f"color:{C['fg_muted']};{FONT_SMALL};font-family:Menlo,Monaco,monospace;")
        bb_left.addWidget(self._ahead_behind_lbl)
        bb.addLayout(bb_left); bb.addStretch()

        bb_btns = QHBoxLayout(); bb_btns.setSpacing(6)
        push_btn = QPushButton("Push"); push_btn.setStyleSheet(BTN_SM_SECONDARY)
        push_btn.clicked.connect(self._git_push); bb_btns.addWidget(push_btn)
        pull_btn = QPushButton("Pull"); pull_btn.setStyleSheet(BTN_SM_SECONDARY)
        pull_btn.clicked.connect(self._git_pull); bb_btns.addWidget(pull_btn)
        fetch_btn = QPushButton("↻ Fetch"); fetch_btn.setStyleSheet(BTN_SM_GHOST)
        fetch_btn.clicked.connect(self._git_fetch); bb_btns.addWidget(fetch_btn)
        bb.addLayout(bb_btns)
        layout.addWidget(self._branch_bar)

        # ── 2. Changes ───────────────────────────────────────────────────────
        changes_w = QWidget()
        ch_layout = QVBoxLayout(changes_w); ch_layout.setContentsMargins(0,0,0,0)
        ch_layout.setSpacing(8)

        ch_hdr = QHBoxLayout(); ch_hdr.setSpacing(6)
        ch_title = QLabel("CHANGES"); ch_title.setStyleSheet(SETTINGS_STITLE)
        ch_hdr.addWidget(ch_title)
        self._changes_count_lbl = QLabel("")
        self._changes_count_lbl.setStyleSheet(f"color:{C['fg_muted']};{FONT_SMALL}")
        ch_hdr.addWidget(self._changes_count_lbl); ch_hdr.addStretch()
        ch_layout.addLayout(ch_hdr)

        changes_card = QFrame(); changes_card.setStyleSheet(SETTINGS_CARD)
        changes_cl = QVBoxLayout(changes_card); changes_cl.setContentsMargins(0,0,0,0)
        self._changes_table = QTableWidget()
        self._changes_table.setColumnCount(2)
        self._changes_table.setHorizontalHeaderLabels(["St", "File"])
        self._changes_table.horizontalHeader().setStyleSheet(SETTINGS_TBL_HDR)
        self._changes_table.setStyleSheet(SETTINGS_TABLE)
        self._changes_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self._changes_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._changes_table.setSortingEnabled(True)
        self._changes_table.setMaximumHeight(160)
        self._changes_table.verticalHeader().setVisible(False)
        ct_hdr = self._changes_table.horizontalHeader()
        ct_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        ct_hdr.resizeSection(0, 36)
        ct_hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        changes_cl.addWidget(self._changes_table)
        ch_layout.addWidget(changes_card)

        commit_row = QHBoxLayout(); commit_row.setSpacing(8)
        self._commit_msg = QLineEdit()
        self._commit_msg.setPlaceholderText("Commit message…")
        self._commit_msg.setStyleSheet(SETTINGS_INPUT)
        commit_row.addWidget(self._commit_msg, stretch=1)
        commit_btn = QPushButton("Commit All"); commit_btn.setStyleSheet(BTN_SM_PRIMARY)
        commit_btn.clicked.connect(self._commit_all); commit_row.addWidget(commit_btn)
        ch_layout.addLayout(commit_row)
        self._commit_status = QLabel("")
        self._commit_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        ch_layout.addWidget(self._commit_status)
        layout.addWidget(changes_w)

        # ── 3. History ───────────────────────────────────────────────────────
        history_w = QWidget()
        hi_layout = QVBoxLayout(history_w); hi_layout.setContentsMargins(0,0,0,0)
        hi_layout.setSpacing(8)

        hi_hdr = QHBoxLayout(); hi_hdr.setSpacing(6)
        hi_title = QLabel("HISTORY"); hi_title.setStyleSheet(SETTINGS_STITLE)
        hi_hdr.addWidget(hi_title)
        self._history_branch_lbl = QLabel("")
        self._history_branch_lbl.setStyleSheet(f"color:{C['fg_muted']};{FONT_SMALL}")
        hi_hdr.addWidget(self._history_branch_lbl); hi_hdr.addStretch()
        hi_layout.addLayout(hi_hdr)

        history_card = QFrame(); history_card.setStyleSheet(SETTINGS_CARD)
        history_cl = QVBoxLayout(history_card); history_cl.setContentsMargins(0,0,0,0)
        self._history_table = QTableWidget()
        self._history_table.setColumnCount(3)
        self._history_table.setHorizontalHeaderLabels(["Hash", "Message", "Date"])
        self._history_table.horizontalHeader().setStyleSheet(SETTINGS_TBL_HDR)
        self._history_table.setStyleSheet(SETTINGS_TABLE)
        self._history_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self._history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._history_table.setSortingEnabled(True)
        self._history_table.setMaximumHeight(180)
        self._history_table.verticalHeader().setVisible(False)
        ht_hdr = self._history_table.horizontalHeader()
        ht_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        ht_hdr.resizeSection(0, 66)
        ht_hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        ht_hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        ht_hdr.resizeSection(2, 60)
        history_cl.addWidget(self._history_table)
        hi_layout.addWidget(history_card)
        layout.addWidget(history_w)

        # ── 4. Branches + Tags (2-col) ────────────────────────────────────────
        bot_row = QHBoxLayout(); bot_row.setSpacing(20)

        # -- Branches --
        br_w = QWidget()
        br_layout = QVBoxLayout(br_w); br_layout.setContentsMargins(0,0,0,0)
        br_layout.setSpacing(8)
        br_hdr = QHBoxLayout(); br_hdr.setSpacing(6)
        br_title = QLabel("BRANCHES"); br_title.setStyleSheet(SETTINGS_STITLE)
        br_hdr.addWidget(br_title); br_hdr.addStretch()
        checkout_btn = QPushButton("Checkout"); checkout_btn.setStyleSheet(BTN_SM_PRIMARY)
        checkout_btn.clicked.connect(self._checkout_selected)
        br_hdr.addWidget(checkout_btn)
        new_br_btn = QPushButton("New"); new_br_btn.setStyleSheet(BTN_SM_SECONDARY)
        new_br_btn.clicked.connect(self._new_branch); br_hdr.addWidget(new_br_btn)
        merge_btn = QPushButton("Merge"); merge_btn.setStyleSheet(BTN_SM_SECONDARY)
        merge_btn.clicked.connect(self._merge_branch); br_hdr.addWidget(merge_btn)
        br_layout.addLayout(br_hdr)

        br_card = QFrame(); br_card.setStyleSheet(SETTINGS_CARD)
        brcl = QVBoxLayout(br_card); brcl.setContentsMargins(4,4,4,4)
        self._branch_tree = QTreeWidget()
        self._branch_tree.setHeaderHidden(True)
        self._branch_tree.setStyleSheet(
            f"QTreeWidget{{background:transparent;border:none;{FONT_BODY}}}"
            f"QTreeWidget::item{{padding:4px 6px;border-radius:3px;}}"
            f"QTreeWidget::item:selected{{background:{C['bg_hover']};}}"
            f"QTreeWidget::item:hover:!selected{{background:{C['bg_hover']};}}")
        self._branch_tree.setMaximumHeight(260)
        brcl.addWidget(self._branch_tree)
        br_layout.addWidget(br_card)
        self._branch_status = QLabel("")
        self._branch_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        br_layout.addWidget(self._branch_status)
        bot_row.addWidget(br_w, stretch=1)

        # -- Tags --
        tg_w = QWidget()
        tg_layout = QVBoxLayout(tg_w); tg_layout.setContentsMargins(0,0,0,0)
        tg_layout.setSpacing(8)
        tg_hdr = QHBoxLayout(); tg_hdr.setSpacing(6)
        tg_title = QLabel("TAGS"); tg_title.setStyleSheet(SETTINGS_STITLE)
        tg_hdr.addWidget(tg_title); tg_hdr.addStretch()
        new_tag_btn = QPushButton("New Tag"); new_tag_btn.setStyleSheet(BTN_SM_SECONDARY)
        new_tag_btn.clicked.connect(self._new_tag); tg_hdr.addWidget(new_tag_btn)
        del_tag_btn = QPushButton("Delete"); del_tag_btn.setStyleSheet(BTN_SM_DANGER)
        del_tag_btn.clicked.connect(self._delete_tag); tg_hdr.addWidget(del_tag_btn)
        tg_layout.addLayout(tg_hdr)

        tg_card = QFrame(); tg_card.setStyleSheet(SETTINGS_CARD)
        tgcl = QVBoxLayout(tg_card); tgcl.setContentsMargins(4,4,4,4)
        self._tag_list = QTreeWidget()
        self._tag_list.setHeaderHidden(True)
        self._tag_list.setColumnCount(2)
        self._tag_list.setStyleSheet(
            f"QTreeWidget{{background:transparent;border:none;{FONT_BODY}}}"
            f"QTreeWidget::item{{padding:4px 6px;}}"
            f"QTreeWidget::item:selected{{background:{C['bg_hover']};}}"
            f"QTreeWidget::item:hover:!selected{{background:{C['bg_hover']};}}")
        self._tag_list.header().setStretchLastSection(True)
        tgcl.addWidget(self._tag_list)
        tg_layout.addWidget(tg_card)
        self._tag_status = QLabel("")
        self._tag_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        tg_layout.addWidget(self._tag_status)
        bot_row.addWidget(tg_w, stretch=1)

        layout.addLayout(bot_row)
        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ── Refresh helpers ───────────────────────────────────────────────────────

    def _refresh(self):
        self._refresh_branch_bar()
        self._refresh_changes()
        self._refresh_history()
        self._refresh_branches()
        self._refresh_tags()

    def _refresh_branch_bar(self):
        if not self._project_path:
            self._branch_name_lbl.setText("No project"); return
        branch, ok = self._run_git(["branch", "--show-current"])
        if not ok:
            self._branch_name_lbl.setText("No repo")
            self._ahead_behind_lbl.setText(""); return
        self._branch_name_lbl.setText(branch or "HEAD detached")
        ab_out, ab_ok = self._run_git(["rev-list", "--left-right", "--count", "HEAD...@{u}"])
        if ab_ok and ab_out:
            parts = ab_out.split()
            if len(parts) == 2:
                self._ahead_behind_lbl.setText(f"↑{parts[0]} ↓{parts[1]}"); return
        self._ahead_behind_lbl.setText("")

    def _refresh_changes(self):
        self._changes_table.setRowCount(0)
        if not self._project_path: return
        out, ok = self._run_git(["status", "--porcelain"])
        if not ok:
            self._changes_count_lbl.setText("not a repo"); return
        lines = [l for l in out.splitlines() if l.strip()]
        self._changes_count_lbl.setText(f"{len(lines)} files" if lines else "clean")
        STATUS_COLORS = {
            'D': C['fg_err_text'], 'M': C['fg_warn'],
            'A': C['teal_light'], '?': C['fg_dim'],
        }
        for line in lines:
            if len(line) < 4: continue
            status = line[:2].strip(); filename = line[3:]
            row = self._changes_table.rowCount()
            self._changes_table.insertRow(row)
            st_item = QTableWidgetItem(status)
            st_item.setForeground(QColor(STATUS_COLORS.get(
                status[0] if status else '?', C['fg'])))
            self._changes_table.setItem(row, 0, st_item)
            self._changes_table.setItem(row, 1, QTableWidgetItem(filename))
        self._history_branch_lbl.setText(f"on {self._branch_name_lbl.text()}")

    def _refresh_history(self):
        self._history_table.setRowCount(0)
        if not self._project_path: return
        out, ok = self._run_git(["log", "--pretty=format:%h|%s|%cr", "-20"])
        if not ok: return
        for line in out.splitlines():
            parts = line.split("|", 2)
            if len(parts) < 3: continue
            hash_str, msg, date = parts
            row = self._history_table.rowCount()
            self._history_table.insertRow(row)
            hi = QTableWidgetItem(hash_str)
            hi.setForeground(QColor(C['fg_warn']))
            self._history_table.setItem(row, 0, hi)
            self._history_table.setItem(row, 1, QTableWidgetItem(msg))
            di = QTableWidgetItem(date)
            di.setForeground(QColor(C['fg_muted']))
            self._history_table.setItem(row, 2, di)

    def _refresh_branches(self):
        self._branch_tree.clear()
        if not self._project_path: return
        out, ok = self._run_git(["branch", "--list"])
        if not ok: return
        branches = [b.strip().lstrip("* ") for b in out.splitlines() if b.strip()]
        current = self._branch_name_lbl.text()

        # Current — pinned at top
        if current and current not in ("—", "No repo", "No project", "HEAD detached"):
            cur_item = QTreeWidgetItem([f"★ {current}", "current"])
            cur_item.setForeground(0, QColor(C['teal']))
            cur_item.setData(0, Qt.ItemDataRole.UserRole, current)
            self._branch_tree.addTopLevelItem(cur_item)

        # main (if not current)
        if "main" in branches and "main" != current:
            mi = QTreeWidgetItem(["main", ""])
            mi.setData(0, Qt.ItemDataRole.UserRole, "main")
            self._branch_tree.addTopLevelItem(mi)

        # Feature branches
        feat = [b for b in branches
                if b != "main" and not b.startswith("claude/") and b != current]
        if feat:
            fg = QTreeWidgetItem([f"▸ Feature Branches ({len(feat)})", ""])
            fg.setForeground(0, QColor(C['fg_muted']))
            fg.setData(0, Qt.ItemDataRole.UserRole, "__group__")
            for b in feat:
                ch = QTreeWidgetItem([b, ""])
                ch.setData(0, Qt.ItemDataRole.UserRole, b)
                fg.addChild(ch)
            self._branch_tree.addTopLevelItem(fg); fg.setExpanded(True)

        # Claude worktrees
        claude = [b for b in branches if b.startswith("claude/") and b != current]
        if claude:
            cg = QTreeWidgetItem([f"▸ Claude Worktrees ({len(claude)})", ""])
            cg.setForeground(0, QColor(C['fg_muted']))
            cg.setData(0, Qt.ItemDataRole.UserRole, "__group__")
            for b in claude:
                ch = QTreeWidgetItem([b, "worktree"])
                ch.setForeground(0, QColor(C['fg_dim']))
                ch.setForeground(1, QColor(C['fg_warn']))
                ch.setData(0, Qt.ItemDataRole.UserRole, b)
                cg.addChild(ch)
            self._branch_tree.addTopLevelItem(cg); cg.setExpanded(True)

    def _refresh_tags(self):
        self._tag_list.clear()
        if not self._project_path: return
        out, ok = self._run_git(["tag"])
        if not ok or not out.strip(): return
        for tag in out.splitlines():
            tag = tag.strip()
            if not tag: continue
            short_hash, _ = self._run_git(["rev-parse", "--short", f"{tag}^{{}}"])
            item = QTreeWidgetItem([tag, short_hash])
            item.setForeground(1, QColor(C['fg_muted']))
            item.setData(0, Qt.ItemDataRole.UserRole, tag)
            self._tag_list.addTopLevelItem(item)

    # ── Git actions ───────────────────────────────────────────────────────────

    def _commit_all(self):
        msg = self._commit_msg.text().strip()
        if not msg:
            self._commit_status.setText("Enter a commit message.")
            self._commit_status.setStyleSheet(f"color:{C['fg_warn']};{FONT_SMALL}"); return
        self._run_git(["add", "-A"])
        out, ok = self._run_git(["commit", "-m", msg])
        if ok:
            self._commit_msg.clear()
            self._commit_status.setText("Committed.")
            self._commit_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
            self._refresh()
        else:
            self._commit_status.setText(f"Commit failed: {out[:80]}")
            self._commit_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _git_push(self):
        out, ok = self._run_git(["push"])
        if ok:
            self._branch_status.setText("Pushed.")
            self._branch_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
        else:
            self._branch_status.setText(f"Push failed: {out[:80]}")
            self._branch_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _git_pull(self):
        out, ok = self._run_git(["pull"])
        if ok:
            self._branch_status.setText("Pulled.")
            self._branch_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
            self._refresh()
        else:
            self._branch_status.setText(f"Pull failed: {out[:80]}")
            self._branch_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _git_fetch(self):
        out, ok = self._run_git(["fetch"])
        if ok:
            self._branch_status.setText("Fetched.")
            self._branch_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
            self._refresh_branch_bar()
        else:
            self._branch_status.setText(f"Fetch failed: {out[:80]}")
            self._branch_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _checkout_selected(self):
        item = self._branch_tree.currentItem()
        if not item: return
        branch = item.data(0, Qt.ItemDataRole.UserRole)
        if not branch or branch == "__group__": return
        out, ok = self._run_git(["checkout", branch])
        if ok:
            self._branch_status.setText(f"Checked out {branch}.")
            self._branch_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
            self._refresh()
        else:
            self._branch_status.setText(f"Checkout failed: {out[:80]}")
            self._branch_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _new_branch(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Branch", "Branch name:")
        if not ok or not name.strip(): return
        out, success = self._run_git(["checkout", "-b", name.strip()])
        if success:
            self._branch_status.setText(f"Created and checked out {name}.")
            self._branch_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
            self._refresh()
        else:
            self._branch_status.setText(f"Failed: {out[:80]}")
            self._branch_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _merge_branch(self):
        item = self._branch_tree.currentItem()
        if not item: return
        branch = item.data(0, Qt.ItemDataRole.UserRole)
        if not branch or branch == "__group__": return
        out, ok = self._run_git(["merge", branch])
        if ok:
            self._branch_status.setText(f"Merged {branch}.")
            self._branch_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
            self._refresh()
        else:
            self._branch_status.setText(f"Merge failed: {out[:80]}")
            self._branch_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _new_tag(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Tag", "Tag name:")
        if not ok or not name.strip(): return
        out, success = self._run_git(["tag", name.strip()])
        if success:
            self._tag_status.setText(f"Created tag {name}.")
            self._tag_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
            self._refresh_tags()
        else:
            self._tag_status.setText(f"Failed: {out[:80]}")
            self._tag_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _delete_tag(self):
        item = self._tag_list.currentItem()
        if not item: return
        tag = item.data(0, Qt.ItemDataRole.UserRole)
        if not tag: return
        out, ok = self._run_git(["tag", "-d", tag])
        if ok:
            self._tag_status.setText(f"Deleted tag {tag}.")
            self._tag_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
            self._refresh_tags()
        else:
            self._tag_status.setText(f"Failed: {out[:80]}")
            self._tag_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")


# =============================================================================
# Rules Tab (System Prompt Editor)
# =============================================================================

class RulesTab(QWidget):
    """Editor for the AI system prompt / rules."""
    rules_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        desc = QLabel(
            "Edit the system prompt rules that control how the AI assistant behaves. "
            "Changes take effect on the next message.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{C['fg_dim']};{FONT_BODY}")
        layout.addWidget(desc)

        self.editor = QPlainTextEdit()
        self.editor.setStyleSheet(
            f"QPlainTextEdit{{background:{C['bg_input']};color:{C['fg']};"
            f"border:1px solid {C['border_light']};border-radius:6px;"
            f"padding:8px;{FONT_CODE}}}")
        self.editor.setPlaceholderText("System prompt rules...")
        self.editor.setTabStopDistance(28)
        layout.addWidget(self.editor, stretch=1)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        layout.addWidget(self._status)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        save_btn = QPushButton("Save Rules")
        save_btn.setStyleSheet(BTN_SM_PRIMARY)
        save_btn.setToolTip("Save rules to disk and apply to next message")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        revert_btn = QPushButton("Revert to Default")
        revert_btn.setStyleSheet(BTN_SM_SECONDARY)
        revert_btn.setToolTip("Reset rules to the built-in default")
        revert_btn.clicked.connect(self._revert)
        btn_row.addWidget(revert_btn)

        load_btn = QPushButton("Load from File...")
        load_btn.setStyleSheet(BTN_SM_GHOST)
        load_btn.setToolTip("Import rules from a text file")
        load_btn.clicked.connect(self._load_from_file)
        btn_row.addWidget(load_btn)

        export_btn = QPushButton("Export to File...")
        export_btn.setStyleSheet(BTN_SM_GHOST)
        export_btn.setToolTip("Export current rules to a text file")
        export_btn.clicked.connect(self._export_to_file)
        btn_row.addWidget(export_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── Reference Documents section ────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C['border']};margin-top:8px;margin-bottom:4px;")
        layout.addWidget(sep)

        ref_hdr = QHBoxLayout(); ref_hdr.setSpacing(6)
        ref_title = QLabel("REFERENCE DOCUMENTS"); ref_title.setStyleSheet(SETTINGS_STITLE)
        ref_hdr.addWidget(ref_title); ref_hdr.addStretch()
        ref_hint = QLabel("Markdown/text files included in AI context for .ino projects")
        ref_hint.setStyleSheet(f"color:{C['fg_muted']};{FONT_SMALL}")
        ref_hdr.addWidget(ref_hint)
        layout.addLayout(ref_hdr)

        self.ref_table = QTableWidget()
        self.ref_table.setColumnCount(3)
        self.ref_table.setHorizontalHeaderLabels(["File", "Size", "Path"])
        self.ref_table.horizontalHeader().setStyleSheet(SETTINGS_TBL_HDR)
        self.ref_table.setStyleSheet(SETTINGS_TABLE)
        self.ref_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.ref_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ref_table.setMaximumHeight(150)
        self.ref_table.verticalHeader().setVisible(False)
        rhdr = self.ref_table.horizontalHeader()
        rhdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        rhdr.resizeSection(0, 180)
        rhdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        rhdr.resizeSection(1, 64)
        rhdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.ref_table)

        ref_btn_row = QHBoxLayout(); ref_btn_row.setSpacing(6)
        add_ref_btn = QPushButton("Add…"); add_ref_btn.setStyleSheet(BTN_SM_PRIMARY)
        add_ref_btn.clicked.connect(self._add_ref_doc); ref_btn_row.addWidget(add_ref_btn)
        rm_ref_btn = QPushButton("Remove"); rm_ref_btn.setStyleSheet(BTN_SM_DANGER)
        rm_ref_btn.clicked.connect(self._remove_ref_doc); ref_btn_row.addWidget(rm_ref_btn)
        prev_ref_btn = QPushButton("Preview"); prev_ref_btn.setStyleSheet(BTN_SM_GHOST)
        prev_ref_btn.clicked.connect(self._preview_ref_doc); ref_btn_row.addWidget(prev_ref_btn)
        ref_btn_row.addStretch()
        layout.addLayout(ref_btn_row)

        self.ref_status = QLabel("")
        self.ref_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        layout.addWidget(self.ref_status)

        self._load_initial()
        self._populate_ref_docs_table()

    def _load_initial(self):
        """Load custom rules if they exist, otherwise show default."""
        custom = _load_custom_rules()
        if custom is not None:
            self.editor.setPlainText(custom)
            self._status.setText("Custom rules loaded from disk.")
        else:
            self.editor.setPlainText(_DEFAULT_RULES_TEXT)
            self._status.setText("Showing default rules.")

    def _save(self):
        """Save current editor content as custom rules."""
        text = self.editor.toPlainText()
        _save_custom_rules(text)
        global SYSTEM_PROMPT
        base = text.strip() if text.strip() else _DEFAULT_RULES_TEXT
        if _TEENSY_QUICK_REF and _TEENSY_QUICK_REF not in base:
            SYSTEM_PROMPT = base + "\n\n--- TEENSY QUICK REFERENCE ---\n" + _TEENSY_QUICK_REF
        else:
            SYSTEM_PROMPT = base
        self._status.setText("Rules saved and applied.")
        self._status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
        self.rules_changed.emit()

    def _revert(self):
        """Reset to built-in default rules."""
        reply = QMessageBox.question(
            self, "Revert Rules",
            "Reset to the built-in default rules? Your custom rules will be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.editor.setPlainText(_DEFAULT_RULES_TEXT)
            _save_custom_rules("")
            global SYSTEM_PROMPT
            SYSTEM_PROMPT = _DEFAULT_SYSTEM_PROMPT  # already includes Teensy ref
            self._status.setText("Reverted to default rules.")
            self._status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
            self.rules_changed.emit()

    def _load_from_file(self):
        """Import rules from a text file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Rules", os.path.expanduser("~"),
            "Text Files (*.txt *.md);;All Files (*)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.editor.setPlainText(f.read())
                self._status.setText(
                    f"Loaded from {os.path.basename(path)}. Click Save to apply.")
                self._status.setStyleSheet(f"color:{C['fg_link']};{FONT_SMALL}")
            except OSError as e:
                self._status.setText(f"Error: {e}")
                self._status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _export_to_file(self):
        """Export current rules to a text file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Rules", os.path.expanduser("~/aide_rules.txt"),
            "Text Files (*.txt *.md);;All Files (*)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.editor.toPlainText())
                self._status.setText(f"Exported to {os.path.basename(path)}.")
                self._status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
            except OSError as e:
                self._status.setText(f"Error: {e}")
                self._status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    # ── Reference Documents management ─────────────────────────────────────

    def _populate_ref_docs_table(self):
        docs = _load_ref_docs()
        self.ref_table.setRowCount(len(docs))
        for i, path in enumerate(docs):
            name_item = QTableWidgetItem(os.path.basename(path))
            name_item.setData(Qt.ItemDataRole.UserRole, path)
            self.ref_table.setItem(i, 0, name_item)
            try:
                size = os.path.getsize(path)
                if size < 1024:
                    sz = f"{size} B"
                else:
                    sz = f"{size // 1024} KB"
            except OSError:
                sz = "missing"
            self.ref_table.setItem(i, 1, QTableWidgetItem(sz))
            self.ref_table.setItem(i, 2, QTableWidgetItem(path))
        self.ref_status.setText(f"{len(docs)} reference document(s)")
        self.ref_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")

    def _add_ref_doc(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Reference Documents", "",
            "Text/Markdown (*.md *.txt *.h *.c *.cpp *.ino);;All Files (*)")
        if not paths:
            return
        docs = _load_ref_docs()
        added = 0
        for p in paths:
            if p not in docs:
                docs.append(p)
                added += 1
        _save_ref_docs(docs)
        self._populate_ref_docs_table()
        if added:
            self.ref_status.setText(f"Added {added} document(s)")
            self.ref_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")

    def _remove_ref_doc(self):
        row = self.ref_table.currentRow()
        if row < 0:
            self.ref_status.setText("Select a document to remove")
            self.ref_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")
            return
        item = self.ref_table.item(row, 0)
        path = item.data(Qt.ItemDataRole.UserRole)
        docs = _load_ref_docs()
        if path in docs:
            docs.remove(path)
        _save_ref_docs(docs)
        self._populate_ref_docs_table()

    def _preview_ref_doc(self):
        row = self.ref_table.currentRow()
        if row < 0:
            self.ref_status.setText("Select a document to preview")
            self.ref_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")
            return
        item = self.ref_table.item(row, 0)
        path = item.data(Qt.ItemDataRole.UserRole)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read(8000)
        except OSError as e:
            self.ref_status.setText(f"Cannot read: {e}")
            self.ref_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Preview — {os.path.basename(path)}")
        dlg.resize(600, 400)
        lay = QVBoxLayout(dlg)
        te = QPlainTextEdit()
        te.setReadOnly(True)
        te.setPlainText(content)
        te.setStyleSheet(
            f"background:{C['bg_input']};color:{C['fg']};"
            f"border:1px solid {C['border_light']};{FONT_CODE}")
        lay.addWidget(te)
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(BTN_SM_SECONDARY)
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        dlg.exec()


# =============================================================================
# Settings Panel — Container
# =============================================================================

class SettingsPanel(QWidget):
    """Settings panel with Models, Git, and Rules tabs."""
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
        self.tabs.setDocumentMode(True)

        self.models_tab = ModelsTab()
        self.models_tab.model_changed.connect(self.model_changed.emit)
        self.tabs.addTab(self.models_tab, "Models")

        self.git_tab = GitTab()
        self.tabs.addTab(self.git_tab, "Git")

        self.rules_tab = RulesTab()
        self.rules_tab.rules_changed.connect(self._on_rules_changed)
        self.tabs.addTab(self.rules_tab, "Rules")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

    def _on_rules_changed(self):
        """Notify that rules changed — triggers system prompt rebuild."""
        self.model_changed.emit()

    def _on_tab_changed(self, index):
        if index == 1:  # Git tab
            self.git_tab._refresh()

    def set_project_path(self, path):
        self.git_tab.set_project_path(path)

    def refresh_models(self):
        """Convenience method for external callers."""
        self.models_tab.refresh_models()


# =============================================================================
# Git Panel
# =============================================================================

class GitPanel(QWidget):
    """Git GUI with graphical branch/tag manager and console output."""
    branch_changed = pyqtSignal()  # emitted after checkout so MainWindow can reload files

    _BTN = BTN_SM_SECONDARY
    _BTN_PRIMARY = BTN_SM_PRIMARY
    _BTN_DANGER = BTN_SM_DANGER

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


# =============================================================================
# Symbol Outline Panel — shows functions/types/globals for the current file
# =============================================================================

class OutlinePanel(QWidget):
    """Compact tree listing symbols in the active editor file."""
    navigate_requested = pyqtSignal(int)  # emits 1-based line number

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("OUTLINE")
        header.setStyleSheet(SETTINGS_STITLE)
        header.setContentsMargins(8, 6, 8, 4)
        layout.addWidget(header)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setStyleSheet(
            f"QTreeWidget{{background:{C['bg_dark']};color:{C['fg']};"
            f"border:none;{FONT_BODY}}}"
            f"QTreeWidget::item{{padding:1px 0;}}"
            f"QTreeWidget::item:selected{{background:{C['teal']};color:#fff;}}"
            f"QTreeWidget::item:hover{{background:{C['bg_input']};}}")
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

        self.setStyleSheet(f"background:{C['bg_dark']};")

    def refresh(self, symbol_index, current_rel_path):
        """Rebuild tree for the given file from symbol_index."""
        self.tree.clear()
        if not symbol_index or not current_rel_path:
            return

        groups = {"function": [], "type": [], "global": []}
        for name, entries in symbol_index.items():
            for e in entries:
                if e.rel_path == current_rel_path and e.kind in groups:
                    groups[e.kind].append(e)

        group_labels = [("Functions", "function"),
                        ("Types", "type"),
                        ("Globals", "global")]
        for label, kind in group_labels:
            items = sorted(groups[kind], key=lambda e: e.line)
            if not items:
                continue
            parent = QTreeWidgetItem(self.tree, [label])
            parent.setForeground(0, QColor(C["fg_muted"]))
            parent.setExpanded(True)
            for e in items:
                child = QTreeWidgetItem(parent, [f"{e.name}  :{e.line}"])
                child.setData(0, Qt.ItemDataRole.UserRole, e.line)
                if kind == "function":
                    child.setForeground(0, QColor(C["syn_fn"]))
                elif kind == "type":
                    child.setForeground(0, QColor(C["syn_type"]))
                else:
                    child.setForeground(0, QColor(C["fg"]))

    def _on_item_clicked(self, item, column):
        line = item.data(0, Qt.ItemDataRole.UserRole)
        if line is not None:
            self.navigate_requested.emit(line)


class MainWindow(QMainWindow):
    def __init__(self, project_path=None, config=None):
        super().__init__()
        self._config = config or {}
        self.setWindowTitle(WINDOW_TITLE)
        # Set window/dock icon from icon.svg with transparent background
        _icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.svg')
        if os.path.exists(_icon_path):
            try:
                from PyQt6.QtSvg import QSvgRenderer
                _renderer = QSvgRenderer(_icon_path)
                _pix = QPixmap(QSize(256, 256))
                _pix.fill(Qt.GlobalColor.transparent)
                _painter = QPainter(_pix)
                _renderer.render(_painter)
                _painter.end()
                _app_icon = QIcon(_pix)
            except ImportError:
                _app_icon = QIcon(_icon_path)  # fallback: may have white bg
            self.setWindowIcon(_app_icon)
            QApplication.instance().setWindowIcon(_app_icon)
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
        self._ai_fix_pending_compile = False   # set True when AI edits are applied
        self._compile_follows_ai_edits = False  # captured at compile start
        self._fix_attempt_count = 0            # AI-assisted fix attempts in current session
        self._prev_diagnostics = []            # snapshot before each fix attempt (for diff)
        self._fix_stall_count = 0              # consecutive attempts with resolved == 0

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

        # Apply saved preferences (font size, tab width, Ollama URL)
        self._apply_preferences(self._config)

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
        self._compile_badge = NavBadge(self.btn_code)
        self._compile_badge.reposition()
        self.btn_chat = SidebarButton("AI", "AI Chat")
        self.btn_files = FileSidebarButton("Files")
        self.btn_libs = LibrarySidebarButton("Libraries")
        self.btn_boards = BoardSidebarButton("Boards")
        self.btn_git = GitSidebarButton("Git")
        self.btn_serial = SerialSidebarButton("Serial Monitor")
        self.btn_plotter = PlotterSidebarButton("Serial Plotter")
        self.btn_settings = SettingsSidebarButton("Settings")

        self.btn_code.clicked.connect(lambda: self._switch_view(0))
        self.btn_chat.clicked.connect(lambda: self._switch_view(1))
        self.btn_files.clicked.connect(lambda: self._switch_view(2))
        self.btn_settings.clicked.connect(lambda: self._switch_view(3))
        self.btn_git.clicked.connect(lambda: self._switch_view(4))
        self.btn_serial.clicked.connect(lambda: self._switch_view(5))
        self.btn_libs.clicked.connect(lambda: self._switch_view(6))
        self.btn_boards.clicked.connect(lambda: self._switch_view(7))
        self.btn_plotter.clicked.connect(lambda: self._switch_view(8))

        sb_layout.addWidget(self.btn_code)
        sb_layout.addWidget(self.btn_chat)
        sb_layout.addWidget(self.btn_files)
        sb_layout.addWidget(self.btn_libs)
        sb_layout.addWidget(self.btn_boards)
        sb_layout.addWidget(self.btn_git)
        sb_layout.addWidget(self.btn_serial)
        sb_layout.addWidget(self.btn_plotter)
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

        # Find/Replace bar (hidden by default, shown with Ctrl+F)
        self._find_bar = QFrame()
        self._find_bar.setStyleSheet(
            f"QFrame{{background:{C['bg_input']};border-bottom:1px solid {C['border_light']};"
            f"padding:4px 8px;}}")
        self._find_bar.hide()
        fb_layout = QHBoxLayout(self._find_bar)
        fb_layout.setContentsMargins(8, 4, 8, 4)
        fb_layout.setSpacing(6)
        fb_find_lbl = QLabel("Find:")
        fb_find_lbl.setStyleSheet(f"color:{C['fg']};{FONT_BODY}")
        fb_layout.addWidget(fb_find_lbl)
        self._find_input = QLineEdit()
        self._find_input.setPlaceholderText("Search...")
        self._find_input.setStyleSheet(
            f"QLineEdit{{background:{C['bg']};color:{C['fg']};"
            f"border:1px solid {C['border_light']};border-radius:3px;padding:3px 6px;}}")
        self._find_input.returnPressed.connect(self._find_next)
        fb_layout.addWidget(self._find_input)
        fb_repl_lbl = QLabel("Replace:")
        fb_repl_lbl.setStyleSheet(f"color:{C['fg']};{FONT_BODY}")
        fb_layout.addWidget(fb_repl_lbl)
        self._replace_input = QLineEdit()
        self._replace_input.setPlaceholderText("Replace with...")
        self._replace_input.setStyleSheet(self._find_input.styleSheet())
        fb_layout.addWidget(self._replace_input)
        for label, slot in [("Next", self._find_next), ("Prev", self._find_prev),
                            ("Replace", self._replace_one), ("All", self._replace_all)]:
            btn = QPushButton(label)
            btn.setStyleSheet(BTN_GHOST)
            btn.clicked.connect(slot)
            fb_layout.addWidget(btn)
        close_btn = QPushButton("\u2715")
        close_btn.setFixedWidth(24)
        close_btn.setStyleSheet(BTN_GHOST)
        close_btn.clicked.connect(lambda: self._find_bar.hide())
        fb_layout.addWidget(close_btn)
        # Escape key closes find bar
        QShortcut(QKeySequence("Escape"), self._find_bar,
                  lambda: self._find_bar.hide())
        cv_layout.addWidget(self._find_bar)

        v_splitter = QSplitter(Qt.Orientation.Vertical)

        # Horizontal splitter: editor + outline panel
        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.editor = TabbedEditor()
        self.editor.file_changed.connect(self._on_editor_file_changed)
        self.editor.ask_llm_requested.connect(self._on_ask_llm)
        h_splitter.addWidget(self.editor)

        self._outline_panel = OutlinePanel()
        self._outline_panel.navigate_requested.connect(self._outline_navigate)
        self._outline_panel.setMinimumWidth(120)
        h_splitter.addWidget(self._outline_panel)
        h_splitter.setSizes([800, 200])
        h_splitter.setStretchFactor(0, 1)  # editor stretches
        h_splitter.setStretchFactor(1, 0)  # outline stays fixed

        v_splitter.addWidget(h_splitter)

        # Bottom panel
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setObjectName("bottomTabs")
        self.bottom_tabs.tabBar().setExpanding(False)
        self.bottom_tabs.setDocumentMode(True)
        # Output tab: raw compiler output + diagnostic table
        self._output_tab = output_wrapper = QWidget()
        ow_layout = QVBoxLayout(output_wrapper)
        ow_layout.setContentsMargins(0, 0, 0, 0)
        ow_layout.setSpacing(0)
        self.compiler_output = CompilerOutput()
        self.compiler_output.jump_to_line.connect(self._jump_to_error)
        ow_layout.addWidget(self.compiler_output, stretch=1)
        self._diag_panel = DiagnosticPanel()
        self._diag_panel.navigate_requested.connect(self._jump_to_error)
        self._diag_panel.hide()
        ow_layout.addWidget(self._diag_panel)
        self.bottom_tabs.addTab(output_wrapper, "Output")

        v_splitter.addWidget(self.bottom_tabs)
        v_splitter.setSizes([675, 225])

        cv_layout.addWidget(v_splitter)
        self.view_stack.addWidget(code_view)

        # View 1: Chat view (full panel)
        self.chat_panel = ChatPanel()
        self.chat_panel.set_editor(self.editor)
        # Wire chat_panel reference to TabbedEditor for code intelligence
        self.editor._chat_panel = self.chat_panel
        self.chat_panel.generation_started.connect(lambda: self.ai_spinner.start())
        self.chat_panel.generation_finished.connect(lambda: self.ai_spinner.stop())
        self.chat_panel.edits_applied.connect(self._on_edits_applied)
        self.chat_panel.recompile_requested.connect(self._compile)
        self.chat_panel.model_switch_requested.connect(self._on_model_switch)
        self.chat_panel.fix_triggered.connect(self._on_fix_triggered)
        self.chat_panel.chat_cleared.connect(self._reset_fix_attempt_count)
        self.view_stack.addWidget(self.chat_panel)

        # View 2: File Manager (full panel)
        self.file_manager = FileManagerView()
        self.file_manager.file_requested.connect(
            lambda fp: (self.editor.open_file(fp), self._switch_view(0)))
        self.view_stack.addWidget(self.file_manager)

        # View 3: Settings (full panel)
        self.settings_panel = SettingsPanel()
        self.settings_panel.models_tab._main_window = self
        self.settings_panel.model_changed.connect(self._refresh_models)
        self.view_stack.addWidget(self.settings_panel)

        # View 4: Git panel (full panel)
        self.git_panel = GitPanel()
        self.git_panel.branch_changed.connect(self._on_branch_changed)
        self.view_stack.addWidget(self.git_panel)

        # View 5: Serial Monitor (full panel)
        self.serial_monitor = SerialMonitor()
        self.view_stack.addWidget(self.serial_monitor)

        # View 6: Library Manager
        self.lib_manager = LibraryManagerPanel()
        self.lib_manager.include_requested.connect(self._on_include_library)
        self.view_stack.addWidget(self.lib_manager)

        # View 7: Board Manager
        self.board_manager = BoardManagerPanel()
        self.view_stack.addWidget(self.board_manager)

        # View 8: Serial Plotter
        self.serial_plotter = SerialPlotterPanel()
        self.serial_monitor.serial_line_received.connect(self.serial_plotter.on_serial_line)
        self.serial_monitor.connection_changed.connect(self.serial_plotter.on_connection_changed)
        self.view_stack.addWidget(self.serial_plotter)

        main_layout.addWidget(self.view_stack)

    def _switch_view(self, idx):
        self.view_stack.setCurrentIndex(idx)
        for i, btn in enumerate([self.btn_code, self.btn_chat, self.btn_files,
                                 self.btn_settings, self.btn_git, self.btn_serial,
                                 self.btn_libs, self.btn_boards, self.btn_plotter]):
            btn.setChecked(i == idx)
        if idx == 4:
            self.git_panel.refresh_status()
        elif idx == 5:
            self.serial_monitor.refresh_ports()

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
        _backend_suffix = " (LM Studio)" if AI_BACKEND == "lmstudio" else ""
        self._status_model = QLabel(f"{OLLAMA_MODEL}{_backend_suffix}")
        self._status_model.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL} padding: 0 8px;")
        self._status_model.setToolTip(
            f"Backend: {'LM Studio' if AI_BACKEND == 'lmstudio' else 'Ollama'}")
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
        if not name or AI_BACKEND == "lmstudio":
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
        """Build a short description from API metadata, or ask the model itself."""
        try:
            if AI_BACKEND == "lmstudio":
                return "LM Studio model"
            r = requests.post(
                f"{OLLAMA_URL}/api/show",
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
                        f"{OLLAMA_URL}/api/chat",
                        json={
                            "model": name,
                            "messages": [{
                                "role": "user",
                                "content": (
                                    "In EXACTLY 6 words or fewer, describe what you specialize in. "
                                    "Reply with ONLY the description, nothing else. "
                                    "Example: 'Teensy embedded systems and audio'")
                            }],
                            "stream": False,
                            "options": OLLAMA_CHAT_OPTIONS,
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

        # ── File ──
        fm = mb.addMenu("File")
        fm.addAction(self._make_action("New Sketch", self._new_sketch_dialog, "Ctrl+N"))
        fm.addAction(self._make_action("Open Sketch...", self._open_project_dialog, "Ctrl+O"))
        self._recent_menu = fm.addMenu("Open Recent")
        self._populate_recent_menu()
        fm.addSeparator()
        fm.addAction(self._make_action("Save", self._save_file, "Ctrl+S"))
        fm.addAction(self._make_action("Save As...", self._save_as, "Ctrl+Shift+S"))
        fm.addAction(self._make_action("Close Tab", self._close_current_tab, "Ctrl+W"))
        fm.addSeparator()
        pref_action = self._make_action("Preferences...", self._show_preferences, "Ctrl+,")
        pref_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        fm.addAction(pref_action)
        fm.addSeparator()
        fm.addAction(self._make_action("Quit", self.close, "Ctrl+Q"))

        # ── Edit ──
        em = mb.addMenu("Edit")
        em.addAction(self._make_action("Undo", self._editor_undo, "Ctrl+Z"))
        em.addAction(self._make_action("Redo", self._editor_redo, "Ctrl+Shift+Z"))
        em.addSeparator()
        em.addAction(self._make_action("Find / Replace", self._toggle_find_bar, "Ctrl+F"))
        em.addSeparator()
        em.addAction(self._make_action("Toggle Comment", self._toggle_comment, "Ctrl+/"))
        em.addSeparator()
        em.addAction(self._make_action("Increase Font Size", self._zoom_in, "Ctrl+="))
        em.addAction(self._make_action("Decrease Font Size", self._zoom_out, "Ctrl+-"))
        em.addSeparator()
        em.addAction(self._make_action("Go to Line\u2026", self._goto_line, "Ctrl+G"))
        em.addSeparator()
        em.addAction(self._make_action("Auto Format", self._auto_format, "Ctrl+T"))
        em.addAction(self._make_action("Find in Project\u2026", self._find_in_project, "Ctrl+Shift+F"))

        # ── Sketch ──
        sm = mb.addMenu("Sketch")
        sm.addAction(self._make_action("Verify / Compile", self._compile, "Ctrl+B"))
        sm.addAction(self._make_action("Upload", self._upload, "Ctrl+U"))
        sm.addAction(self._make_action("Export Compiled Binary", self._export_binary))
        sm.addSeparator()
        self._include_lib_menu = sm.addMenu("Include Library")
        self._include_lib_menu.aboutToShow.connect(self._populate_include_menu)

        # ── Tools ──
        tm = mb.addMenu("Tools")
        tm.addAction(self._make_action("Serial Monitor", lambda: self._switch_view(5), "Ctrl+Shift+M"))
        self._tools_board_action = tm.addAction("Board: (see toolbar)")
        self._tools_board_action.setEnabled(False)
        self._tools_port_action = tm.addAction("Port: (see toolbar)")
        self._tools_port_action.setEnabled(False)

        # ── AI ──
        am = mb.addMenu("AI")
        am.addAction(self._make_action("Open AI Chat", lambda: self._switch_view(1), "Ctrl+Shift+A"))
        am.addAction(self._make_action("Send Errors to AI", self._send_errors_to_ai, "Ctrl+Shift+E"))
        am.addAction(self._make_action("Fix Compile Errors", self.chat_panel._cmd_fix, "Ctrl+Shift+F"))
        am.addAction(self._make_action("Clear Chat", self.chat_panel.clear_chat))

        # ── View ──
        vm = mb.addMenu("View")
        vm.addAction(self._make_action("Code Editor", lambda: self._switch_view(0), "Ctrl+1"))
        vm.addAction(self._make_action("AI Chat", lambda: self._switch_view(1), "Ctrl+2"))
        vm.addAction(self._make_action("Files", lambda: self._switch_view(2), "Ctrl+3"))
        vm.addAction(self._make_action("Settings", lambda: self._switch_view(3), "Ctrl+4"))
        vm.addAction(self._make_action("Git", lambda: self._switch_view(4), "Ctrl+5"))
        vm.addAction(self._make_action("Libraries", lambda: self._switch_view(6), "Ctrl+6"))
        vm.addAction(self._make_action("Boards", lambda: self._switch_view(7), "Ctrl+7"))
        vm.addAction(self._make_action("Serial Plotter", lambda: self._switch_view(8), "Ctrl+8"))
        vm.addSeparator()
        vm.addAction(self._make_action("Preferences...", self._show_preferences))

        # ── Help ──
        hm = mb.addMenu("Help")
        hm.addAction(self._make_action("About ArduinoAIDE", self._show_about))

        # Ctrl+H shortcut to open find bar with focus on replace field
        QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(
            self._toggle_find_bar_replace)

    # ---- File operations ----
    def _open_project_dialog(self):
        p = QFileDialog.getExistingDirectory(self, "Open", os.path.expanduser("~/Documents/Arduino"))
        if p: self._open_project(p)

    def _open_project(self, path):
        self.project_path = path
        self._ai_fix_pending_compile = False
        self._compile_follows_ai_edits = False
        self._fix_attempt_count = 0
        self._prev_diagnostics = []
        self._fix_stall_count = 0
        self.serial_monitor.refresh_ports()
        self.setWindowTitle(f"{WINDOW_TITLE} — {os.path.basename(path)}")
        self.editor.open_all_project_files(path)
        self.chat_panel.set_project_path(path)
        self.chat_panel._update_context_bar()
        self.settings_panel.set_project_path(path)
        self.git_panel.set_project(path)
        self.file_manager.set_project(path)
        self._restore_project_state()
        self._add_to_recent(path)

    # ── Recent Sketches ──

    def _add_to_recent(self, path):
        """Add a project path to the recent sketches list."""
        cfg = _load_config()
        recents = cfg.get("recent_projects", [])
        abs_path = os.path.abspath(path)
        recents = [r for r in recents if os.path.abspath(r) != abs_path]
        recents.insert(0, abs_path)
        recents = recents[:10]  # keep last 10
        cfg["recent_projects"] = recents
        _save_config(cfg)
        self._populate_recent_menu()

    def _populate_recent_menu(self):
        """Fill File > Open Recent submenu from config."""
        self._recent_menu.clear()
        cfg = _load_config()
        recents = cfg.get("recent_projects", [])
        if not recents:
            self._recent_menu.addAction("(none)").setEnabled(False)
            return
        for path in recents:
            name = os.path.basename(path)
            action = self._recent_menu.addAction(f"{name}   ({path})")
            action.triggered.connect(lambda checked, p=path: self._open_project(p))
        self._recent_menu.addSeparator()
        clear_action = self._recent_menu.addAction("Clear Recent")
        clear_action.triggered.connect(self._clear_recent)

    def _clear_recent(self):
        """Clear all recent projects."""
        cfg = _load_config()
        cfg["recent_projects"] = []
        _save_config(cfg)
        self._populate_recent_menu()

    # ── Preferences ──

    def _show_preferences(self):
        """Show Preferences dialog."""
        from PyQt6.QtWidgets import (QDialog, QFormLayout, QDialogButtonBox,
                                     QGroupBox, QVBoxLayout, QLineEdit)

        dlg = QDialog(self)
        dlg.setWindowTitle("Preferences")
        dlg.setMinimumWidth(450)
        dlg.setStyleSheet(
            f"QDialog{{background:{C['bg']};color:{C['fg']};}}"
            f"QLabel{{color:{C['fg']};}}"
            f"QLineEdit,QSpinBox,QComboBox{{background:{C['bg_input']};color:{C['fg']};"
            f"border:1px solid {C['border_light']};border-radius:3px;padding:4px 8px;}}"
            f"QGroupBox{{color:{C['teal']};border:1px solid {C['border']};border-radius:4px;"
            f"margin-top:10px;padding-top:16px;}}"
            f"QGroupBox::title{{subcontrol-origin:margin;left:10px;padding:0 4px;}}")

        layout = QVBoxLayout(dlg)
        cfg = _load_config()

        # ── Editor Settings ──
        editor_group = QGroupBox("Editor")
        eg_layout = QFormLayout(editor_group)

        font_spin = QSpinBox()
        font_spin.setRange(8, 32)
        font_spin.setValue(cfg.get("editor_font_size", 13))
        eg_layout.addRow("Font Size:", font_spin)

        tab_spin = QSpinBox()
        tab_spin.setRange(1, 8)
        tab_spin.setValue(cfg.get("tab_width", 2))
        eg_layout.addRow("Tab Width:", tab_spin)

        layout.addWidget(editor_group)

        # ── AI Context Settings ──
        ctx_group = QGroupBox("AI Context")
        cg_layout = QFormLayout(ctx_group)

        budget_spin = QSpinBox()
        budget_spin.setRange(2000, 100000)
        budget_spin.setSingleStep(1000)
        budget_spin.setSuffix(" tokens")
        budget_spin.setValue(cfg.get("context_budget", 12000))
        budget_spin.setToolTip("Token budget for file context sent to the AI")
        cg_layout.addRow("Context Budget:", budget_spin)

        layout.addWidget(ctx_group)

        # ── Build Settings ──
        build_group = QGroupBox("Build")
        bg_layout = QFormLayout(build_group)

        arduino_cli_input = QLineEdit()
        arduino_cli_input.setText(cfg.get("arduino_cli_path", "arduino-cli"))
        arduino_cli_input.setPlaceholderText(
            "Path to arduino-cli (or leave as 'arduino-cli')")
        bg_layout.addRow("arduino-cli:", arduino_cli_input)

        board_urls_input = QPlainTextEdit()
        board_urls_input.setPlainText(
            "\n".join(cfg.get("additional_board_urls", [])))
        board_urls_input.setPlaceholderText("One URL per line")
        board_urls_input.setMaximumHeight(60)
        board_urls_input.setStyleSheet(
            f"QPlainTextEdit{{background:{C['bg_input']};color:{C['fg']};"
            f"border:1px solid {C['border_light']};border-radius:3px;padding:4px 8px;}}")
        bg_layout.addRow("Board URLs:", board_urls_input)

        from PyQt6.QtWidgets import QCheckBox
        verbose_cb = QCheckBox("Verbose output during compile/upload")
        verbose_cb.setChecked(cfg.get("verbose_compile", False))
        bg_layout.addRow(verbose_cb)

        warnings_combo = QComboBox()
        for w in ["none", "default", "more", "all"]:
            warnings_combo.addItem(w.capitalize(), w)
        current_warnings = cfg.get("compiler_warnings", "default")
        idx = warnings_combo.findData(current_warnings)
        if idx >= 0:
            warnings_combo.setCurrentIndex(idx)
        bg_layout.addRow("Compiler warnings:", warnings_combo)

        layout.addWidget(build_group)

        # ── Buttons ──
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.setStyleSheet(
            f"QPushButton{{background:{C['bg_input']};color:{C['fg']};"
            f"border:1px solid {C['border_light']};border-radius:4px;padding:6px 16px;}}"
            f"QPushButton:hover{{background:{C['teal']};color:white;}}")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            cfg["editor_font_size"] = font_spin.value()
            cfg["tab_width"] = tab_spin.value()
            cfg["context_budget"] = budget_spin.value()
            cfg["arduino_cli_path"] = arduino_cli_input.text().strip()
            urls = [u.strip() for u in board_urls_input.toPlainText().split('\n')
                    if u.strip()]
            cfg["additional_board_urls"] = urls
            cfg["verbose_compile"] = verbose_cb.isChecked()
            cfg["compiler_warnings"] = warnings_combo.currentData()
            _save_config(cfg)
            self._apply_preferences(cfg)

    def _apply_preferences(self, cfg):
        """Apply preferences to the running app (editor + build settings only;
        AI backend is managed by the Models tab)."""
        # Editor font size
        font_size = cfg.get("editor_font_size", 13)
        if hasattr(self, 'editor') and hasattr(self.editor, 'tabs'):
            for i in range(self.editor.tabs.count()):
                ed = self.editor.tabs.widget(i)
                if hasattr(ed, 'lexer') and callable(ed.lexer) and ed.lexer():
                    font = ed.lexer().font(0)
                    font.setPointSize(font_size)
                    ed.lexer().setFont(font)
            # Tab width
            tab_width = cfg.get("tab_width", 2)
            for i in range(self.editor.tabs.count()):
                ed = self.editor.tabs.widget(i)
                if hasattr(ed, 'setTabWidth'):
                    ed.setTabWidth(tab_width)
        # Context budget
        budget = cfg.get("context_budget", 12000)
        if hasattr(self, 'chat_panel') and hasattr(self.chat_panel, '_working_set'):
            self.chat_panel._working_set.budget = budget
        # Board manager additional URLs
        urls = cfg.get("additional_board_urls", [])
        if urls:
            cli = cfg.get("arduino_cli_path", "arduino-cli")
            try:
                subprocess.run(
                    [cli, "config", "set", "board_manager.additional_urls"] + urls,
                    capture_output=True, timeout=10)
            except Exception:
                pass

    def _on_include_library(self, name):
        """Insert #include <LibName.h> into the active editor."""
        ed = self.editor.current_editor()
        if not ed:
            return
        include_line = f'#include <{name}.h>'
        # Check if already included
        if HAS_QSCINTILLA:
            text = ed.text()
        else:
            text = ed.toPlainText()
        if include_line in text:
            return
        # Find last #include line
        lines = text.split('\n')
        last_include = -1
        for i, line in enumerate(lines):
            if line.strip().startswith('#include'):
                last_include = i
        insert_at = last_include + 1 if last_include >= 0 else 0
        if HAS_QSCINTILLA:
            ed.setCursorPosition(insert_at, 0)
            ed.insert(include_line + '\n')
        else:
            cursor = ed.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            for _ in range(insert_at):
                cursor.movePosition(cursor.MoveOperation.Down)
            cursor.insertText(include_line + '\n')
        self._switch_view(0)

    def _populate_include_menu(self):
        """Dynamically fill Sketch > Include Library submenu."""
        self._include_lib_menu.clear()
        if hasattr(self, 'lib_manager') and self.lib_manager._installed_libs:
            for item in self.lib_manager._installed_libs:
                lib = item.get("library", item)
                name = lib.get("name", "")
                if name:
                    action = self._include_lib_menu.addAction(name)
                    action.triggered.connect(
                        lambda checked, n=name: self._on_include_library(n))
        self._include_lib_menu.addSeparator()
        manage_action = self._include_lib_menu.addAction("Manage Libraries...")
        manage_action.triggered.connect(lambda: self._switch_view(6))

    def _on_branch_changed(self):
        """Reload all project files after a git checkout/merge."""
        if not self.project_path:
            return
        # Close all tabs and reopen from disk (files now reflect new branch)
        self.editor.close_all()
        self.editor.open_all_project_files(self.project_path)
        self.chat_panel._update_context_bar()

    def _on_ask_llm(self):
        """Switch to chat view and focus input when Ask LLM is clicked in editor."""
        self._switch_view(1)
        self.chat_panel.input_field.setFocus()

    def _on_edits_applied(self):
        """Refresh file browser and context after AI creates/edits files."""
        if self.project_path:
            self.file_manager.file_browser._refresh()
        self.chat_panel._update_context_bar()
        self._ai_fix_pending_compile = True

    def _on_fix_triggered(self):
        """Increment fix attempt counter and snapshot diagnostics for diffing."""
        self._fix_attempt_count += 1
        self._prev_diagnostics = list(getattr(self, '_compiler_diagnostics', []))

    def _reset_fix_attempt_count(self):
        """Reset fix attempt counter, diagnostic snapshot, and stall detection."""
        self._fix_attempt_count = 0
        self._prev_diagnostics = []
        self._fix_stall_count = 0

    def _on_model_switch(self, model_name):
        """Handle /model command — update toolbar combo and status bar."""
        global OLLAMA_MODEL
        OLLAMA_MODEL = model_name
        if hasattr(self, 'model_combo'):
            idx = self.model_combo.findText(model_name)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            else:
                self.model_combo.addItem(model_name)
                self.model_combo.setCurrentText(model_name)
        if hasattr(self, '_status_model'):
            _bs = " (LM Studio)" if AI_BACKEND == "lmstudio" else ""
            self._status_model.setText(f"{model_name}{_bs}")

    def _on_editor_file_changed(self, fp):
        self.setWindowTitle(f"{WINDOW_TITLE} — {os.path.basename(fp)}")
        self.chat_panel._update_context_bar()
        self._refresh_outline()

    def _refresh_outline(self):
        """Refresh the symbol outline panel for the current editor file."""
        if not hasattr(self, '_outline_panel'):
            return
        ed = self.editor.tabs.currentWidget()
        if not ed or not hasattr(ed, 'current_file') or not ed.current_file:
            self._outline_panel.refresh({}, "")
            return
        proj = getattr(self.chat_panel, '_project_path', None) or ""
        sym_index = getattr(self.chat_panel, '_symbol_index', {})
        if proj and ed.current_file.startswith(proj):
            rel_path = os.path.relpath(ed.current_file, proj)
        else:
            rel_path = os.path.basename(ed.current_file)
        self._outline_panel.refresh(sym_index, rel_path)

    def _outline_navigate(self, line):
        """Jump to a line from the outline panel."""
        ed = self.editor.tabs.currentWidget()
        if not ed:
            return
        if HAS_QSCINTILLA:
            ed.setCursorPosition(line - 1, 0)
            ed.ensureLineVisible(line - 1)
        else:
            cursor = ed.textCursor()
            block = ed.document().findBlockByLineNumber(line - 1)
            cursor.setPosition(block.position())
            ed.setTextCursor(cursor)
            ed.ensureCursorVisible()
        ed.setFocus()

    def _save_file(self):
        self.editor.save_all()

    def _new_sketch_dialog(self):
        """File > New Sketch — user picks location via file browser."""
        import datetime
        default_name = f"sketch_{datetime.datetime.now().strftime('%b%d').lower()}"
        default_dir = os.path.expanduser("~/Documents/Arduino")
        os.makedirs(default_dir, exist_ok=True)
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Create New Sketch",
            os.path.join(default_dir, default_name),
            "Arduino Sketch (*.ino)")
        if not filepath:
            return
        if not filepath.endswith(".ino"):
            filepath += ".ino"
        sketch_name = os.path.splitext(os.path.basename(filepath))[0]
        chosen_dir = os.path.dirname(filepath)
        sketch_dir = os.path.join(chosen_dir, sketch_name)
        ino_file = os.path.join(sketch_dir, f"{sketch_name}.ino")
        if os.path.exists(sketch_dir):
            QMessageBox.warning(self, "Exists",
                                f"Folder '{sketch_name}' already exists at that location.")
            return
        try:
            os.makedirs(sketch_dir)
            with open(ino_file, "w") as f:
                f.write(f"// {sketch_name}.ino\n\nvoid setup() {{\n\n}}\n\nvoid loop() {{\n\n}}\n")
            self._open_project(sketch_dir)
        except OSError as e:
            QMessageBox.warning(self, "Error", str(e))

    def _save_as(self):
        """File > Save As — save current file to a new location."""
        ed = self.editor.tabs.currentWidget()
        if not ed:
            return
        current_path = getattr(ed, 'current_file', None)
        suggested = current_path or os.path.expanduser(
            "~/Documents/Arduino/untitled.ino")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save As", suggested,
            "Arduino Files (*.ino *.h *.cpp);;All Files (*)")
        if path:
            try:
                content = ed.text() if hasattr(ed, 'text') else ed.toPlainText()
                with open(path, "w") as f:
                    f.write(content)
                # Update tab label
                idx = self.editor.tabs.indexOf(ed)
                if idx >= 0:
                    self.editor.tabs.setTabText(idx, os.path.basename(path))
                self.setWindowTitle(f"{WINDOW_TITLE} — {os.path.basename(path)}")
            except OSError as e:
                QMessageBox.warning(self, "Error", str(e))

    # ---- Edit menu helpers ----
    def _editor_undo(self):
        ed = self.editor.tabs.currentWidget()
        if ed and hasattr(ed, 'undo'):
            ed.undo()

    def _editor_redo(self):
        ed = self.editor.tabs.currentWidget()
        if ed and hasattr(ed, 'redo'):
            ed.redo()

    def _zoom_in(self):
        ed = self.editor.tabs.currentWidget()
        if ed and hasattr(ed, 'zoomIn'):
            ed.zoomIn(1)

    def _zoom_out(self):
        ed = self.editor.tabs.currentWidget()
        if ed and hasattr(ed, 'zoomOut'):
            ed.zoomOut(1)

    def _goto_line(self):
        """Show Go-to-Line dialog and jump to the entered line number."""
        ed = self.editor.tabs.currentWidget()
        if not ed:
            return
        if HAS_QSCINTILLA:
            max_line = ed.lines()
        else:
            max_line = ed.document().blockCount()
        line, ok = QInputDialog.getInt(
            self, "Go to Line", "Line number:", 1, 1, max_line)
        if ok:
            if HAS_QSCINTILLA:
                ed.setCursorPosition(line - 1, 0)
                ed.ensureLineVisible(line - 1)
            else:
                cursor = ed.textCursor()
                block = ed.document().findBlockByLineNumber(line - 1)
                cursor.setPosition(block.position())
                ed.setTextCursor(cursor)
                ed.ensureCursorVisible()
            self._switch_view(0)
            ed.setFocus()

    def _auto_format(self):
        """Auto-format the current file using clang-format."""
        import shutil
        ed = self.editor.tabs.currentWidget()
        if not ed:
            return
        cf = shutil.which("clang-format")
        if not cf:
            self.statusBar().showMessage(
                "clang-format not found \u2014 install with: brew install clang-format", 5000)
            return
        import tempfile, subprocess
        content = ed.text() if HAS_QSCINTILLA else ed.toPlainText()
        try:
            with tempfile.NamedTemporaryFile(
                    mode='w', suffix='.cpp', delete=False, encoding='utf-8') as f:
                f.write(content)
                tmp_path = f.name
            subprocess.run(
                [cf, '-style={BasedOnStyle: LLVM, IndentWidth: 2, ColumnLimit: 100}',
                 '-i', tmp_path], check=True, capture_output=True)
            with open(tmp_path, 'r', encoding='utf-8') as f:
                formatted = f.read()
            os.unlink(tmp_path)
            if formatted != content:
                if HAS_QSCINTILLA:
                    ed.beginUndoAction()
                    ed.selectAll()
                    ed.replaceSelectedText(formatted)
                    ed.endUndoAction()
                else:
                    ed.selectAll()
                    ed.insertPlainText(formatted)
                self.statusBar().showMessage("Formatted with clang-format", 3000)
            else:
                self.statusBar().showMessage("Already formatted", 3000)
        except Exception as ex:
            self.statusBar().showMessage(f"Format error: {ex}", 5000)

    def _find_in_project(self):
        """Open project-wide search dialog."""
        from PyQt6.QtWidgets import (QDialog, QCheckBox)
        if not self.project_path:
            QMessageBox.warning(self, "No Project", "Open a project first.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Find in Project")
        dlg.setMinimumSize(600, 400)
        dlg.setStyleSheet(
            f"QDialog{{background:{C['bg']};color:{C['fg']};}}"
            f"QLabel{{color:{C['fg']};}}"
            f"QLineEdit{{background:{C['bg_input']};color:{C['fg']};"
            f"border:1px solid {C['border_light']};border-radius:3px;padding:6px;}}"
            f"QCheckBox{{color:{C['fg']};}}")

        layout = QVBoxLayout(dlg)

        search_row = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search in project files...")
        search_row.addWidget(search_input)
        case_cb = QCheckBox("Case sensitive")
        search_row.addWidget(case_cb)
        regex_cb = QCheckBox("Regex")
        search_row.addWidget(regex_cb)
        search_btn = QPushButton("Search")
        search_btn.setStyleSheet(
            f"QPushButton{{background:{C['teal']};color:#fff;"
            f"border:none;border-radius:4px;padding:6px 16px;}}")
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        results_tree = QTreeWidget()
        results_tree.setHeaderLabels(["Match", "Line"])
        results_tree.setStyleSheet(
            f"QTreeWidget{{background:{C['bg_dark']};color:{C['fg']};"
            f"border:1px solid {C['border']};{FONT_BODY}}}"
            f"QTreeWidget::item:selected{{background:{C['teal']};color:#fff;}}"
            f"QHeaderView::section{{background:{C['bg_input']};color:{C['fg']};"
            f"border:1px solid {C['border']};padding:4px;}}")
        results_tree.setColumnWidth(0, 500)
        layout.addWidget(results_tree)

        status_label = QLabel("")
        status_label.setStyleSheet(f"color:{C['fg_muted']};{FONT_SMALL}")
        layout.addWidget(status_label)

        def do_search():
            import re as _re
            results_tree.clear()
            query = search_input.text()
            if not query:
                return
            all_files = self.chat_panel._scan_project_files(self.project_path)
            flags = 0 if case_cb.isChecked() else _re.IGNORECASE
            total = 0
            try:
                if regex_cb.isChecked():
                    pattern = _re.compile(query, flags)
                else:
                    pattern = _re.compile(_re.escape(query), flags)
            except _re.error as e:
                status_label.setText(f"Invalid regex: {e}")
                return
            for rel_path, content in sorted(all_files.items()):
                ext = os.path.splitext(rel_path)[1].lower()
                if ext not in {".ino", ".cpp", ".c", ".h", ".hpp"}:
                    continue
                file_matches = []
                for line_num, line_text in enumerate(content.split('\n'), 1):
                    if pattern.search(line_text):
                        file_matches.append((line_num, line_text.strip()))
                        total += 1
                        if total >= 500:
                            break
                if file_matches:
                    parent = QTreeWidgetItem(results_tree,
                                             [f"{rel_path} ({len(file_matches)})", ""])
                    parent.setForeground(0, QColor(C["teal"]))
                    parent.setExpanded(True)
                    abs_path = os.path.join(self.project_path, rel_path)
                    parent.setData(0, Qt.ItemDataRole.UserRole, abs_path)
                    for ln, txt in file_matches:
                        child = QTreeWidgetItem(parent,
                                                 [txt[:120], str(ln)])
                        child.setData(0, Qt.ItemDataRole.UserRole, abs_path)
                        child.setData(1, Qt.ItemDataRole.UserRole, ln)
                if total >= 500:
                    break
            status_label.setText(f"{total} matches" + (" (limited to 500)" if total >= 500 else ""))

        def on_item_dblclick(item, col):
            abs_path = item.data(0, Qt.ItemDataRole.UserRole)
            ln = item.data(1, Qt.ItemDataRole.UserRole)
            if abs_path and ln:
                self.editor.goto_line(abs_path, ln)
                self._switch_view(0)
                dlg.accept()

        search_btn.clicked.connect(do_search)
        search_input.returnPressed.connect(do_search)
        results_tree.itemDoubleClicked.connect(on_item_dblclick)
        dlg.exec()

    def _close_current_tab(self):
        """Close the active editor tab. Prompt to save if dirty."""
        idx = self.editor.tabs.currentIndex()
        if idx < 0 or self.editor.tabs.count() <= 1:
            return
        ed = self.editor.tabs.widget(idx)
        if ed and hasattr(ed, 'isModified') and ed.isModified():
            r = QMessageBox.question(
                self, "Unsaved Changes",
                f"Save changes to {self.editor.tabs.tabText(idx).lstrip('\u2022 ')}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel)
            if r == QMessageBox.StandardButton.Cancel:
                return
            if r == QMessageBox.StandardButton.Yes:
                if hasattr(ed, 'save_file'):
                    ed.save_file()
        self.editor._close_tab(idx)

    def _export_binary(self):
        """Export compiled binary to build/ folder."""
        if not self.project_path:
            QMessageBox.warning(self, "No Project", "Open a project first.")
            return
        self._save_file()
        self.compiler_output.clear_output()
        self._switch_view(0)
        self.bottom_tabs.setCurrentWidget(self._output_tab)
        build_dir = os.path.join(self.project_path, "build")
        self.compiler_output.append_output("Exporting compiled binary...", C["fg_link"])
        self._run_cli([
            "compile", "--fqbn", self._current_fqbn(),
            "--output-dir", build_dir, self.project_path])

    def _toggle_comment(self):
        """Toggle // comment on selected lines (or current line)."""
        ed = self.editor.tabs.currentWidget()
        if not ed:
            return
        if hasattr(ed, 'hasSelectedText') and ed.hasSelectedText():
            line_from, _, line_to, col_to = ed.getSelection()
            if col_to == 0 and line_to > line_from:
                line_to -= 1
        else:
            line_from, _ = ed.getCursorPosition()
            line_to = line_from

        # Check if ALL lines are already commented
        all_commented = True
        for ln in range(line_from, line_to + 1):
            text = ed.text(ln).rstrip('\n').rstrip('\r')
            stripped = text.lstrip()
            if stripped and not stripped.startswith("//"):
                all_commented = False
                break

        ed.beginUndoAction()
        for ln in range(line_from, line_to + 1):
            text = ed.text(ln).rstrip('\n').rstrip('\r')
            if all_commented:
                idx = text.find("//")
                if idx >= 0:
                    if text[idx:idx + 3] == "// ":
                        new_text = text[:idx] + text[idx + 3:]
                    else:
                        new_text = text[:idx] + text[idx + 2:]
                    ed.setSelection(ln, 0, ln, len(text))
                    ed.replaceSelectedText(new_text)
            else:
                stripped = text.lstrip()
                indent = len(text) - len(stripped)
                new_text = text[:indent] + "// " + text[indent:]
                ed.setSelection(ln, 0, ln, len(text))
                ed.replaceSelectedText(new_text)
        ed.endUndoAction()

    # ---- Find / Replace ----
    def _toggle_find_bar(self):
        if self._find_bar.isVisible():
            self._find_bar.hide()
        else:
            self._find_bar.show()
            self._find_input.setFocus()
            ed = self.editor.tabs.currentWidget()
            if ed and hasattr(ed, 'hasSelectedText') and ed.hasSelectedText():
                self._find_input.setText(ed.selectedText())
            self._find_input.selectAll()

    def _toggle_find_bar_replace(self):
        self._find_bar.show()
        self._replace_input.setFocus()

    def _find_next(self):
        ed = self.editor.tabs.currentWidget()
        text = self._find_input.text()
        if not ed or not text:
            return
        if hasattr(ed, 'findFirst'):
            ed.findFirst(text, False, False, False, True, True)

    def _find_prev(self):
        ed = self.editor.tabs.currentWidget()
        text = self._find_input.text()
        if not ed or not text:
            return
        if hasattr(ed, 'findFirst'):
            ed.findFirst(text, False, False, False, True, False)

    def _replace_one(self):
        ed = self.editor.tabs.currentWidget()
        if not ed or not self._find_input.text():
            return
        if (hasattr(ed, 'hasSelectedText') and ed.hasSelectedText()
                and ed.selectedText() == self._find_input.text()):
            ed.replaceSelectedText(self._replace_input.text())
        self._find_next()

    def _replace_all(self):
        ed = self.editor.tabs.currentWidget()
        text = self._find_input.text()
        repl = self._replace_input.text()
        if not ed or not text:
            return
        count = 0
        ed.beginUndoAction()
        ed.setCursorPosition(0, 0)
        while ed.findFirst(text, False, False, False, False, True):
            ed.replaceSelectedText(repl)
            count += 1
        ed.endUndoAction()

    def _show_about(self):
        QMessageBox.about(self, "About ArduinoAIDE",
            "ArduinoAIDE\n\n"
            "An AI-powered IDE for Teensy & Arduino development.\n"
            "Built with PyQt6, QScintilla, and Ollama.\n\n"
            "github.com/okfx/ArduinoAIDE")

    # ---- Build ----
    def _compile(self):
        if not self.project_path:
            QMessageBox.warning(self, "No Project", "Open a project first."); return
        self._compile_follows_ai_edits = self._ai_fix_pending_compile
        self._ai_fix_pending_compile = False
        self._save_file(); self.compiler_output.clear_output()
        self._switch_view(0); self.bottom_tabs.setCurrentWidget(self._output_tab)
        self.compiler_output.append_output("Compiling...", C["fg_link"])
        cmd = ["compile", "--fqbn", self._current_fqbn()]
        cfg = _load_config()
        warnings = cfg.get("compiler_warnings", "default")
        if warnings and warnings != "none":
            cmd.extend(["--warnings", warnings])
        if cfg.get("verbose_compile", False):
            cmd.append("-v")
        cmd.append(self.project_path)
        self._run_cli(cmd)

    def _upload(self):
        if not self.project_path:
            QMessageBox.warning(self, "No Project", "Open a project first."); return
        port = self.port_combo.currentText().strip()
        if not port:
            QMessageBox.warning(self, "No Port", "Select a port first."); return
        self._save_file(); self.compiler_output.clear_output()
        self._switch_view(0); self.bottom_tabs.setCurrentWidget(self._output_tab)
        self.compiler_output.append_output("Compiling and uploading...", C["fg_link"])
        cmd = ["compile", "--upload", "--fqbn", self._current_fqbn(), "--port", port]
        cfg = _load_config()
        warnings = cfg.get("compiler_warnings", "default")
        if warnings and warnings != "none":
            cmd.extend(["--warnings", warnings])
        if cfg.get("verbose_compile", False):
            cmd.append("-v")
        cmd.append(self.project_path)
        self._run_cli(cmd)

    def _run_cli(self, args):
        self._compiler_errors = ""
        self._compiler_diagnostics = []
        self.editor.clear_diagnostics()
        self._diag_panel.hide()
        self._compile_badge.set_count(0, 0)
        def go():
            try:
                r = subprocess.run(["arduino-cli"]+args, capture_output=True, text=True, timeout=120)
                if r.stdout:
                    for l in r.stdout.splitlines():
                        QTimer.singleShot(0, lambda l=l: self.compiler_output.append_output(l))
                if r.stderr:
                    self._compiler_errors = r.stderr
                    self._compiler_diagnostics, _ = _parse_compiler_diagnostics(r.stderr)
                    for l in r.stderr.splitlines():
                        c = C["fg_err"] if "error" in l.lower() else C["fg_warn"] if "warning" in l.lower() else C["fg"]
                        QTimer.singleShot(0, lambda l=l,c=c: self.compiler_output.append_output(l,c))
                # Populate diagnostic panel
                diags = list(self._compiler_diagnostics)
                QTimer.singleShot(0, lambda: self._update_diag_panel(diags))
                if r.returncode == 0:
                    QTimer.singleShot(0, lambda: self.compiler_output.append_output("\nDone compiling.", C["fg_ok"]))
                    QTimer.singleShot(0, self._reset_fix_attempt_count)
                else:
                    QTimer.singleShot(0, lambda: self.compiler_output.append_output("\nCompilation failed.", C["fg_err"]))
                    QTimer.singleShot(0, lambda: self.chat_panel.set_error_context(
                        self._compiler_errors, self._compiler_diagnostics))
                    QTimer.singleShot(0, self._show_fix_errors_btn)
                    QTimer.singleShot(0, self._apply_compile_diagnostics)
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
            if AI_BACKEND == "lmstudio":
                r = requests.get(f"{LMSTUDIO_URL}/v1/models", timeout=5)
                if r.status_code == 200:
                    for m in r.json().get("data", []):
                        n = m.get("id", "")
                        if n: self.model_combo.addItem(n)
            else:
                r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
                if r.status_code == 200:
                    for m in r.json().get("models", []):
                        n = m.get("name", "")
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
        # Update status bar with backend info
        if hasattr(self, '_status_model'):
            backend_label = " (LM Studio)" if AI_BACKEND == "lmstudio" else ""
            self._status_model.setText(f"{OLLAMA_MODEL}{backend_label}")
            self._status_model.setToolTip(
                f"Backend: {'LM Studio' if AI_BACKEND == 'lmstudio' else 'Ollama'}")
        # Update model desc label (clear for LM Studio, generate for Ollama)
        self._update_model_desc()
        # Rebuild system prompt in conversation (e.g. after rules change)
        if hasattr(self, 'chat_panel') and self.chat_panel._conversation:
            if self.chat_panel._conversation[0].get("role") == "system":
                self.chat_panel._conversation[0]["content"] = \
                    self.chat_panel._build_system_prompt()

    def _on_model_changed(self, name):
        global OLLAMA_MODEL
        if name and name != OLLAMA_MODEL:
            OLLAMA_MODEL = name
            self._update_model_desc()
            if hasattr(self, '_status_model'):
                self._status_model.setText(name)

    def _send_errors_to_ai(self):
        if self._compiler_errors:
            self.chat_panel.set_error_context(
                self._compiler_errors, getattr(self, '_compiler_diagnostics', []))
            self.chat_panel.send_errors_btn.setChecked(True)
            self._switch_view(1); self.chat_panel.input_field.setFocus()

    def _show_fix_errors_btn(self):
        """Show fix hint in compiler output; show continuation bar if this follows AI edits."""
        n = len(self._compiler_diagnostics)
        if self._compile_follows_ai_edits:
            self._compile_follows_ai_edits = False
            hint = f"\nErrors remain after applying AI changes ({n} diagnostic{'s' if n != 1 else ''})."
            self.compiler_output.append_output(hint, C["fg_warn"])
            # Compute diagnostic diff if we have a previous snapshot
            diff = None
            if self._prev_diagnostics:
                diff = _diff_diagnostics(self._prev_diagnostics, self._compiler_diagnostics)
            # Track stall: consecutive attempts where resolved == 0
            if diff:
                resolved, _, _ = diff
                if resolved == 0:
                    self._fix_stall_count += 1
                else:
                    self._fix_stall_count = 0
            stalled = self._fix_stall_count >= 2 and self._fix_attempt_count >= 3
            self.chat_panel.show_fix_continuation(
                n, self._fix_attempt_count, diff, stalled)
        else:
            hint = f"\nType /fix in AI Chat to auto-fix ({n} diagnostic{'s' if n != 1 else ''})"
            self.compiler_output.append_output(hint, C["teal"])

    def _update_diag_panel(self, diags):
        """Populate diagnostic panel and show/hide it."""
        self._diag_panel.populate(diags)
        self._diag_panel.setVisible(bool(diags))
        errors = sum(1 for d in diags if d.severity == "error")
        warnings = sum(1 for d in diags if d.severity == "warning")
        self._compile_badge.set_count(errors, warnings)

    def _apply_compile_diagnostics(self):
        """Apply gutter markers to editors based on compiler diagnostics."""
        if self._compiler_diagnostics:
            self.editor.apply_diagnostics(
                self._compiler_diagnostics, self.project_path or "")

    def _jump_to_error(self, filepath, line):
        """Jump to a file:line from compiler output double-click."""
        if not os.path.isabs(filepath) and self.project_path:
            filepath = os.path.join(self.project_path, filepath)
        self._switch_view(0)
        self.editor.goto_line(filepath, line)

    _PANEL_NAMES = {0: "editor", 1: "chat", 2: "files", 3: "settings", 4: "git", 5: "serial", 6: "libraries", 7: "boards", 8: "plotter"}
    _PANEL_INDICES = {v: k for k, v in _PANEL_NAMES.items()}

    def _save_project_state(self):
        """Save editor state to <project_root>/.arduinoaide_state.json."""
        if not self.project_path:
            return
        try:
            # Collect open files in tab order
            open_files = []
            for i in range(self.editor.tabs.count()):
                w = self.editor.tabs.widget(i)
                for fp, ed in self.editor._editors.items():
                    if ed is w:
                        open_files.append(os.path.relpath(fp, self.project_path))
                        break
            # Scroll positions
            scroll_positions = {}
            for fp, ed in self.editor._editors.items():
                rel = os.path.relpath(fp, self.project_path)
                if HAS_QSCINTILLA and hasattr(ed, 'firstVisibleLine'):
                    scroll_positions[rel] = ed.firstVisibleLine()
                else:
                    scroll_positions[rel] = ed.verticalScrollBar().value()
            # Active file
            active = self.editor.current_file()
            active_file = os.path.relpath(active, self.project_path) if active else ""
            # Active panel
            active_panel = self._PANEL_NAMES.get(
                self.view_stack.currentIndex(), "editor")
            state = {
                "open_files": open_files,
                "active_file": active_file,
                "scroll_positions": scroll_positions,
                "active_panel": active_panel,
            }
            state_path = os.path.join(self.project_path, ".arduinoaide_state.json")
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            # Ensure .arduinoaide_state.json is in .gitignore
            gi = os.path.join(self.project_path, ".gitignore")
            if os.path.isfile(gi):
                with open(gi, "r", encoding="utf-8") as f:
                    content = f.read()
                if ".arduinoaide_state.json" not in content:
                    with open(gi, "a", encoding="utf-8") as f:
                        if not content.endswith("\n"):
                            f.write("\n")
                        f.write(".arduinoaide_state.json\n")
        except Exception:
            pass  # silently ignore write errors

    def _restore_project_state(self):
        """Restore editor state from <project_root>/.arduinoaide_state.json."""
        if not self.project_path:
            return
        state_path = os.path.join(self.project_path, ".arduinoaide_state.json")
        if not os.path.isfile(state_path):
            return
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            return  # corrupt or unreadable — skip silently
        # Open files from saved list (skip any that no longer exist)
        saved_files = state.get("open_files", [])
        for rel in saved_files:
            abs_path = os.path.join(self.project_path, rel)
            if os.path.isfile(abs_path):
                self.editor.open_file(abs_path)
        # Defer scroll/tab/panel restoration until event loop processes new tabs
        def _finish_restore():
            # Restore scroll positions
            for rel, pos in state.get("scroll_positions", {}).items():
                abs_path = os.path.join(self.project_path, rel)
                ed = self.editor._editors.get(abs_path)
                if ed is None:
                    continue
                if HAS_QSCINTILLA and hasattr(ed, 'setFirstVisibleLine'):
                    ed.setFirstVisibleLine(pos)
                elif hasattr(ed, 'verticalScrollBar'):
                    ed.verticalScrollBar().setValue(pos)
            # Restore active tab
            active_file = state.get("active_file", "")
            if active_file:
                abs_active = os.path.join(self.project_path, active_file)
                if abs_active in self.editor._editors:
                    self.editor.tabs.setCurrentWidget(
                        self.editor._editors[abs_active])
            # Restore active panel
            panel = state.get("active_panel", "editor")
            idx = self._PANEL_INDICES.get(panel, 0)
            self._switch_view(idx)
        QTimer.singleShot(0, _finish_restore)

    def closeEvent(self, event):
        # Save project state before closing
        self._save_project_state()
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
        self.serial_monitor.cleanup()
        if self.chat_panel.thread.isRunning():
            self.chat_panel.worker.stop(); self.chat_panel.thread.quit(); self.chat_panel.thread.wait(2000)
        event.accept()


# =============================================================================
# Entry Point
# =============================================================================

def _ensure_backend():
    """Check backend connectivity; start Ollama if needed."""
    if AI_BACKEND == "lmstudio":
        # Just verify LM Studio is reachable — don't try to launch it
        try:
            requests.get(f"{LMSTUDIO_URL}/v1/models", timeout=2)
        except Exception:
            pass  # Non-fatal — user may start LM Studio later
        return
    # Ollama path
    try:
        requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
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
            requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
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
    # Load persisted configs
    config = _load_config()
    # Set globals from config before window creation
    global OLLAMA_MODEL, OLLAMA_URL, AI_BACKEND, LMSTUDIO_URL
    OLLAMA_MODEL = config.get("ollama_model", "teensy-coder")
    OLLAMA_URL = config.get("ollama_url", "http://localhost:11434").rstrip("/")
    AI_BACKEND = config.get("ai_backend", "ollama")
    LMSTUDIO_URL = config.get("lmstudio_url", "http://localhost:1234").rstrip("/")
    # Ensure AI backend is running
    _ensure_backend()
    # CLI arg takes precedence over saved project path
    project_path = None
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        project_path = os.path.abspath(sys.argv[1])
    elif config.get("project_path") and os.path.isdir(config["project_path"]):
        project_path = config["project_path"]
    w = MainWindow(project_path, config=config)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
