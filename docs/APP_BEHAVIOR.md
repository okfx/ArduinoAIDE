# ArduinoAIDE — App Behavior Specification

**This document defines what the app does — the logic, interactions, and user flows.**
For visual styling, see `DESIGN_SYSTEM.md` and `UI_SPEC.md`. For chat-specific layout, see `CHAT_SPEC.md`.

---

## Core Concept

ArduinoAIDE is a local desktop IDE for Teensy microcontroller development. It combines a code editor, build tools, and a local AI assistant (via Ollama) in a single window. The AI can see all open project files and suggest code edits that the user can apply with one click.

The user workflow is: **write code → compile → fix errors (optionally with AI) → upload to board → monitor serial output**. The AI is a tool in this loop, not the center of it.

---

## Views and Navigation

The app has 5 views, accessed via the left sidebar. Only one view is visible at a time.

| Sidebar Button | View | Shortcut | Purpose |
|---|---|---|---|
| `{}` | Code Editor | Ctrl+1 | Write and edit code |
| AI | AI Chat | Ctrl+2 | Chat with local LLM |
| Folder | File Browser | Ctrl+3 | Browse and manage project files |
| Git | Git | Ctrl+5 | Branch, commit, push/pull |
| Gear | Settings | Ctrl+4 | AI tools config, model management |

### Sidebar Behavior
- Exactly one button is active at a time (exclusive toggle)
- Clicking the active button does nothing (stays on current view)
- Switching to Git view auto-refreshes git status
- The sidebar is always visible regardless of which view is active

---

## Code Editor View

### Tab Management
- Each open file gets a tab
- Tabs are closable (× button appears on hover)
- Opening a file that's already open switches to its tab (no duplicates)
- Modified files should show an indicator (dot or asterisk in tab title — future enhancement)

### Opening a Project
- **File > Open Project** (Ctrl+O) opens a folder dialog
- Opening a project:
  1. Sets the project path globally
  2. Opens all `.ino` files first, then `.cpp`, `.c`, `.h` files
  3. Updates the Chat panel's context (project name, file list)
  4. Updates the File Browser's root
  5. Updates the Git panel's working directory
  6. Updates the status bar with board/port info

### Saving
- **Ctrl+S** saves the currently active tab's file to disk
- Only the currently focused editor tab is saved (not all tabs)

### Code Editor Features
- Syntax highlighting via QScintilla (C/C++ lexer) when available
- Falls back to QPlainTextEdit if QScintilla not installed
- Right-click context menu includes:
  - Standard edit actions (Cut, Copy, Paste, Select All)
  - AI actions submenu (configurable in Settings > AI Tools)

### AI Context Menu Actions
- Right-clicking selected code shows AI actions (e.g., "Explain This Code", "Find Bugs")
- Selecting an action sends the selected code + prompt template to the Chat panel
- The app automatically switches to the Chat view (View 1)
- The full prompt includes `{code}` replaced with the selected text

---

## Compile and Upload (Toolbar)

### Verify (Compile)
- Toolbar button: ✓ (Ctrl+B)
- Runs: `arduino-cli compile --fqbn {FQBN} {project_path}`
- Before compiling: saves the current file
- Output streams to the **Output** tab in the bottom panel
- On success: shows success message in green
- On failure: shows errors in red, stores error text for "Attach Errors" feature

### Upload
- Toolbar button: ➤ (Ctrl+U)
- Runs: `arduino-cli upload --fqbn {FQBN} -p {port} {project_path}`
- Requires a valid port selected in the toolbar
- Output streams to the **Output** tab

### Board and Port Selection
- **Board combo**: shows friendly names ("Teensy 4.0"), stores FQBN as item data
- **Port combo**: editable, auto-scans for `/dev/cu.usbmodem*`, `/dev/ttyACM*`, `/dev/cu.usbserial*`
- **Refresh button** (↻): re-scans available ports
- Board/port changes update the status bar immediately

---

## AI Chat View

### Message Flow
1. User types in the input field and presses Enter or clicks Send
2. The app automatically prepends:
   - All open file contents (full text of every tab)
   - The project name and directory
   - Compiler errors (if "Attach Errors" is checked)
3. The user only sees their own message in a right-aligned bubble
4. The AI response streams token-by-token into a left-aligned text area
5. On completion, the response is parsed for edit blocks

### AI Response Parsing
After the AI finishes responding, the app scans for two block formats:

**EDIT blocks** (targeted search & replace):
```
<<<EDIT filename.ino
<<<OLD
(exact code to find)
>>>NEW
(replacement code)
>>>END
```

**FILE blocks** (full file replacement):
```
<<<FILE filename.ino
(complete file contents)
>>>FILE
```

If blocks are found:
- The Apply bar appears below the chat with: "N changes in filename" + [Replace] + [Dismiss]
- A green info message appears in the chat

If no EDIT/FILE blocks are found but fenced code blocks (```) exist:
- The app offers to replace the current file with the code block content
- This is a fallback and less precise than EDIT blocks

### Apply Bar
- **Replace**: iterates through parsed edits, applies each to the editor
  - EDIT: finds the OLD text in the file, replaces with NEW (first match only)
  - FILE: replaces the entire file content
  - Reports success/failure count
- **Dismiss**: hides the bar, discards pending edits
- Applying edits modifies the in-editor content (the user can still Ctrl+Z to undo)

### Attach Errors
- Toggle button at the bottom of chat
- When checked, the next message sent will include compiler error output
- Auto-unchecks after sending one message with errors attached
- Shortcut: Ctrl+Shift+E sends errors to AI immediately

### Stop Generation
- Stops the Ollama stream mid-response
- The partial response remains visible in the chat
- Worker thread is gracefully stopped (wait 2s, then terminate + recreate if needed)

### Clear Chat
- Removes all message widgets from the scroll area
- Resets conversation history to just the system prompt
- Hides the Apply bar and clears pending edits

### Context Header
- Shows "AI Chat" as the panel title (static)
- Dim text beside it shows project name and file count when a project is loaded
- "Show Files" link (hidden until project loaded) toggles an expandable section showing the file list

---

## File Browser View

### Layout
- **Header**: "File Browser" (or project name when a project is loaded)
- **Top pane** (Parent Folder): shows the parent directory of the current focus
- **Bottom pane** (main tree): shows the project file hierarchy

### Behavior
- Double-clicking a file opens it in the Code Editor and switches to View 0
- Double-clicking a folder in the parent pane navigates into it
- Clicking a folder in the main tree updates the parent context pane
- Files are color-coded by extension:
  - `.ino`, `.cpp`, `.c`: keyword blue
  - `.h`, `.hpp`: type teal
  - `.md`, `.txt`: dim gray
  - Others: standard foreground

### Bottom Action Bar
- **+ New File**: creates an empty file in the current focus directory (prompts for name)
- **+ New Folder**: creates a directory (prompts for name)
- **New Sketch**: creates a new Arduino sketch folder with a `.ino` file containing setup()/loop() template

---

## Git View

### Header
- Shows "Branch: {name}" (updates dynamically)
- **Refresh** button: re-reads git status, branches, tags
- **Init Repo**: runs `git init` in the project directory

### Branch Management
- **Branch list**: shows all local branches, current branch highlighted
- **Checkout**: switches to selected branch, emits `branch_changed` signal which reloads open files
- **New Branch**: prompts for name, creates from current HEAD
- **Merge Into Current**: merges selected branch into the current branch
- **Delete**: deletes the selected branch (with confirmation)

### Tag Management
- **Tag list**: shows all tags
- **New Tag**: prompts for name, creates at HEAD
- **Checkout**: detached HEAD checkout of the tag
- **Delete**: deletes the selected tag

### Commit Row
- Commit message input field
- **Commit All**: runs `git add -A && git commit -m "message"`
- **Push**: pushes to remote
- **Pull**: pulls from remote

### Console
- Bottom half shows git command output
- Read-only, monospace font
- Shows both stdout and stderr from git commands

---

## Settings View

### AI Tools Tab
- CRUD editor for the right-click context menu AI actions
- Each action has a label and a prompt template with `{code}` placeholder
- "Ask AI About This..." is a built-in action that cannot be edited or deleted
- Actions can be reordered (▲/▼), separated, and reset to defaults
- Changes persist to `~/.teensy_ide_ai_actions.json`

### Models Tab
- **Left column**: installed Ollama models (name, size, modified date)
  - Refresh button re-queries `/api/tags`
  - Delete button calls `/api/delete`
- **Right column** (scrollable):
  - **Model Details**: shows model info from `/api/show`, editable description
  - **Create Model**: build custom models with base model, context size, temperature, system prompt → calls `/api/create` with generated Modelfile
  - **Pull Model**: curated list of popular models + custom name input → calls `/api/pull` with streaming progress

### Model Selection
- Toolbar combo shows all available models
- Selecting a model:
  1. Sets the global `OLLAMA_MODEL` variable
  2. Saves to `~/.teensy_ide_config.json`
  3. Updates the model description label in the toolbar
- The selected model persists across app restarts

---

## Serial Monitor (Bottom Panel Tab)

### Controls
- **Port combo**: same ports as toolbar, editable
- **Baud combo**: standard rates (9600 through 1000000)
- **Start/Stop**: opens/closes serial connection
  - Start: opens `serial.Serial(port, baud)`, starts 50ms polling timer
  - Stop: closes connection, stops timer
  - Button toggles between "Start" (primary) and "Stop" (danger)
- **Clear**: clears the display
- **Send input**: sends text + newline to the serial port on Enter

### Display
- Read-only QPlainTextEdit
- Shows incoming serial data decoded as UTF-8
- Auto-scrolls to bottom

---

## Status Bar

- **Left**: cursor position — "Ln X, Col Y" (updates on cursor move or tab switch)
- **Right**: board and port info — "Teensy 4.0 on /dev/cu.usbmodem14201"
- Fixed 22px height, dim text

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+O | Open Project folder |
| Ctrl+S | Save current file |
| Ctrl+Q | Quit |
| Ctrl+B | Verify / Compile |
| Ctrl+U | Upload to board |
| Ctrl+1 | Switch to Code Editor |
| Ctrl+2 | Switch to AI Chat |
| Ctrl+3 | Switch to File Browser |
| Ctrl+4 | Switch to Settings |
| Ctrl+5 | Switch to Git |
| Ctrl+Shift+A | Open AI Chat |
| Ctrl+Shift+E | Send compiler errors to AI |
| Ctrl+X/C/V/A | Standard edit (in code editor context menu) |

---

## Data Persistence

| Data | Location | Format |
|---|---|---|
| Selected AI model | `~/.teensy_ide_config.json` | `{"model": "name"}` |
| Model descriptions | `~/.teensy_ide_model_descs.json` | `{"model-name": "description"}` |
| AI tool actions | `~/.teensy_ide_ai_actions.json` | Array of `[label, template]` or `null` (separator) |

---

## Error Handling

- **Ollama not running**: Chat shows connection error, model combo stays empty, model management shows "Ollama error: ..."
- **Compile failure**: errors shown in red in Output tab, stored for "Attach Errors"
- **Serial port unavailable**: error shown in Serial Monitor display
- **Git not initialized**: Git panel shows empty state, "Init Repo" button available
- **File operation failures**: QMessageBox warnings (new file, new folder, new sketch)

---

## Signal Flow (Key Chains)

### AI Action from Code Editor
```
CodeEditor right-click → AI action selected
  → ai_action_requested(prompt, code) signal
  → TabbedEditor relays signal
  → MainWindow._on_ai_action() switches to Chat view
  → ChatPanel.send_ai_action(prompt)
  → builds full context + sends to Ollama
```

### Compile → Error → AI Fix
```
User clicks Verify (Ctrl+B)
  → MainWindow._compile() saves file, runs arduino-cli
  → Output streams to CompilerOutput
  → On failure: errors stored in MainWindow._compiler_errors
  → User clicks "Attach Errors" in Chat (or Ctrl+Shift+E)
  → Next chat message includes compiler errors
  → AI suggests fix with EDIT blocks
  → User clicks "Replace"
  → Edits applied to editor tabs
  → User re-compiles
```

### Branch Checkout
```
User selects branch in Git panel → clicks Checkout
  → GitPanel._checkout_branch() runs git checkout
  → On success: branch_changed signal emitted
  → MainWindow._on_branch_changed() reloads project files
  → TabbedEditor reopens all files (content may have changed)
```

---

## Future Enhancements (Not Yet Implemented)

These are planned but not built. Do not implement unless explicitly asked.

**See `docs/AGENTIC_FEATURES.md` for the full specification of planned Claude Code-inspired
features**, including: seamless file reading, visual diffs, slash commands, AI-git integration,
code block rendering, and AI-triggered compile. That document includes phased implementation
priorities.

Additional enhancements not covered in AGENTIC_FEATURES.md:

- **Modified file indicator**: dot/asterisk in tab title for unsaved changes
- **Auto-save**: periodic save of modified files
- **Project templates**: starter sketches for common Teensy peripherals
- **Search/Replace**: global find across project files
- **Minimap**: code overview sidebar in the editor
