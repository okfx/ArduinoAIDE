# Chat View — Detailed Specification

The chat view should feel like Claude Code's conversation interface adapted for an embedded IDE.
This is the most important view aesthetically. Get this right.

---

## Overall Structure (top to bottom)

```
┌─ Context Header ──────────────────────────────────────────────┐
│ height: 48px, bg: C['bg'], border-bottom: 1px solid border   │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  QScrollArea (flex: 1)                                        │
│  bg: C['bg_dark'] (#1a1a1a)                                   │
│                                                               │
│  ┌─ Outer container (fills scroll area) ───────────────────┐  │
│  │           ┌─ Inner column (max 800px) ──────┐           │  │
│  │  stretch  │ padding: 20px H, 16px V         │  stretch  │  │
│  │           │ spacing: 20px between messages   │           │  │
│  │           │ Messages flow here...            │           │  │
│  │           └─────────────────────────────────┘           │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│ Apply Bar (hidden unless edits found)                         │
│ height: ~44px, bg: C['bg'], border-top: 1px solid border      │
├───────────────────────────────────────────────────────────────┤
│ Input Area                                                    │
│ height: ~56px, bg: C['bg'], border-top: 1px solid border      │
├───────────────────────────────────────────────────────────────┤
│ Bottom buttons row                                            │
│ height: ~32px, bg: C['bg_dark']                               │
└───────────────────────────────────────────────────────────────┘
```

---

## Centered Column Layout

The chat messages are displayed in a centered column with a max-width of 800px. On wide windows, equal space appears on both sides; on narrow windows, the column fills the available width.

```python
# Outer container fills the scroll area width
outer_container = QWidget()
outer_layout = QHBoxLayout(outer_container)
outer_layout.addStretch()

# Inner column is centered, max-width 800px
chat_container = QWidget()
chat_container.setMaximumWidth(800)
chat_container.setSizePolicy(Expanding, Preferred)
chat_layout = QVBoxLayout(chat_container)
chat_layout.setContentsMargins(20, 16, 20, 16)
chat_layout.setSpacing(20)
chat_layout.addStretch()

outer_layout.addWidget(chat_container)
outer_layout.addStretch()
scroll_area.setWidget(outer_container)
```

---

## Context Header

```python
# Container
ctx_panel.setStyleSheet(f"background:{C['bg']};border-bottom:1px solid {C['border']};")
ctx_layout.setContentsMargins(16, 8, 16, 8)

# Project label
f"color:{C['fg_head']};{FONT_BODY}font-weight:bold;"

# Path label
f"color:{C['fg_dim']};{FONT_SMALL}"

# "Show Files" toggle
f"background:transparent;color:{C['teal']};border:none;{FONT_SMALL}text-decoration:underline;"
```

---

## Message Types

### User Message (right-aligned bubble)

This is the most distinctive visual element. It should look like an iMessage or Claude Code user bubble.

```
Layout:
  QWidget container
    QVBoxLayout (margins: 0, spacing: 4)
      QLabel "You"
        alignment: right
        style: color: C['fg_link'] (#7aafff), FONT_CHAT_BOLD
        padding-right: 8px
      QHBoxLayout (margins: 0, 0, 12, 0)  ← 12px right margin for breathing room
        stretch (pushes bubble right)
        QFrame bubble
          max-width: 600px
          style: background: C['bg_input'] (#2a2a2a), border-radius: 14px
          QVBoxLayout (margins: 16, 12, 16, 12)
            QLabel text
              word-wrap: true
              format: PlainText
              style: color: #e0e0e0, FONT_CHAT, background: transparent, border: none
```

**Key details:**
- The bubble should NOT stretch to full width. It hugs the text content, up to 600px max.
- 14px border-radius gives the pill/bubble shape.
- 12px right margin inside the row provides breathing room from the column edge.
- Background is `C['bg_input']` (#2a2a2a) — slightly lighter than the chat bg (#1a1a1a).
- No border on the bubble. The contrast between #2a2a2a and #1a1a1a is enough.
- Slash commands are also displayed as user message bubbles before being executed.

### AI Message (left-aligned, NO bubble)

The AI response should look like Claude Code's responses — clean text flowing directly on the dark background with no container. The wrapper is constrained to 700px max width to keep text at a comfortable reading width.

```
Layout:
  QWidget container (max-width: 700px)
    QVBoxLayout (margins: 0, spacing: 4)
      QLabel model_name
        style: color: C['teal'] (#00979d), FONT_CHAT_BOLD
        padding-left: 2px
      QTextEdit stream
        read-only: true
        scrollbars: off (both)
        style:
          background: transparent
          border: none
          color: C['fg'] (#d4d4d4)
          FONT_CHAT (14px, system font)
          padding: 0
          margin: 0
          selection-background-color: C['teal']
        minimum-height: 24px
        auto-resize: connect document().contentsChanged to resize handler
```

**Key details:**
- NO bubble, NO background color, NO border. Just text on the dark bg.
- The QTextEdit must have `background: transparent` — it should be invisible as a container.
- Max width 700px on the wrapper keeps text readable on wide windows.
- Speaker name is the same 14px size as the message text, just bold and teal.
- The streaming QTextEdit auto-resizes its height as tokens arrive.
- Scrollbars must be off on the QTextEdit — the parent QScrollArea handles scrolling.

### Stats Row (below AI message during streaming)

During AI streaming, a stats row appears below the AI message showing a spinning gear and live token counter.

```
Layout:
  QWidget (transparent)
    QHBoxLayout (margins: 2, 4, 0, 4, spacing: 6)
      SpinnerWidget (24x24 animated teal gear)
      QLabel "142 tokens · 3.2s"
        style: color: C['fg_dim'], FONT_SMALL, transparent
      stretch

On completion, spinner stops/hides and label updates to final stats:
  "247 tokens · 5.1s · 48.4 tok/s"
  style changes to: color: C['fg_muted']
```

### Error Message (left-aligned)

```
Layout:
  QWidget container
    QVBoxLayout (margins: 0, spacing: 4)
      QLabel "Error"
        style: color: C['fg_err'] (#f44747), FONT_CHAT_BOLD
        padding-left: 2px
      QLabel text
        word-wrap: true
        format: PlainText
        style: color: C['fg_err_text'] (#f08080), FONT_CHAT
        background: transparent, border: none
        padding-left: 2px
```

### Code Blocks in AI Responses (post-rendered)

After streaming completes, `_render_formatted_response()` re-renders the AI QTextEdit HTML. Fenced code blocks and edit blocks each have distinct styling.

**Fenced code blocks** (` ``` `)  — terminal-style:
```
Container: <div> inside QTextEdit HTML
  background: C['bg_input']
  border: 1px solid C['border_light']
  padding: 10px
  margin: 6px 0
  font: Menlo, Monaco, Courier New, monospace, 13px
Language label (if present):
  color: C['fg_dim'], font-size: 11px, margin-bottom: 4px
Content: <pre> with white-space: pre-wrap
```

**Edit blocks** (`<<<EDIT` / `<<<FILE`) — teal accent:
```
Container: <div> inside QTextEdit HTML
  background: C['bg_input']
  border: 1px solid C['border_light']
  border-left: 3px solid C['teal']   ← distinguishes from regular code blocks
  padding: 10px
  margin: 6px 0
  font: Menlo, Monaco, Courier New, monospace, 13px
Header: "EDIT: filename" or "FILE: filename"
  color: C['teal'], font-size: 12px, font-weight: bold, margin-bottom: 4px
Section markers (<<<OLD / >>>NEW):
  ── OLD ── in C['fg_dim']
  ── NEW ── in C['teal']
Content: <pre> with white-space: pre-wrap
```

### Info Line (e.g. "Found 2 edits")

```
QLabel text
  word-wrap: true
  style: color: C['fg_ok'] or C['fg_warn'], FONT_CHAT
  background: transparent, border: none
  padding-left: 2px
```

---

## Input Area

```python
# Container
inp.setStyleSheet(f"background:{C['bg']};border-top:1px solid {C['border']};")
il.setContentsMargins(16, 10, 16, 10)
il.setSpacing(8)

# Input field
input_field.setStyleSheet(f"""
    QLineEdit {{
        background-color: {C['bg_input']};
        color: {C['fg']};
        border: 1px solid {C['border_light']};
        border-radius: 10px;
        padding: 8px 14px;
        {FONT_CHAT}
    }}
    QLineEdit:focus {{
        border-color: {C['teal']};
    }}
""")

# Send button — min-width 72px, padding-based sizing
send_btn.setStyleSheet(
    f"background:{C['teal']};color:white;border:none;"
    f"border-radius:10px;font-weight:600;padding:8px 20px;{FONT_CHAT}")

# Stop button — min-width 72px, padding-based sizing
stop_btn.setStyleSheet(
    f"background:{C['bg_input']};color:{C['fg']};border:1px solid {C['border_light']};"
    f"border-radius:10px;padding:8px 20px;{FONT_CHAT}")
```

---

## Slash Command Autocomplete Popup

When the user types `/` in the input field, a popup appears above the input showing matching commands.

```python
_slash_popup = QListWidget()
_slash_popup.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
_slash_popup.setStyleSheet(f"""
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
```

**Behavior:**
- Shows on `/` keystroke, filters as user types (e.g. `/mo` shows only `/model`)
- Max height: 240px (~6 items visible)
- Max width: min(input_field.width(), 400px)
- Positioned above the input field with 4px gap
- Keyboard nav: Up/Down to navigate, Tab/Enter to select, Escape to dismiss
- Click on item fills input with the command
- Selecting a command fills the input field text; user presses Enter to execute

---

## Apply Bar

```python
apply_bar.setStyleSheet(f"background:{C['bg']};border-top:1px solid {C['border']};")
ab_layout.setContentsMargins(16, 8, 16, 8)

# Label
apply_label.setStyleSheet(f"color:{C['fg']};{FONT_BODY}")

# Apply button — BTN_PRIMARY style but with 6px radius
f"background:{C['teal']};color:white;border:none;border-radius:6px;font-weight:bold;padding:6px 16px;{FONT_BODY}"

# Dismiss button — BTN_SECONDARY
f"background:{C['bg_input']};color:{C['fg']};border:1px solid {C['border_light']};border-radius:6px;padding:6px 12px;{FONT_BODY}"
```

---

## Auto-Scroll

```python
def _scroll_to_bottom(self):
    QTimer.singleShot(10, lambda: self.scroll_area.verticalScrollBar().setValue(
        self.scroll_area.verticalScrollBar().maximum()))
```

Call after: adding any message widget, every token during streaming.

---

## Common Mistakes to Avoid

1. **User bubble stretches full width** — It must NOT. Use QHBoxLayout with stretch on the left and the bubble QFrame on the right. Set `bubble.setMaximumWidth(600)`.
2. **AI text has a visible container** — The QTextEdit must be completely invisible. `background: transparent; border: none; padding: 0; margin: 0;`
3. **Speaker names are a different size than message text** — Both must be 14px (FONT_CHAT). Speaker names are just bold.
4. **Scrollbar on the AI QTextEdit** — Must be off. Only the parent QScrollArea scrolls.
5. **AI QTextEdit doesn't resize** — Must connect `document().contentsChanged` to a handler that sets `setFixedHeight(max(24, int(doc.size().height()) + 4))`.
6. **Hardcoded colors in chat code** — Every color must use `C['key']`.
7. **Messages not centered** — The chat column must be max-width 800px, centered via outer HBoxLayout with stretches on both sides.
