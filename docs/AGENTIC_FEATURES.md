# ArduinoAIDE — Agentic Features Specification

**This document specifies the Claude Code-inspired features for ArduinoAIDE.**
It covers seamless file reading, code auditing/refactoring, edit insertion with visual diffs,
GitHub integration with the AI, slash commands, and context management.

For visual styling, see `DESIGN_SYSTEM.md`. For existing behavior, see `APP_BEHAVIOR.md`.

---

## Implementation Status

| Feature | Section | Status |
|---|---|---|
| WorkingSet context system | 1a, 1b | **DONE** — priority-based, budget-constrained |
| Project tree context | 1a | **DONE** — `_build_directory_tree()` |
| Smart context budgeting | 1b | **DONE** — 12K token budget, priority 0-3 |
| AI-edited file tracking | 1b | **DONE** — `_ai_edited_files` set |
| Git context in AI messages | 4a | **DONE** — `_build_git_context()` |
| Slash commands (core) | 5a, 5b | **DONE** — `/clear`, `/model`, `/compact`, `/context`, `/help` |
| `/compact` with one-shot LLM | 5d | **DONE** — background CompactWorker thread |
| Code block rendering | 6 | **DONE** — `_render_formatted_response()` post-render |
| Edit block rendering | 6 | **DONE** — styled <<<EDIT/<<<FILE blocks in HTML |
| AIWorkResult typed container | — | **DONE** — `ProposedEdit`, `AIWorkResult` dataclasses |
| Debug observability | — | **DONE** — `/debug-ws`, `/debug-use-ws`, `_last_prompt_stats` |
| WorkingSet safety checks | — | **DONE** — warns if active/AI-edited files excluded |
| AI-requested file reading | 1c | NOT STARTED |
| Built-in audit actions | 2a | NOT STARTED |
| Whole-file AI actions | 2b | NOT STARTED |
| Visual diff widget | 3a | NOT STARTED |
| Per-edit accept/reject | 3b | NOT STARTED |
| AI-generated commit messages | 4b | NOT STARTED |
| Merge conflict resolution | 4c | NOT STARTED |
| Attach Diff button | 4d | NOT STARTED |
| `/audit`, `/refactor` commands | 5b | NOT STARTED |
| `/diff`, `/commit` commands | 5b | NOT STARTED |
| Slash command autocomplete | 5c | NOT STARTED |
| AI-triggered compile | 7 | NOT STARTED (AIWorkResult has `request_compile` field ready) |
| Conversation persistence | 8 | NOT STARTED |
| Project-level .aide_prompt | 9 | NOT STARTED |
| Structured compile diagnostics | 10 | NOT STARTED (next planned feature) |

---

## Architecture Notes (Current)

### WorkingSet Context System
The old "dump all open files" approach has been replaced with a deterministic, priority-based
WorkingSet. This is now the production context architecture.

**Priority levels:**
- **0** — Active file in the editor (always included, even over budget)
- **1** — Files the AI has edited during this session (`_ai_edited_files`)
- **2** — Files currently open in editor tabs
- **3** — Other project files discovered by `_scan_project_files()`

**Behavior:** Files are sorted by priority and included until the token budget (~12,000) is
reached. Overflow files get a one-line stub. A directory tree is always included. Safety
checks warn if priority-0 or priority-1 files get excluded.

**Data structures:** `WorkingSetEntry` (filepath, rel_path, priority, content, token_estimate)
and `WorkingSet` (entries dict, budget, `build_context()`, `total_tokens`, `included_count`).

**Debug commands:** `/debug-ws` shows full WorkingSet state; `/debug-use-ws off` falls back
to legacy full-context mode.

### AIWorkResult
A typed container for each AI response. Currently holds `assistant_text`, `proposed_edits`
(list of `ProposedEdit`), and placeholder fields for `requested_reads`, `request_compile`,
`warnings`, and `metadata`. Future features should populate these fields rather than using
ad-hoc side channels.

### Git Context
`_build_git_context()` is called in `_send_prompt()` alongside `_build_file_context()`.
It provides branch name, last 5 commits, `git diff --stat`, and untracked files.

**IMPORTANT:** Future features must integrate with WorkingSet rather than bypass it.

---

## 1. Seamless File Reading (Enhanced Context Injection)

### Completed
- **1a. Project tree context** — `_build_directory_tree()` walks the project directory,
  skipping hidden dirs and build output, and includes file sizes. Always injected.
- **1b. Smart context budgeting** — WorkingSet with 12K token budget, priority-based
  inclusion. Active tab always included. AI-edited files tracked and prioritized.

### Remaining: 1c. AI-Requested File Reading
When the AI needs to see a file not in its context, it can request it:

```
<<<READ sensors.h
```

The app detects this in `_parse_edits()` (or a new `_parse_commands()`), reads the file
from disk, and automatically sends a follow-up message with the contents injected.
The user sees an info line: *"Reading sensors.h for the AI..."*

**Implementation notes:**
- The `AIWorkResult.requested_reads` field already exists for this
- Should add the read file to WorkingSet as priority 1 (AI-referenced) so it stays
  in context for subsequent turns
- Limit to 3 auto-reads per turn to prevent runaway loops
- If the file doesn't exist, inject an error message instead

```python
def _handle_requested_reads(self, result):
    """Process <<<READ requests from AI response."""
    if not result.requested_reads:
        return
    for filename in result.requested_reads[:3]:  # max 3 per turn
        content = self._read_project_file(filename)
        if content:
            self._add_info_msg(f"Reading {filename} for the AI...", C['fg_dim'])
            inject = f"[FILE CONTENT: {filename}]\n{content}\n[END FILE: {filename}]"
            self._conversation.append({"role": "user", "content": inject})
            # Add to working set as AI-referenced
            rel_path = filename  # resolve to relative path
            self._ai_edited_files.add(rel_path)  # ensures priority 1
        else:
            self._conversation.append(
                {"role": "user", "content": f"[File not found: {filename}]"})
    self._conversation.append(
        {"role": "user", "content": "[Continue your previous response.]"})
    self._auto_send()
```

---

## 2. Code Auditing and Refactoring

### Current State
Right-click selected code → AI action with prompt template → AI responds with text + EDIT
blocks. Works only on selected text.

### Remaining

#### 2a. Built-in Audit Actions (Pre-configured AI Tools)
Add to the default AI Tools list in Settings:

| Action | Prompt Template |
|---|---|
| **Audit File** | "Review `{filename}` for bugs, memory leaks, type errors, unused variables, and poor practices. List each issue with line numbers and suggest fixes using <<<EDIT blocks." |
| **Refactor File** | "Refactor `{filename}` to improve readability, reduce duplication, and follow Arduino/C++ best practices. Use <<<EDIT blocks for each change." |
| **Optimize for Teensy** | "Analyze `{filename}` for Teensy-specific optimizations: PROGMEM, F() macro, DMA, interrupt safety, timing. Suggest concrete changes with <<<EDIT blocks." |
| **Explain File** | "Explain the purpose and flow of `{filename}` section by section. Note any confusing areas." |

These work on the **full active file**, not just selected text. `{filename}` resolves to
the current tab's filename.

#### 2b. Whole-File Actions (No Selection Required)
Add entry points for audit actions without needing to select code first:
- **Menu bar**: `AI > Audit Current File`, `AI > Refactor Current File`
- **Keyboard shortcut**: `Ctrl+Shift+R` for "Refactor Current File"
- **Slash commands**: `/audit`, `/refactor` (see Section 5)

When triggered without a selection, `{code}` in the template becomes the full file content
and `{filename}` becomes the active tab name.

---

## 3. Code Insertion and Visual Diffs

### Current State
- EDIT/FILE blocks parsed by `_parse_edits()` and stored as `ProposedEdit` objects
- Apply bar shows "N changes in filename" with Apply All / Dismiss
- Code blocks and edit blocks render with styled HTML in AI responses (post-render)
- No visual diff preview before applying

### Remaining

#### 3a. Visual Diff Widget
Create a `DiffWidget(QFrame)` that renders a single edit as red/green line-by-line diff:

```
┌─ sensors.cpp ──────────────────────────────────────┐
│  15 │   int readSensor() {                          │  (context, dim)
│  16 │ - int val = analogRead(A0);                   │  (red bg)
│  17 │ + int val = analogRead(SENSOR_PIN);           │  (green bg)
│  18 │     return map(val, 0, 1023, 0, 100);         │  (context, dim)
└─────────────────────────────────────────────────────┘
```

Styling:
- Container: `bg: C['bg']`, `border: 1px solid C['border_light']`, `border-radius: 8px`
- Header: `bg: C['bg_hover']`, filename in `FONT_CODE`, bottom border
- Deletions: `background: rgba(244, 71, 71, 0.12)`, `color: C['fg_err_text']`
- Additions: `background: rgba(78, 205, 196, 0.12)`, `color: #7ee0d8`
- Context lines: `color: C['fg_dim']`
- Line numbers: `color: C['fg_muted']`, right-aligned, 40px gutter

Use `difflib.unified_diff()` with 3 lines of context.

#### 3b. Per-Edit Accept/Reject
Replace the simple apply bar with an expanded review panel (QScrollArea) containing:
- Summary header: "3 changes across 2 files [Apply All] [Dismiss All]"
- One DiffWidget per edit, each with [Accept] [Reject] buttons
- Accepted edits show green check and dim out; rejected show red X and dim out

#### 3c. Inline Diff in Chat (Future)
Render DiffWidgets inline within the AI response where EDIT blocks appear. Phase 2.

#### 3d. Undo Integration
Store pre-edit content before applying:
```python
self._pre_edit_snapshots = {}  # filename -> content before edits
```
Show "Undo Last Apply" button for 10 seconds after applying.

---

## 4. GitHub / Git Integration with AI

### Completed
- **4a. Git context in AI messages** — `_build_git_context()` injects branch, last 5
  commits, diff stat, and untracked files into every AI prompt automatically.

### Remaining

#### 4b. AI-Generated Commit Messages
Add button in Git panel commit row:
```
[Commit msg input·····] [✨ AI] [Commit All] [Push] [Pull]
```

The "✨ AI" button:
1. Runs `git diff --cached` (or `git diff` if nothing staged)
2. One-shot Ollama call: "Generate a concise conventional commit message. Return ONLY
   the message."
3. Fills commit message input
4. User reviews and clicks "Commit All"

#### 4c. Merge Conflict Resolution
When merge/pull produces conflicts:
1. GitPanel detects conflict markers in output
2. Opens conflicted files in editor
3. Shows info bar: "Merge conflict in sensors.cpp — [Ask AI to Resolve]"
4. AI receives conflicted file with resolution prompt
5. User reviews via diff widget

#### 4d. Attach Diff Button
Add "Attach Diff" toggle next to "Attach Errors":
```
[Attach Errors] [Attach Diff] [Clear Chat]    (stretch)
```
When checked, next message includes full `git diff` output.

---

## 5. Slash Commands

### Completed
- **5a. Command parser** — `_handle_slash_command()` intercepts `/` input
- **5b. Core commands** — `/clear`, `/model <name>`, `/compact`, `/help`, `/context`
- **5d. /compact** — Full implementation with background CompactWorker thread,
  one-shot Ollama summarization, conversation history replacement
- **Debug commands** — `/debug-ws`, `/debug-use-ws on|off`

### Remaining

#### Additional Commands to Add

| Command | Action | Description |
|---|---|---|
| `/audit` | Trigger audit action | Send full current file with audit prompt |
| `/refactor` | Trigger refactor action | Send full current file with refactor prompt |
| `/diff` | Show git diff | Display `git diff` output as info message in chat |
| `/commit <msg>` | Quick commit | Run `git add -A && git commit -m "msg"` from chat |

#### 5c. Autocomplete Popup
When user types `/`, show a popup above the input with matching commands:
- `bg: C['bg_input']`, `border: 1px solid C['border_light']`, `border-radius: 6px`
- Items: command in `C['teal']`, description in `C['fg_dim']`
- Max 6 visible items, scrollable
- Filter as user types

---

## 6. Code Block Rendering in AI Responses

### Completed
- **Post-render** via `_render_formatted_response()` — called in `_on_complete()`
- Detects fenced code blocks (```) and <<<EDIT/<<<FILE blocks
- Code blocks: `C['bg_input']` background, `C['border_light']` border, Menlo 13px
- Edit blocks: teal left border accent, <<<OLD/>>>NEW section headers
- Language labels shown above code blocks

### Remaining
- **Copy button** on code blocks (small button in top-right corner)
- **Live render** during streaming (Phase 2 — state machine in `_on_token()`)

---

## 7. AI-Triggered Compile (Closing the Loop)

### Current State
Compile→error→AI fix loop is manual (7 steps). `AIWorkResult` already has a
`request_compile` field (currently unused).

### Target State
AI can emit `<<<COMPILE` to trigger a build and receive results automatically.

### Implementation
```python
def _handle_compile_request(self, result):
    """Process <<<COMPILE from AI response."""
    if not result.request_compile:
        return
    if self._auto_compile_count >= 2:
        self._add_info_msg("Max auto-compile retries reached.", C['fg_warn'])
        return
    self._auto_compile_count += 1
    self._add_info_msg(
        f"Compiling at AI's request (attempt {self._auto_compile_count}/2)...",
        C['fg_dim'])
    self.compile_requested.emit()
    QTimer.singleShot(500, self._send_compile_results)
```

Reset `_auto_compile_count` on each user message.

---

## 8. Conversation Persistence (Session Save/Load)

Save `self._conversation` to `{project_path}/.aide_chat_history.json` on app close,
project switch, and `/clear`. Load on project open. Add `/sessions` and `/load <n>`.

---

## 9. Project-Level AI Configuration

Support `.aide_prompt` file in project root, prepended to system prompt on project open.

```python
def _build_system_prompt(self):
    base = SYSTEM_PROMPT
    custom_file = os.path.join(self._project_path, ".aide_prompt")
    if os.path.exists(custom_file):
        with open(custom_file) as f:
            return f.read().strip() + "\n\n" + base
    return base
```

---

## 10. Structured Compile Diagnostics (Next Planned)

Parse compiler output into structured objects:
```python
@dataclass
class CompileDiagnostic:
    file: str
    line: int
    column: int
    severity: str       # "error", "warning", "note"
    message: str
```

Feed these back into the AI for an automated edit→compile→diagnose→fix→retry loop.
This integrates with the `<<<COMPILE` command (Section 7) and the WorkingSet system
(diagnostics reference specific files, which should be promoted to priority 1).

---

## Implementation Priority (Updated)

### Phase 1 — DONE
1. ~~Slash commands~~ (`/clear`, `/model`, `/compact`, `/help`, `/context`)
2. ~~Project tree context~~ (`_build_directory_tree`)
3. ~~Smart context budgeting~~ (WorkingSet, 12K budget, priority 0-3)
4. ~~Git context in AI messages~~ (`_build_git_context`)
5. ~~Code block rendering~~ (`_render_formatted_response`)
6. ~~AIWorkResult typed container~~ (`ProposedEdit`, `AIWorkResult`)

### Phase 2 — Next Up (Visual Diffs & Review)
7. **Visual diff widget** — Section 3a
8. **Per-edit accept/reject** — Section 3b
9. **Built-in audit actions** + `/audit`, `/refactor` — Sections 2a, 2b, 5
10. **Project-level .aide_prompt** — Section 9

### Phase 3 — Agentic Features
11. **Structured compile diagnostics** — Section 10
12. **AI-requested file reading** (`<<<READ`) — Section 1c
13. **AI-triggered compile** (`<<<COMPILE`) — Section 7
14. **AI commit messages** — Section 4b

### Phase 4 — Polish
15. **Slash command autocomplete popup** — Section 5c
16. **Conversation persistence** — Section 8
17. **Attach Diff button** — Section 4d
18. **Merge conflict resolution** — Section 4c
19. **Inline diff in chat** — Section 3c
20. **Undo Last Apply** — Section 3d
21. **Code block copy button** — Section 6

---

## Signal Flow: Agentic Edit Cycle

```
User: "Fix the bug in sensors.cpp"
  → ChatPanel._send_prompt() injects:
      - WorkingSet context (active file + budget-constrained others)
      - Project tree (always)
      - Git status (branch, diff stat, recent commits)
      - Compiler errors (if attached)
  → AI responds with analysis + <<<EDIT blocks
  → _on_complete() → _render_formatted_response() (styled code/edit blocks)
  → _parse_edits() → populates AIWorkResult.proposed_edits
  → [FUTURE] DiffWidgets render in review panel (3a)
  → User clicks Accept on each / Apply All (3b)
  → Edits applied to editor → _track_ai_edited_file() promotes to priority 1
  → [FUTURE] AI emits <<<COMPILE → app compiles, sends results back (7)
  → AI sees "BUILD SUCCESSFUL" → done
     OR AI sees new errors → suggests fixes (max 2 retries)
```

## Signal Flow: AI-Assisted Commit (Future)

```
User clicks "✨ AI" in Git panel commit row
  → GitPanel runs `git diff`
  → One-shot Ollama call with diff + commit message prompt
  → Response fills commit message input
  → User reviews, edits if needed, clicks "Commit All"
```
