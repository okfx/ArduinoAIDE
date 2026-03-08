# ArduinoAIDE

A macOS desktop IDE for Teensy microcontroller development, styled after Arduino IDE 2.x. Single-file PyQt6 application with local LLM integration via Ollama.

## Tech Stack
- **Python 3 + PyQt6 6.10.2 + QScintilla** — native macOS desktop app
- **Ollama REST API** — local LLM chat (streaming via `/api/chat`), model management (`/api/tags`, `/api/show`, `/api/create`, `/api/delete`, `/api/pull`)
- **arduino-cli** — compile/upload with FQBN `teensy:avr:teensy40`
- **Single file**: `teensy_ide.py` (~3200 lines) — everything is in this one file
- **Virtual env**: `~/teensy-ide-env` — activate before running

## Running
```bash
source ~/teensy-ide-env/bin/activate
python3 teensy_ide.py [project_path]
```

## Architecture

All classes live in `teensy_ide.py`:

| Class | Line | Purpose |
|---|---|---|
| `SidebarButton` | ~368 | Base sidebar button with hover/checked states |
| `GitSidebarButton` | ~389 | Custom-painted git branch icon |
| `FileSidebarButton` | ~416 | Custom-painted folder icon |
| `SettingsSidebarButton` | ~438 | Custom-painted gear icon (larger) |
| `SpinnerWidget` | ~479 | Animated teal gear for AI activity indicator |
| `OllamaWorker` | ~530 | QObject worker for streaming Ollama responses in QThread |
| `TabbedEditor` | ~875 | Tab widget wrapping QScintilla/QPlainTextEdit code editors |
| `FileBrowser` | ~960 | QTreeView-based file tree |
| `FileManagerView` | ~1070 | Full file browser with parent context, SKETCHBOOK header |
| `ChatPanel` | ~1290 | AI chat with QScrollArea widget-based bubbles |
| `CompilerOutput` | ~1760 | Compiler output pane |
| `SerialMonitor` | ~1790 | Serial port monitor |
| `ModelManager` | ~1870 | Ollama model list, create, delete, pull, descriptions |
| `GitPanel` | ~2280 | Git GUI (status, commit, branch, tag, push/pull) |
| `MainWindow` | ~3040 | Main window with sidebar, toolbar, status bar, stacked views |

## Key Patterns

- **Sidebar views** via QStackedWidget — 5 views: Code(0), Chat(1), Files(2), Settings(3), Git(4)
- **AI streaming**: `OllamaWorker` runs in a `QThread`, emits `token_received` signals. `ChatPanel._on_token()` appends to a QTextEdit inside the AI message widget. Race condition handling: `worker.stop()` + `thread.wait(2000)` + recreate on timeout.
- **Chat display**: QScrollArea with per-message widgets. User messages are right-aligned QFrame bubbles with border-radius. AI responses are left-aligned QTextEdit (no bubble) that auto-resizes via `document().contentsChanged`.
- **AI code edits**: AI outputs `<<<EDIT filename / <<<OLD / >>>NEW / >>>END` blocks. `ChatPanel._parse_edits()` parses these, shows an "Apply" bar.
- **Signals chain for AI actions**: CodeEditor `ai_action_requested(str, str)` → TabbedEditor → MainWindow → `ChatPanel.send_ai_action()`
- **Config persistence**: `~/.teensy_ide_config.json` for selected model. `~/.teensy_ide_model_descs.json` for model descriptions.
- **Color theme**: Dark theme defined in `C = {}` dict at top of file (~line 50). Key colors: `teal=#00979d`, `bg=#1e1e1e`, `fg=#d4d4d4`.
- **Status bar**: Shows `Ln X, Col Y` (left) and board/port info (right). Board combo uses `BOARD_DISPLAY` mapping for friendly names, stores FQBN as item data.
- **Global model**: `OLLAMA_MODEL` global variable, changed via toolbar combo box, persisted to config.

## QTextEdit HTML Limitations
QTextEdit's rich text engine supports a subset of CSS 2.1. It does NOT support `border-radius`, `flexbox`, `grid`, or most modern CSS. For styled containers, use QFrame/QWidget with Qt stylesheets instead of HTML/CSS in QTextEdit. This is why the chat was rewritten to use widget-based bubbles.

## Recent Work / Known State
- Visual overhaul: icon-only toolbar buttons, widget-based chat bubbles, status bar, SKETCHBOOK file browser
- Chat display uses QScrollArea+widgets: user msgs are right-aligned dark bubbles, AI msgs are plain left-aligned QTextEdit
- Board combo shows friendly names (e.g. "Teensy 4.0") but stores FQBN as item data — use `_current_fqbn()` to get the actual FQBN
- Settings gear icon is custom-painted `SettingsSidebarButton`, positioned at bottom of sidebar
- Sidebar order: Code, AI Chat, Files, Git, (stretch), Settings at bottom
