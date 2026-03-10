# ArduinoAIDE

A desktop IDE for Teensy microcontroller development with integrated local LLM assistance via Ollama. Styled after Arduino IDE 2.x, built with PyQt6 and QScintilla.

## Features

- **Code editor** with C/C++ syntax highlighting, line numbers, brace matching, code folding, and diagnostic gutter markers
- **AI chat** powered by local Ollama models — sees your project files automatically via a priority-based WorkingSet context system, suggests edits in a structured format you apply with one click
- **Workspace panel** — select code in the editor and use quick action buttons (Explain, Fix/Improve, Refactor, Optimize) directly from the chat panel
- **Selection-based editing** — AI replaces only the selected code region, with pre-fill prompting for reliable output from local models
- **Ask LLM** — right-click selected code and choose "Ask LLM" to jump to chat with context
- **Compile & upload** via `arduino-cli` with board and port selection
- **Diagnostic panel** — structured error/warning table with clickable line references and gutter markers
- **Buffer-only apply** — AI edits update the editor buffer without writing to disk; save explicitly with Ctrl+S or auto-save before compile
- **Undo apply** — revert the last batch of AI edits with one click
- **Serial monitor** with baud rate selection and auto-scroll
- **Git integration** — graphical branch/tag manager with console output, confirmations on destructive operations
- **Model manager** — browse, pull, create, and delete Ollama models with auto-generated descriptions
- **Model load/unload** — explicit Load and Unload buttons with status display; auto-unloads the previous model when switching to free VRAM
- **Teensy reference** — built-in quick reference and API docs injected into AI context for .ino projects
- **Slash commands** — `/clear`, `/model`, `/compact`, `/context`, `/fix`, `/help` with autocomplete
- **Response cleanup** — automatically strips model special tokens and raw LaTeX from LLM output

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally (`ollama serve`)
- [arduino-cli](https://arduino.github.io/arduino-cli/) installed and configured with Teensy board support

```
pip install PyQt6 PyQt6-QScintilla requests pyserial
```

## Usage

```bash
source ~/teensy-ide-env/bin/activate
python3 ArduinoAIDE.py [project_path]
```

If no project path is given, the app restores the last opened project or you can use **File > Open Project**.

## Creating a custom Teensy model

You can create a specialized Ollama model for Teensy development:

```
ollama create teensy-coder -f Modelfile-teensy
```

Example `Modelfile-teensy`:

```
FROM qwen2.5-coder:14b
PARAMETER num_ctx 32768
SYSTEM """You are an expert embedded systems developer specializing in Teensy microcontrollers..."""
```

## How the AI edits your code

The AI uses a structured format to suggest changes. When it responds with edit blocks like:

```
<<<EDIT filename.ino
<<<OLD
(exact lines to replace)
>>>NEW
(replacement lines)
>>>END
```

An "Apply All Changes" bar appears so you can review and apply them in one click. Edits go to the editor buffer only — save to disk with Ctrl+S.

For selection-based edits (via the workspace panel), the AI replaces only the selected region directly.

## License

MIT
