# ArduinoAIDE

A macOS desktop IDE for Teensy microcontroller development, styled after Arduino IDE 2.x. Single-file PyQt6 application with dual AI backend support (Ollama + LM Studio).

## Tech Stack
- **Python 3 + PyQt6 6.10.2 + QScintilla** — native macOS desktop app
- **Ollama REST API** — `/api/chat` (streaming), `/api/tags`, `/api/show`, `/api/create`, `/api/delete`, `/api/pull`
- **LM Studio / OpenAI-compatible API** — `/v1/chat/completions` (SSE streaming), `/v1/models`
- **arduino-cli** — compile/upload with FQBN `teensy:avr:teensy40`
- **Single file**: `ArduinoAIDE.py` (~11,000 lines) — everything is in this one file
- **Virtual env**: `~/teensy-ide-env` — activate before running

## Running
```bash
source ~/teensy-ide-env/bin/activate
python3 ArduinoAIDE.py [project_path]
```

## Architecture

All classes live in `ArduinoAIDE.py`:

| Class | Line | Purpose |
|---|---|---|
| `WorkingSetEntry` | ~178 | Dataclass: single file in the AI context window |
| `WorkingSet` | ~188 | Priority-based AI context manager (12K token budget) |
| `ProposedEdit` | ~270 | Dataclass: parsed AI code edit block |
| `SymbolEntry` | ~283 | Dataclass: code symbol for context |
| `StructuredDiagnostic` | ~291 | Dataclass: compiler diagnostic |
| `AIWorkResult` | ~300 | Dataclass: typed container for AI responses |
| `SidebarButton` | ~945 | Base sidebar button with hover/checked states |
| `GitSidebarButton` | ~975 | Custom-painted git branch icon |
| `FileSidebarButton` | ~1001 | Custom-painted folder icon |
| `SettingsSidebarButton` | ~1024 | Custom-painted gear icon |
| `SerialSidebarButton` | ~1065 | Custom-painted serial/terminal icon |
| `LibrarySidebarButton` | ~1089 | Custom-painted library/book icon |
| `BoardSidebarButton` | ~1109 | Custom-painted board/chip icon |
| `PlotterSidebarButton` | ~1133 | Custom-painted line-chart icon |
| `NavBadge` | ~1158 | Notification badge label |
| `SpinnerWidget` | ~1191 | Animated teal gear for AI activity indicator |
| `OllamaWorker` | ~1249 | QObject worker for streaming AI responses in QThread |
| `TabbedEditor` | ~1577 | Tab widget wrapping QScintilla/QPlainTextEdit editors |
| `FileBrowser` | ~1800 | QTreeView-based file tree |
| `FileManagerView` | ~1906 | Full file browser with parent context, SKETCHBOOK header |
| `LibraryManagerPanel` | ~2125 | arduino-cli library search, install, remove |
| `BoardManagerPanel` | ~2421 | Board platform install/remove, board URL management |
| `PlotWidget` | ~2747 | QPainter-based real-time chart renderer |
| `SerialPlotterPanel` | ~2932 | Serial data plotter with CSV export |
| `ChatPanel` | ~3191 | AI chat with QScrollArea widget-based bubbles |
| `CompilerOutput` | ~6731 | Compiler output pane |
| `DiagnosticPanel` | ~6768 | Structured compiler diagnostics display |
| `HistoryLineEdit` | ~6882 | QLineEdit with up/down arrow history |
| `SerialReaderThread` | ~6931 | QThread for reading serial port data |
| `SerialMonitor` | ~6979 | Serial port monitor with send/receive |
| `ModelsTab` | ~7353 | AI model list, details, load/unload, auto-descriptions |
| `GitTab` | ~8103 | Git GUI (status, commit, branch, tag, push/pull) |
| `RulesTab` | ~8571 | AI system prompt rules + Reference Documents manager |
| `SettingsPanel` | ~8840 | Stacked tabs: Models, Git, Rules |
| `GitPanel` | ~8892 | Sidebar git view (quick status + commit) |
| `MainWindow` | ~9430 | Main window with sidebar, toolbar, status bar, stacked views |

## Sidebar Views

9 views via QStackedWidget, mapped in `_switch_view(idx)`:

| Index | View | Sidebar Button | Shortcut |
|---|---|---|---|
| 0 | Code Editor | `btn_code` | Ctrl+1 |
| 1 | AI Chat | `btn_chat` | Ctrl+2 |
| 2 | Files | `btn_files` | Ctrl+3 |
| 3 | Settings | `btn_settings` | Ctrl+4 |
| 4 | Git | `btn_git` | Ctrl+5 |
| 5 | Serial Monitor | `btn_serial` | Ctrl+6 |
| 6 | Libraries | `btn_libs` | Ctrl+7 |
| 7 | Boards | `btn_boards` | Ctrl+8 |
| 8 | Serial Plotter | `btn_plotter` | Ctrl+9 |

Sidebar order top-to-bottom: Code, AI Chat, Files, Git, Serial, Plotter, Libraries, Boards, (stretch), Settings at bottom.

## AI Backend System

Dual backend controlled by globals (~line 447):
```python
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "teensy-coder"
AI_BACKEND = "ollama"        # "ollama" or "lmstudio"
LMSTUDIO_URL = "http://localhost:1234"
```

- **OllamaWorker.run()** dispatches to `_run_ollama()` or `_run_openai()` based on `AI_BACKEND`
- **Ollama**: `/api/chat` with JSON streaming (line-delimited JSON objects)
- **LM Studio**: `/v1/chat/completions` with SSE streaming (`data: {...}` lines, `[DONE]` sentinel)
- **Model listing**: `/api/tags` (Ollama) or `/v1/models` (LM Studio)
- **Model show/load/unload**: Ollama only — LM Studio returns early with info message
- **CompactWorker**: also dual-protocol for `/compact` summarization
- **Backend selection**: Preferences dialog dropdown, persisted to config
- **Status bar**: shows "(LM Studio)" suffix when LM Studio active

## Key Patterns

- **AI streaming**: `OllamaWorker` runs in a `QThread`, emits `token_received` signals. `ChatPanel._on_token()` appends to a QTextEdit inside the AI message widget.
- **Chat display**: QScrollArea with per-message widgets. User messages are right-aligned QFrame bubbles. AI responses are left-aligned QTextEdit that auto-resizes via `document().contentsChanged`.
- **AI code edits**: AI outputs `<<<EDIT filename / <<<OLD / >>>NEW / >>>END` or `<<<FILE filename / >>>END` blocks. `ChatPanel._parse_edits()` (~5751) parses these, shows a "Replace" bar via `_populate_apply_bar()` (~6296). `_apply_all_edits()` (~5996) applies them.
- **WorkingSet context**: Priority-based (0=active, 1=AI-edited, 2=open, 3=project/ref docs), 12K token budget. Built in `_build_file_context()` (~4113). Reference docs loaded from `~/.teensy_ide_ref_docs.json` at priority 3.
- **Git context**: `_build_git_context()` (~4272) injects branch, recent commits, diff stat into every AI prompt.
- **Signals chain for AI actions**: CodeEditor `ai_action_requested(str, str)` → TabbedEditor → MainWindow → `ChatPanel.send_ai_action()`
- **Serial data sharing**: `SerialMonitor.serial_line_received(str)` signal → `SerialPlotterPanel.on_serial_line()`. Plotter uses 60ms QTimer refresh with dirty flag.
- **Code block rendering**: `_render_formatted_response()` (~5383) post-renders fenced code blocks and EDIT/FILE blocks with styled HTML.
- **Slash commands**: `/clear`, `/model`, `/compact`, `/context`, `/help`, `/debug-ws`, `/debug-use-ws` with autocomplete popup on `/`.
- **Color theme**: Dark theme in `C = {}` dict (~line 71). Key colors: `teal=#00979d`, `bg=#1e1e1e`, `fg=#d4d4d4`.
- **Global model**: `OLLAMA_MODEL` global, changed via toolbar combo box, persisted to config.
- **Board combo**: Shows friendly names (e.g. "Teensy 4.0") via `BOARD_DISPLAY` mapping, stores FQBN as item data — use `_current_fqbn()` to get actual FQBN.

## Config Persistence

| File | Purpose |
|---|---|
| `~/.teensy_ide_config.json` | Selected model, backend, URLs, preferences |
| `~/.teensy_ide_model_descs.json` | AI-generated model descriptions cache |
| `~/.teensy_ide_ref_docs.json` | Reference document paths for WorkingSet |
| `~/.teensy_ide_rules.txt` | User-defined AI system prompt rules |
| `~/.teensy_ide_chat_history.json` | Saved chat conversations |

## QTextEdit HTML Limitations
QTextEdit's rich text engine supports a subset of CSS 2.1. It does NOT support `border-radius`, `flexbox`, `grid`, or most modern CSS. For styled containers, use QFrame/QWidget with Qt stylesheets instead of HTML/CSS in QTextEdit.

## Design System (MANDATORY)

**Before making ANY visual/layout changes, read these files in order:**

1. **`docs/DESIGN_SYSTEM.md`** — Strict design tokens (colors, fonts, spacing, radius, button styles). Every stylesheet value MUST come from these tokens.
2. **`docs/UI_SPEC.md`** — Layout blueprints and component specs for each view.
3. **`docs/CHAT_SPEC.md`** — Detailed chat view implementation spec.

**Rules:** Never hardcode a hex color — use `C['key']`. Never inline a font-size — use `FONT_BODY` etc.

## App Behavior & Agentic Features (MANDATORY)

**Before adding or modifying any feature logic, read:**

- **`docs/APP_BEHAVIOR.md`** — View navigation, compile/upload flow, AI chat message flow, edit parsing/application, file browser, git, serial monitor, keyboard shortcuts, signal chains, data persistence.
- **`docs/AGENTIC_FEATURES.md`** — Claude Code-inspired features: status table showing what's DONE vs NOT STARTED. Covers WorkingSet context system, slash commands, visual diffs, AI-git integration, code block rendering, AI-triggered compile, and more. **Check the status table before implementing — many Phase 1 features are already done.** New features MUST integrate with the WorkingSet context architecture.
