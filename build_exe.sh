#!/bin/bash
set -e

# Configuration
VENV_DIR="build_venv"
DIST_DIR="dist"
SPEC_FILE="report_builder.spec"

# Clean previous builds
rm -rf ${VENV_DIR} ${DIST_DIR} build/

# Create and activate virtual environment
python3 -m venv ${VENV_DIR}
source ${VENV_DIR}/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements_host.txt
pip install pyinstaller

# Install ChromeDriver with platform-specific handling
echo "Installing ChromeDriver..."
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux installation
    if ! command -v chromium-browser &> /dev/null; then
        echo "Error: Chromium browser not found. Install with: sudo apt install chromium-browser"
        exit 1
    fi
    CHROME_MAJOR=$(chromium-browser --version | awk '{print $2}' | cut -d'.' -f1)
    DRIVER_ZIP="chromedriver_linux64.zip"
    DRIVER_BIN="chromedriver"
elif [[ "$OSTYPE" == "msys" ]]; then
    # Windows installation
    if ! reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version &> /dev/null; then
        echo "Error: Chrome not found in registry"
        exit 1
    fi
    CHROME_MAJOR=$(reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version | awk '{print $3}' | cut -d'.' -f1)
    DRIVER_ZIP="chromedriver_win32.zip"
    DRIVER_BIN="chromedriver.exe"
else
    echo "Unsupported OS: $OSTYPE"
    exit 1
fi

CHROME_DRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_MAJOR")
if ! wget -q "https://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/$DRIVER_ZIP"; then
    echo "Failed to download ChromeDriver"
    exit 1
fi

unzip $DRIVER_ZIP
rm $DRIVER_ZIP
mv $DRIVER_BIN chromedriver.exe
chmod +x chromedriver.exe

# Run PyInstaller
pyinstaller ${SPEC_FILE} --clean --noconfirm

# Deactivate and remove venv (optional)
deactivate
rm -rf ${VENV_DIR}

echo "Build complete! EXE location: $(pwd)/dist/ReportBuilder"