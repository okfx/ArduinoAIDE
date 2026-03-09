# ArduinoAIDE — Agentic Features Specification

**This document specifies the Claude Code-inspired features to be implemented in ArduinoAIDE.**
It covers seamless file reading, code auditing/refactoring, edit insertion with visual diffs,
GitHub integration with the AI, slash commands, and context management.

For visual styling, see `DESIGN_SYSTEM.md`. For existing behavior, see `APP_BEHAVIOR.md`.

---

## 1. Seamless File Reading (Enhanced Context Injection)

### Current State
The AI receives the complete content of every open editor tab via `_build_file_context()`.
This means the AI only sees files the user has explicitly opened.

### Target State
The AI should be able to see any file in the project, not just open tabs. This is how Claude Code
works — it reads files on demand, sees the project structure, and understands the full codebase.

### Implementation

#### 1a. Project Tree Context
Every AI message should automatically include a directory listing of the project (file names and
sizes, not contents). This gives the AI awareness of the full project structure without consuming
the entire context window.

```
[PROJECT STRUCTURE]
MySketch/
  MySketch.ino        (2.4 KB)
  config.h            (0.8 KB)
  sensors.cpp         (3.1 KB)
  sensors.h           (0.5 KB)
  lib/
    display.cpp       (1.9 KB)
    display.h         (0.4 KB)
  README.md           (0.3 KB)
```

Add a helper `_build_tree_context()` that walks `self._project_path` recursively, skipping
hidden dirs (`.git`, `.DS_Store`), build output (`build/`, `.pio/`), and returns a formatted
tree string with file sizes.

#### 1b. Smart Context: Open Files + Referenced Files
Instead of dumping ALL open files every message (which wastes context on large projects),
inject only:
- The **currently active tab** (full content, always)
- **Other open tabs** (full content, but with a total budget — e.g., 12,000 tokens max;
  truncate or summarize the rest)
- **Files the AI previously edited** in this conversation (full content, so it can see its
  own work)

This keeps the context window lean for local models with limited capacity (8K–32K).

#### 1c. AI-Requested File Reading
When the AI needs to see a file it doesn't have, it can request it with a special block:

```
<<<READ sensors.h
```

The app detects this in `_parse_edits()` (or a new `_parse_commands()`), reads the requested
file from disk, and automatically sends a follow-up message with the file contents injected —
no user action required. The user sees an info line in chat:

> *Reading sensors.h for the AI...*

Then the conversation continues seamlessly. This is a simplified version of Claude Code's
tool-use pattern.

**Implementation sketch:**
```python
def _parse_commands(self, response):
    """Parse <<<READ blocks and auto-inject file contents."""
    read_pat = re.compile(r'<<<READ\s+(\S+)')
    reads = read_pat.findall(response)
    if reads:
        for filename in reads:
            content = self._read_project_file(filename)
            if content:
                self._add_info_msg(f"Reading {filename} for the AI...", C['fg_dim'])
                inject = f"[FILE CONTENT: {filename}]\n{content}\n[END FILE: {filename}]"
                self._conversation.append({"role": "user", "content": inject})
        # Auto-continue the conversation
        self._conversation.append({"role": "user", "content": "[Continue your previous response now that you can see the requested files.]"})
        self._auto_send()
```

#### 1d. Git Diff as Context
When the user has uncommitted changes, include a condensed `git diff --stat` summary
(not the full diff) in the context. This tells the AI what's been changed recently.

```
[GIT STATUS]
Branch: feature/sensor-calibration
Modified: sensors.cpp (+12, -3), config.h (+1, -1)
Untracked: test_calibration.ino
```

---

## 2. Code Auditing and Refactoring

### Current State
The user can right-click selected code and send it to the AI with a prompt template
(e.g., "Find Bugs", "Explain This Code"). The AI responds with plain text and optional
EDIT blocks.

### Target State
Add dedicated auditing workflows that analyze code systematically — not just the selected
snippet, but whole files or the full project.

### Implementation

#### 2a. Built-in Audit Actions (Pre-configured AI Tools)
Add these to the default AI Tools list in Settings:

| Action | Prompt Template |
|---|---|
| **Audit File** | "Review the entire file `{filename}` for bugs, memory leaks, type errors, unused variables, and poor practices. List each issue with line numbers and a suggested fix using <<<EDIT blocks." |
| **Refactor File** | "Refactor `{filename}` to improve readability, reduce duplication, and follow Arduino/C++ best practices. Use <<<EDIT blocks for each change." |
| **Optimize for Teensy** | "Analyze `{filename}` for Teensy-specific optimizations: memory usage (PROGMEM, F() macro), DMA, interrupt safety, timing. Suggest concrete changes with <<<EDIT blocks." |
| **Explain File** | "Explain the purpose and flow of `{filename}` section by section. Note any confusing areas." |

These should work on the **full active file**, not just selected text. The `{filename}`
placeholder resolves to the current tab's filename, and the full file content is injected
as context.

#### 2b. Whole-File Actions (No Selection Required)
Currently, AI actions only trigger from right-click on selected code. Add a way to invoke
audit actions on the full current file:

- **Menu bar**: `AI > Audit Current File`, `AI > Refactor Current File`
- **Keyboard shortcut**: `Ctrl+Shift+R` for "Refactor Current File"
- **Slash command in chat**: `/audit`, `/refactor` (see Section 5)

When triggered without a selection, `{code}` in the template is replaced with the full file
content and `{filename}` with the active tab name.

#### 2c. Multi-File Refactoring
For refactoring that spans files (e.g., "move this function to a new file and update all
includes"), the AI should be able to emit multiple EDIT blocks and FILE blocks targeting
different files in a single response. This already works in `_parse_edits()` — the
enhancement is in the Apply bar UI (see Section 3).

---

## 3. Code Insertion and Visual Diffs

### Current State
- EDIT blocks are parsed and applied via string replacement
- FILE blocks replace entire file contents
- The Apply bar shows "N changes in filename" with Apply All / Dismiss
- No visual preview of what will change

### Target State
Before applying, show the user exactly what will change with a visual diff — red lines for
deletions, green lines for additions — so they can review and accept/reject per-file or
per-edit.

### Implementation

#### 3a. Visual Diff Widget
Create a `DiffWidget(QFrame)` that renders a single edit as a visual diff:

```
┌─ sensors.cpp ──────────────────────────────────────┐
│  15 │   int readSensor() {                          │  (context, dim)
│  16 │ - int val = analogRead(A0);                   │  (red bg, strikethrough)
│  17 │ + int val = analogRead(SENSOR_PIN);           │  (green bg)
│  18 │     return map(val, 0, 1023, 0, 100);         │  (context, dim)
│  19 │   }                                           │
└─────────────────────────────────────────────────────┘
```

Styling (matches UI_SPEC.md future enhancement section):
- Container: `bg: C['bg']`, `border: 1px solid C['border_light']`, `border-radius: 8px`
- Header: `bg: C['bg_hover']`, filename in `FONT_CODE`, bottom border
- Diff lines: `FONT_CODE` (13px monospace)
- Deletions: `background: rgba(244, 71, 71, 0.12)`, `color: C['fg_err_text']`
- Additions: `background: rgba(78, 205, 196, 0.12)`, `color: #7ee0d8`
- Context lines: `color: C['fg_dim']`
- Line numbers: `color: C['fg_muted']`, right-aligned, 40px gutter

Use `difflib.unified_diff()` to generate the diff from OLD and NEW text. Display 3 lines
of context around each change.

#### 3b. Per-Edit Accept/Reject
Replace the single "Apply All Changes" bar with an expanded review mode:

```
┌─ Apply Bar (expanded) ──────────────────────────────┐
│ 3 changes across 2 files   [Apply All] [Dismiss All]│
├──────────────────────────────────────────────────────┤
│ ┌ DiffWidget: sensors.cpp (edit 1 of 2) ──────────┐ │
│ │ [visual diff lines]                               │ │
│ │                          [Accept ✓] [Reject ✗]    │ │
│ └───────────────────────────────────────────────────┘ │
│ ┌ DiffWidget: sensors.cpp (edit 2 of 2) ──────────┐ │
│ │ [visual diff lines]                               │ │
│ │                          [Accept ✓] [Reject ✗]    │ │
│ └───────────────────────────────────────────────────┘ │
│ ┌ DiffWidget: config.h (1 edit) ──────────────────┐  │
│ │ [visual diff lines]                               │ │
│ │                          [Accept ✓] [Reject ✗]    │ │
│ └───────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

The diff widgets render inside a QScrollArea that replaces the simple apply bar. Each has
its own Accept/Reject buttons. "Apply All" and "Dismiss All" still exist at the top.

When an edit is accepted, the DiffWidget shows a green check and dims out. When rejected,
it shows a red X and dims out. This gives the user full control over each change.

#### 3c. Inline Diff in Chat (Future Phase)
Eventually, render the DiffWidgets inline within the AI response itself (where the EDIT
blocks appear in the text), similar to how Claude Code shows diffs inline. This is a more
complex layout change and should be Phase 2.

#### 3d. Undo Integration
After applying edits, the user can always Ctrl+Z in the editor to undo. But add an
explicit "Undo Last Apply" button that appears in the apply bar for 10 seconds after
applying, which reverses the most recent batch of applied edits.

Store the pre-edit content of each file before applying:
```python
self._pre_edit_snapshots = {}  # filename -> content before edits
```

---

## 4. GitHub / Git Integration with AI

### Current State
- GitPanel is fully functional: branch/tag management, commit, push, pull
- But it's completely separate from the AI — the AI has zero awareness of git state
- The commit row uses a plain text input for commit messages

### Target State
Git and the AI should talk to each other. The AI should see git state, suggest commit
messages, and help with merge conflicts.

### Implementation

#### 4a. Git Context in AI Messages
Add git status info to the AI context automatically (see 1d above). This includes:
- Current branch name
- Uncommitted changes summary (`git diff --stat`)
- Recent commit log (last 3-5 commits, one line each)

```
[GIT STATUS]
Branch: feature/sensor-calibration
Last commits:
  abc1234 Add initial sensor reading (2 hours ago)
  def5678 Setup project structure (yesterday)
Modified: sensors.cpp (+12, -3), config.h (+1, -1)
Untracked: test_calibration.ino
```

Implementation: add `_build_git_context()` to ChatPanel that calls `git` commands via
subprocess (reuse GitPanel's `_run_git` pattern):
- `git branch --show-current`
- `git diff --stat`
- `git log --oneline -5`

Only include this when git is initialized (check for `.git` dir).

#### 4b. AI-Generated Commit Messages
Add a button or shortcut in the Git panel's commit row:

```
[Commit msg input·····] [✨ AI] [Commit All] [Push] [Pull]
```

The "✨ AI" button:
1. Runs `git diff --cached` (or `git diff` if nothing staged)
2. Sends the diff to the AI with the prompt: "Generate a concise git commit message for
   these changes. Use conventional commit format (feat:, fix:, refactor:, etc.).
   Return ONLY the commit message, nothing else."
3. Fills the commit message input with the AI's response
4. User reviews and clicks "Commit All"

This is a fast, non-chat interaction — it uses a one-shot Ollama call, not the full
conversation.

#### 4c. Merge Conflict Resolution
When `git merge` or `git pull` produces conflicts:
1. GitPanel detects conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) in the output
2. Opens conflicted files in the editor (they'll show the conflict markers)
3. Shows an info bar: "Merge conflict in sensors.cpp — [Ask AI to Resolve]"
4. Clicking "Ask AI to Resolve" sends the conflicted file to the AI with:
   "This file has git merge conflicts. Resolve them intelligently, keeping the best parts
   of both sides. Return the resolved file using <<<FILE blocks."
5. User reviews the AI's resolution via the diff widget, then accepts or edits manually

#### 4d. Git Diff View in AI Context (Attach Diff)
Add an "Attach Diff" toggle button alongside "Attach Errors" at the bottom of the chat:

```
[Attach Errors] [Attach Diff] [Clear Chat]    (stretch)
```

When checked, the next message includes the full `git diff` output so the user can ask
the AI things like "What did I change?" or "Is this diff safe to commit?"

---

## 5. Slash Commands

### Current State
The chat input is a plain QLineEdit. No command system.

### Target State
Support `/` commands in the chat input for quick actions, similar to Claude Code's
slash commands.

### Implementation

#### 5a. Command Parser
Intercept input in `send_message()` before sending to Ollama:

```python
def send_message(self):
    text = self.input_field.text().strip()
    if not text:
        return
    if text.startswith("/"):
        self._handle_slash_command(text)
        return
    self._send_prompt(text, display_text=text)
```

#### 5b. Command List

| Command | Action | Description |
|---|---|---|
| `/clear` | `self.clear_chat()` | Clear conversation history |
| `/model <name>` | Switch active model | Change Ollama model mid-conversation |
| `/compact` | Summarize and reset history | Ask AI to summarize the conversation, then replace history with the summary (critical for small context windows) |
| `/context` | Show what the AI sees | Display the full context that would be sent (file list, git status, error context) in an info message — useful for debugging |
| `/audit` | Audit current file | Trigger the "Audit File" AI action on the active tab |
| `/refactor` | Refactor current file | Trigger the "Refactor File" AI action on the active tab |
| `/diff` | Show git diff | Display `git diff` output in the chat as an info message |
| `/commit <msg>` | Quick commit | Run `git add -A && git commit -m "msg"` from chat |
| `/help` | List commands | Show all available slash commands in an info message |

#### 5c. Autocomplete Popup
When the user types `/` in the input field, show a popup above the input with matching
commands (filter as they type). Use a QListWidget popup positioned above the input field.

Styling:
- `bg: C['bg_input']`, `border: 1px solid C['border_light']`, `border-radius: 6px`
- Items: `FONT_CHAT`, `color: C['fg']`, hover: `bg: C['bg_hover']`
- Command name in `C['teal']`, description in `C['fg_dim']`
- Max 6 visible items, scrollable

#### 5d. /compact Implementation (Critical for Local Models)
The `/compact` command is the highest-priority slash command because local models have
limited context windows.

```python
def _compact_conversation(self):
    """Summarize conversation history to free context window space."""
    if len(self._conversation) < 4:
        self._add_info_msg("Conversation too short to compact.", C['fg_warn'])
        return

    # Build a summary request
    summary_prompt = (
        "Summarize the key points of our conversation so far in a concise paragraph. "
        "Include: what files we discussed, what changes were made, what issues remain. "
        "This summary will replace the conversation history to save context space."
    )

    # Send as a one-shot (not added to visible chat)
    # ... get summary from Ollama ...

    # Replace conversation with: system prompt + summary + last 2 messages
    self._conversation = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"[CONVERSATION SUMMARY]\n{summary}"},
        {"role": "assistant", "content": "Understood. I have the context from our previous discussion. How can I help?"},
    ] + self._conversation[-2:]  # keep last exchange for continuity

    self._add_info_msg(
        f"Compacted conversation: {old_len} messages → {len(self._conversation)} messages",
        C['fg_ok'])
```

---

## 6. Code Block Rendering in AI Responses

### Current State
AI responses stream into a plain QTextEdit as raw text. Code blocks appear as plain
monospace text with no visual distinction.

### Target State
Detect fenced code blocks (``` ... ```) in AI responses and render them with:
- Monospace font (FONT_CODE)
- Subtle background (`C['bg_input']`)
- Rounded container
- Language label (if specified, e.g., ```cpp)
- Copy button

### Implementation
This is complex to do during streaming (the ``` delimiters arrive as tokens). Two approaches:

**Approach A: Post-render (simpler, Phase 1)**
After streaming completes, re-render the full response with code blocks styled. Replace the
QTextEdit content with HTML that wraps code blocks in styled `<pre>` tags.

**Approach B: Live render (complex, Phase 2)**
Track state during streaming: when ``` is detected, switch to a monospace font and apply
background styling. When the closing ``` arrives, revert. This requires a state machine in
`_on_token()`.

Recommend Phase 1 first: on `_on_complete()`, call `_render_formatted_response()` that
parses the response text for code fences and rebuilds the QTextEdit content with HTML
formatting:

```python
def _render_formatted_response(self):
    """Re-render the AI response with styled code blocks."""
    text = self._current_response
    html_parts = []
    in_code = False
    lang = ""

    for line in text.split("\n"):
        if line.startswith("```") and not in_code:
            lang = line[3:].strip()
            html_parts.append(
                f'<div style="background:{C["bg_input"]};border-radius:6px;'
                f'padding:10px;margin:6px 0;font-family:Menlo,monospace;font-size:13px;">')
            if lang:
                html_parts.append(
                    f'<div style="color:{C["fg_dim"]};font-size:11px;'
                    f'margin-bottom:4px;">{lang}</div>')
            html_parts.append('<pre style="margin:0;white-space:pre-wrap;">')
            in_code = True
        elif line.startswith("```") and in_code:
            html_parts.append("</pre></div>")
            in_code = False
        elif in_code:
            html_parts.append(html.escape(line) + "\n")
        else:
            html_parts.append(html.escape(line) + "<br>")

    if self._current_ai_widget:
        self._current_ai_widget.setHtml("".join(html_parts))
```

---

## 7. AI-Triggered Compile (Closing the Loop)

### Current State
The compile→error→AI fix loop requires manual steps:
1. User compiles (Ctrl+B)
2. Errors appear in Output tab
3. User clicks "Attach Errors" or presses Ctrl+Shift+E
4. User asks AI to fix
5. AI suggests EDIT blocks
6. User clicks Apply
7. User compiles again

### Target State
The AI can request a compile and automatically receive the results, reducing the loop to:
1. User asks AI to fix errors
2. AI fixes and says `<<<COMPILE`
3. App compiles, feeds results back to AI
4. If errors remain, AI tries again (up to 2 retries)

### Implementation

Add a `<<<COMPILE` command block (similar to `<<<READ`):

```python
def _parse_commands(self, response):
    """Parse special command blocks from AI response."""
    # ... existing READ parsing ...

    if "<<<COMPILE" in response:
        self._add_info_msg("Compiling at AI's request...", C['fg_dim'])
        # Trigger compile via signal to MainWindow
        self.compile_requested.emit()
        # MainWindow._compile() runs and stores errors
        # After compile, auto-send results back:
        QTimer.singleShot(500, self._send_compile_results)
```

Add a retry limit (max 2 auto-compiles) to prevent infinite loops. Show each compile
attempt as an info line in chat.

---

## 8. Conversation Persistence (Session Save/Load)

### Current State
Conversation history is lost when the app closes. Each session starts fresh.

### Target State
Save and restore chat sessions per-project.

### Implementation

Save `self._conversation` to `{project_path}/.aide_chat_history.json` on:
- App close
- Project switch
- `/clear` (save before clearing)

Load on project open. Show an info message: "Restored previous conversation (12 messages)."

Add `/sessions` command to list saved sessions and `/load <n>` to restore one.

---

## 9. Project-Level AI Configuration

### Current State
System prompt is hardcoded in `SYSTEM_PROMPT` constant. Same for all projects.

### Target State
Support a `.aide_prompt` file in the project root that gets prepended to the system prompt.
This lets users customize AI behavior per-project.

### Implementation

On project open, check for `{project_path}/.aide_prompt`. If found, prepend its contents
to the system prompt:

```python
def _build_system_prompt(self):
    base = SYSTEM_PROMPT
    custom_file = os.path.join(self._project_path, ".aide_prompt")
    if os.path.exists(custom_file):
        with open(custom_file) as f:
            custom = f.read().strip()
        return custom + "\n\n" + base
    return base
```

Example `.aide_prompt`:
```
This is a Teensy 4.0 project for a MIDI controller.
Libraries in use: Bounce2, MIDI, Adafruit_NeoPixel.
Always use PROGMEM for string constants.
Pin assignments: see config.h — never change pin numbers without asking.
```

---

## Implementation Priority

### Phase 1 (Core — do these first)
1. **Slash commands** (`/clear`, `/model`, `/compact`, `/help`, `/context`) — Section 5
2. **Project tree context** — Section 1a
3. **Git context in AI messages** — Section 4a
4. **Code block rendering** (post-render) — Section 6
5. **Project-level .aide_prompt** — Section 9

### Phase 2 (Visual Diffs & Review)
6. **Visual diff widget** — Section 3a
7. **Per-edit accept/reject** — Section 3b
8. **Smart context budgeting** — Section 1b
9. **Built-in audit actions** — Section 2a

### Phase 3 (Agentic Features)
10. **AI-requested file reading** (`<<<READ`) — Section 1c
11. **AI-triggered compile** (`<<<COMPILE`) — Section 7
12. **AI commit messages** — Section 4b
13. **Merge conflict resolution** — Section 4c

### Phase 4 (Polish)
14. **Slash command autocomplete popup** — Section 5c
15. **Conversation persistence** — Section 8
16. **Attach Diff button** — Section 4d
17. **Inline diff in chat** — Section 3c
18. **Undo Last Apply** — Section 3d

---

## Signal Flow: Agentic Edit Cycle

```
User: "Fix the bug in sensors.cpp"
  → ChatPanel._send_prompt() injects:
      - Project tree (1a)
      - Active file content (current tab)
      - Git diff summary (4a)
      - Compiler errors (if attached)
  → AI responds with analysis + <<<EDIT blocks
  → _parse_edits() extracts edits
  → DiffWidgets render in review panel (3a)
  → User clicks Accept on each / Apply All (3b)
  → Edits applied to editor
  → AI also emits <<<COMPILE
  → App compiles, sends results back (7)
  → AI sees "BUILD SUCCESSFUL" → conversation complete
     OR AI sees new errors → suggests additional fixes (max 2 retries)
```

## Signal Flow: AI-Assisted Commit

```
User clicks "✨ AI" in Git panel commit row
  → GitPanel runs `git diff`
  → One-shot Ollama call with diff + commit message prompt
  → Response fills commit message input
  → User reviews, edits if needed, clicks "Commit All"
  → Commit executes normally
```
