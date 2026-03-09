# ArduinoAIDE

A macOS desktop IDE for Teensy microcontroller development, styled after Arduino IDE 2.x. Single-file PyQt6 application with local LLM integration via Ollama.

## Tech Stack
- **Python 3 + PyQt6 6.10.2 + QScintilla** — native macOS desktop app
- **Ollama REST API** — local LLM chat (streaming via `/api/chat`), model management (`/api/tags`, `/api/show`, `/api/create`, `/api/delete`, `/api/pull`)
- **arduino-cli** — compile/upload with FQBN `teensy:avr:teensy40`
- **Single file**: `ArduinoAIDE.py` (~3200 lines) — everything is in this one file
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

## Design System (MANDATORY)

**Before making ANY visual/layout changes, read these files in order:**

1. **`docs/DESIGN_SYSTEM.md`** — Strict design tokens (colors, fonts, spacing, radius, button styles). Every stylesheet value MUST come from these tokens.
2. **`docs/UI_SPEC.md`** — Layout blueprints and component specs for each view.
3. **`docs/CHAT_SPEC.md`** — Detailed chat view implementation spec.

**Rules:** Never hardcode a hex color — use `C['key']`. Never inline a font-size — use `FONT_BODY` etc.

## App Behavior & Agentic Features (MANDATORY)

**Before adding or modifying any feature logic, read:**

- **`docs/APP_BEHAVIOR.md`** — What the app does: view navigation, compile/upload flow, AI chat message flow, edit parsing/application, file browser, git, serial monitor, keyboard shortcuts, signal chains, data persistence.
- **`docs/AGENTIC_FEATURES.md`** — Claude Code-inspired features: status table showing what's DONE vs NOT STARTED. Covers WorkingSet context system, slash commands, visual diffs, AI-git integration, code block rendering, AI-triggered compile, and more. **Check the status table before implementing — many Phase 1 features are already done.** New features MUST integrate with the WorkingSet context architecture.

## Recent Work / Known State
- **WorkingSet context system** — priority-based (0=active, 1=AI-edited, 2=open, 3=project), 12K token budget, replaces old full-project dump. Safety checks warn if critical files excluded.
- **Slash commands** — `/clear`, `/model`, `/compact`, `/context`, `/help`, `/debug-ws`, `/debug-use-ws`
- **Code block rendering** — `_render_formatted_response()` post-renders fenced code blocks and EDIT/FILE blocks with styled HTML
- **AIWorkResult** — typed container for AI responses (`ProposedEdit`, `AIWorkResult` dataclasses)
- **Git context** — `_build_git_context()` injects branch, commits, diff stat into every AI prompt
- Visual overhaul: icon-only toolbar buttons, widget-based chat bubbles, status bar, file browser
- Board combo shows friendly names (e.g. "Teensy 4.0") but stores FQBN as item data — use `_current_fqbn()` to get the actual FQBN
- Sidebar order: Code, AI Chat, Files, Git, (stretch), Settings at bottom
