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
│  padding: 20px horizontal, 16px vertical                      │
│  spacing: 20px between message groups                         │
│                                                               │
│  Messages flow here...                                        │
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
      QHBoxLayout
        stretch (pushes bubble right)
        QFrame bubble
          max-width: 500px
          style: background: C['bg_input'] (#2a2a2a), border-radius: 14px
          QVBoxLayout (margins: 12, 10, 12, 10)
            QLabel text
              word-wrap: true
              format: PlainText
              style: color: #e0e0e0, FONT_CHAT, background: transparent, border: none
```

**Key details:**
- The bubble should NOT stretch to full width. It hugs the text content, up to 500px max.
- 14px border-radius gives the pill/bubble shape.
- Background is `C['bg_input']` (#2a2a2a) — slightly lighter than the chat bg (#1a1a1a).
- No border on the bubble. The contrast between #2a2a2a and #1a1a1a is enough.

### AI Message (left-aligned, NO bubble)

The AI response should look like Claude Code's responses — clean text flowing directly on the dark background with no container.

```
Layout:
  QWidget container
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
- Speaker name is the same 14px size as the message text, just bold and teal.
- The streaming QTextEdit auto-resizes its height as tokens arrive.
- Scrollbars must be off on the QTextEdit — the parent QScrollArea handles scrolling.

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

### Info Line (e.g. "Found 2 edits")

```
QLabel text
  word-wrap: true
  style: color: C['fg_ok'] or C['fg_warn'], FONT_CHAT
  background: transparent, border: none
  padding-left: 2px
```

---

## Scroll Area Setup

```python
scroll_area = QScrollArea()
scroll_area.setWidgetResizable(True)
scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
scroll_area.setStyleSheet(f"""
    QScrollArea {{
        background-color: {C['bg_dark']};
        border: none;
    }}
    QScrollBar:vertical {{
        background: {C['bg_dark']};
        width: 8px;
    }}
    QScrollBar::handle:vertical {{
        background: {C['border_light']};
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
""")

_chat_container = QWidget()
_chat_container.setStyleSheet(f"background:{C['bg_dark']};")
chat_layout = QVBoxLayout(_chat_container)
chat_layout.setContentsMargins(20, 16, 20, 16)
chat_layout.setSpacing(20)
chat_layout.addStretch()  # pushes messages to top
scroll_area.setWidget(_chat_container)
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

# Send button
send_btn.setStyleSheet(
    f"background:{C['teal']};color:white;border:none;"
    f"border-radius:10px;font-weight:600;padding:8px 16px;{FONT_CHAT}")

# Stop button
stop_btn.setStyleSheet(
    f"background:{C['bg_input']};color:{C['fg']};border:1px solid {C['border_light']};"
    f"border-radius:10px;padding:8px 14px;font-size:12px;")
```

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

1. **User bubble stretches full width** — It must NOT. Use QHBoxLayout with stretch on the left and the bubble QFrame on the right. Set `bubble.setMaximumWidth(500)`.
2. **AI text has a visible container** — The QTextEdit must be completely invisible. `background: transparent; border: none; padding: 0; margin: 0;`
3. **Speaker names are a different size than message text** — Both must be 14px (FONT_CHAT). Speaker names are just bold.
4. **Scrollbar on the AI QTextEdit** — Must be off. Only the parent QScrollArea scrolls.
5. **AI QTextEdit doesn't resize** — Must connect `document().contentsChanged` to a handler that sets `setFixedHeight(max(24, int(doc.size().height()) + 4))`.
6. **Hardcoded colors in chat code** — Every color must use `C['key']`.
