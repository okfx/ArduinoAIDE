#!/bin/bash
# ArduinoAIDE.command — Double-click this file in Finder to launch ArduinoAIDE
# macOS opens .command files in Terminal automatically.

cd "$(dirname "$0")"

# Find venv Python
PYTHON=""
for candidate in "$HOME/teensy-ide-env/bin/python3" "./venv/bin/python3" "./.venv/bin/python3"; do
    if [ -x "$candidate" ]; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "ERROR: Python virtual environment not found."
    echo ""
    echo "Run these commands to set it up:"
    echo "  python3 -m venv ~/teensy-ide-env"
    echo "  source ~/teensy-ide-env/bin/activate"
    echo "  pip install PyQt6 PyQt6-QScintilla requests pyserial"
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi

exec "$PYTHON" ArduinoAIDE.py "$@"
