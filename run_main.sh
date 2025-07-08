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

# --- Configuration File Sanity Checks ---
echo "INFO: Verifying configuration files..."

# Check for .env file
if [ ! -f ".env" ]; then
    echo "WARNING: .env file not found. Copying from example..."
    if [ -f "settings/env.example" ]; then
        cp "settings/env.example" ".env"
        echo "INFO: .env file created."
    else
        echo "ERROR: settings/env.example not found. Cannot create .env file."
    fi
fi

# Check for ai_models.yml file
AI_MODELS_PATH="settings/llm_settings/ai_models.yml"
AI_MODELS_EXAMPLE_PATH="settings/llm_settings/ai_models.example.yml"
if [ ! -f "$AI_MODELS_PATH" ]; then
    echo "WARNING: $AI_MODELS_PATH not found. Copying from example..."
    if [ -f "$AI_MODELS_EXAMPLE_PATH" ]; then
        mkdir -p "$(dirname "$AI_MODELS_PATH")"
        cp "$AI_MODELS_EXAMPLE_PATH" "$AI_MODELS_PATH"
        echo "INFO: $AI_MODELS_PATH created."
    else
        echo "ERROR: $AI_MODELS_EXAMPLE_PATH not found. Cannot create ai_models.yml."
    fi
fi

echo "INFO: Starting application..."
# Make sure run_app.sh is executable
chmod +x ./settings/run_app.sh
./settings/run_app.sh