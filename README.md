# ArduinoAIDE

A desktop IDE for Teensy microcontroller development with integrated local LLM assistance via Ollama. Styled after Arduino IDE 2.x, built with PyQt6 and QScintilla.

## Features

- **Code editor** with C/C++ syntax highlighting, line numbers, brace matching, and code folding
- **AI chat** powered by local Ollama models — the AI sees all your project files automatically and can suggest edits in a structured format you apply with one click
- **Right-click AI tools** — highlight code and choose Explain, Fix, Refactor, Find Bugs, Optimize for Teensy, and more
- **Compile & upload** via `arduino-cli` with board and port selection
- **Serial monitor** with baud rate selection and auto-scroll
- **Git integration** — graphical branch/tag manager with console output, confirmations on destructive operations
- **Model manager** — browse, create, and delete Ollama models with auto-generated descriptions

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally (`ollama serve`)
- [arduino-cli](https://arduino.github.io/arduino-cli/) installed and configured with Teensy board support

```
pip install PyQt6 PyQt6-QScintilla requests pyserial
```

## Usage

```bash
python3 teensy_ide.py [project_path]
```

If no project path is given, use **File → Open Project** to select an Arduino project folder.

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

An "Apply All Changes" button appears so you can review and apply them in one click.

## License

MIT
