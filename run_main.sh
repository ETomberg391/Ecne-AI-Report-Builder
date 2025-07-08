#!/bin/bash

# Exit on any error
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the project directory
cd "$SCRIPT_DIR"

# Check if virtual environment exists
VENV_PATH="host_venv"
if [ ! -d "$VENV_PATH" ]; then
    echo "INFO: Virtual environment not found at $VENV_PATH"
    echo "INFO: Running installer..."
    # Make sure Installer.sh is executable
    chmod +x ./settings/Installer.sh
    ./settings/Installer.sh
fi

echo "INFO: Starting application..."
# Make sure run_app.sh is executable
chmod +x ./settings/run_app.sh
./settings/run_app.sh