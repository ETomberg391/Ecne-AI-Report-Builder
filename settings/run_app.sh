#!/bin/bash

# Script to activate virtual environment and run the Flask app

# Exit on any error
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the project directory (one level up from script)
cd "$SCRIPT_DIR/.."

# Check if virtual environment exists
VENV_PATH="host_venv"
if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH"
    echo "Please create a virtual environment first:"
    echo "  python -m venv host_venv"
    echo "  source host_venv/bin/activate"
    echo "  pip install -r requirements_host.txt"
    exit 1
fi

# Activate the virtual environment
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# Check if required packages are installed
if ! python -c "import flask" 2>/dev/null; then
    echo "Flask not found. Installing requirements..."
    pip install -r requirements_host.txt
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. You may need to configure API keys."
    echo "You can copy settings/env.example to .env and fill in your API keys."
fi

# Run the Flask application
echo "Starting Flask application..."
echo "The app will be available at: http://localhost:5000"
echo "Press Ctrl+C to stop the application"
echo ""

# Function to open URL in default browser
open_url() {
    local url="$1"
    case "$(uname -s)" in
        Linux*)     xdg-open "$url" >/dev/null 2>&1 ;;
        Darwin*)    open "$url" >/dev/null 2>&1 ;;
        CYGWIN*|MINGW*|MSYS*) start "$url" >/dev/null 2>&1 ;;
        *)          echo "Please open your browser and navigate to $url" ;;
    esac
}

# Give the server a moment to start, then open the browser
(sleep 2 && open_url "http://127.0.0.1:5000/") &

python app.py