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
    QAbstractItemView, QGridLayout, QHeaderView
)
from PyQt6.QtCore import (
    Qt, QDir, QModelIndex, pyqtSignal, QObject, QThread,
    QTimer, QSize, QPoint, QPointF
)
from PyQt6.QtGui import (
    QFont, QColor, QAction, QKeySequence, QTextCursor,
    QTextCharFormat, QPalette, QFileSystemModel,
    QStandardItemModel, QStandardItem, QPainter, QPen,
    QPainterPath, QPolygonF, QPixmap, QIcon
)

try:
    from PyQt6.Qsci import QsciScintilla, QsciScintillaBase, QsciLexerCPP
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
TARGET_EXTENSIONS = {".ino", ".cpp", ".c", ".h", ".hpp"}  # code extensions for file-targeting detection
PROJECT_SKIP_DIRS = {'.git', '__pycache__', 'build', 'node_modules', '.venv', 'venv'}

SYSTEM_PROMPT = """You are an embedded-systems coding assistant integrated into an IDE for Teensy microcontrollers (PJRC).
You write clean, efficient C/C++ for real-time applications. You understand hardware registers, interrupts, DMA, timers, and peripheral configuration.

YOUR ROLE: Act, don't ask. The user's project files are included in every message — you already have them. Produce code edits directly.

BEHAVIOR RULES:
- When asked to change, fix, add, or remove code: produce <<<EDIT blocks immediately. Do not explain what you would do — do it.
- When asked to explain or analyze code: respond in plain text, no edit blocks.
- When compiler errors are included: produce <<<EDIT blocks that fix them. Do not ask which errors or which file.
- NEVER ask the user to "provide", "share", or "paste" a file — you already have it.
- NEVER say "please provide the path" — look at the files in your context.
- NEVER respond with only "Sure, I can help with that" — always include an edit or substantive answer.
- Prefer action over explanation. If the intent is clear, produce the edit.
- If genuinely ambiguous, ask ONE short clarifying question — never multiple.
- If you need a file not in your context, name it and the IDE will add it.

EDIT FORMAT — output this exact syntax to modify files:

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
- For adding code near a known landmark WITHOUT modifying existing code, prefer <<<INSERT_BEFORE or <<<INSERT_AFTER (see below). These only need a short anchor — no OLD/NEW replacement.
- You can also use <<<EDIT with enough OLD context to find the insertion point.
- NEVER use <<<FILE just to add a comment or make a small change — use <<<EDIT or <<<INSERT_BEFORE/<<<INSERT_AFTER.
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
>>>FILE

To INSERT new code before or after a known anchor line (without replacing anything):
<<<INSERT_BEFORE path/to/file.ext
<<<ANCHOR
void setup() {
>>>ANCHOR
<<<CONTENT
void blinkLED(int pin, int ms) {
  digitalWrite(pin, HIGH);
  delay(ms);
  digitalWrite(pin, LOW);
}
>>>CONTENT

<<<INSERT_AFTER works the same way but inserts AFTER the anchor.
Use INSERT_BEFORE/INSERT_AFTER when:
- Adding a new function, #include, or variable near a known landmark
- You don't need to modify the anchor code, just add code next to it
- The anchor is a short, unique snippet (e.g., a function signature, #include line)
Use <<<EDIT when you need to REPLACE existing code."""

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
    # Marker numbers for QScintilla gutter (0-31 available)
    _MARKER_ERROR = 8
    _MARKER_WARNING = 9

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
        self._working_set = WorkingSet()          # shadow context tracker (Step 2)
        self._ai_edited_files = set()             # rel_paths of files the AI has edited
        self._use_working_set_context = True      # WorkingSet is default; /debug-use-ws off for old path
        self._last_prompt_stats = None            # dict: stats from the last actual prompt sent
        self._target_override = None              # str: rel_path of file detected in user message (per-prompt only)
        self._symbol_index = {}                   # {name: [SymbolEntry, ...]} across all project files
        self._last_work_result = None             # AIWorkResult from most recent AI turn
        self._selection_mode = False              # True when using selection-based edit flow
        self._selection_edit = None               # dict with selection coords for selection mode
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
        # Outer container fills scroll area width; inner column centered at 800px
        outer_container = QWidget()
        outer_container.setStyleSheet(f"background:{C['bg_dark']};")
        outer_lay = QHBoxLayout(outer_container)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(0)
        outer_lay.addStretch()
        chat_column = QWidget()
        chat_column.setMaximumWidth(800)
        chat_column.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._chat_layout = QVBoxLayout(chat_column)
        self._chat_layout.setContentsMargins(20, 16, 20, 16)
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
        self.apply_all_btn = QPushButton("Apply All Changes")
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
                    entry = SymbolEntry(name, rel_path, offset_to_line(m.start()), "function")
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
        # Guard: reject if a generation is already in progress
        if self.thread.isRunning():
            self._add_info_msg(
                "Please wait — model is currently responding.", C['fg_warn'])
            return

        # Guard: warn if pending edits will be discarded
        # apply_bar is hidden after edits are applied, so escalation buttons
        # (which fire after apply) naturally bypass this check.
        if self._pending_edits and self.apply_bar.isVisible():
            n = len(self._pending_edits)
            reply = QMessageBox.question(
                self,
                "Discard pending edits?",
                f"You have {n} pending edit{'s' if n != 1 else ''} in the apply bar.\n"
                "Sending a new message will discard them.\n\n"
                "Discard and send?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Selection-based edit flow: if the active editor has selected text,
        # use a simpler prompt/response format that bypasses the <<<EDIT parser
        if self._editor_ref:
            editor_widget = self._editor_ref.tabs.currentWidget()
            if (editor_widget and hasattr(editor_widget, 'hasSelectedText')
                    and editor_widget.hasSelectedText()):
                sel_text = editor_widget.selectedText()
                l_from, c_from, l_to, c_to = editor_widget.getSelection()
                file_path = self._editor_ref.current_file()
                if sel_text.strip() and file_path:
                    self._send_selection_prompt(
                        text, sel_text, l_from, c_from, l_to, c_to,
                        file_path, display_text=display_text,
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
        user_msg = (f"File: {basename}\n\n{marked_content}\n\n"
                    f"User request: {user_text}")

        # One-shot conversation: system + single user message (no history)
        messages = [
            {"role": "system", "content": self._SELECTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        # Show user bubble
        show = display_text or user_text
        sel_preview = selected_text[:80].replace('\n', ' ')
        if len(selected_text) > 80:
            sel_preview += '…'
        self._add_user_msg(show, code=sel_preview if display_code is None else display_code)

        # Prepare UI for streaming (same as _send_prompt)
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._current_response = ""
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
        Strip code fences, detect explanations, or create selection edit."""
        text = response_text.strip()

        # Strip markdown code fences if LLM wrapped its response
        if text.startswith('```'):
            first_nl = text.find('\n')
            if first_nl != -1:
                text = text[first_nl + 1:]
        if text.endswith('```'):
            text = text[:text.rfind('```')].rstrip()

        # Detect explanation responses (no apply bar needed)
        original = self._selection_edit['original_text']
        code_starters = ('//', '#', '/*', 'void', 'int', 'float', 'char',
                         'bool', 'const', 'static', 'class', 'struct', 'enum',
                         'if', 'for', 'while', 'return', '#include', 'unsigned',
                         'long', 'short', 'double', 'auto', 'extern', 'typedef',
                         'namespace', 'template', 'using', 'public', 'private',
                         'protected', 'virtual', 'inline', 'volatile', 'register',
                         'switch', 'case', 'break', 'continue', 'do', 'else',
                         'try', 'catch', 'throw', 'delete', 'new', 'sizeof',
                         '{', '}', '(', ')', '[', ']')
        first_word = text.split()[0] if text.split() else ''
        is_explanation = (
            len(text) > len(original) * 3
            and '. ' in text
            and not any(text.lstrip().startswith(c) for c in code_starters)
            and not first_word.endswith(';')
        )
        if is_explanation:
            # Already rendered in chat as streaming text — nothing more to do
            return

        # Preserve trailing newline from original selection
        if original.endswith('\r\n') and not text.endswith('\r\n'):
            text = text.rstrip('\n') + '\r\n'
        elif original.endswith('\n') and not text.endswith('\n'):
            text += '\n'

        # Create a ProposedEdit for the selection replacement
        file_path = self._selection_edit['file_path']
        edit = ProposedEdit(
            edit_type="selection",
            filename=os.path.basename(file_path),
            old_text=original,
            new_text=text,
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
        f'padding:10px;margin:12px 0;'
        f'font-family:Menlo,Monaco,Courier New,monospace;font-size:13px;')
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
            # Selection mode: bypass <<<EDIT parser, handle replacement directly
            if self._selection_mode:
                self._handle_selection_response(self._current_response)
                self._selection_mode = False
            else:
                self._conversation.append(
                    {"role": "assistant", "content": self._current_response})
                self._render_formatted_response()
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
                if self._editor_ref.set_file_content(fp, edit.new_text):
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
                    if self._editor_ref.set_file_content(fp, new_content):
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
                    if self._editor_ref.set_file_content(fp, new_content):
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
                            # Save to disk
                            if hasattr(editor_w, 'save_file'):
                                editor_w.save_file()
                        else:
                            # Selection shifted — fall back to search_replace
                            files = self._editor_ref.get_all_files()
                            content = files.get(fp, "")
                            if edit.old_text and edit.old_text in content:
                                new_content = content.replace(
                                    edit.old_text, edit.new_text, 1)
                                if self._editor_ref.set_file_content(
                                        fp, new_content):
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
                            if self._editor_ref.set_file_content(fp, new_content):
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
            if self._editor_ref.set_file_content(fpath, original):
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
            f"Apply {n_accepted} of {n_total}" if n_excluded else "Apply All Changes")
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
        row.setContentsMargins(0, 0, 12, 0)
        row.addStretch()
        bubble = QFrame()
        bubble.setStyleSheet(
            f"QFrame {{ background-color:{C['bg_input']}; border-radius:14px; }}")
        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(16, 10, 16, 10)
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
            # Code block inside the bubble
            code_label = QLabel(code)
            code_label.setWordWrap(False)
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
# Settings Panel — AI Tools Tab
# =============================================================================

class AIToolsTab(QWidget):
    """CRUD editor for the right-click AI context menu actions — 2-column layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(20)

        # ====== LEFT column: Right-Click Actions list ======
        left = QVBoxLayout()
        left.setSpacing(0)

        hdr_left = QHBoxLayout()
        hdr_left.setContentsMargins(0, 0, 0, 10)
        hdr_left.setSpacing(6)
        left_title = QLabel("RIGHT-CLICK ACTIONS")
        left_title.setStyleSheet(SETTINGS_STITLE)
        hdr_left.addWidget(left_title)
        hdr_left.addStretch()
        add_btn = QPushButton("+ Add"); add_btn.setStyleSheet(BTN_SM_PRIMARY)
        add_btn.clicked.connect(self._add_action); hdr_left.addWidget(add_btn)
        sep_btn = QPushButton("+ Separator"); sep_btn.setStyleSheet(BTN_SM_GHOST)
        sep_btn.clicked.connect(self._add_separator); hdr_left.addWidget(sep_btn)
        reset_btn = QPushButton("Reset"); reset_btn.setStyleSheet(BTN_SM_GHOST)
        reset_btn.clicked.connect(self._reset_defaults); hdr_left.addWidget(reset_btn)
        left.addLayout(hdr_left)

        list_card = QFrame()
        list_card.setStyleSheet(SETTINGS_CARD)
        list_card_layout = QVBoxLayout(list_card)
        list_card_layout.setContentsMargins(0, 0, 0, 0)
        list_card_layout.setSpacing(0)

        self.action_list = QListWidget()
        self.action_list.setStyleSheet(
            f"QListWidget{{background:transparent;border:none;{FONT_BODY}}}"
            f"QListWidget::item{{border-bottom:1px solid {C['border']};padding:0px;}}"
            f"QListWidget::item:selected{{background:{C['bg_hover']};"
            f"border-left:2px solid {C['teal']};}}"
            f"QListWidget::item:hover:!selected{{background:{C['bg_hover']};}}")
        self.action_list.currentRowChanged.connect(self._on_row_changed)
        list_card_layout.addWidget(self.action_list)
        left.addWidget(list_card, stretch=1)

        self.list_status = QLabel("")
        self.list_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        self.list_status.setContentsMargins(0, 4, 0, 0)
        left.addWidget(self.list_status)

        left_w = QWidget(); left_w.setLayout(left)
        outer.addWidget(left_w, stretch=1)

        # ====== RIGHT column: Edit Action pane (always visible) ======
        right = QVBoxLayout()
        right.setSpacing(0)

        hdr_right = QHBoxLayout()
        hdr_right.setContentsMargins(0, 0, 0, 10)
        right_title = QLabel("EDIT ACTION")
        right_title.setStyleSheet(SETTINGS_STITLE)
        hdr_right.addWidget(right_title)
        hdr_right.addStretch()
        right.addLayout(hdr_right)

        edit_card = QFrame()
        edit_card.setStyleSheet(SETTINGS_CARD)
        ecl = QVBoxLayout(edit_card)
        ecl.setContentsMargins(16, 16, 16, 16)
        ecl.setSpacing(10)

        lbl_row = QHBoxLayout()
        lbl_row.setSpacing(8)
        lbl_lbl = QLabel("Label")
        lbl_lbl.setMinimumWidth(56)
        lbl_lbl.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        lbl_row.addWidget(lbl_lbl)
        self.label_edit = QLineEdit()
        self.label_edit.setStyleSheet(SETTINGS_INPUT)
        self.label_edit.setPlaceholderText("Action name…")
        lbl_row.addWidget(self.label_edit)
        ecl.addLayout(lbl_row)

        prompt_row = QHBoxLayout()
        prompt_row.setSpacing(8)
        prompt_row.setAlignment(Qt.AlignmentFlag.AlignTop)
        prompt_lbl = QLabel("Prompt")
        prompt_lbl.setMinimumWidth(56)
        prompt_lbl.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        prompt_row.addWidget(prompt_lbl)
        prompt_col = QVBoxLayout()
        self.template_edit = QPlainTextEdit()
        self.template_edit.setStyleSheet(
            f"background:{C['bg_input']};color:{C['fg']};"
            f"border:1px solid {C['border_light']};border-radius:6px;"
            f"padding:6px 10px;{FONT_CODE}")
        self.template_edit.setMinimumHeight(200)
        self.template_edit.setPlaceholderText(
            'e.g. "Explain what the following code does:\\n\\n```cpp\\n{code}\\n```"')
        prompt_col.addWidget(self.template_edit)
        hint_lbl = QLabel("Use {code} where the selected code should be inserted.")
        hint_lbl.setStyleSheet(f"color:{C['fg_muted']};{FONT_SMALL}")
        prompt_col.addWidget(hint_lbl)
        prompt_row.addLayout(prompt_col)
        ecl.addLayout(prompt_row)

        btns_row = QHBoxLayout()
        btns_row.addStretch()
        cancel_btn = QPushButton("Cancel"); cancel_btn.setStyleSheet(BTN_SM_GHOST)
        cancel_btn.clicked.connect(self._cancel_edit); btns_row.addWidget(cancel_btn)
        self.save_edit_btn = QPushButton("Save Changes")
        self.save_edit_btn.setStyleSheet(BTN_SM_PRIMARY)
        self.save_edit_btn.clicked.connect(self._save_current_edit)
        btns_row.addWidget(self.save_edit_btn)
        ecl.addLayout(btns_row)

        self.edit_status = QLabel("")
        self.edit_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        ecl.addWidget(self.edit_status)

        right.addWidget(edit_card, stretch=1)
        right_w = QWidget(); right_w.setLayout(right)
        outer.addWidget(right_w, stretch=1)

        self._editing_index = -1
        self._populate_list()

    # -- Custom item widget helpers --

    def _make_action_widget(self, label, template):
        w = QWidget()
        w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        rl = QHBoxLayout(w); rl.setContentsMargins(8, 6, 8, 6); rl.setSpacing(8)
        drag = QLabel("\u28bf")
        drag.setStyleSheet(f"color:{C['fg_muted']};{FONT_BODY}")
        drag.setFixedWidth(16)
        rl.addWidget(drag)
        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(f"color:{C['fg']};{FONT_BODY}")
        rl.addWidget(name_lbl, stretch=1)
        preview = (template[:48].replace("\n", " ") + "…") if len(template) > 48 else template.replace("\n", " ")
        prev_lbl = QLabel(preview)
        prev_lbl.setStyleSheet(f"color:{C['fg_muted']};{FONT_SMALL}")
        prev_lbl.setMaximumWidth(160)
        rl.addWidget(prev_lbl)
        return w

    def _make_builtin_widget(self, label):
        w = QWidget()
        w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        rl = QHBoxLayout(w); rl.setContentsMargins(8, 6, 8, 6); rl.setSpacing(8)
        spacer = QLabel(""); spacer.setFixedWidth(16); rl.addWidget(spacer)
        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(f"color:{C['fg']};{FONT_BODY}")
        rl.addWidget(name_lbl, stretch=1)
        tag = QLabel("built-in")
        tag.setStyleSheet(
            f"color:{C['fg_dim']};background:{C['bg_hover']};"
            f"{FONT_SMALL};border-radius:3px;padding:1px 5px;")
        rl.addWidget(tag)
        return w

    def _populate_list(self):
        self.action_list.clear()
        for entry in AI_ACTIONS:
            if entry is None:
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 18))
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setData(Qt.ItemDataRole.UserRole, "separator")
                sep_w = QWidget()
                sl = QHBoxLayout(sep_w); sl.setContentsMargins(12, 0, 12, 0)
                line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
                line.setStyleSheet(f"color:{C['border_light']};")
                sl.addWidget(line)
                self.action_list.addItem(item)
                self.action_list.setItemWidget(item, sep_w)
            else:
                label, template = entry
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 36))
                item.setData(Qt.ItemDataRole.UserRole,
                             "builtin" if template is None else "action")
                w = self._make_builtin_widget(label) if template is None \
                    else self._make_action_widget(label, template)
                self.action_list.addItem(item)
                self.action_list.setItemWidget(item, w)
        # Restore or default selection
        sel = max(0, min(self._editing_index, self.action_list.count() - 1))
        self.action_list.setCurrentRow(sel)

    def _on_row_changed(self, row):
        """Populate the always-visible edit pane from the selected row."""
        if row < 0 or row >= len(AI_ACTIONS):
            self._editing_index = -1
            self.label_edit.setEnabled(False); self.template_edit.setEnabled(False)
            self.save_edit_btn.setEnabled(False)
            return
        entry = AI_ACTIONS[row]
        if entry is None:
            self._editing_index = -1
            self.label_edit.setEnabled(False); self.template_edit.setEnabled(False)
            self.save_edit_btn.setEnabled(False)
            self.label_edit.clear(); self.template_edit.clear()
            self.edit_status.setText("Separators cannot be edited.")
            self.edit_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
            return
        label, template = entry
        if template is None:
            self._editing_index = -1
            self.label_edit.setEnabled(False); self.template_edit.setEnabled(False)
            self.save_edit_btn.setEnabled(False)
            self.label_edit.setText(label)
            self.template_edit.setPlainText("(Built-in action — cannot be edited)")
            self.edit_status.setText("Built-in actions cannot be edited.")
            self.edit_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
            return
        self._editing_index = row
        self.label_edit.setEnabled(True); self.template_edit.setEnabled(True)
        self.save_edit_btn.setEnabled(True)
        self.label_edit.setText(label)
        self.template_edit.setPlainText(template)
        self.edit_status.setText("")

    def _add_action(self):
        insert_idx = len(AI_ACTIONS) - 1
        for i in range(len(AI_ACTIONS) - 1, -1, -1):
            if AI_ACTIONS[i] is not None and AI_ACTIONS[i][1] is None:
                insert_idx = i; break
        AI_ACTIONS.insert(insert_idx, (
            "New Action",
            "Your prompt here. Use {code} for selected code.\n\n```cpp\n{code}\n```"))
        self._persist()
        self._editing_index = insert_idx
        self._populate_list()
        self.action_list.setCurrentRow(insert_idx)

    def _edit_action(self):
        self._on_row_changed(self.action_list.currentRow())

    def _save_current_edit(self):
        if self._editing_index < 0:
            return
        label = self.label_edit.text().strip()
        template = self.template_edit.toPlainText()
        if not label:
            self.edit_status.setText("Label cannot be empty.")
            self.edit_status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")
            return
        AI_ACTIONS[self._editing_index] = (label, template)
        self._persist()
        row = self._editing_index
        self._populate_list()
        self.action_list.setCurrentRow(row)
        self.edit_status.setText("Action saved.")
        self.edit_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")

    def _cancel_edit(self):
        row = self._editing_index if self._editing_index >= 0 \
            else self.action_list.currentRow()
        self._on_row_changed(row)

    def _delete_action(self):
        row = self.action_list.currentRow()
        if row < 0 or row >= len(AI_ACTIONS):
            return
        entry = AI_ACTIONS[row]
        if entry is not None and entry[1] is None:
            self.list_status.setText("Cannot delete 'Ask AI About This...'")
            self.list_status.setStyleSheet(f"color:{C['fg_warn']};{FONT_SMALL}")
            return
        del AI_ACTIONS[row]
        self._persist()
        self._editing_index = -1
        self._populate_list()
        self.list_status.setText("Action deleted.")
        self.list_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")

    def _add_separator(self):
        row = self.action_list.currentRow()
        insert_at = row + 1 if row >= 0 else len(AI_ACTIONS) - 1
        if insert_at >= len(AI_ACTIONS):
            insert_at = len(AI_ACTIONS) - 1
        AI_ACTIONS.insert(insert_at, None)
        self._persist()
        self._populate_list()

    def _move_up(self):
        row = self.action_list.currentRow()
        if row <= 0: return
        AI_ACTIONS[row], AI_ACTIONS[row - 1] = AI_ACTIONS[row - 1], AI_ACTIONS[row]
        self._persist(); self._editing_index = row - 1
        self._populate_list(); self.action_list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.action_list.currentRow()
        if row < 0 or row >= len(AI_ACTIONS) - 2: return
        AI_ACTIONS[row], AI_ACTIONS[row + 1] = AI_ACTIONS[row + 1], AI_ACTIONS[row]
        self._persist(); self._editing_index = row + 1
        self._populate_list(); self.action_list.setCurrentRow(row + 1)

    def _reset_defaults(self):
        if QMessageBox.question(
            self, "Reset AI Tools",
            "Reset all AI actions to defaults?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        AI_ACTIONS[:] = list(DEFAULT_AI_ACTIONS)
        self._persist()
        self._editing_index = -1
        self._populate_list()
        self.list_status.setText("Reset to defaults.")
        self.list_status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")

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
        # Outer scroll area wrapping the 2×2 grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{C['bg_dark']};}}")

        content = QWidget()
        content.setStyleSheet(f"background:{C['bg_dark']};")
        scroll_layout = QVBoxLayout(content)
        scroll_layout.setContentsMargins(16, 16, 16, 16)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # ── Cell (0,0): Installed Models ──────────────────────────────────────
        cell00 = QWidget()
        c00 = QVBoxLayout(cell00); c00.setContentsMargins(0,0,0,0); c00.setSpacing(8)

        hdr00 = QHBoxLayout(); hdr00.setSpacing(6)
        t00 = QLabel("INSTALLED MODELS"); t00.setStyleSheet(SETTINGS_STITLE)
        hdr00.addWidget(t00); hdr00.addStretch()
        refresh_btn = QPushButton("↻ Refresh"); refresh_btn.setStyleSheet(BTN_SM_GHOST)
        refresh_btn.clicked.connect(self.refresh_models); hdr00.addWidget(refresh_btn)
        c00.addLayout(hdr00)

        self.model_table = QTableWidget()
        self.model_table.setColumnCount(4)
        self.model_table.setHorizontalHeaderLabels(["Model", "Size", "Modified", "Status"])
        self.model_table.horizontalHeader().setStyleSheet(SETTINGS_TBL_HDR)
        self.model_table.setStyleSheet(SETTINGS_TABLE)
        self.model_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.model_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.model_table.setSortingEnabled(True)
        self.model_table.setMaximumHeight(200)
        self.model_table.verticalHeader().setVisible(False)
        mhdr = self.model_table.horizontalHeader()
        mhdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        mhdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        mhdr.resizeSection(1, 64)
        mhdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        mhdr.resizeSection(2, 64)
        mhdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        mhdr.resizeSection(3, 68)
        self.model_table.itemClicked.connect(self._on_select)
        c00.addWidget(self.model_table)

        btn_row00 = QHBoxLayout(); btn_row00.setSpacing(6)
        self.load_btn = QPushButton("Load"); self.load_btn.setStyleSheet(BTN_SM_PRIMARY)
        self.load_btn.setToolTip("Load model into memory")
        self.load_btn.clicked.connect(self._load_selected); btn_row00.addWidget(self.load_btn)
        self.unload_btn = QPushButton("Unload"); self.unload_btn.setStyleSheet(BTN_SM_SECONDARY)
        self.unload_btn.setToolTip("Unload from memory")
        self.unload_btn.clicked.connect(self._unload_selected)
        btn_row00.addWidget(self.unload_btn)
        del00_btn = QPushButton("Delete"); del00_btn.setStyleSheet(BTN_SM_DANGER)
        del00_btn.clicked.connect(self._delete); btn_row00.addWidget(del00_btn)
        btn_row00.addStretch()
        c00.addLayout(btn_row00)

        self.model_status = QLabel("")
        self.model_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        c00.addWidget(self.model_status)

        grid.addWidget(cell00, 0, 0, Qt.AlignmentFlag.AlignTop)

        # ── Cell (0,1): Pull New Model ────────────────────────────────────────
        cell01 = QWidget()
        c01 = QVBoxLayout(cell01); c01.setContentsMargins(0,0,0,0); c01.setSpacing(8)

        t01 = QLabel("PULL NEW MODEL"); t01.setStyleSheet(SETTINGS_STITLE)
        c01.addWidget(t01)

        self.pull_filter = QLineEdit()
        self.pull_filter.setPlaceholderText("Search models…")
        self.pull_filter.setStyleSheet(SETTINGS_INPUT)
        self.pull_filter.textChanged.connect(self._filter_curated)
        c01.addWidget(self.pull_filter)

        self.curated_table = QTableWidget()
        self.curated_table.setColumnCount(2)
        self.curated_table.setHorizontalHeaderLabels(["Model", "Size"])
        self.curated_table.horizontalHeader().setStyleSheet(SETTINGS_TBL_HDR)
        self.curated_table.setStyleSheet(SETTINGS_TABLE)
        self.curated_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.curated_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.curated_table.setSortingEnabled(True)
        self.curated_table.setMaximumHeight(148)
        self.curated_table.verticalHeader().setVisible(False)
        chdr = self.curated_table.horizontalHeader()
        chdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        chdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        chdr.resizeSection(1, 64)
        c01.addWidget(self.curated_table)

        pull_action_row = QHBoxLayout(); pull_action_row.setSpacing(6)
        pull_sel_btn = QPushButton("Pull Selected"); pull_sel_btn.setStyleSheet(BTN_SM_PRIMARY)
        pull_sel_btn.clicked.connect(self._pull_curated)
        pull_action_row.addWidget(pull_sel_btn)
        or_lbl = QLabel("or"); or_lbl.setStyleSheet(f"color:{C['fg_muted']};{FONT_SMALL}")
        pull_action_row.addWidget(or_lbl)
        self.custom_pull_name = QLineEdit()
        self.custom_pull_name.setPlaceholderText("e.g. mistral:7b")
        self.custom_pull_name.setStyleSheet(SETTINGS_INPUT)
        self.custom_pull_name.returnPressed.connect(self._pull_custom)
        pull_action_row.addWidget(self.custom_pull_name, stretch=1)
        pull_any_btn = QPushButton("Pull"); pull_any_btn.setStyleSheet(BTN_SM_SECONDARY)
        pull_any_btn.clicked.connect(self._pull_custom); pull_action_row.addWidget(pull_any_btn)
        c01.addLayout(pull_action_row)

        pull_prog_row = QHBoxLayout(); pull_prog_row.setSpacing(6)
        self.pull_progress = QProgressBar()
        self.pull_progress.setRange(0, 100); self.pull_progress.setTextVisible(True)
        self.pull_progress.setStyleSheet(
            f"QProgressBar{{background:{C['bg_input']};border:1px solid {C['border_light']};"
            f"border-radius:3px;height:12px;{FONT_SMALL}}}"
            f"QProgressBar::chunk{{background:{C['teal']};border-radius:2px;}}")
        self.pull_progress.hide(); pull_prog_row.addWidget(self.pull_progress, stretch=1)
        self._pull_cancel_btn = QPushButton("Cancel")
        self._pull_cancel_btn.setStyleSheet(BTN_DANGER)
        self._pull_cancel_btn.clicked.connect(self._cancel_pull)
        self._pull_cancel_btn.hide(); pull_prog_row.addWidget(self._pull_cancel_btn)
        c01.addLayout(pull_prog_row)
        self._pull_cancelled = False

        self.pull_status = QLabel("")
        self.pull_status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        c01.addWidget(self.pull_status)

        grid.addWidget(cell01, 0, 1, Qt.AlignmentFlag.AlignTop)

        # ── Cell (1,0): Model Details ─────────────────────────────────────────
        cell10 = QWidget()
        c10 = QVBoxLayout(cell10); c10.setContentsMargins(0,0,0,0); c10.setSpacing(8)

        t10 = QLabel("MODEL DETAILS"); t10.setStyleSheet(SETTINGS_STITLE)
        c10.addWidget(t10)

        details_card = QFrame(); details_card.setStyleSheet(SETTINGS_CARD)
        dcl = QVBoxLayout(details_card)
        dcl.setContentsMargins(16, 14, 16, 14); dcl.setSpacing(4)

        info_grid = QGridLayout(); info_grid.setSpacing(3); info_grid.setColumnStretch(1, 1)
        self._detail_vals = {}
        for i, key in enumerate(["Name", "Architecture", "Parameters",
                                  "Max Context", "Quantization"]):
            k_lbl = QLabel(key)
            k_lbl.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
            v_lbl = QLabel("—"); v_lbl.setStyleSheet(f"color:{C['fg']};{FONT_BODY}")
            info_grid.addWidget(k_lbl, i, 0); info_grid.addWidget(v_lbl, i, 1)
            self._detail_vals[key] = v_lbl
        dcl.addLayout(info_grid)

        sep_line = QFrame(); sep_line.setFrameShape(QFrame.Shape.HLine)
        sep_line.setStyleSheet(f"color:{C['border']};margin-top:6px;margin-bottom:6px;")
        dcl.addWidget(sep_line)

        desc_row = QHBoxLayout(); desc_row.setSpacing(6)
        desc_lbl = QLabel("Description"); desc_lbl.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        desc_row.addWidget(desc_lbl)
        self.desc_edit = QLineEdit()
        self.desc_edit.setStyleSheet(SETTINGS_INPUT)
        self.desc_edit.setPlaceholderText("Short label shown in toolbar dropdown")
        desc_row.addWidget(self.desc_edit, stretch=1)
        save_desc_btn = QPushButton("Save"); save_desc_btn.setStyleSheet(BTN_SM_PRIMARY)
        save_desc_btn.clicked.connect(self._save_desc); desc_row.addWidget(save_desc_btn)
        gen_desc_btn = QPushButton("Auto"); gen_desc_btn.setStyleSheet(BTN_SM_GHOST)
        gen_desc_btn.clicked.connect(self._auto_gen_desc); desc_row.addWidget(gen_desc_btn)
        dcl.addLayout(desc_row)

        hint10 = QLabel("Short label shown in the toolbar dropdown")
        hint10.setStyleSheet(f"color:{C['fg_muted']};{FONT_SMALL}")
        dcl.addWidget(hint10)

        self.status = QLabel(""); self.status.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        dcl.addWidget(self.status)

        c10.addWidget(details_card)
        grid.addWidget(cell10, 1, 0, Qt.AlignmentFlag.AlignTop)

        # ── Cell (1,1): Create Custom Model ───────────────────────────────────
        cell11 = QWidget()
        c11 = QVBoxLayout(cell11); c11.setContentsMargins(0,0,0,0); c11.setSpacing(8)

        t11 = QLabel("CREATE CUSTOM MODEL"); t11.setStyleSheet(SETTINGS_STITLE)
        c11.addWidget(t11)

        create_card = QFrame(); create_card.setStyleSheet(SETTINGS_CARD)
        ccl = QVBoxLayout(create_card)
        ccl.setContentsMargins(16, 14, 16, 14); ccl.setSpacing(8)

        r1 = QHBoxLayout(); r1.setSpacing(8)
        r1_lbl = QLabel("Name"); r1_lbl.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        r1_lbl.setMinimumWidth(64); r1.addWidget(r1_lbl)
        self.name_in = QLineEdit(); self.name_in.setPlaceholderText("e.g. teensy-coder-v2")
        self.name_in.setStyleSheet(SETTINGS_INPUT); r1.addWidget(self.name_in); ccl.addLayout(r1)

        r2 = QHBoxLayout(); r2.setSpacing(8)
        r2_lbl = QLabel("Base"); r2_lbl.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        r2_lbl.setMinimumWidth(64); r2.addWidget(r2_lbl)
        self.base_cb = QComboBox(); self.base_cb.setEditable(True)
        self.base_cb.setStyleSheet(SETTINGS_COMBO)
        r2.addWidget(self.base_cb, stretch=1); ccl.addLayout(r2)

        r3 = QHBoxLayout(); r3.setSpacing(8)
        r3_lbl = QLabel("Context"); r3_lbl.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        r3_lbl.setMinimumWidth(64); r3.addWidget(r3_lbl)
        self.ctx_cb = QComboBox(); self.ctx_cb.addItems(["4096","8192","16384","32768","65536"])
        self.ctx_cb.setCurrentText("16384"); self.ctx_cb.setEditable(True)
        self.ctx_cb.setStyleSheet(SETTINGS_COMBO); self.ctx_cb.setFixedWidth(90)
        r3.addWidget(self.ctx_cb)
        temp_lbl = QLabel("Temp"); temp_lbl.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        r3.addWidget(temp_lbl)
        self.temp_in = QLineEdit("0.7"); self.temp_in.setStyleSheet(SETTINGS_INPUT)
        self.temp_in.setFixedWidth(52); r3.addWidget(self.temp_in)
        r3.addStretch(); ccl.addLayout(r3)

        r4 = QHBoxLayout(); r4.setSpacing(8); r4.setAlignment(Qt.AlignmentFlag.AlignTop)
        r4_lbl = QLabel("System"); r4_lbl.setStyleSheet(f"color:{C['fg_dim']};{FONT_SMALL}")
        r4_lbl.setMinimumWidth(64); r4.addWidget(r4_lbl)
        self.sys_in = QPlainTextEdit()
        self.sys_in.setStyleSheet(
            f"background:{C['bg_input']};color:{C['fg']};"
            f"border:1px solid {C['border_light']};border-radius:6px;"
            f"padding:6px 10px;{FONT_CODE}")
        self.sys_in.setPlaceholderText("e.g. You are an expert embedded systems developer…")
        self.sys_in.setMinimumHeight(54)
        r4.addWidget(self.sys_in, stretch=1); ccl.addLayout(r4)

        r5 = QHBoxLayout(); r5.addStretch()
        prev_btn = QPushButton("Preview"); prev_btn.setStyleSheet(BTN_SM_GHOST)
        prev_btn.clicked.connect(self._preview); r5.addWidget(prev_btn)
        create_btn = QPushButton("Create Model"); create_btn.setStyleSheet(BTN_SM_PRIMARY)
        create_btn.clicked.connect(self._create); r5.addWidget(create_btn)
        ccl.addLayout(r5)

        self.mf_preview = QPlainTextEdit(); self.mf_preview.setReadOnly(True)
        self.mf_preview.setMaximumHeight(90); self.mf_preview.setPlaceholderText("Modelfile preview…")
        self.mf_preview.hide(); ccl.addWidget(self.mf_preview)

        c11.addWidget(create_card)
        grid.addWidget(cell11, 1, 1, Qt.AlignmentFlag.AlignTop)

        scroll_layout.addLayout(grid)
        scroll_layout.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        outer.addWidget(scroll)

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
        self.model_table.setRowCount(0); self.base_cb.clear()
        try:
            r = requests.get(f"{self.BASE}/api/tags", timeout=5)
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
                    st_item = QTableWidgetItem("Idle")
                    st_item.setForeground(QColor(C['fg_dim']))
                    self.model_table.setItem(row, 3, st_item)
                    self.base_cb.addItem(n)
        except Exception as e:
            self.status.setText(f"Ollama error: {e}")
            self.status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

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

    def _on_select(self, item):
        row = item.row()
        ni = self.model_table.item(row, 0)
        if not ni: return
        name = ni.text(); self.name_in.setText(name)
        descs = self._load_descs()
        self.desc_edit.setText(descs.get(name, ""))
        try:
            r = requests.post(f"{self.BASE}/api/show", json={"name": name}, timeout=10)
            if r.status_code == 200:
                d = r.json(); info = d.get("model_info", {})
                arch = info.get("general.architecture", "?") if info else "?"
                pc = info.get("general.parameter_count", "") if info else ""
                cl = info.get(f"{arch}.context_length", "") if info else ""
                quant = ""
                for k, v in (info.items() if info else []):
                    if "quantization" in k.lower(): quant = str(v); break
                self._detail_vals["Name"].setText(name)
                self._detail_vals["Architecture"].setText(arch)
                self._detail_vals["Parameters"].setText(
                    f"{int(pc)/1e9:.1f}B" if pc else "?")
                self._detail_vals["Max Context"].setText(
                    f"{int(cl):,} tokens" if cl else "?")
                self._detail_vals["Quantization"].setText(quant or "?")
                sys_prompt = d.get("system", "")
                mf = d.get("modelfile", "")
                if mf:
                    self.mf_preview.setPlainText(mf)
                    if not sys_prompt:
                        if 'SYSTEM """' in mf:
                            try:
                                sys_prompt = mf[mf.index('SYSTEM """')+10:
                                               mf.index('"""', mf.index('SYSTEM """')+10)].strip()
                            except: pass
                        elif 'SYSTEM "' in mf:
                            try:
                                start = mf.index('SYSTEM "') + 8
                                sys_prompt = mf[start:mf.index('"', start)].strip()
                            except: pass
                    for ln in mf.splitlines():
                        if ln.startswith("FROM "): self.base_cb.setCurrentText(ln[5:].strip())
                        if "num_ctx" in ln.lower(): self.ctx_cb.setCurrentText(ln.split()[-1])
                        if "temperature" in ln.lower(): self.temp_in.setText(ln.split()[-1])
                if sys_prompt:
                    self.sys_in.setPlainText(sys_prompt)
        except Exception as e:
            self.status.setText(f"Error: {e}")
            self.status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

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
        row = self.model_table.currentRow()
        if row < 0: return
        name = self.model_table.item(row, 0).text()
        if QMessageBox.question(self, "Delete", f"Delete '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                r = requests.delete(f"{self.BASE}/api/delete", json={"name": name}, timeout=30)
                if r.status_code == 200:
                    self.status.setText(f"Deleted."); self.status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
                    self.refresh_models(); self.model_changed.emit()
            except Exception as e:
                self.status.setText(str(e)); self.status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _rename(self):
        """Rename selected model via Ollama copy + delete."""
        from PyQt6.QtWidgets import QInputDialog
        row = self.model_table.currentRow()
        if row < 0:
            return
        old_name = self.model_table.item(row, 0).text()
        new_name, ok = QInputDialog.getText(
            self, "Rename Model", f"New name for '{old_name}':", text=old_name)
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        new_name = new_name.strip()
        try:
            r = requests.post(f"{self.BASE}/api/copy",
                              json={"source": old_name, "destination": new_name},
                              timeout=30)
            if r.status_code == 200:
                requests.delete(f"{self.BASE}/api/delete",
                                json={"name": old_name}, timeout=30)
                self.status.setText(f"Renamed to '{new_name}'.")
                self.status.setStyleSheet(f"color:{C['fg_ok']};{FONT_SMALL}")
                self.refresh_models()
                self.model_changed.emit()
            else:
                self.status.setText(f"Rename failed: {r.text}")
                self.status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")
        except Exception as e:
            self.status.setText(str(e))
            self.status.setStyleSheet(f"color:{C['fg_err']};{FONT_SMALL}")

    def _reveal_models_folder(self):
        """Open the Ollama models folder in Finder."""
        import subprocess
        folder = os.path.expanduser("~/.ollama/models")
        if not os.path.isdir(folder):
            folder = os.path.expanduser("~/.ollama")
        subprocess.Popen(["open", folder])

    # ---- Load / Unload Model methods ----

    def _load_selected(self):
        """Load the selected model into Ollama memory."""
        row = self.model_table.currentRow()
        if row < 0:
            self.model_status.setText("Select a model to load.")
            self.model_status.setStyleSheet(f"color:{C['fg_warn']};{FONT_SMALL}")
            return
        name = self.model_table.item(row, 0).text()
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
        row = self.model_table.currentRow()
        if row < 0:
            self.model_status.setText("Select a model to unload.")
            self.model_status.setStyleSheet(f"color:{C['fg_warn']};{FONT_SMALL}")
            return
        name = self.model_table.item(row, 0).text()
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
        for row in range(self.model_table.rowCount()):
            item = self.model_table.item(row, 0)
            if item:
                names.add(item.text())
        return names

    def _populate_curated_list(self, filter_text=""):
        self.curated_table.setRowCount(0)
        installed = self._get_installed_names()
        ft = filter_text.lower()
        for m in CURATED_MODELS:
            name, size, desc = m["name"], m["size"], m["desc"]
            if ft and ft not in name.lower() and ft not in desc.lower():
                continue
            row = self.curated_table.rowCount()
            self.curated_table.insertRow(row)
            is_installed = name in installed
            name_item = QTableWidgetItem(name)
            size_item = QTableWidgetItem(size)
            if is_installed:
                name_item.setForeground(QColor(C["fg_dim"]))
                size_item.setForeground(QColor(C["fg_dim"]))
            self.curated_table.setItem(row, 0, name_item)
            self.curated_table.setItem(row, 1, size_item)

    def _filter_curated(self, text):
        self._populate_curated_list(text)

    def _pull_curated(self):
        row = self.curated_table.currentRow()
        if row < 0:
            self.pull_status.setText("Select a model from the list first.")
            self.pull_status.setStyleSheet(f"color:{C['fg_warn']};{FONT_SMALL}")
            return
        name_item = self.curated_table.item(row, 0)
        if not name_item: return
        self._pull_model(name_item.text().strip())

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
        self.pull_progress.setValue(0)
        self.pull_progress.show()
        self._pull_cancel_btn.show()
        self._pull_cancelled = False

        def go():
            try:
                r = requests.post(
                    f"{self.BASE}/api/pull",
                    json={"name": name}, stream=True, timeout=(10, 600))
                last_status = ""
                for line in r.iter_lines():
                    if self._pull_cancelled:
                        r.close()
                        QTimer.singleShot(0, lambda: self._on_pull_done(
                            f"Pull of '{name}' cancelled.", False))
                        return
                    if line:
                        try:
                            chunk = json.loads(line)
                            status = chunk.get("status", "")
                            completed = chunk.get("completed", 0)
                            total = chunk.get("total", 0)
                            if total and completed:
                                pct = int(completed / total * 100)
                                msg = f"{status} \u2014 {pct}%"
                            else:
                                pct = -1  # indeterminate
                                msg = status
                            last_status = status
                            QTimer.singleShot(0, lambda m=msg, p=pct: self._on_pull_progress(m, p))
                        except json.JSONDecodeError:
                            continue
                ok = "success" in last_status.lower()
                QTimer.singleShot(0, lambda: self._on_pull_done(name, ok))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_pull_done(str(e), False))
        threading.Thread(target=go, daemon=True).start()

    def _cancel_pull(self):
        """Cancel an in-progress model pull."""
        self._pull_cancelled = True
        self.pull_status.setText("Cancelling...")

    def _on_pull_progress(self, msg, pct=-1):
        self.pull_status.setText(msg)
        if pct >= 0:
            self.pull_progress.setRange(0, 100)
            self.pull_progress.setValue(pct)
        else:
            # Indeterminate (e.g. "pulling manifest", "verifying sha256")
            self.pull_progress.setRange(0, 0)

    def _on_pull_done(self, name, success):
        self.pull_progress.hide()
        self._pull_cancel_btn.hide()
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
# Settings Panel — Container
# =============================================================================

class SettingsPanel(QWidget):
    """Settings panel with Models, AI Tools, and Git tabs."""
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

        self.git_tab = GitTab()
        self.tabs.addTab(self.git_tab, "Git")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

    def _on_tab_changed(self, index):
        if index == 2:  # Git tab
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
        self.btn_git = GitSidebarButton("Git")
        self.btn_serial = SerialSidebarButton("Serial Monitor")
        self.btn_settings = SettingsSidebarButton("Settings")

        self.btn_code.clicked.connect(lambda: self._switch_view(0))
        self.btn_chat.clicked.connect(lambda: self._switch_view(1))
        self.btn_files.clicked.connect(lambda: self._switch_view(2))
        self.btn_settings.clicked.connect(lambda: self._switch_view(3))
        self.btn_git.clicked.connect(lambda: self._switch_view(4))
        self.btn_serial.clicked.connect(lambda: self._switch_view(5))

        sb_layout.addWidget(self.btn_code)
        sb_layout.addWidget(self.btn_chat)
        sb_layout.addWidget(self.btn_files)
        sb_layout.addWidget(self.btn_git)
        sb_layout.addWidget(self.btn_serial)
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
        self.settings_panel.model_changed.connect(self._refresh_models)
        self.view_stack.addWidget(self.settings_panel)

        # View 4: Git panel (full panel)
        self.git_panel = GitPanel()
        self.git_panel.branch_changed.connect(self._on_branch_changed)
        self.view_stack.addWidget(self.git_panel)

        # View 5: Serial Monitor (full panel)
        self.serial_monitor = SerialMonitor()
        self.view_stack.addWidget(self.serial_monitor)

        main_layout.addWidget(self.view_stack)

    def _switch_view(self, idx):
        self.view_stack.setCurrentIndex(idx)
        for i, btn in enumerate([self.btn_code, self.btn_chat, self.btn_files,
                                 self.btn_settings, self.btn_git, self.btn_serial]):
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
        am.addAction(self._make_action("Fix Compile Errors", self.chat_panel._cmd_fix, "Ctrl+Shift+F"))
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
        self._compile_follows_ai_edits = self._ai_fix_pending_compile
        self._ai_fix_pending_compile = False
        self._save_file(); self.compiler_output.clear_output()
        self._switch_view(0); self.bottom_tabs.setCurrentWidget(self._output_tab)
        self.compiler_output.append_output("Compiling...", C["fg_link"])
        self._run_cli(["compile", "--fqbn", self._current_fqbn(), self.project_path])

    def _upload(self):
        if not self.project_path:
            QMessageBox.warning(self, "No Project", "Open a project first."); return
        port = self.port_combo.currentText().strip()
        if not port:
            QMessageBox.warning(self, "No Port", "Select a port first."); return
        self._save_file(); self.compiler_output.clear_output()
        self._switch_view(0); self.bottom_tabs.setCurrentWidget(self._output_tab)
        self.compiler_output.append_output("Compiling and uploading...", C["fg_link"])
        self._run_cli(["compile","--upload","--fqbn",self._current_fqbn(),"--port",port,self.project_path])

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

    _PANEL_NAMES = {0: "editor", 1: "chat", 2: "files", 3: "settings", 4: "git", 5: "serial"}
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
