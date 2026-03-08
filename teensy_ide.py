#!/usr/bin/env python3
"""
Teensy Ollama IDE — Arduino IDE 2.x inspired desktop app
with local LLM (Ollama) integration for Teensy development.

Usage:
    python3 teensy_ide.py [project_path]

Requirements:
    pip3 install PyQt6 PyQt6-QScintilla requests
"""

import sys, os, json, glob, re, threading, subprocess, math
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTreeView, QPlainTextEdit, QStackedWidget,
    QLineEdit, QPushButton, QToolBar, QTabWidget, QTabBar,
    QLabel, QComboBox, QFileDialog, QMessageBox, QTextEdit,
    QGroupBox, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QDir, QModelIndex, pyqtSignal, QObject, QThread,
    QTimer, QSize
)
from PyQt6.QtGui import (
    QFont, QColor, QAction, QKeySequence, QTextCursor,
    QTextCharFormat, QPalette, QFileSystemModel,
    QStandardItemModel, QStandardItem, QPainter, QPen
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
    "bg":           "#2b2b2b",
    "bg_editor":    "#1e1e1e",
    "bg_sidebar":   "#252526",
    "bg_toolbar":   "#1e1e1e",
    "bg_tabs":      "#2d2d2d",
    "bg_tab_active":"#1e1e1e",
    "bg_input":     "#2d2d2d",
    "bg_output":    "#1e1e1e",
    "teal":         "#00979d",
    "teal_hover":   "#00b5bc",
    "danger":       "#c62828",
    "fg":           "#d4d4d4",
    "fg_dim":       "#858585",
    "fg_head":      "#e0e0e0",
    "fg_err":       "#f44747",
    "fg_warn":      "#dcdcaa",
    "fg_ok":        "#4ec9b0",
    "fg_link":      "#569cd6",
    "border":       "#3c3c3c",
    "syn_kw":       "#569cd6",
    "syn_cmt":      "#6a9955",
    "syn_str":      "#ce9178",
    "syn_num":      "#b5cea8",
    "syn_pp":       "#c586c0",
    "syn_type":     "#4ec9b0",
}

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "teensy-coder"
DEFAULT_FQBN = "teensy:avr:teensy40"
WINDOW_TITLE = "Teensy Ollama IDE"

SYSTEM_PROMPT = """You are an expert embedded C/C++ developer for Teensy microcontrollers (PJRC).
You write clean, efficient code for real-time applications.
You understand hardware registers, interrupts, DMA, timers, and peripheral configuration.

The user's project files are provided automatically with every message so you can always see the full code.

IMPORTANT: When you suggest code changes, you MUST use this exact format so the IDE can apply them:

To replace existing code in a file:
<<<EDIT filename.ino
<<<OLD
(exact lines to find and replace)
>>>NEW
(replacement lines)
>>>END

To rewrite an entire file:
<<<FILE filename.ino
(complete file contents)
>>>FILE

Rules:
- The OLD block must match existing code EXACTLY (including whitespace/indentation).
- You can include multiple EDIT or FILE blocks in one response.
- Use EDIT for targeted changes; use FILE only for major rewrites or new files.
- Keep explanations brief and focused."""

# =============================================================================
# Stylesheet
# =============================================================================
STYLESHEET = f"""
QMainWindow {{ background-color: {C['bg']}; }}
QWidget {{ background-color: {C['bg']}; color: {C['fg']}; font-size: 13px; }}

QToolBar {{
    background-color: {C['bg_toolbar']};
    border-bottom: 1px solid {C['border']};
    padding: 6px 8px; spacing: 8px;
    min-height: 42px;
}}
QToolBar QLabel {{ color: {C['fg_dim']}; font-size: 11px; margin: 0 2px; background: transparent; border: none; letter-spacing: 0.3px; }}
QToolBar QComboBox {{
    background-color: {C['bg_input']}; color: {C['fg']};
    border: 1px solid {C['border']}; border-radius: 3px;
    padding: 5px 8px; font-size: 12px; min-height: 22px;
}}
QToolBar QComboBox QAbstractItemView {{
    background-color: {C['bg_input']}; color: {C['fg']};
    selection-background-color: {C['teal']};
}}
QToolBar::separator {{
    width: 1px; margin: 4px 6px;
    background-color: {C['border']};
}}

QToolBar QPushButton {{
    background-color: transparent; color: #cccccc;
    border: 1px solid #404040; border-radius: 4px;
    padding: 5px 14px; font-size: 12px; font-weight: 500;
}}
QToolBar QPushButton:hover {{ background-color: #383838; border-color: #00979d; color: white; }}
QToolBar QPushButton:pressed {{ background-color: #00979d; }}

/* File tabs across top — wider, left-aligned text */
QTabWidget#fileTabs::pane {{ border: none; }}
QTabBar#fileTabBar {{ background-color: {C['bg_tabs']}; }}
QTabBar#fileTabBar::tab {{
    background-color: {C['bg_tabs']}; color: {C['fg_dim']};
    border: none; border-right: 1px solid {C['border']};
    padding: 7px 28px 7px 16px; min-width: 120px;
    text-align: left;
}}
QTabBar#fileTabBar::tab:selected {{
    background-color: {C['bg_tab_active']}; color: {C['fg']};
    border-bottom: 2px solid {C['teal']};
}}
QTabBar#fileTabBar::tab:hover:!selected {{
    background-color: #383838; color: {C['fg']};
}}
QTabBar#fileTabBar::close-button {{
    subcontrol-position: right;
    padding: 2px;
    margin-right: 6px;
}}

/* Bottom panel tabs */
QTabWidget#bottomTabs::pane {{ border: none; background-color: {C['bg_output']}; }}
QTabWidget#bottomTabs > QTabBar::tab {{
    background-color: {C['bg_tabs']}; color: {C['fg_dim']};
    border: none; border-right: 1px solid {C['border']};
    padding: 5px 14px; min-width: 80px;
}}
QTabWidget#bottomTabs > QTabBar::tab:selected {{
    background-color: {C['bg_tab_active']}; color: {C['fg']};
    border-bottom: 2px solid {C['teal']};
}}
QTabWidget#bottomTabs > QTabBar::tab:hover:!selected {{
    background-color: #383838;
}}

QTreeView {{
    background-color: {C['bg_sidebar']}; color: {C['fg']};
    border: none; font-size: 12px;
}}
QTreeView::item:selected {{ background-color: {C['teal']}; color: white; }}
QTreeView::item:hover:!selected {{ background-color: #383838; }}
QTreeView::branch {{ background-color: {C['bg_sidebar']}; }}

QSplitter::handle {{ background-color: {C['border']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

QPlainTextEdit, QTextEdit {{
    background-color: {C['bg_output']}; color: {C['fg']};
    border: none; font-family: Menlo, Monaco, monospace; font-size: 12px; padding: 6px;
}}
QLineEdit {{
    background-color: {C['bg_input']}; color: {C['fg']};
    border: 1px solid {C['border']}; border-radius: 3px;
    padding: 5px 8px; font-family: Menlo, monospace; font-size: 12px;
}}
QLineEdit:focus {{ border-color: {C['teal']}; }}

QPushButton {{
    background-color: {C['bg_input']}; color: {C['fg']};
    border: 1px solid {C['border']}; border-radius: 3px;
    padding: 4px 10px; font-size: 12px;
}}
QPushButton:hover {{ background-color: #383838; border-color: {C['teal']}; }}

QGroupBox {{
    border: 1px solid {C['border']}; border-radius: 3px;
    margin-top: 10px; padding-top: 14px;
    font-weight: bold; color: {C['fg_head']};
}}
QGroupBox::title {{ subcontrol-origin: margin; padding: 0 4px; }}

QComboBox {{
    background-color: {C['bg_input']}; color: {C['fg']};
    border: 1px solid {C['border']}; border-radius: 3px; padding: 3px 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {C['bg_input']}; color: {C['fg']};
    selection-background-color: {C['teal']};
}}

QScrollBar:vertical {{
    background: {C['bg_editor']}; width: 8px; border: none;
}}
QScrollBar::handle:vertical {{
    background: #555; border-radius: 3px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #777; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {C['bg_editor']}; height: 8px; border: none;
}}
QScrollBar::handle:horizontal {{
    background: #555; border-radius: 3px; min-width: 30px;
}}

QMenu {{
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #454545;
    border-radius: 6px;
    padding: 4px 0px;
    font-size: 13px;
}}
QMenu::item {{
    padding: 6px 32px 6px 20px;
    border-radius: 0px;
    margin: 0px 4px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: #094771;
    color: white;
}}
QMenu::item:disabled {{
    color: #6e6e6e;
}}
QMenu::separator {{
    height: 1px;
    background-color: #454545;
    margin: 4px 12px;
}}
QMenu::right-arrow {{
    width: 8px;
    height: 8px;
}}
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
        self.setFixedSize(50, 50)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {C['fg_dim']};
                border: none; font-size: 21px; border-radius: 0;
                border-left: 3px solid transparent;
            }}
            QPushButton:hover {{ color: {C['fg']}; background-color: #383838; }}
            QPushButton:checked {{
                color: {C['fg']}; border-left: 3px solid {C['teal']};
                background-color: #383838;
            }}
        """)


class GitSidebarButton(SidebarButton):
    """Sidebar button with a custom-painted Git branch icon."""
    def __init__(self, tooltip, parent=None):
        super().__init__("", tooltip, parent)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = QColor(C['fg']) if self.isChecked() or self.underMouse() else QColor(C['fg_dim'])
        pen = QPen(col, 2.0)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = self.width() / 2, self.height() / 2
        # Main vertical line (trunk)
        p.drawLine(int(cx), int(cy - 12), int(cx), int(cy + 14))
        # Branch line forking off to the right
        p.drawLine(int(cx), int(cy - 2), int(cx + 9), int(cy - 10))
        # Dots at the nodes (commits)
        p.setBrush(col)
        r = 3
        p.drawEllipse(int(cx - r), int(cy + 14 - r), r * 2, r * 2)     # bottom
        p.drawEllipse(int(cx - r), int(cy - 12 - r), r * 2, r * 2)     # top
        p.drawEllipse(int(cx + 9 - r), int(cy - 10 - r), r * 2, r * 2) # branch tip
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
        p.setBrush(QColor("#1a1a1a"))
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
                stream=True, timeout=(5, 10))
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

AI_ACTIONS = [
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
            self.setPaper(QColor(C["bg_editor"]))
            self.setColor(QColor(C["fg"]))
            self.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
            self.setMarginWidth(0, "00000")
            self.setMarginsForegroundColor(QColor(C["fg_dim"]))
            self.setMarginsBackgroundColor(QColor(C["bg_editor"]))
            self.setCaretLineVisible(True)
            self.setCaretLineBackgroundColor(QColor("#2a2d2e"))
            self.setCaretForegroundColor(QColor(C["fg"]))
            self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
            self.setMatchedBraceBackgroundColor(QColor("#3a3d41"))
            self.setMatchedBraceForegroundColor(QColor(C["fg"]))
            self.setAutoIndent(True)
            self.setIndentationGuides(True)
            self.setIndentationGuidesBackgroundColor(QColor("#2a2a2a"))
            self.setIndentationGuidesForegroundColor(QColor("#404040"))
            self.setTabWidth(2)
            self.setIndentationsUseTabs(False)
            self.setEdgeMode(QsciScintilla.EdgeMode.EdgeNone)
            self.setFolding(QsciScintilla.FoldStyle.BoxedTreeFoldStyle)
            self.setFoldMarginColors(QColor(C["bg_editor"]), QColor(C["bg_editor"]))
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self._show_context_menu)
            # Lexer
            lexer = QsciLexerCPP(self)
            lexer.setFont(font)
            lexer.setDefaultPaper(QColor(C["bg_editor"]))
            lexer.setDefaultColor(QColor(C["fg"]))
            for i in range(20): lexer.setPaper(QColor(C["bg_editor"]), i)
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
        """Open all project files as tabs, like Arduino IDE."""
        extensions = {".ino", ".cpp", ".c", ".h", ".hpp", ".md"}
        files = []
        for f in sorted(os.listdir(project_path)):
            ext = os.path.splitext(f)[1].lower()
            if ext in extensions:
                files.append(os.path.join(project_path, f))
        # Open .ino first
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
        """Set content of an open file by path. Returns True if found."""
        if filepath in self._editors:
            ed = self._editors[filepath]
            if hasattr(ed, 'setText'): ed.setText(content)
            else: ed.setPlainText(content)
            return True
        return False

    def find_file_by_name(self, basename):
        """Find full path of an open file by its basename."""
        for fp in self._editors:
            if os.path.basename(fp) == basename:
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
            f"QTreeView {{ background:{C['bg_sidebar']};border:none;font-size:12px; }}"
            f"QTreeView::item {{ padding: 3px 4px; }}"
            f"QTreeView::item:selected {{ background:{C['teal']};color:white; }}"
            f"QTreeView::item:hover:!selected {{ background:#383838; }}")
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
# Chat Panel
# =============================================================================

class ChatPanel(QWidget):
    """AI chat with automatic project context and code-edit application."""
    apply_edit = pyqtSignal(str, str, str)  # filename, old, new
    apply_file = pyqtSignal(str, str)        # filename, full content
    generation_started = pyqtSignal()
    generation_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conversation = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._current_response = ""
        self._error_context = ""
        self._editor_ref = None          # will be set by MainWindow
        self._pending_edits = []         # list of parsed edit operations

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Context panel — shows project path and files visible to AI
        ctx_panel = QWidget()
        ctx_panel.setStyleSheet(
            f"background: {C['bg_tabs']}; border-bottom: 1px solid {C['border']};")
        ctx_layout = QVBoxLayout(ctx_panel)
        ctx_layout.setContentsMargins(10, 6, 10, 6)
        ctx_layout.setSpacing(3)

        ctx_top = QHBoxLayout()
        self.project_label = QLabel("No project open")
        self.project_label.setStyleSheet(
            f"color: {C['fg_head']}; font-size: 12px; font-weight: bold;")
        ctx_top.addWidget(self.project_label)
        ctx_top.addStretch()
        self.toggle_files_btn = QPushButton("Show Files")
        self.toggle_files_btn.setFixedHeight(20)
        self.toggle_files_btn.setStyleSheet(
            f"background: transparent; color: {C['teal']}; border: none;"
            f" font-size: 11px; text-decoration: underline;")
        self.toggle_files_btn.clicked.connect(self._toggle_file_list)
        ctx_top.addWidget(self.toggle_files_btn)
        ctx_layout.addLayout(ctx_top)

        self.path_label = QLabel("")
        self.path_label.setStyleSheet(f"color: {C['fg_dim']}; font-size: 10px;")
        ctx_layout.addWidget(self.path_label)

        self.file_list_widget = QLabel("")
        self.file_list_widget.setWordWrap(True)
        self.file_list_widget.setStyleSheet(
            f"color: {C['teal']}; font-size: 11px; padding: 4px 0px;")
        self.file_list_widget.hide()
        ctx_layout.addWidget(self.file_list_widget)

        layout.addWidget(ctx_panel)

        # Chat display — clean aesthetic
        self.display = QTextEdit()
        self.display.setReadOnly(True)
        self.display.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1a1a1a;
                color: {C['fg']};
                border: none;
                font-family: Helvetica, Arial, sans-serif;
                font-size: 15px;
                padding: 12px 20px;
                selection-background-color: {C['teal']};
            }}
        """)
        layout.addWidget(self.display)

        # Apply bar — shows after AI suggests edits
        self.apply_bar = QWidget()
        self.apply_bar.setStyleSheet(f"background: {C['bg_tabs']}; border-top: 1px solid {C['border']};")
        ab_layout = QHBoxLayout(self.apply_bar)
        ab_layout.setContentsMargins(8, 4, 8, 4)
        self.apply_label = QLabel("")
        self.apply_label.setStyleSheet(f"color: {C['fg']}; font-size: 12px;")
        ab_layout.addWidget(self.apply_label)
        ab_layout.addStretch()
        self.apply_all_btn = QPushButton("Apply All Changes")
        self.apply_all_btn.setStyleSheet(
            f"background: {C['teal']}; color: white; border: none; border-radius: 3px;"
            f" font-weight: bold; padding: 5px 14px;")
        self.apply_all_btn.clicked.connect(self._apply_all_edits)
        ab_layout.addWidget(self.apply_all_btn)
        self.dismiss_btn = QPushButton("Dismiss")
        self.dismiss_btn.setStyleSheet(
            f"background: {C['bg_input']}; color: {C['fg']}; border: 1px solid {C['border']};"
            f" border-radius: 3px; padding: 5px 10px;")
        self.dismiss_btn.clicked.connect(self._dismiss_edits)
        ab_layout.addWidget(self.dismiss_btn)
        self.apply_bar.hide()
        layout.addWidget(self.apply_bar)

        # Input area — clean, modern look
        inp = QWidget()
        inp.setStyleSheet(f"background: #222222; border-top: 1px solid {C['border']};")
        il = QHBoxLayout(inp); il.setContentsMargins(12, 8, 12, 8); il.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask about your code...")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: #2d2d2d; color: {C['fg']};
                border: 1px solid #404040; border-radius: 8px;
                padding: 8px 14px; font-size: 14px;
            }}
            QLineEdit:focus {{ border-color: {C['teal']}; }}
        """)
        self.input_field.returnPressed.connect(self.send_message)
        il.addWidget(self.input_field)

        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedWidth(60)
        self.send_btn.setStyleSheet(
            f"background: {C['teal']}; color: white; border: none;"
            f" border-radius: 8px; font-weight: 600; padding: 8px 0; font-size: 13px;")
        self.send_btn.clicked.connect(self.send_message)
        il.addWidget(self.send_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedWidth(52)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(
            f"background: {C['bg_input']}; color: {C['fg']}; border: 1px solid {C['border']};"
            f" border-radius: 8px; padding: 8px 0; font-size: 12px;")
        self.stop_btn.clicked.connect(self.stop_generation)
        il.addWidget(self.stop_btn)

        layout.addWidget(inp)

        # Bottom buttons
        btns = QWidget()
        btns.setStyleSheet(f"background: {C['bg']};")
        bl = QHBoxLayout(btns); bl.setContentsMargins(8, 2, 8, 5)
        self.send_errors_btn = QPushButton("Attach Errors")
        self.send_errors_btn.setCheckable(True)
        bl.addWidget(self.send_errors_btn)
        clr = QPushButton("Clear Chat")
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

    def set_error_context(self, e):
        self._error_context = e

    def _build_file_context(self):
        """Build a string with all open project files for the AI to see."""
        if not self._editor_ref:
            return ""
        files = self._editor_ref.get_all_files()
        if not files:
            return ""
        proj = getattr(self, '_project_path', None) or ""
        proj_name = os.path.basename(proj) if proj else "unknown"
        parts = [f"[PROJECT: {proj_name}]\n[DIRECTORY: {proj}]\n"]
        parts.append(f"[The following {len(files)} files are open in the editor. "
                     f"This is the COMPLETE content of each file.]\n")
        names = []
        for fp, content in files.items():
            basename = os.path.basename(fp)
            names.append(basename)
            parts.append(f"========== FILE: {basename} ==========\n{content}\n========== END: {basename} ==========\n")
        self._update_context_display(proj_name, proj, names)
        return "\n".join(parts)

    def send_message(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self._send_prompt(text, display_text=text)

    def send_ai_action(self, prompt):
        """Called from the right-click AI context menu in the code editor."""
        # Show a short summary in the chat, not the full prompt with code
        short = prompt.split("\n")[0][:80]
        self._send_prompt(prompt, display_text=f"[AI Tool] {short}")

    def _send_prompt(self, text, display_text=None):
        """Core send method used by both manual chat and AI actions."""
        # Build the full message with automatic file context
        msg = self._build_file_context()
        if self.send_errors_btn.isChecked() and self._error_context:
            msg += f"\n[COMPILER ERRORS:]\n```\n{self._error_context}\n```\n\n"
            self.send_errors_btn.setChecked(False)
        msg += f"\n[USER REQUEST:]\n{text}"

        # Show the display text in the chat
        show = display_text or text
        self._append(
            f'<br><table width="100%" cellpadding="10" cellspacing="0" bgcolor="#262626">'
            f'<tr><td><font color="{C["fg_link"]}" size="3"><b>You</b></font><br>'
            f'<font color="{C["fg"]}">{self._esc(show)}</font>'
            f'</td></tr></table>')
        self._conversation.append({"role": "user", "content": msg})
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._current_response = ""
        self.apply_bar.hide()
        self._pending_edits = []
        self._append(
            f'<br><table width="100%" cellpadding="10" cellspacing="0" bgcolor="#1e2a2a">'
            f'<tr><td><font color="{C["teal"]}" size="3"><b>{self._esc(OLLAMA_MODEL)}</b></font><br>'
            f'<font color="{C["fg"]}">')
        self.worker.messages = list(self._conversation)
        if self.thread.isRunning():
            self.worker.stop()
            self.thread.quit()
            if not self.thread.wait(2000):
                # Thread didn't stop — recreate worker/thread
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
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.input_field.setFocus()
        self.generation_finished.emit()

    def _on_token(self, t):
        self._current_response += t
        cur = self.display.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        cur.insertText(t)
        self.display.setTextCursor(cur)
        self.display.ensureCursorVisible()

    def _on_complete(self):
        if self.thread.isRunning():
            self.thread.quit()
        if self._current_response:
            self._conversation.append({"role": "assistant", "content": self._current_response})
            self._parse_edits(self._current_response)
        self._append("</font></td></tr></table>")
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.input_field.setFocus()
        self.generation_finished.emit()

    def _on_error(self, m):
        self._append(
            f'<br><table width="100%" cellpadding="8" cellspacing="0" bgcolor="#2a1a1a">'
            f'<tr><td><font color="{C["fg_err"]}" size="3"><b>Error</b></font><br>'
            f'<font color="{C["fg"]}" size="4">{self._esc(m)}</font>'
            f'</td></tr></table>')
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

    def _parse_edits(self, response):
        """Parse <<<EDIT and <<<FILE blocks from the AI response."""
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

        if edits:
            self._pending_edits = edits
            n = len(edits)
            files_touched = set(e[1] for e in edits)
            self.apply_label.setText(
                f"{n} change{'s' if n > 1 else ''} in {', '.join(files_touched)}")
            self.apply_bar.show()
            self._append(
                f'<br><font color="{C["fg_ok"]}" size="3">'
                f'Found {n} code edit{"s" if n > 1 else ""} — '
                f'use the Apply bar below to apply.</font>')

    def _apply_all_edits(self):
        """Apply all parsed edits to the editor."""
        if not self._editor_ref or not self._pending_edits:
            return
        applied = 0
        errors = []
        for edit_type, filename, old, new in self._pending_edits:
            fp = self._editor_ref.find_file_by_name(filename)
            if not fp:
                errors.append(f"File not found: {filename}")
                continue
            if edit_type == "file":
                # Full file replacement
                if self._editor_ref.set_file_content(fp, new):
                    applied += 1
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
                    else:
                        errors.append(f"Could not write: {filename}")
                else:
                    errors.append(f"Could not find matching code in {filename}")

        status = f"Applied {applied} change{'s' if applied != 1 else ''}."
        if errors:
            status += " Errors: " + "; ".join(errors)
        self._append(
            f'<p style="color:{C["fg_ok"] if not errors else C["fg_warn"]}; font-size: 12px;">'
            f'{self._esc(status)}</p><br>')
        self.apply_bar.hide()
        self._pending_edits = []

    def _dismiss_edits(self):
        self.apply_bar.hide()
        self._pending_edits = []

    def clear_chat(self):
        self.display.clear()
        self._conversation = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.apply_bar.hide()
        self._pending_edits = []
        self._update_context_bar()

    def _update_context_display(self, proj_name, proj_path, names):
        """Update the context panel with project info and file list."""
        self.project_label.setText(f"Project: {proj_name}  —  {len(names)} files loaded")
        self.path_label.setText(proj_path)
        self.file_list_widget.setText("  •  ".join(names))

    def _toggle_file_list(self):
        """Toggle visibility of the file list."""
        if self.file_list_widget.isVisible():
            self.file_list_widget.hide()
            self.toggle_files_btn.setText("Show Files")
        else:
            self.file_list_widget.show()
            self.toggle_files_btn.setText("Hide Files")

    def _update_context_bar(self):
        if self._editor_ref:
            files = self._editor_ref.get_all_files()
            if files:
                proj = getattr(self, '_project_path', None) or ""
                proj_name = os.path.basename(proj) if proj else "unknown"
                names = [os.path.basename(fp) for fp in files]
                self._update_context_display(proj_name, proj, names)
                return
        self.project_label.setText("No project open")
        self.path_label.setText("")
        self.file_list_widget.setText("")

    def _append(self, html):
        cur = self.display.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        self.display.setTextCursor(cur)
        self.display.insertHtml(html)
        self.display.ensureCursorVisible()

    @staticmethod
    def _esc(t):
        return (t.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace("\n", "<br>")
                 .replace(" ", "&nbsp;"))


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
        cl = QHBoxLayout(ctrl); cl.setContentsMargins(8, 4, 8, 4)
        cl.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox(); self.port_combo.setEditable(True); self.port_combo.setMinimumWidth(140)
        cl.addWidget(self.port_combo)
        cl.addWidget(QLabel("Baud:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600","19200","38400","57600","115200","250000","500000","1000000"])
        self.baud_combo.setCurrentText("9600")
        cl.addWidget(self.baud_combo)
        self.start_btn = QPushButton("Start")
        self.start_btn.setStyleSheet(f"background:{C['teal']};color:white;border:none;border-radius:3px;font-weight:bold;")
        self.start_btn.clicked.connect(self._toggle)
        cl.addWidget(self.start_btn)
        clr = QPushButton("Clear"); clr.clicked.connect(self.display.clear); cl.addWidget(clr)
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
            self.start_btn.setStyleSheet(f"background:{C['danger']};color:white;border:none;border-radius:3px;font-weight:bold;")
            self._timer = QTimer(); self._timer.timeout.connect(self._read); self._timer.start(50)
        except ImportError: self.display.appendPlainText("pyserial not installed. Run: pip install pyserial")
        except Exception as e: self.display.appendPlainText(f"Error: {e}")

    def _stop(self):
        self._running = False
        if hasattr(self, '_timer'): self._timer.stop()
        if hasattr(self, '_serial') and self._serial.is_open: self._serial.close()
        self.start_btn.setText("Start")
        self.start_btn.setStyleSheet(f"background:{C['teal']};color:white;border:none;border-radius:3px;font-weight:bold;")

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
# Model Manager
# =============================================================================

class ModelManager(QWidget):
    model_changed = pyqtSignal()
    BASE = "http://localhost:11434"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        QTimer.singleShot(500, self.refresh_models)

    def _setup_ui(self):
        layout = QHBoxLayout(self); layout.setContentsMargins(4, 4, 4, 4)

        left = QVBoxLayout()
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("<b>Installed Models</b>"))
        rb = QPushButton("Refresh"); rb.setFixedWidth(65); rb.clicked.connect(self.refresh_models)
        hdr.addWidget(rb); left.addLayout(hdr)

        self.model_list = QTreeView()
        self.model_list.setHeaderHidden(False); self.model_list.setRootIsDecorated(False)
        self._lm = QStandardItemModel()
        self._lm.setHorizontalHeaderLabels(["Model", "Size", "Modified"])
        self.model_list.setModel(self._lm)
        self.model_list.clicked.connect(self._on_select)
        left.addWidget(self.model_list)

        db = QPushButton("Delete Selected")
        db.setStyleSheet(f"color:{C['fg_err']};"); db.clicked.connect(self._delete)
        left.addWidget(db)

        lw = QWidget(); lw.setLayout(left); lw.setMinimumWidth(260)

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
        save_desc_btn.setFixedWidth(55)
        save_desc_btn.setStyleSheet(
            f"background:{C['teal']};color:white;border:none;"
            f"border-radius:3px;font-weight:bold;")
        save_desc_btn.clicked.connect(self._save_desc)
        desc_row.addWidget(save_desc_btn)
        gen_desc_btn = QPushButton("Auto-Generate")
        gen_desc_btn.setFixedWidth(100)
        gen_desc_btn.setStyleSheet(
            f"background:{C['bg_input']};color:{C['fg']};border:1px solid {C['border']};"
            f"border-radius:3px;")
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
        pb = QPushButton("Preview"); pb.clicked.connect(self._preview); r3.addWidget(pb)
        cb = QPushButton("Create Model")
        cb.setStyleSheet(f"background:{C['teal']};color:white;border:none;border-radius:3px;font-weight:bold;padding:5px 14px;")
        cb.clicked.connect(self._create); r3.addWidget(cb); r3.addStretch()
        cl.addLayout(r3)

        self.mf_preview = QPlainTextEdit(); self.mf_preview.setReadOnly(True)
        self.mf_preview.setMaximumHeight(90); self.mf_preview.setPlaceholderText("Preview...")
        cl.addWidget(self.mf_preview)
        self.status = QLabel(""); cl.addWidget(self.status)

        right.addWidget(cg)
        rw = QWidget(); rw.setLayout(right)

        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.addWidget(lw); sp.addWidget(rw); sp.setSizes([260, 500])
        layout.addWidget(sp)

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
        if not name: self.status.setText("Enter a name."); self.status.setStyleSheet(f"color:{C['fg_err']};"); return
        mf = self._build_mf()
        self.status.setText(f"Creating '{name}'..."); self.status.setStyleSheet(f"color:{C['fg_link']};")
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
            self.status.setText(f"'{m}' created!"); self.status.setStyleSheet(f"color:{C['fg_ok']};")
            self.refresh_models(); self.model_changed.emit()
        else:
            self.status.setText(f"Error: {m}"); self.status.setStyleSheet(f"color:{C['fg_err']};")

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
        self.status.setStyleSheet(f"color:{C['fg_ok']};")

    def _auto_gen_desc(self):
        """Ask the model to generate its own description, then save it."""
        name = self.name_in.text().strip()
        if not name:
            return
        self.desc_edit.setText("Generating...")
        self.status.setText("Asking model to describe itself...")
        self.status.setStyleSheet(f"color:{C['teal']};")
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
                    self.status.setStyleSheet(f"color:{C['fg_ok']};")
                else:
                    self.status.setText(desc)
                    self.status.setStyleSheet(f"color:{C['fg_err']};")
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
                    self.status.setText(f"Deleted."); self.status.setStyleSheet(f"color:{C['fg_ok']};")
                    self.refresh_models(); self.model_changed.emit()
            except Exception as e:
                self.status.setText(str(e)); self.status.setStyleSheet(f"color:{C['fg_err']};")


# =============================================================================
# Main Window
# =============================================================================

# =============================================================================
# Git Panel
# =============================================================================

class GitPanel(QWidget):
    """Git GUI with graphical branch/tag manager and console output."""
    branch_changed = pyqtSignal()  # emitted after checkout so MainWindow can reload files

    _BTN = (f"background:{C['bg_input']};color:{C['fg']};border:1px solid {C['border']};"
            f"border-radius:4px;padding:6px 12px;font-size:12px;")
    _BTN_PRIMARY = (f"background:{C['teal']};color:white;border:none;"
                    f"border-radius:4px;padding:6px 14px;font-size:12px;font-weight:bold;")
    _BTN_DANGER = (f"background:{C['danger']};color:white;border:none;"
                   f"border-radius:4px;padding:6px 12px;font-size:12px;font-weight:bold;")

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # ===== Top half: graphical branch/tag manager =====
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(10, 10, 10, 6)
        top_layout.setSpacing(8)

        # -- Current branch indicator --
        branch_bar = QHBoxLayout()
        self.branch_label = QLabel("Branch: —")
        self.branch_label.setStyleSheet(
            f"color:{C['fg_head']};font-size:15px;font-weight:bold;")
        branch_bar.addWidget(self.branch_label)
        branch_bar.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(self._BTN_PRIMARY)
        refresh_btn.clicked.connect(self.refresh_status)
        branch_bar.addWidget(refresh_btn)

        init_btn = QPushButton("Init Repo")
        init_btn.setStyleSheet(self._BTN)
        init_btn.clicked.connect(self._init_repo)
        branch_bar.addWidget(init_btn)
        top_layout.addLayout(branch_bar)

        # -- Branches & Tags side by side --
        lists_row = QHBoxLayout()

        # Branches panel
        br_box = QWidget()
        br_layout = QVBoxLayout(br_box)
        br_layout.setContentsMargins(0, 0, 0, 0)
        br_layout.setSpacing(4)
        br_hdr = QLabel("Branches")
        br_hdr.setStyleSheet(f"color:{C['teal']};font-size:13px;font-weight:bold;")
        br_layout.addWidget(br_hdr)

        self.branch_list = QTreeView()
        self.branch_list.setHeaderHidden(True)
        self.branch_list.setRootIsDecorated(False)
        self.branch_list.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.branch_list.setStyleSheet(
            f"QTreeView {{ background:{C['bg_editor']};border:1px solid {C['border']};"
            f"border-radius:3px; }} "
            f"QTreeView::item {{ padding: 4px 6px; }} "
            f"QTreeView::item:selected {{ background:{C['teal']};color:white; }}")
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
        tag_hdr.setStyleSheet(f"color:{C['teal']};font-size:13px;font-weight:bold;")
        tag_layout.addWidget(tag_hdr)

        self.tag_list = QTreeView()
        self.tag_list.setHeaderHidden(True)
        self.tag_list.setRootIsDecorated(False)
        self.tag_list.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tag_list.setStyleSheet(
            f"QTreeView {{ background:{C['bg_editor']};border:1px solid {C['border']};"
            f"border-radius:3px; }} "
            f"QTreeView::item {{ padding: 4px 6px; }} "
            f"QTreeView::item:selected {{ background:{C['teal']};color:white; }}")
        self._tag_model = QStandardItemModel()
        self.tag_list.setModel(self._tag_model)
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
        self.output.setFont(QFont("Menlo", 12))
        self.output.setStyleSheet(
            f"background:{C['bg_editor']};color:{C['fg']};"
            f"border:none;border-top:1px solid {C['border']};")
        splitter.addWidget(self.output)

        splitter.setSizes([400, 250])
        layout.addWidget(splitter)

        self._project_path = None

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

        # Populate branches
        self._branch_model.clear()
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
        """When a branch is clicked, filter tags to show those on that branch."""
        name = self._selected_branch()
        if not name:
            return
        # For remote branches, use full ref
        ref = name
        if ref.startswith("remotes/"):
            pass  # use as-is
        self._refresh_tags_for(ref)
        # Show branch info in the console
        log = self._run_git(["log", "--oneline", "-10", ref], silent=True)
        self._log(f"\n--- Commits on '{name}' ---\n{log or '(none)'}")

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
    def __init__(self, project_path=None):
        super().__init__()
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
        self.setStatusBar(None)  # No status bar

        self._setup_ui()
        self._setup_toolbar()
        self._setup_menubar()

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
        sidebar.setFixedWidth(52)
        sidebar.setStyleSheet(f"background-color: {C['bg_sidebar']}; border-right: 1px solid {C['border']};")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 4, 0, 4)
        sb_layout.setSpacing(2)

        self.btn_code = SidebarButton("{}", "Code Editor")
        self.btn_code.setChecked(True)
        self.btn_chat = SidebarButton("AI", "AI Chat")
        self.btn_models = SidebarButton("M", "Model Manager")
        self.btn_git = GitSidebarButton("Git")

        self.btn_code.clicked.connect(lambda: self._switch_view(0))
        self.btn_chat.clicked.connect(lambda: self._switch_view(1))
        self.btn_models.clicked.connect(lambda: self._switch_view(2))
        self.btn_git.clicked.connect(lambda: self._switch_view(3))

        sb_layout.addWidget(self.btn_code)
        sb_layout.addWidget(self.btn_chat)
        sb_layout.addWidget(self.btn_models)
        sb_layout.addWidget(self.btn_git)
        sb_layout.addStretch()

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
        self.view_stack.addWidget(self.chat_panel)

        # View 2: Model manager (full panel)
        self.model_manager = ModelManager()
        self.model_manager.model_changed.connect(self._refresh_models)
        self.view_stack.addWidget(self.model_manager)

        # View 3: Git panel (full panel)
        self.git_panel = GitPanel()
        self.git_panel.branch_changed.connect(self._on_branch_changed)
        self.view_stack.addWidget(self.git_panel)

        main_layout.addWidget(self.view_stack)

    def _switch_view(self, idx):
        self.view_stack.setCurrentIndex(idx)
        for i, btn in enumerate([self.btn_code, self.btn_chat, self.btn_models, self.btn_git]):
            btn.setChecked(i == idx)
        if idx == 3:
            self.git_panel.refresh_status()

    def _setup_toolbar(self):
        toolbar = QToolBar("Build")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.addToolBar(toolbar)

        tb_btn_style = (
            f"background:{C['teal']};color:white;border:none;border-radius:4px;"
            f"font-weight:bold;padding:7px 16px;font-size:13px;")
        tb_secondary_style = (
            f"background:{C['bg_input']};color:{C['fg']};border:1px solid {C['border']};"
            f"border-radius:4px;padding:6px 12px;font-size:12px;")

        # Verify button with checkmark
        verify_btn = QPushButton("  \u2713  Verify")
        verify_btn.setToolTip("Compile sketch (Ctrl+B)")
        verify_btn.setStyleSheet(tb_btn_style)
        verify_btn.clicked.connect(self._compile)
        toolbar.addWidget(verify_btn)

        # Upload button with arrow
        upload_btn = QPushButton("  \u27A4  Upload")
        upload_btn.setToolTip("Upload to Teensy (Ctrl+U)")
        upload_btn.setStyleSheet(tb_btn_style)
        upload_btn.clicked.connect(self._upload)
        toolbar.addWidget(upload_btn)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel("Board:"))
        self.board_combo = QComboBox()
        self.board_combo.addItems(["teensy:avr:teensy40","teensy:avr:teensy41",
            "teensy:avr:teensy36","teensy:avr:teensy32","teensy:avr:teensyLC"])
        self.board_combo.setCurrentText(DEFAULT_FQBN); self.board_combo.setMinimumWidth(120)
        toolbar.addWidget(self.board_combo)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox(); self.port_combo.setEditable(True); self.port_combo.setMinimumWidth(120)
        self._refresh_ports()
        toolbar.addWidget(self.port_combo)

        rb = QPushButton("Refresh")
        rb.setStyleSheet(tb_secondary_style)
        rb.clicked.connect(self._refresh_ports)
        toolbar.addWidget(rb)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel("AI Model:"))
        self.model_combo = QComboBox(); self.model_combo.setMinimumWidth(120)
        self._refresh_models()
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        toolbar.addWidget(self.model_combo)

        self.model_desc_label = QLabel("")
        self.model_desc_label.setStyleSheet(
            f"color:{C['fg_dim']};font-size:11px;font-style:italic;"
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
        vm.addAction(self._make_action("Model Manager", lambda: self._switch_view(2), "Ctrl+3"))
        vm.addAction(self._make_action("Git", lambda: self._switch_view(3), "Ctrl+4"))

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
        self._run_cli(["compile", "--fqbn", self.board_combo.currentText(), self.project_path])

    def _upload(self):
        if not self.project_path:
            QMessageBox.warning(self, "No Project", "Open a project first."); return
        port = self.port_combo.currentText().strip()
        if not port:
            QMessageBox.warning(self, "No Port", "Select a port first."); return
        self._save_file(); self.compiler_output.clear_output()
        self._switch_view(0); self.bottom_tabs.setCurrentWidget(self.compiler_output)
        self.compiler_output.append_output("Compiling and uploading...", C["fg_link"])
        self._run_cli(["compile","--upload","--fqbn",self.board_combo.currentText(),"--port",port,self.project_path])

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

    def _send_errors_to_ai(self):
        if self._compiler_errors:
            self.chat_panel.set_error_context(self._compiler_errors)
            self.chat_panel.send_errors_btn.setChecked(True)
            self._switch_view(1); self.chat_panel.input_field.setFocus()

    def closeEvent(self, event):
        if self.chat_panel.thread.isRunning():
            self.chat_panel.worker.stop(); self.chat_panel.thread.quit(); self.chat_panel.thread.wait(2000)
        event.accept()


# =============================================================================
# Entry Point
# =============================================================================

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(WINDOW_TITLE)
    app.setStyleSheet(STYLESHEET)
    project_path = None
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        project_path = os.path.abspath(sys.argv[1])
    w = MainWindow(project_path)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
