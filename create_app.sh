#!/bin/bash
# create_app.sh — Build ArduinoAIDE.app for macOS Finder launch
#
# Usage:
#   cd /path/to/ArduinoAIDE
#   bash create_app.sh
#
# The resulting .app can be double-clicked from Finder or copied to /Applications.
set -e

APP_NAME="ArduinoAIDE"
APP_DIR="${APP_NAME}.app"
CONTENTS="${APP_DIR}/Contents"
MACOS="${CONTENTS}/MacOS"
RESOURCES="${CONTENTS}/Resources"

# Determine absolute path to this script's directory (where ArduinoAIDE.py lives)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IDE_SCRIPT="${SCRIPT_DIR}/ArduinoAIDE.py"

if [ ! -f "$IDE_SCRIPT" ]; then
    echo "Error: ArduinoAIDE.py not found in ${SCRIPT_DIR}"
    exit 1
fi

# Clean previous build
rm -rf "${SCRIPT_DIR}/${APP_DIR}"

# Create directory structure
mkdir -p "${SCRIPT_DIR}/${MACOS}" "${SCRIPT_DIR}/${RESOURCES}"

# Create Info.plist
cat > "${SCRIPT_DIR}/${CONTENTS}/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>ArduinoAIDE</string>
    <key>CFBundleDisplayName</key>
    <string>ArduinoAIDE</string>
    <key>CFBundleIdentifier</key>
    <string>com.teensy.arduinoaide</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>ArduinoAIDE</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.developer-tools</string>
</dict>
</plist>
PLIST

# Create launcher shell script
# NOTE: The IDE_SCRIPT path is baked in at build time
cat > "${SCRIPT_DIR}/${MACOS}/${APP_NAME}" << LAUNCHER
#!/bin/bash
# ArduinoAIDE launcher — finds venv Python and runs ArduinoAIDE.py

# Log for debugging launch issues
LOG="\$HOME/.teensy_ide_launch.log"
exec > "\$LOG" 2>&1
echo "ArduinoAIDE launch at \$(date)"

# Find ArduinoAIDE.py — check build-time path first, then fallback locations
IDE_SCRIPT=""
CANDIDATES=(
    "${IDE_SCRIPT}"
    "\$HOME/Documents/ArduinoAIDE/ArduinoAIDE.py"
    "\$(dirname "\$0")/../../ArduinoAIDE.py"
)
for candidate in "\${CANDIDATES[@]}"; do
    if [ -f "\$candidate" ]; then
        IDE_SCRIPT="\$candidate"
        break
    fi
done

if [ -z "\$IDE_SCRIPT" ]; then
    osascript -e 'display alert "ArduinoAIDE" message "Cannot find ArduinoAIDE.py. Make sure the app is in the same directory as ArduinoAIDE.py or in ~/Documents/ArduinoAIDE/." as critical'
    exit 1
fi

# Find venv Python (same search order as _bootstrap_venv in ArduinoAIDE.py)
PYTHON=""
IDE_DIR="\$(dirname "\$IDE_SCRIPT")"
VENV_CANDIDATES=(
    "\$HOME/teensy-ide-env/bin/python3"
    "\$IDE_DIR/venv/bin/python3"
    "\$IDE_DIR/.venv/bin/python3"
)
for candidate in "\${VENV_CANDIDATES[@]}"; do
    if [ -x "\$candidate" ]; then
        PYTHON="\$candidate"
        break
    fi
done

if [ -z "\$PYTHON" ]; then
    osascript -e 'display alert "ArduinoAIDE" message "Cannot find Python virtual environment. Please run these commands in Terminal:\n\npython3 -m venv ~/teensy-ide-env\nsource ~/teensy-ide-env/bin/activate\npip install PyQt6 PyQt6-QScintilla requests pyserial" as critical'
    exit 1
fi

echo "Using Python: \$PYTHON"
echo "Running: \$IDE_SCRIPT"

exec "\$PYTHON" "\$IDE_SCRIPT"
LAUNCHER

chmod +x "${SCRIPT_DIR}/${MACOS}/${APP_NAME}"

# Copy app icon if present
ICON_FILE="${SCRIPT_DIR}/AppIcon.icns"
if [ -f "$ICON_FILE" ]; then
    cp "$ICON_FILE" "${SCRIPT_DIR}/${RESOURCES}/AppIcon.icns"
    echo "Included app icon"
else
    echo "Warning: AppIcon.icns not found — app will use generic icon"
fi

echo "Created ${APP_DIR} in ${SCRIPT_DIR}"
echo ""
echo "To run:     open ${SCRIPT_DIR}/${APP_DIR}"
echo "To install: cp -r ${SCRIPT_DIR}/${APP_DIR} /Applications/"
