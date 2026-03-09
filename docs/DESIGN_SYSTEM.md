# ArduinoAIDE Design System

**THIS IS THE SINGLE SOURCE OF TRUTH FOR ALL VISUAL STYLING.**

When writing or modifying any UI code in `ArduinoAIDE.py`, you MUST:
1. Use ONLY the colors defined in the `C = {}` dict — never invent hex values
2. Use ONLY the font constants (`FONT_TITLE`, `FONT_BODY`, etc.) — never inline font-size
3. Use ONLY the spacing scale below — never invent padding/margin values
4. Use ONLY the shared button styles (`BTN_PRIMARY`, `BTN_SECONDARY`, etc.) — never inline button styles
5. Use ONLY the border-radius values below — never invent radius values

If a value you need doesn't exist, ADD it to the constants at the top of the file first, then use the constant. Never hardcode a one-off value in a widget's stylesheet.

---

## Color Palette (the `C = {}` dict)

These are the ONLY colors allowed in the entire application. The dict should contain exactly these entries:

```python
C = {
    # Backgrounds — from darkest to lightest
    "bg_dark":      "#1a1a1a",   # Darkest: chat area, file tree, bottom panel, line numbers
    "bg":           "#1e1e1e",   # Standard: editor, toolbar, panel headers, apply bar, input areas
    "bg_sidebar":   "#181818",   # Sidebar strip only
    "bg_input":     "#2a2a2a",   # Input fields, combo boxes, user chat bubbles, code blocks
    "bg_hover":     "#252525",   # Hover state for items, also active sidebar button bg

    # Borders
    "border":       "#2a2a2a",   # Primary border — dividers, panel edges, separators
    "border_light": "#333333",   # Secondary border — toolbar button outlines, subtle dividers

    # Text
    "fg":           "#d4d4d4",   # Primary text — body copy, labels, code
    "fg_dim":       "#888888",   # Secondary text — placeholders, descriptions, hints
    "fg_head":      "#e0e0e0",   # Emphasis text — active tabs, headers, bright labels
    "fg_muted":     "#555555",   # Muted — line numbers, disabled text

    # Semantic colors
    "teal":         "#00979d",   # Primary accent — active states, primary buttons, AI name, links
    "teal_hover":   "#00b5bc",   # Hover state for teal elements
    "teal_light":   "#4ecdc4",   # Success messages, lighter teal accents
    "danger":       "#c62828",   # Danger buttons (delete, destructive actions)
    "fg_err":       "#f44747",   # Error labels (speaker name "Error")
    "fg_err_text":  "#f08080",   # Error body text (softer red)
    "fg_warn":      "#e8b54d",   # Warnings, folder icons
    "fg_ok":        "#4ec9b0",   # Success/applied messages
    "fg_link":      "#7aafff",   # User speaker name "You", clickable links

    # Syntax highlighting (editor only)
    "syn_kw":       "#569cd6",   # Keywords (if, else, for, return)
    "syn_cmt":      "#6a9955",   # Comments
    "syn_str":      "#ce9178",   # Strings
    "syn_num":      "#b5cea8",   # Numbers
    "syn_pp":       "#c586c0",   # Preprocessor, control flow
    "syn_type":     "#4ec9b0",   # Types (int, void, uint8_t)
    "syn_fn":       "#dcdcaa",   # Function names
    # Operators (+, -, =, etc.) and identifiers use C['fg'] (#d4d4d4)
    # — they must be explicitly set in the lexer to avoid black defaults
}
```

### Color Rules

- **NO** inventing hex values. If you need a color, it must be in `C`.
- **NO** hardcoding hex strings in stylesheets. Always use `C['key']`.
- **NO** using `C['teal']` for text that should be `C['fg_ok']` or vice versa. Each token has a specific purpose.
- Every `background:` must use a `C['bg_*']` value.
- Every `color:` for text must use a `C['fg_*']` or `C['teal*']` value.
- Every `border:` must use `C['border']` or `C['border_light']`.

---

## Typography Scale

These are the ONLY font declarations allowed:

```python
FONT_TITLE    = "font-size: 14px; font-weight: bold;"
FONT_SECTION  = "font-size: 13px; font-weight: bold;"
FONT_BODY     = "font-size: 13px;"
FONT_SMALL    = "font-size: 11px;"
FONT_CODE     = "font-family: 'SF Mono', Menlo, Monaco, 'Courier New', monospace; font-size: 13px;"
FONT_CHAT     = "font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 14px;"
FONT_CHAT_BOLD = "font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 14px; font-weight: bold;"
```

### Where each font is used

| Constant | Used for |
|---|---|
| `FONT_TITLE` | Panel headers ("Installed Models", project name), toolbar labels |
| `FONT_SECTION` | Section headers within panels ("Branches", "Tags"), group box titles |
| `FONT_BODY` | Standard body text, tree items, list items, combo items, status bar |
| `FONT_SMALL` | Hints, descriptions, context info, model descriptions, path labels |
| `FONT_CODE` | Code editor (QScintilla handles this), compiler output, serial monitor, diff blocks |
| `FONT_CHAT` | Chat message content (user bubbles, AI responses), chat input field |
| `FONT_CHAT_BOLD` | Chat speaker names ("You", model name, "Error") |

### Typography Rules

- **NO** inline `font-size` in stylesheets. Use the constant.
- Chat speaker names and chat message text are BOTH 14px. Speaker names are bold.
- Everything outside chat is 13px body / 11px small. No other sizes.
- The ONLY place 14px appears is in chat. Everything else is 13px or 11px.

---

## Spacing Scale

All padding and margin values must come from this scale:

```
2px  — micro gap (between icon and text within a button)
4px  — tight (spacing between small elements, e.g. status bar items)
6px  — compact (sidebar button internal padding, compact layouts)
8px  — standard (default gap between elements, HBox spacing)
10px — comfortable (bubble internal padding top/bottom)
12px — spacious (panel content margins, chat horizontal margin)
14px — large (bubble internal horizontal padding)
16px — extra (chat message spacing, main content margins)
20px — section (chat area horizontal padding)
```

### Spacing Rules

- `QVBoxLayout.setSpacing()` — use 4, 8, or 16
- `QHBoxLayout.setSpacing()` — use 4 or 8
- `setContentsMargins()` — use combinations from the scale: `(12, 8, 12, 8)` or `(16, 12, 16, 12)` etc.
- **NO** margins/padding values outside this scale (no 3px, 5px, 7px, 9px, 11px, 13px, 15px, etc.)
- Exception: `padding: 0px` is always allowed

---

## Border Radius Scale

```
0px  — sharp (no rounding)
4px  — subtle (toolbar buttons, secondary buttons, combo boxes)
6px  — standard (sidebar buttons, group boxes)
8px  — soft (bottom panel tabs, diff code blocks)
10px — round (chat input, send/stop buttons)
14px — pill (chat user bubbles)
```

### Radius Rules

- **NO** inventing radius values. Pick from the scale.
- User chat bubbles: always 14px
- Toolbar/action buttons: always 4px
- Chat input + send/stop: always 10px
- Sidebar buttons: always 6px

---

## Button Styles

These are the ONLY button styles. Use them by name, never create one-off button styles.

```python
BTN_PRIMARY = (
    f"background:{C['teal']};color:white;border:none;"
    f"border-radius:4px;padding:6px 14px;{FONT_BODY}font-weight:bold;")

BTN_SECONDARY = (
    f"background:{C['bg_input']};color:{C['fg']};border:1px solid {C['border_light']};"
    f"border-radius:4px;padding:6px 14px;{FONT_BODY}")

BTN_DANGER = (
    f"background:{C['danger']};color:white;border:none;"
    f"border-radius:4px;padding:6px 14px;{FONT_BODY}font-weight:bold;")

BTN_TOOLBAR = (
    f"background:{C['teal']};color:white;border:none;"
    f"border-radius:4px;padding:6px 14px;{FONT_BODY}font-weight:bold;")

BTN_GHOST = (
    f"background:transparent;color:{C['teal']};border:none;"
    f"{FONT_SMALL}text-decoration:underline;")
```

### Button Rules

- **Primary actions** (Verify, Upload, Create Model, Apply Changes, Send): `BTN_PRIMARY`
- **Secondary actions** (Refresh, Dismiss, Stop, Preview): `BTN_SECONDARY`
- **Destructive actions** (Delete): `BTN_DANGER`
- **Toolbar compile/upload**: `BTN_TOOLBAR`
- **Text-only links** (Show Files, toggle): `BTN_GHOST`
- **NO** inventing button styles. If a new type is needed, add it to the constants first.

---

## Component Specifications

### Sidebar Button
```
Size: 40×40px
Background: transparent (default), #252525 (hover/active)
Icon: QPainter, 20×20px viewport, color #666 (default) → #aaa (hover) → #fff (active)
Active indicator: 3px wide bar, left edge, teal, inset 8px top/bottom, 2px border-radius
Border-radius: 6px
```

### Tab Bar Tab
```
Height: 36px
Background: transparent (default), #1e1e1e (active)
Text: 13px, #888 (default) → #e0e0e0 (active)
Active indicator: 2px teal bottom border
Close button: ×, 16×16px, #555 → #ccc on hover, 3px radius hover bg
```

### Chat User Bubble
```
Alignment: right (QHBoxLayout with stretch on left)
Max width: 500px
Background: #2a2a2a (C['bg_input'])
Border-radius: 14px
Padding: 10px 16px
Text: FONT_CHAT, color #e0e0e0
Speaker "You": FONT_CHAT_BOLD, color C['fg_link'], right-aligned, 6px right padding
```

### Chat AI Message
```
Alignment: left
Max width: 700px (wrapper QWidget)
Background: transparent (no bubble)
Text: FONT_CHAT, color C['fg'], in a QTextEdit (for streaming)
QTextEdit: transparent bg, no border, no scrollbars, auto-resize
Speaker: FONT_CHAT_BOLD, color C['teal'], left-aligned, 2px left padding
```

### Chat Code Block (in AI responses, post-rendered HTML)
```
Background: C['bg_input']
Border: 1px solid C['border_light']
Font: Menlo, Monaco, Courier New, monospace — 13px
Padding: 10px, margin: 6px 0
Language label: C['fg_dim'], 11px
```

### Chat Edit Block (<<<EDIT / <<<FILE in AI responses)
```
Background: C['bg_input']
Border: 1px solid C['border_light'], border-left: 3px solid C['teal']
Font: Menlo, Monaco, Courier New, monospace — 13px
Padding: 10px, margin: 6px 0
Header ("EDIT: filename"): C['teal'], 12px, bold
OLD marker: C['fg_dim']
NEW marker: C['teal']
```

### Chat Input
```
Background: C['bg_input']
Border: 1px solid #3a3a3a → C['teal'] on focus
Border-radius: 10px
Padding: 9px 14px
Font: FONT_CHAT
```

### Combo Box (All — Flat Style)

macOS will render native "shiny" Aqua combo boxes unless explicitly overridden. The global stylesheet flattens them by styling `QComboBox::drop-down` and `QComboBox::down-arrow`.

```
Background: C['bg_input']
Border: 1px solid C['border_light'] → C['teal'] on hover/focus
Border-radius: 4px
Padding: 4px 24px 4px 8px  (right padding for arrow)
Font: FONT_BODY
Drop-down arrow: CSS triangle (border-based), C['fg_dim'] → C['fg'] on hover
Dropdown list: C['bg_input'] bg, C['teal'] selection, C['bg_hover'] hover
Min-width: 100px (board/port), 140px (AI model)
```

**CRITICAL**: Never remove the `QComboBox::drop-down` and `QComboBox::down-arrow` rules from the global stylesheet. Without them, macOS reverts to the glossy native chrome.

### Status Bar
```
Height: 26px
Background: C['bg_sidebar']
Top border: 1px solid C['border']
Font: FONT_SMALL, color C['fg_dim']
Padding: 0 12px
Layout: left items + flex spacer + right items
```

### Bottom Panel (Output/Serial)
```
Default height: ~150px (resizable via QSplitter)
Background: C['bg_dark']
Tab bar: 30px height, tabs with 2px bottom border (teal when active)
Content: FONT_CODE, color C['teal_light']
```

---

## View Layout Blueprints

### Code View
```
┌─ Tab Bar (36px) ─────────────────────────────────────────────┐
│ [tab1] [tab2] [tab3·active] [tab4]                          │
├──────────────────────────────────────────────────────────────┤
│ LineNums │  Code Content                            │ flex:1 │
│  (bg_dark│  (bg: #1e1e1e, FONT_CODE)               │        │
│  #555)   │                                          │        │
├──────────┴──────────────────────────────────────────┤        │
│ ── QSplitter handle ──                               │        │
├──────────────────────────────────────────────────────┤        │
│ [Output·active] [Serial Monitor]    ← 30px tab bar  │ ~150px │
│ Compiler output text (FONT_CODE, teal_light)         │        │
└──────────────────────────────────────────────────────┘        │
```

### Chat View
```
┌─ Context Header ─────────────────────────────────────────────┐
│ Project: Name — N files          [Show Files]  ← BTN_GHOST  │
│ /path/to/project                 (FONT_SMALL, fg_dim)       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ← QScrollArea, bg_dark ─────────────────────────────────   │
│                                                              │
│                                          You (fg_link,bold) │
│                              ╭────────────────────╮         │
│                              │ user message       │ ← max   │
│                              ╰────────────────────╯   500px │
│                                                              │
│  model-name (teal, bold)                                     │
│  AI response text flows here with no bubble,                 │
│  just plain text on bg_dark...                               │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ Apply bar: "N changes in file" [Apply All] [Dismiss]         │
├──────────────────────────────────────────────────────────────┤
│ [input field ····················] [Send] [Stop]             │
├──────────────────────────────────────────────────────────────┤
│ [Attach Errors] [Clear Chat]                                 │
└──────────────────────────────────────────────────────────────┘
```

### Files View
```
┌─ Header ─────────────────────────────────────────────────────┐
│ ProjectName (FONT_TITLE)              [Open Folder...] btn   │
│ /path/to/project (FONT_SMALL, fg_dim)                        │
├──────────────────────────────────────────────────────────────┤
│ 📁 src/                                          ← bg_dark  │
│   📄 main.ino                                    FONT_BODY  │
│   📄 audio.h                                     hover:     │
│   📄 display.h                                   bg_hover   │
│ 📄 README.md                                                │
├──────────────────────────────────────────────────────────────┤
│ [+ New File] [+ New Folder]              [Open Folder...]    │
└──────────────────────────────────────────────────────────────┘
```

---

## Panel Headers (`_make_panel_header`)

Every major view (Chat, Files, Git, Settings) starts with a standardized panel header. Use `_make_panel_header()` — never build ad-hoc headers.

```python
# Returns (widget, title_label, header_layout)
# Callers add buttons to header_layout (they appear right-aligned)

header.setStyleSheet(PANEL_HEADER_STYLE)   # bg, border-bottom, fixed height
header.setFixedHeight(40)
layout.setContentsMargins(10, 0, 10, 0)
layout.setSpacing(8)
title.setStyleSheet(f"color: {C['fg_head']}; {FONT_TITLE}")
```

### Header Button Alignment
- Title label on the **left**
- `addStretch()` in the middle
- Action buttons on the **right**
- Header buttons use `BTN_PRIMARY` for the main action (e.g. "Refresh") and `BTN_SECONDARY` for secondary actions (e.g. "Init Repo")
- Ghost-style links (e.g. "Show Files") use `BTN_GHOST`

---

## Action Bars (Bottom Bars)

Action bars at the bottom of panels follow a consistent pattern:

```python
bar = QWidget()
bar.setStyleSheet(f"background: {C['bg']}; border-top: 1px solid {C['border']};")
bl = QHBoxLayout(bar)
bl.setContentsMargins(16, 6, 16, 6)
bl.setSpacing(8)
```

### Button Alignment in Action Bars
- **Left-aligned secondary actions**: "+ New File", "+ New Folder" — use `BTN_SECONDARY`
- `addStretch()` in the middle
- **Right-aligned primary action**: "New Sketch", "Apply All" — use `BTN_PRIMARY`
- Ghost actions (non-critical toggles): use `BTN_GHOST`

**Pattern:**
```
[Secondary] [Secondary]              [Primary]
```

### Bottom Button Rows (e.g. chat bottom)
- Background: `C['bg_dark']`
- Margins: `(16, 4, 16, 4)`
- Ghost-style buttons (Attach Errors, Clear Chat): `BTN_GHOST`

---

## QGroupBox Styling

QGroupBox is used in Settings panels (Model Details, Create Model, Pull Model, Edit Action).

```python
QGroupBox {
    background: transparent;
    border: 1px solid C['border_light'];
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 12px;
    font-weight: bold;
    color: C['fg_head'];
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: C['fg_head'];
}
```

### Inside QGroupBox
- Content margins: `(10, 10, 10, 10)`
- Spacing: `6px` or `8px`
- Labels: `FONT_BODY`, color `C['fg']`
- Hint text: `FONT_SMALL`, color `C['fg_dim']`

---

## Section Headers

Used inside panels to label subsections (e.g. "Branches", "Tags" in Git panel):

```python
header = QLabel("Section Name")
header.setStyleSheet(f"color: {C['teal']}; {FONT_SECTION}")
```

- Color: always `C['teal']`
- Font: `FONT_SECTION` (13px bold)
- No background, no border

---

## QTreeView / QListWidget Styling

Used in: Git branches/tags, model list, file browser, AI actions list.

```python
tree.setStyleSheet(f"""
    QTreeView {{
        background: {C['bg']};
        border: 1px solid {C['border']};
        border-radius: 4px;
        {FONT_BODY}
    }}
    QTreeView::item {{
        padding: 4px 6px;
    }}
    QTreeView::item:selected {{
        background: {C['teal']};
        color: white;
    }}
    QTreeView::item:hover:!selected {{
        background: {C['bg_hover']};
    }}
""")
```

- Border: `1px solid C['border']`
- Radius: `4px`
- Selection: teal bg, white text
- Hover: `C['bg_hover']`

---

## Button Group Layouts

When multiple buttons appear in a row (e.g. Git branch buttons, AI Tools button bar):

```python
btns = QHBoxLayout()
btns.setSpacing(4)   # tight spacing between related buttons

# Pattern: Primary first, then secondary, danger last
primary_btn.setStyleSheet(BTN_PRIMARY)
btns.addWidget(primary_btn)
secondary_btn.setStyleSheet(BTN_SECONDARY)
btns.addWidget(secondary_btn)
danger_btn.setStyleSheet(BTN_DANGER)
btns.addWidget(danger_btn)
btns.addStretch()  # always add stretch at the end to left-align
```

### Button Group Patterns
- **Git Branches**: `[Checkout (primary)] [New Branch] [Merge Into Current] [Delete (danger)]` + stretch
- **Git Tags**: `[New Tag] [Checkout] [Delete (danger)]` + stretch
- **Git Commit row**: `[Commit message input] [Commit All (primary)] [Push] [Pull]`
- **AI Tools bar**: `[Add (primary)] [Edit] [Delete (danger)] [Add Separator] | spacing | [▲] [▼]` + stretch + `[Reset to Defaults]`
- **Edit Action save row**: `[Save Changes (primary)] [Cancel]` + stretch

### Move Up/Down Buttons
- Use `BTN_SECONDARY`
- Fixed width: `30px`
- Unicode arrows: `▲` (U+25B2), `▼` (U+25BC)

---

## Splitter Handles

```python
# Splitter handle: thin, border-colored line
QSplitter::handle { background-color: C['border']; }
```

- Horizontal splitter handle: 1px wide
- Vertical splitter handle: 1px tall

---

## Serial Monitor Control Bar

```python
ctrl = QWidget()
ctrl.setStyleSheet(f"background: {C['bg']}; border-top: 1px solid {C['border']};")
cl = QHBoxLayout(ctrl)
cl.setContentsMargins(8, 4, 8, 4)
cl.setSpacing(8)
```

- Labels ("Port:", "Baud:"): `FONT_BODY`, color `C['fg']`
- Start button: `BTN_PRIMARY` → toggles to `BTN_DANGER` when running ("Stop")
- Clear button: `BTN_GHOST`
- Send input: standard QLineEdit styling, fixed width 140px
- `addStretch()` at end

---

## Status Labels (Feedback Text)

Used in: Models tab, AI Tools tab, Pull Model section.

```python
status = QLabel("")
status.setStyleSheet(f"color: {C['fg_dim']}; {FONT_SMALL}")
```

Status colors by state:
- **Error**: `C['fg_err']`
- **Warning**: `C['fg_warn']`
- **Success**: `C['fg_ok']`
- **Info/In-progress**: `C['fg_link']`
- **Default/idle**: `C['fg_dim']`

---

## Scroll Areas (Non-Chat)

Used for: Settings right column, any panel with potentially tall content.

```python
scroll = QScrollArea()
scroll.setWidgetResizable(True)
scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {C['bg']}; }}")
```

---

## Anti-Patterns (DO NOT DO THESE)

1. **DO NOT** write `font-size: 12px` or any font-size inline. Use `FONT_BODY`, `FONT_SMALL`, etc.
2. **DO NOT** write `background: #2d2d2d` or any hex inline. Use `C['bg_input']`.
3. **DO NOT** write `border-radius: 3px` or `5px` or `7px`. Use the radius scale.
4. **DO NOT** write `padding: 5px 10px` or `7px 13px`. Use the spacing scale.
5. **DO NOT** create one-off button stylesheets. Use `BTN_PRIMARY`, `BTN_SECONDARY`, etc.
6. **DO NOT** use different fonts/sizes for similar elements in different views.
7. **DO NOT** use `C['teal']` where `C['fg_ok']` is correct (success messages).
8. **DO NOT** use `C['fg_link']` for anything except the user's "You" label and clickable links.
9. **DO NOT** add new colors to `C` without documenting their specific purpose.
10. **DO NOT** use `setStyleSheet()` with a string that contains any hardcoded hex value.
