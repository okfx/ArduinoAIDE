# ArduinoAIDE — UI Specification

Visual reference: `docs/ui_mockup.html` (open in browser to see the interactive mockup)

This document is the definitive UI spec. The mockup HTML is pixel-accurate for colors, spacing, fonts, and layout. When in doubt, read the CSS in the mockup.

---

## Design Philosophy

A cross between **Arduino IDE 2.x** (toolbar, sidebar, editor+output split) and **Claude Code/Cowork** (chat aesthetic, diff display, clean dark polish). The app should feel like a native macOS creative tool — not a web app, not a generic IDE.

---

## Color Palette

All colors live in the `C = {}` dict at the top of `ArduinoAIDE.py`.

| Token | Hex | Usage |
|---|---|---|
| `bg` | `#1e1e1e` | Editor background, toolbar bg, panels |
| `bg_dark` | `#1a1a1a` | Chat bg, file browser bg, bottom panel bg, tab bar bg |
| `bg_sidebar` | `#181818` | Sidebar strip background |
| `bg_input` | `#2a2a2a` | Input fields, user chat bubbles, code blocks in chat |
| `border` | `#2a2a2a` | All borders and dividers |
| `border_light` | `#333333` | Toolbar buttons border, subtle separators |
| `fg` | `#d4d4d4` | Primary text |
| `fg_dim` | `#888888` | Secondary text, labels, placeholders |
| `fg_head` | `#cccccc` | Tab text, header text |
| `teal` | `#00979d` | Primary accent — active indicators, buttons, AI speaker name |
| `fg_link` | `#7aafff` | User speaker name "You" |
| `fg_err` | `#f44747` | Error speaker name, error text |
| `fg_ok` | `#4ecdc4` | Success text (lighter teal) |
| `fg_warn` | `#e8b54d` | Warning text, folder icons |

---

## Typography

| Context | Font | Size | Weight |
|---|---|---|---|
| Code editor | `SF Mono, Menlo, Courier New, monospace` | 13px | normal |
| Chat messages (user + AI) | `-apple-system, Helvetica, Arial, sans-serif` | 14px | normal |
| Chat speaker names | same as messages | 14px | **bold** |
| Inline code in chat | `SF Mono, Menlo, Courier New, monospace` | 13px | normal |
| Toolbar labels | system | 11px | normal |
| Toolbar buttons | system | 12px | 600 |
| Tab labels | system | 12px | normal |
| Status bar | system | 11px | normal |

**Key rule: Speaker names are the SAME font-size as message text (14px), just bold.**

---

## Layout Structure

```
┌─────────────────────────────────────────────────────────┐
│                     Title Bar (38px)                     │
├──────┬──────────────────────────────────────────────────┤
│      │              Toolbar (44px)                       │
│      ├──────────────────────────────────────────────────┤
│  S   │                                                   │
│  i   │         View Content Area (flex)                  │
│  d   │                                                   │
│  e   │   Code View: tab bar + editor + bottom panel      │
│  b   │   Chat View: header + messages + apply + input    │
│  a   │   Files View: header + tree + bottom bar          │
│  r   │   Git View: full git panel                        │
│      │   Settings: model manager                         │
│(48px)│                                                   │
│      ├──────────────────────────────────────────────────┤
│      │              Status Bar (26px)                    │
└──────┴──────────────────────────────────────────────────┘
```

---

## Sidebar (48px wide)

- Background: `#181818`, right border `1px solid #2a2a2a`
- Buttons: 40×40px, 6px border-radius, centered icons (SVG-style, drawn with QPainter)
- Hover: `color: #aaa, bg: #252525`
- Active: `color: #fff, bg: #252525` + 3px teal left accent bar (rounded, inset 8px from top/bottom)
- Icon size: 20×20px (16×16 for Git and Settings)

**Order top to bottom:**
1. `</>` Code Editor (code bracket icon)
2. 💬 AI Chat (speech bubble icon)
3. 📁 Files (folder icon)
4. Git (branch/fork icon)
5. *(stretch spacer)*
6. ⚙ Settings/Models (gear icon) — at very bottom

---

## Toolbar (44px tall)

- Background: `#1e1e1e`, bottom border `1px solid #2a2a2a`
- Horizontal layout with 8px gaps

**Contents left to right:**
1. **Verify button** — teal bg (`#00979d`), white text, checkmark icon, "Verify", 6px radius
2. **Upload button** — teal bg, white text, arrow-up icon, "Upload", 6px radius
3. *separator* (1px × 24px, `#333`)
4. **Board label** "Board" (11px, `#888`) + **Board combo** (dark select, `#2a2a2a` bg)
5. **Port label** "Port" + **Port combo**
6. *separator*
7. **AI label** "AI" + **Model combo** (min-width 140px) + **Model description** (11px italic dim)
8. *flex spacer*
9. **Spinner** — animated teal gear, 20×20, visible only during generation

---

## Code View (View 0)

### Tab Bar (36px)
- Background: `#1a1a1a`, bottom border
- Tabs: 12px text, `#888` inactive → `#e0e0e0` active
- Active tab: `bg: #1e1e1e`, 2px teal bottom border
- Close button: `×`, 16×16, appears on hover, `#555` → `#ccc` hover

### Editor
- Background: `#1e1e1e`
- Line numbers: `#1a1a1a` bg, `#555` text, right border
- Code font: `SF Mono / Menlo`, 13px, line-height 1.6
- Syntax colors: keywords `#c586c0`, types `#4ec9b0`, functions `#dcdcaa`, strings `#ce9178`, numbers `#b5cea8`, comments `#6a9955`, preprocessor `#c586c0`

### Bottom Panel (resizable, default ~150px)
- Background: `#1a1a1a`, top border
- Tab bar: "Output" and "Serial Monitor" tabs (same style as bottom-tab)
- Content: monospace 12px, teal for compiler output

---

## Chat View (View 1)

### Chat Header
- Background: `#1e1e1e`, bottom border
- Shows: **Project: Name** — *N files loaded* + "Show Files" link (teal)

### Messages Area (QScrollArea)
- Background: `#1a1a1a`
- Padding: 16px horizontal, 12px vertical
- Spacing between messages: 18px
- Thin scrollbar: 8px wide, `#444` handle, `#1a1a1a` track

**User messages (right-aligned):**
- Speaker label "You": 14px bold, color `#7aafff`, right-aligned, 6px right padding
- Bubble: QFrame, `bg: #2a2a2a`, `border-radius: 14px`, padding 10px 16px
- Max width: ~70% of chat area (or 500px)
- Text: 14px, color `#e0e0e0`, word wrap
- Layout: QHBoxLayout with stretch on left, bubble on right

**AI messages (left-aligned, NO bubble):**
- Speaker label: 14px bold, teal, left-aligned
- Content: QTextEdit (for streaming), transparent bg, no border, no scrollbars
- Text: 14px, color `#d4d4d4`
- Auto-resizes height via `document().contentsChanged`
- Code snippets in AI responses should eventually render in monospace (future enhancement)

**Error messages (left-aligned):**
- Speaker "Error": 14px bold, `#f44747`
- Text: QLabel, `#f08080`, word wrap

**Code diff blocks in AI responses (future enhancement):**
- Container: `bg: #1e1e1e`, `border: 1px solid #333`, `border-radius: 8px`
- Header: `bg: #252525`, filename, 12px, bottom border
- Diff lines: monospace 13px
- Deletions: `bg: rgba(244, 71, 71, 0.12)`, `color: #f08080`
- Additions: `bg: rgba(78, 205, 196, 0.12)`, `color: #7ee0d8`
- Context lines: `color: #888`

### Apply Bar
- Background: `#1e1e1e`, top border
- "N changes in filename" label + "Apply All Changes" (teal btn) + "Dismiss" (dark btn)

### Input Area
- Background: `#1e1e1e`, top border
- Input: `bg: #2a2a2a`, `border: 1px solid #3a3a3a`, `border-radius: 10px`, 14px text
- Focus: border-color teal
- Send button: teal bg, rounded 10px, bold
- Stop button: dark bg, rounded 10px

---

## Files View (View 2)

- Header: project name (13px bold), path below (11px dim)
- Tree: `#1a1a1a` bg, 13px text, folder icons yellow (`#e8b54d`), file icons gray
- Items: 5px vertical padding, hover `#252525`
- Bottom bar: "+ New File", "+ New Folder" buttons, "Open Folder..." on right

---

## Status Bar (26px)

- Background: `#181818`, top border `1px solid #2a2a2a`
- Font: 11px, color `#666`
- Left side: teal dot `●` + board/port connection status
- Right side: AI model name + `Ln X, Col Y` cursor position
- Flex spacer between left and right

---

## Git View (View 4)

### Header
- Uses `_make_panel_header("Branch: —")`
- Right buttons: **Refresh** (`BTN_PRIMARY`) + **Init Repo** (`BTN_SECONDARY`)

### Layout
```
┌─ Header ─────────────────────────────────────────────────────┐
│ Branch: main (FONT_TITLE)   [Refresh (primary)] [Init Repo]  │
├──────────────────────────────────────────────────────────────┤
│ ── QSplitter Vertical ──                                      │
│                                                                │
│ ┌─ Top half: graphical manager ─────────────────────────────┐ │
│ │ ┌── Branches (stretch:3) ──┐ ┌── Tags (stretch:2) ──────┐│ │
│ │ │ "Branches" (teal, bold)  │ │ "Tags" (teal, bold)       ││ │
│ │ │ [QTreeView branch list]  │ │ [QTreeView tag list]       ││ │
│ │ │ [Checkout][New][Merge]   │ │ [New Tag][Checkout]        ││ │
│ │ │ [Delete(danger)] +stretch│ │ [Delete(danger)] +stretch  ││ │
│ │ └──────────────────────────┘ └────────────────────────────┘│ │
│ │                                                            │ │
│ │ [Filter indicator — italic teal, hidden by default]        │ │
│ │                                                            │ │
│ │ [Commit msg input·····] [Commit All(primary)] [Push] [Pull]│ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                │
│ ┌─ Bottom half: console ────────────────────────────────────┐ │
│ │ QPlainTextEdit, read-only, FONT_CODE (Menlo 12px)         │ │
│ │ bg: C['bg'], border-top: 1px solid C['border']            │ │
│ └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Branches/Tags Button Layout
- Spacing: `4px` between buttons
- Pattern: `[Primary] [Secondary...] [Danger]` + `stretch`
- Buttons left-aligned, stretch pushes nothing to right

### Commit Row
- Spacing: `6px`
- Commit message QLineEdit fills available space
- Buttons: `[Commit All (primary)] [Push (secondary)] [Pull (secondary)]`

---

## Settings View (View 3)

### Layout
```
┌─ Header ─────────────────────────────────────────────────────┐
│ Settings (FONT_TITLE)                                         │
├──────────────────────────────────────────────────────────────┤
│ [AI Tools] [Models]  ← QTabWidget ("settingsTabs")            │
│                                                                │
│ Content of selected tab fills remaining space                  │
└──────────────────────────────────────────────────────────────┘
```

### AI Tools Tab
```
┌──────────────────────────────────────────────────────────────┐
│ [Add(primary)][Edit][Delete(danger)][Add Separator]  |       │
│                                   [▲][▼]    [Reset Defaults] │
├──────────────────────────────────────────────────────────────┤
│ QListWidget (Menlo 12px font)                                │
│ • Explain This Code — "Explain what the..."                  │
│ • ──── separator ────                                        │
│ • Ask AI About This... (built-in)                            │
├──────────────────────────────────────────────────────────────┤
│ QGroupBox "Edit Action" (hidden until editing)               │
│ │ Label: [input field]                                       │
│ │ Prompt template hint (FONT_SMALL, fg_dim)                  │
│ │ [QPlainTextEdit, max 120px]                                │
│ │ [Save Changes(primary)] [Cancel]  +stretch                 │
├──────────────────────────────────────────────────────────────┤
│ Status label (FONT_SMALL, color changes by state)            │
└──────────────────────────────────────────────────────────────┘
```

### Models Tab
```
┌──────────────────────────────────────────────────────────────┐
│ ── QSplitter Horizontal ──                                    │
│                                                                │
│ ┌─ Left (min 260px) ──────┐ ┌─ Right (QScrollArea) ────────┐│
│ │ <b>Installed Models</b> │ │ ┌ QGroupBox: Model Details ─┐││
│ │ [Refresh]               │ │ │ Details pane (read-only)   │││
│ │                         │ │ │ Description: [edit] [Save] │││
│ │ [QTreeView with cols:   │ │ │ [Auto-Generate]            │││
│ │  Model | Size | Modified│ │ └────────────────────────────┘││
│ │  ]                      │ │                                ││
│ │                         │ │ ┌ QGroupBox: Create/Edit ───┐││
│ │ [Delete Selected(danger)│ │ │ Name: [input]              │││
│ │                         │ │ │ Base: [combo] Ctx: [combo] │││
│ └─────────────────────────┘ │ │ Temp: [input 45px]         │││
│                              │ │ System Prompt: [textarea]  │││
│                              │ │ [Preview] [Create(primary)]│││
│                              │ │ Preview pane (max 90px)    │││
│                              │ │ Status label               │││
│                              │ └────────────────────────────┘││
│                              │                                ││
│                              │ ┌ QGroupBox: Pull Model ────┐││
│                              │ │ Filter: [input]            │││
│                              │ │ [Curated list, max 180px]  │││
│                              │ │ [Pull Selected(primary)]   │││
│                              │ │ Or pull any: [name] [Pull] │││
│                              │ │ Pull status label           │││
│                              │ └────────────────────────────┘││
│                              └────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

---

## Serial Monitor (Bottom Panel Tab)

```
┌──────────────────────────────────────────────────────────────┐
│ QPlainTextEdit (read-only)                                    │
│ Placeholder: "Serial output will appear here..."              │
├──────────────────────────────────────────────────────────────┤
│ Control bar: bg C['bg'], border-top 1px solid C['border']     │
│ Port: [combo] Baud: [combo] [Start(primary)] [Clear(ghost)]  │
│ [Send input, 140px]  +stretch                                 │
└──────────────────────────────────────────────────────────────┘
```

- Start/Stop toggles: `BTN_PRIMARY` ↔ `BTN_DANGER`
- Clear: `BTN_GHOST`
- Control bar margins: `(8, 4, 8, 4)`

---

## Interaction Details

- Sidebar buttons use exclusive selection (QButtonGroup-like behavior via `_switch_view()`)
- Active sidebar button has a **3px teal left accent** — not just a background change
- Toolbar Verify/Upload buttons should be teal (`#00979d`) background with dark text
- All other toolbar buttons are transparent with `#333` border
- Tab close buttons are hidden by default, appear on tab hover
- Chat auto-scrolls to bottom during AI streaming
- Spinner in toolbar rotates only while AI is generating
