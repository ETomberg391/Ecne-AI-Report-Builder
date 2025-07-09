#!/bin/bash
# Shell Script to Check and Update ChromeDriver
set -e
set -o pipefail

# --- Helper Functions ---
print_info() {
    echo "INFO: $1"
}

print_warning() {
    echo "WARNING: $1"
}

print_error() {
    echo "ERROR: $1" >&2
}

# --- Prerequisite Check ---
for cmd in curl unzip jq; do
    if ! command -v "$cmd" &> /dev/null; then
        print_error "Required command '$cmd' is not installed. Please install it first."
        exit 1
    fi
done

# --- Main Script ---
print_info "Starting ChromeDriver check for Linux..."

# --- Find Chrome/Chromium ---
get_chrome_version() {
    local chrome_version=""
    # List of common browser commands
    local browsers=("google-chrome-stable" "google-chrome" "chromium-browser" "chromium")
    
    for browser in "${browsers[@]}"; do
        if command -v "$browser" &> /dev/null; then
            chrome_version=$($browser --version 2>/dev/null)
            if [ -n "$chrome_version" ]; then
                # Extract version number (e.g., "Google Chrome 114.0.5735.198" -> "114.0.5735.198")
                echo "$chrome_version" | grep -oP '(\d+\.\d+\.\d+\.\d+)' | head -n 1
                return 0
            fi
        fi
    done
    return 1
}

chrome_full_version=$(get_chrome_version)
if [ -z "$chrome_full_version" ]; then
    print_error "Google Chrome or Chromium is not found on this system."
    exit 1
fi

chrome_major_version=$(echo "$chrome_full_version" | cut -d. -f1)
print_info "Detected Chrome/Chromium version: $chrome_full_version (Major: $chrome_major_version)"

# --- Check Existing ChromeDriver ---
# Assume the script is run from the root of the project directory
VENV_PATH="./host_venv"
if [ ! -d "$VENV_PATH" ]; then
    print_error "Virtual environment not found at '$VENV_PATH'. Please run the main installer first."
    exit 1
fi

CHROMEDRIVER_PATH="${VENV_PATH}/bin/chromedriver"
should_install_driver="true"

if [ -f "$CHROMEDRIVER_PATH" ] && [ -x "$CHROMEDRIVER_PATH" ]; then
    driver_version_output=$("$CHROMEDRIVER_PATH" --version 2>/dev/null || echo "")
    driver_full_version=$(echo "$driver_version_output" | grep -oP 'ChromeDriver\s+(\d+\.\d+\.\d+\.\d+)' | sed -n 's/ChromeDriver //p')
    
    if [ -n "$driver_full_version" ]; then
        driver_major_version=$(echo "$driver_full_version" | cut -d. -f1)
        print_info "Found existing ChromeDriver version: $driver_full_version (Major: $driver_major_version)"
        
        if [ "$driver_major_version" = "$chrome_major_version" ]; then
            print_info "ChromeDriver version is compatible with Chrome."
            should_install_driver="false"
        else
            print_warning "ChromeDriver version mismatch. Will proceed with update."
        fi
    else
        print_warning "Could not determine existing ChromeDriver version. Will proceed with update."
    fi
else
    print_info "ChromeDriver not found. Will proceed with installation."
fi

# --- Download and Install ---
if [ "$should_install_driver" = "true" ]; then
    print_info "Attempting to download and install matching ChromeDriver..."
    
    # Use the known-good-versions-with-downloads endpoint
    versions_url="https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
    
    print_info "Fetching latest ChromeDriver version information..."
    # Use jq to find the latest version for the major build
    download_url=$(curl -s "$versions_url" | jq -r --arg major_version "$chrome_major_version" '
        .versions | 
        map(select(.version | startswith($major_version + "."))) | 
        sort_by(.version | split(".") | map(tonumber))[-1] | 
        .downloads.chromedriver[] | 
        select(.platform == "linux64") | 
        .url
    ')

    if [ -z "$download_url" ]; then
        print_error "Could not find a suitable linux64 ChromeDriver download URL for Chrome major version $chrome_major_version."
        exit 1
    fi

    print_info "Downloading from: $download_url"
    temp_zip="/tmp/chromedriver_linux64.zip"
    temp_extract_dir="/tmp/chromedriver_extract"

    if ! curl -L -o "$temp_zip" "$download_url"; then
        print_error "Failed to download ChromeDriver."
        rm -f "$temp_zip"
        exit 1
    fi

    print_info "Extracting archive..."
    rm -rf "$temp_extract_dir"
    mkdir -p "$temp_extract_dir"
    if ! unzip -q "$temp_zip" -d "$temp_extract_dir"; then
        print_error "Failed to unzip ChromeDriver archive."
        rm -f "$temp_zip"
        rm -rf "$temp_extract_dir"
        exit 1
    fi

    # Find the executable, which is often in a nested directory
    extracted_driver=$(find "$temp_extract_dir" -name chromedriver -type f)
    if [ -z "$extracted_driver" ]; then
        print_error "chromedriver executable not found in the downloaded archive."
        rm -f "$temp_zip"
        rm -rf "$temp_extract_dir"
        exit 1
    fi

    destination_dir="${VENV_PATH}/bin"
    print_info "Installing to: $destination_dir"
    mv "$extracted_driver" "$CHROMEDRIVER_PATH"
    chmod +x "$CHROMEDRIVER_PATH"

    # Cleanup
    rm -f "$temp_zip"
    rm -rf "$temp_extract_dir"

    print_info "ChromeDriver installation successful."
    installed_version=$($CHROMEDRIVER_PATH --version 2>/dev/null)
    print_info "Installed version: $installed_version"
else
    print_info "Update process finished. No installation was needed."
fi

exit 0