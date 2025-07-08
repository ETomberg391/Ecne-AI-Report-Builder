#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e
# Treat unset variables as an error when substituting.
set -u
# Pipelines return the exit status of the last command to exit non-zero.
set -o pipefail

# Store the original directory where the script is being run from
ORIGINAL_DIR=$(pwd)

# --- Configuration ---
PYTHON_CMD="python3" # Change if your python 3 is just 'python'
PIP_CMD="pip3"     # Change if your pip 3 is just 'pip'

# --- Helper Functions ---
print_info() {
    echo "INFO: $1"
}

print_warning() {
    echo "WARNING: $1"
}

print_error() {
    echo "ERROR: $1" >&2
    exit 1
}

# Updated check_command to attempt installation of missing prerequisites
check_command() {
    local cmd="$1"
    local install_suggestion="${2:-}" # Use default empty string if $2 is unset
    local pkg_name="${3:-$cmd}" # Package name might differ from command name, default to cmd name
    local pkg_manager="${4:-}" # Pass detected package manager
    local install_cmd="${5:-}" # Pass install command base

    if ! command -v "$cmd" &> /dev/null; then
        print_warning "Command '$cmd' not found."

        # Only offer to install if we have a package manager and install command
        if [ -n "$pkg_manager" ] && [ -n "$install_cmd" ]; then
            read -p "Do you want to attempt to install '$pkg_name' using $pkg_manager? [Y/n]: " install_prereq
            install_prereq=$(echo "$install_prereq" | tr '[:upper:]' '[:lower:]')

            if [[ "$install_prereq" != "n" ]]; then
                print_info "Attempting to install '$pkg_name'..."
                set +e # Temporarily disable exit on error for the install command
                sudo $install_cmd "$pkg_name"
                local install_exit_code=$?
                set -e # Re-enable exit on error

                if [ $install_exit_code -ne 0 ]; then
                    print_error "Failed to install '$pkg_name' using $pkg_manager (Exit Code: $install_exit_code)."
                    if [ -n "$install_suggestion" ]; then
                         print_error "$install_suggestion"
                    else
                         print_error "Please install it manually."
                    fi
                    exit 1 # Exit if installation failed
                else
                    print_info "'$pkg_name' installed successfully."
                    # Verify command is now available
                    if ! command -v "$cmd" &> /dev/null; then
                         print_error "Installation of '$pkg_name' seemed successful, but command '$cmd' is still not found. Please check your PATH or the installation."
                         exit 1
                    fi
                    # Command is now available, continue script execution
                    return 0
                fi
            else
                # User chose not to install
                local error_msg="Command '$cmd' is required to continue."
                 if [ -n "$install_suggestion" ]; then
                    error_msg="$error_msg $install_suggestion"
                else
                    error_msg="$error_msg Please install it first."
                fi
                print_error "$error_msg"
                exit 1
            fi
        else
            # No package manager detected, just show error and suggestion
            local error_msg="Command '$cmd' not found."
            if [ -n "$install_suggestion" ]; then
                error_msg="$error_msg $install_suggestion"
            else
                error_msg="$error_msg Please install it first."
            fi
            print_error "$error_msg"
            exit 1
        fi
    fi
     # Command exists, return success
     return 0
}

# --- Main Script ---

echo "-----------------------------------------------------"
echo " Report Builder Environment Setup Script             "
echo "-----------------------------------------------------"

# --- OS Detection and Package Manager Setup ---
# (Moved OS detection before prerequisite checks that might need the package manager)
print_info "Detecting operating system and package manager..."

# Initialize variables
OS_TYPE=""
OS_ID=""
PKG_MANAGER=""
INSTALL_CMD=""
UPDATE_CMD=""
CHROME_INSTALLED_VIA_PKG_MANAGER="false" # Flag to track if we used package manager

# Debug information
print_info "OSTYPE: ${OSTYPE:-unknown}"
print_info "uname -s: $(uname -s 2>/dev/null || echo unknown)"

# Check if we're in WSL and set flags accordingly
if grep -q Microsoft /proc/version 2>/dev/null; then
    print_info "Windows Subsystem for Linux (WSL) detected."
    OS_TYPE="linux" # Treat WSL as Linux for package management
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID=$ID
    fi
fi

# Check for Windows (Combined and more robust detection)
# Covers Git Bash, Cygwin, MSYS, and native Windows environments
if [[ "$OSTYPE" == "msys" ]] || \
   [[ "$OSTYPE" == "cygwin" ]] || \
   [[ -n "${SYSTEMROOT:-}" ]] || \
   [[ -d "/c/Windows" ]] || \
   [[ -d "/c/WINDOWS" ]] || \
   [[ -n "$(command -v wmic 2>/dev/null)" ]] || \
   [[ "$(uname -s 2>/dev/null)" =~ ^MINGW|^MSYS ]] || \
   [[ -n "${MINGW_PREFIX:-}" ]] || \
   [[ -n "${MSYSTEM:-}" ]] || \
   [[ -d "/mingw64" ]]; then
    print_info "Windows environment detected (via OSTYPE/env vars/paths)"
    OS_TYPE="windows"
    # Detect Windows version using PowerShell (handle potential errors)
    WIN_VER=$(powershell.exe -NoProfile -Command "[System.Environment]::OSVersion.Version.Major" 2>/dev/null || echo "unknown")
    if [ "$WIN_VER" -eq "10" ] 2>/dev/null; then # Use numeric comparison, suppress errors
        OS_ID="windows10"
        print_info "Detected Windows 10"
    elif [ "$WIN_VER" -eq "11" ] 2>/dev/null; then # Use numeric comparison, suppress errors
        OS_ID="windows11"
        print_info "Detected Windows 11"
    else
        OS_ID="windows"
        print_info "Detected Windows (version unknown or PowerShell failed)"
    fi

    # Check for package managers (Winget/Choco) - INSTALL_CMD will be set if found
    if command -v winget &> /dev/null; then
        PKG_MANAGER="winget"
        INSTALL_CMD="winget install -e --accept-source-agreements --accept-package-agreements"
        print_info "Found winget package manager"
    elif command -v choco &> /dev/null; then
        PKG_MANAGER="choco"
        INSTALL_CMD="choco install -y"
        print_info "Found Chocolatey package manager"
    else
        print_warning "No supported package manager found on Windows (winget or chocolatey). Some prerequisites might need manual installation."
        # Let script continue, but check_command won't offer installs
    fi
# Check for Linux (only if not already identified as Windows or WSL Linux)
elif [ "$OS_TYPE" != "linux" ] && [ -f /etc/os-release ]; then
    OS_TYPE="linux"
    . /etc/os-release
    OS_ID=$ID
    print_info "Detected Linux OS ID: $OS_ID"

    case "$OS_ID" in
        ubuntu|debian|linuxmint|pop|elementary|zorin)
            PKG_MANAGER="apt"
            UPDATE_CMD="sudo apt update"
            INSTALL_CMD="sudo apt install -y"
            ;;
        arch|manjaro|endeavouros|garuda)
            PKG_MANAGER="pacman"
            UPDATE_CMD="sudo pacman -Sy"
            INSTALL_CMD="sudo pacman -S --noconfirm"
            ;;
        fedora|centos|rhel|rocky|almalinux)
            if command -v dnf &> /dev/null; then
                PKG_MANAGER="dnf"
                UPDATE_CMD="sudo dnf check-update"
                INSTALL_CMD="sudo dnf install -y"
            elif command -v yum &> /dev/null; then
                PKG_MANAGER="yum"
                UPDATE_CMD="sudo yum check-update"
                INSTALL_CMD="sudo yum install -y"
            fi
            ;;
        opensuse*|sles)
             PKG_MANAGER="zypper"
             UPDATE_CMD="sudo zypper refresh"
             INSTALL_CMD="sudo zypper install -y"
             ;;
        *)
            if [ -n "${ID_LIKE:-}" ]; then
                print_info "Trying fallback detection based on ID_LIKE='$ID_LIKE'..."
                case "$ID_LIKE" in
                    *debian*) PKG_MANAGER="apt"; UPDATE_CMD="sudo apt update"; INSTALL_CMD="sudo apt install -y";;
                    *arch*) PKG_MANAGER="pacman"; UPDATE_CMD="sudo pacman -Sy"; INSTALL_CMD="sudo pacman -S --noconfirm";;
                    *fedora*)
                        if command -v dnf &> /dev/null; then PKG_MANAGER="dnf"; UPDATE_CMD="sudo dnf check-update"; INSTALL_CMD="sudo dnf install -y";
                        elif command -v yum &> /dev/null; then PKG_MANAGER="yum"; UPDATE_CMD="sudo yum check-update"; INSTALL_CMD="sudo yum install -y"; fi;;
                    *suse*) PKG_MANAGER="zypper"; UPDATE_CMD="sudo zypper refresh"; INSTALL_CMD="sudo zypper install -y";;
                    *) print_warning "Unsupported ID_LIKE ($ID_LIKE) for automatic prerequisite installation."; PKG_MANAGER="";;
                esac
            else
                 print_warning "Unsupported Linux distribution ($OS_ID) for automatic prerequisite installation."
                 PKG_MANAGER=""
            fi
            ;;
    esac
# Fallback using lsb_release if /etc/os-release wasn't found/parsed
elif [ "$OS_TYPE" != "linux" ] && command -v lsb_release &> /dev/null; then
    OS_TYPE="linux" # Assume Linux if lsb_release exists and we haven't ID'd OS yet
    OS_ID=$(lsb_release -is | tr '[:upper:]' '[:lower:]')
    print_warning "Using fallback OS detection (lsb_release). May be less accurate."
    # Add cases for lsb_release output if needed, similar to above, to set PKG_MANAGER/INSTALL_CMD
    case "$OS_ID" in
        ubuntu|debian) PKG_MANAGER="apt"; UPDATE_CMD="sudo apt update"; INSTALL_CMD="sudo apt install -y";;
        # Add other distros recognized by lsb_release if necessary
        *) print_warning "Unsupported distribution ($OS_ID from lsb_release) for automatic prerequisite installation."; PKG_MANAGER="";;
    esac
else
    # If OS_TYPE is still empty, we couldn't determine the OS/Package Manager
     if [ -z "$OS_TYPE" ]; then
        print_warning "Could not determine operating system or package manager."
        print_warning "Automatic installation of prerequisites will be skipped. Please install manually if needed."
        OS_TYPE="unknown" # Mark as unknown
     fi
fi

if [ -n "$PKG_MANAGER" ]; then
    print_info "Detected Package Manager: $PKG_MANAGER"
fi
echo
# --- End OS Detection ---


# --- Prerequisite Checks ---
print_info "Checking core prerequisites..."
# Pass package manager info to check_command
check_command "git" "Please install git (e.g., sudo apt install git)" "git" "$PKG_MANAGER" "$INSTALL_CMD"
check_command "${PYTHON_CMD}" "Please install Python 3 (e.g., sudo apt install python3)" "python3" "$PKG_MANAGER" "$INSTALL_CMD"
check_command "${PIP_CMD}" "Please install pip for Python 3 (e.g., sudo apt install python3-pip)" "python3-pip" "$PKG_MANAGER" "$INSTALL_CMD" # Package name often differs
check_command "curl" "Please install curl (e.g., sudo apt install curl)" "curl" "$PKG_MANAGER" "$INSTALL_CMD"
check_command "unzip" "Please install unzip (e.g., sudo apt install unzip)" "unzip" "$PKG_MANAGER" "$INSTALL_CMD"
check_command "jq" "Please install jq (e.g., sudo apt install jq)" "jq" "$PKG_MANAGER" "$INSTALL_CMD"

print_info "Core prerequisites check complete."
echo

# --- Setup Host Python Environment ---
# Moved earlier to ensure venv exists before Chrome/ChromeDriver/wkhtmltopdf install steps
print_info "Setting up Python virtual environment ('host_venv') for report_builder.py..."

# Determine expected activation script path first
VENV_ACTIVATE=""
if [ "$OS_TYPE" = "windows" ]; then
    VENV_ACTIVATE="./host_venv/Scripts/activate"
else
    VENV_ACTIVATE="./host_venv/bin/activate"
fi

if [ -d "host_venv" ]; then
    print_warning "Host virtual environment 'host_venv' already exists."
    if [ ! -f "$VENV_ACTIVATE" ]; then
        print_error "Existing 'host_venv' appears incomplete (missing activation script: $VENV_ACTIVATE)."
        read -p "Do you want to remove the existing 'host_venv' and recreate it? [Y/n]: " REMOVE_VENV
        REMOVE_VENV=$(echo "$REMOVE_VENV" | tr '[:upper:]' '[:lower:]')
        if [[ "$REMOVE_VENV" != "n" ]]; then
            print_info "Removing existing 'host_venv'..."
            rm -rf "host_venv"
            print_info "Creating Python virtual environment 'host_venv'..."
            $PYTHON_CMD -m venv "host_venv"
        else
            print_error "Cannot proceed with incomplete virtual environment. Please remove 'host_venv' manually and re-run."
            exit 1
        fi
    else
        print_info "Existing 'host_venv' found and appears valid. Skipping creation."
        print_warning "If you encounter issues later, remove the 'host_venv' directory and re-run the script."
    fi
else
    print_info "Creating Python virtual environment 'host_venv'..."
    $PYTHON_CMD -m venv "host_venv"
fi


print_info "Activating venv and installing dependencies from requirements_host.txt..."

# The VENV_ACTIVATE variable is now set earlier (before the if/else block checking the directory)
# We still need the MSYS2 export for Windows cases if the venv exists or is created.
if [ "$OS_TYPE" = "windows" ]; then
    # Ensure Windows-style path handling in MSYS2/Git Bash
    export MSYS2_ARG_CONV_EXCL="*"
fi

# Use subshell to activate, install, and deactivate without affecting parent script's environment
(
    if [ ! -f "$VENV_ACTIVATE" ]; then
        # This check might be redundant now due to the check+recreate logic above, but keep for safety
        print_error "Virtual environment activation script not found at: $VENV_ACTIVATE"
    fi

    source "$VENV_ACTIVATE"
    print_info "Upgrading pip in host venv..."
    $PIP_CMD install --upgrade pip

    if [ -f "requirements_host.txt" ]; then
        print_info "Installing host dependencies from requirements_host.txt..."
        $PIP_CMD install -r "requirements_host.txt"
    else
        # Deactivate before erroring
        deactivate
        print_error "Could not find requirements_host.txt in the current directory. Cannot install host dependencies."
    fi
    print_info "Deactivating venv..."
    deactivate
)
print_info "Host Python environment setup complete."
echo


# --- Optional Chrome/ChromeDriver Installation ---
# (Now runs *after* venv setup)

# --- ChromeDriver Setup Functions ---

# Function to find installed Chrome/Chromium version
get_chrome_version() {
    local chrome_version=""
    # Try common commands
    if command -v google-chrome-stable &> /dev/null; then
        chrome_version=$(google-chrome-stable --version 2>/dev/null)
    elif command -v google-chrome &> /dev/null; then
        chrome_version=$(google-chrome --version 2>/dev/null)
    elif command -v chromium-browser &> /dev/null; then
        chrome_version=$(chromium-browser --version 2>/dev/null)
    elif command -v chromium &> /dev/null; then
        chrome_version=$(chromium --version 2>/dev/null)
    fi

    # Extract version number (e.g., "Google Chrome 114.0.5735.198" -> "114.0.5735.198")
    # Handles variations like "Chromium 114..."
    chrome_version=$(echo "$chrome_version" | grep -oP '(\d+\.\d+\.\d+\.\d+)' | head -n 1)

    if [ -n "$chrome_version" ]; then
        echo "$chrome_version"
    else
        return 1 # Indicate not found
    fi
}

# Function to check local ChromeDriver version
# Define path relative to script location (assuming script is run from repo root)
CHROMEDRIVER_DIR="./host_venv/bin"
CHROMEDRIVER_PATH="${CHROMEDRIVER_DIR}/chromedriver"

get_local_chromedriver_version() {
    if [ -f "$CHROMEDRIVER_PATH" ] && [ -x "$CHROMEDRIVER_PATH" ]; then
        local driver_version_output=$("$CHROMEDRIVER_PATH" --version 2>/dev/null)
        # Extract version (e.g., "ChromeDriver 114.0.5735.90 ..." -> "114.0.5735.90")
        local driver_version=$(echo "$driver_version_output" | grep -oP 'ChromeDriver\s+(\d+\.\d+\.\d+\.\d+)' | sed -n 's/ChromeDriver //p')
        if [ -n "$driver_version" ]; then
            echo "$driver_version"
        else
             # Handle cases where version format might differ or command fails silently
             print_warning "Could not parse version from existing ChromeDriver at $CHROMEDRIVER_PATH"
             echo "" # Return empty if parsing fails
        fi
    else
        echo "" # Return empty if not found or not executable
    fi
}

# Function to download and install ChromeDriver matching a major Chrome version
install_local_chromedriver() {
    local required_major_version="$1"
    # Use the more targeted endpoint first
    local latest_patch_url="https://googlechromelabs.github.io/chrome-for-testing/latest-patch-versions-per-build-with-downloads.json"
    # Fallback endpoint if the exact build isn't in the latest-patch endpoint
    local milestone_url="https://googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone-with-downloads.json"

    local temp_zip="/tmp/chromedriver_linux64.zip"
    local temp_extract_dir="/tmp/chromedriver_extract"
    local download_url=""
    local chrome_full_version=$(get_chrome_version) # Get the full installed version
    local chrome_build_version=$(echo "$chrome_full_version" | cut -d. -f1-3) # Extract major.minor.build

    print_info "Installed Chrome version: $chrome_full_version (Major.Minor.Build: $chrome_build_version)"
    print_info "Attempting to find exact ChromeDriver match using latest-patch endpoint..."

    # Attempt 1: Find the exact build version in the latest-patch endpoint
    download_url=$(curl -s "$latest_patch_url" | jq -r --arg build "$chrome_build_version" '
        .builds[$build].downloads.chromedriver[]? |
        select(.platform == "linux64") |
        .url // empty
    ' 2>/dev/null)

    # Attempt 2: If exact build not found, fall back to the latest milestone endpoint
    if [ -z "$download_url" ]; then
        print_warning "Exact match for build $chrome_build_version not found in latest-patch data."
        print_info "Attempting to find latest ChromeDriver for major version $required_major_version using milestone endpoint..."
        download_url=$(curl -s "$milestone_url" | jq -r --arg milestone "$required_major_version" '
            .milestones[$milestone].downloads.chromedriver[]? |
            select(.platform == "linux64") |
            .url // empty
        ' 2>/dev/null)

        if [ -z "$download_url" ]; then
             print_error "Could not find a suitable linux64 ChromeDriver download URL for Chrome major version $required_major_version using milestone endpoint either."
             print_warning "Please install ChromeDriver manually from https://googlechromelabs.github.io/chrome-for-testing/"
             return 1
        else
             print_info "Found latest ChromeDriver URL for major version $required_major_version via milestone endpoint."
        fi
    else
        print_info "Found exact ChromeDriver URL for build $chrome_build_version via latest-patch endpoint."
    fi

    # Proceed with download using the found URL
    print_info "Downloading ChromeDriver from: $download_url"
    if ! curl -L -o "$temp_zip" "$download_url"; then
        print_error "Failed to download ChromeDriver from $download_url"
        rm -f "$temp_zip"
        return 1
    fi

    print_info "Extracting ChromeDriver..."
    rm -rf "$temp_extract_dir" # Clean up previous attempt if any
    mkdir -p "$temp_extract_dir"
    # Extract directly into the target directory structure if possible, handling potential nested folders
    # The zip file from google contains a top-level directory like chromedriver-linux64/
    if ! unzip -q "$temp_zip" -d "$temp_extract_dir"; then
        print_error "Failed to unzip $temp_zip"
        rm -f "$temp_zip"
        rm -rf "$temp_extract_dir"
        return 1
    fi

    # Find the chromedriver executable (it's often in a nested folder like chromedriver-linux64/chromedriver)
    local extracted_driver_path=$(find "$temp_extract_dir" -name chromedriver -type f -executable | head -n 1)


    if [ -z "$extracted_driver_path" ]; then
        print_error "Could not find 'chromedriver' executable in the extracted archive."
        rm -f "$temp_zip"
        rm -rf "$temp_extract_dir"
        return 1
    fi

    print_info "Installing ChromeDriver to $CHROMEDRIVER_PATH..."
    # Ensure the target directory exists (should be created by venv setup)
    mkdir -p "$CHROMEDRIVER_DIR"
    # Move the found executable directly, overwriting if necessary
    if ! mv "$extracted_driver_path" "$CHROMEDRIVER_PATH"; then
         print_error "Failed to move ChromeDriver to $CHROMEDRIVER_PATH"
         # Don't remove the zip/extract dir yet, user might want to inspect
         return 1
    fi

    # Ensure it's executable after moving (mv should preserve permissions, but double-check)
    if ! chmod +x "$CHROMEDRIVER_PATH"; then
        print_error "Failed to ensure ChromeDriver is executable at $CHROMEDRIVER_PATH"
        # Attempt to remove the potentially corrupted file
        rm -f "$CHROMEDRIVER_PATH"
        # Don't remove the zip/extract dir yet
        return 1
    fi

    # Clean up
    rm -f "$temp_zip"
    rm -rf "$temp_extract_dir"

    local installed_version=$(get_local_chromedriver_version)
    if [ -n "$installed_version" ]; then
         print_info "ChromeDriver installation successful. Version: $installed_version"
         return 0
    else
         print_error "ChromeDriver installed, but failed to verify version."
         return 1
    fi
}

# --- End ChromeDriver Setup Functions ---


if [ -n "$PKG_MANAGER" ] && [ -n "$INSTALL_CMD" ]; then
    echo
    read -p "Do you want to attempt to install/update Google Chrome/Chromium using $PKG_MANAGER? (Browser is required for Selenium features) [y/N]: " INSTALL_CHROME
    INSTALL_CHROME=$(echo "$INSTALL_CHROME" | tr '[:upper:]' '[:lower:]')

    if [[ "$INSTALL_CHROME" == "y" ]]; then
        GOOGLE_CHROME_INSTALLED_FLAG="false" # Track if google-chrome was installed specifically
        print_info "Attempting to install/update Chrome/Chromium using $PKG_MANAGER..."
        if [ -n "$UPDATE_CMD" ]; then
            print_info "Running package list update ($UPDATE_CMD)..."
            set +e
            $UPDATE_CMD
            if [ $? -ne 0 ]; then print_warning "Package list update failed. Installation might use outdated lists or fail."; fi
            set -e
        fi

        print_info "Running installation..."
        set +e # Don't exit immediately if install fails
        INSTALL_EXIT_CODE=0

        case "$PKG_MANAGER" in
            winget)
                # Install Google Chrome using winget
                print_info "Attempting to install Google Chrome using winget..."
                $INSTALL_CMD Google.Chrome # Winget package name
                INSTALL_EXIT_CODE=$?
                if [ $INSTALL_EXIT_CODE -eq 0 ]; then
                    CHROME_INSTALLED_VIA_PKG_MANAGER="true"
                fi
                ;;
            choco)
                # Install Google Chrome using chocolatey
                print_info "Attempting to install Google Chrome using chocolatey..."
                $INSTALL_CMD googlechrome # Choco package name
                INSTALL_EXIT_CODE=$?
                if [ $INSTALL_EXIT_CODE -eq 0 ]; then
                    CHROME_INSTALLED_VIA_PKG_MANAGER="true"
                fi
                ;;
            apt)
                # Install Google Chrome (adds repo)
                print_info "Attempting to install Google Chrome Stable via official repository..."
                wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add - > /dev/null 2>&1
                sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list'
                $UPDATE_CMD # Update again after adding repo
                sudo $INSTALL_CMD google-chrome-stable
                INSTALL_EXIT_CODE=$?
                GOOGLE_CHROME_INSTALLED_FLAG="true" # Mark that we tried to install google-chrome
                ;;
            dnf|yum)
                # Install Chromium (driver handled by webdriver-manager)
                print_info "Attempting to install Chromium using $PKG_MANAGER..."
                sudo $INSTALL_CMD chromium # Package name on dnf/yum
                INSTALL_EXIT_CODE=$?
                CHROME_INSTALLED_VIA_PKG_MANAGER="true"
                ;;
            pacman)
                # Use --needed to only install if missing or outdated (driver handled by webdriver-manager)
                print_info "Attempting to install Chromium using $PKG_MANAGER..."
                sudo $INSTALL_CMD --needed chromium # Package name on pacman
                INSTALL_EXIT_CODE=$?
                CHROME_INSTALLED_VIA_PKG_MANAGER="true"
                ;;
            zypper)
                 # Driver handled by webdriver-manager
                print_info "Attempting to install Chromium using $PKG_MANAGER..."
                sudo $INSTALL_CMD chromium # Package name on zypper
                INSTALL_EXIT_CODE=$?
                CHROME_INSTALLED_VIA_PKG_MANAGER="true"
                ;;
        esac
        set -e # Re-enable exit on error

        if [ $INSTALL_EXIT_CODE -eq 0 ]; then
            print_info "Package manager installation attempt finished successfully."
        else
            print_warning "Package manager installation attempt finished with Exit Code: $INSTALL_EXIT_CODE."
            # Don't error out here, let the chromedriver check proceed
        fi

        # --- Check and Install ChromeDriver ---
        print_info "Checking installed Chrome/Chromium version..."
        chrome_full_version=$(get_chrome_version)

        if [ -z "$chrome_full_version" ]; then
             print_warning "Could not detect installed Chrome/Chromium version after installation attempt."
             print_warning "Skipping ChromeDriver setup. Please ensure a compatible version is installed manually or via report_builder.py."
        else
            chrome_major_version=$(echo "$chrome_full_version" | cut -d. -f1)
            print_info "Detected Chrome/Chromium version: $chrome_full_version (Major: $chrome_major_version)"

            print_info "Checking local ChromeDriver version at $CHROMEDRIVER_PATH..."
            driver_full_version=$(get_local_chromedriver_version)
            should_install_driver="true"

            if [ -n "$driver_full_version" ]; then
                driver_major_version=$(echo "$driver_full_version" | cut -d. -f1)
                print_info "Found local ChromeDriver version: $driver_full_version (Major: $driver_major_version)"
                if [ "$driver_major_version" = "$chrome_major_version" ]; then
                    print_info "Local ChromeDriver version is compatible."
                    should_install_driver="false"
                else
                    print_warning "Local ChromeDriver version mismatch. Will attempt to install matching version."
                fi
            else
                 print_info "Local ChromeDriver not found or version unknown. Will attempt to install."
            fi

            if [ "$should_install_driver" = "true" ]; then
                 install_local_chromedriver "$chrome_major_version"
                 # The function install_local_chromedriver prints success/error messages
            fi
        fi
        # --- End ChromeDriver Check ---

    else
        print_info "Skipping automatic Chrome/ChromeDriver installation."
        print_info "Skipping automatic Chrome/Chromium installation by user choice."
        # Still check existing chrome/driver if chrome wasn't installed by script
        print_info "Checking installed Chrome/Chromium version..."
        chrome_full_version=$(get_chrome_version)
        if [ -z "$chrome_full_version" ]; then
            print_warning "Could not detect installed Chrome/Chromium version."
            print_warning "Please ensure Chrome/Chromium AND a matching ChromeDriver are installed for Selenium features."
        else
            chrome_major_version=$(echo "$chrome_full_version" | cut -d. -f1)
            print_info "Detected Chrome/Chromium version: $chrome_full_version (Major: $chrome_major_version)"
            print_info "Checking local ChromeDriver version at $CHROMEDRIVER_PATH..."
            driver_full_version=$(get_local_chromedriver_version)
             if [ -n "$driver_full_version" ]; then
                driver_major_version=$(echo "$driver_full_version" | cut -d. -f1)
                print_info "Found local ChromeDriver version: $driver_full_version (Major: $driver_major_version)"
                if [ "$driver_major_version" != "$chrome_major_version" ]; then
                     print_warning "Local ChromeDriver version does NOT match Chrome/Chromium version."
                     print_warning "Attempting to install matching ChromeDriver..."
                     install_local_chromedriver "$chrome_major_version"
                else
                     print_info "Local ChromeDriver version is compatible."
                fi
            else
                 print_warning "Local ChromeDriver not found or version unknown."
                 print_warning "Attempting to install matching ChromeDriver..."
                 install_local_chromedriver "$chrome_major_version"
            fi
        fi
    fi
else
    print_warning "Could not detect package manager. Skipping automatic Chrome/Chromium installation."
    # Still check existing chrome/driver if package manager wasn't found
    print_info "Checking installed Chrome/Chromium version..."
    chrome_full_version=$(get_chrome_version)
     if [ -z "$chrome_full_version" ]; then
        print_warning "Could not detect installed Chrome/Chromium version."
        print_warning "Please ensure Chrome/Chromium AND a matching ChromeDriver are installed for Selenium features."
    else
        chrome_major_version=$(echo "$chrome_full_version" | cut -d. -f1)
        print_info "Detected Chrome/Chromium version: $chrome_full_version (Major: $chrome_major_version)"
        print_info "Checking local ChromeDriver version at $CHROMEDRIVER_PATH..."
        driver_full_version=$(get_local_chromedriver_version)
         if [ -n "$driver_full_version" ]; then
            driver_major_version=$(echo "$driver_full_version" | cut -d. -f1)
            print_info "Found local ChromeDriver version: $driver_full_version (Major: $driver_major_version)"
            if [ "$driver_major_version" != "$chrome_major_version" ]; then
                 print_warning "Local ChromeDriver version does NOT match Chrome/Chromium version."
                 print_warning "Attempting to install matching ChromeDriver..."
                 install_local_chromedriver "$chrome_major_version"
            else
                 print_info "Local ChromeDriver version is compatible."
            fi
        else
             print_warning "Local ChromeDriver not found or version unknown."
             print_warning "Attempting to install matching ChromeDriver..."
             install_local_chromedriver "$chrome_major_version"
        fi
    fi
fi
echo

# --- Install wkhtmltopdf ---
print_info "Checking wkhtmltopdf installation..."

install_wkhtmltopdf() {
    if command -v wkhtmltopdf &> /dev/null; then
        print_info "wkhtmltopdf is already installed."
        return 0
    fi

    print_info "Installing wkhtmltopdf..."

    case "$OS_ID" in
        debian|ubuntu)
            # First attempt: Try installing via apt
            print_info "Attempting to install wkhtmltopdf via apt..."
            if sudo apt-get update && sudo apt-get install -y wkhtmltopdf; then
                print_info "Successfully installed wkhtmltopdf via apt"
                return 0
            fi

            print_warning "apt installation failed, attempting manual installation..."

            local version=""
            local arch="amd64"
            local success=false

            # First try matching version-specific package
            case "$VERSION_ID" in
                "12"|"bookworm") version="0.12.7-1.bookworm";;
                "11"|"bullseye") version="0.12.7-1.bullseye";;
                "10"|"buster") version="0.12.7-1.buster";;
                "24.04"|"noble") version="0.12.7-1.jammy";; # Try jammy package for noble
                "23.10"|"mantic") version="0.12.7-1.jammy";; # Try jammy package for mantic
                "23.04"|"lunar") version="0.12.7-1.jammy";; # Try jammy package for lunar
                "22.10"|"kinetic") version="0.12.7-1.jammy";; # Try jammy package for kinetic
                "22.04"|"jammy") version="0.12.7-1.jammy";;
                "20.04"|"focal") version="0.12.7-1.focal";;
                "18.04"|"bionic") version="0.12.7-1.bionic";;
                *)
                    # For unknown versions, try using the package for the latest LTS
                    print_warning "Unknown Debian/Ubuntu version: $VERSION_ID, attempting with jammy package..."
                    version="0.12.7-1.jammy"
                    ;;
            esac

            local download_url="https://github.com/wkhtmltopdf/packaging/releases/download/0.12.7-1/wkhtmltox_${version}_${arch}.deb"
            local temp_deb="/tmp/wkhtmltopdf.deb"

            print_info "Downloading wkhtmltopdf package from: $download_url"
            if wget -q -O "$temp_deb" "$download_url"; then
                print_info "Installing downloaded wkhtmltopdf package..."
                if sudo dpkg -i "$temp_deb"; then
                    success=true
                else
                    print_warning "dpkg installation failed, attempting to fix dependencies..."
                    if sudo apt-get install -f -y && sudo dpkg -i "$temp_deb"; then
                        success=true
                    fi
                fi
                rm -f "$temp_deb"
            fi

            if [ "$success" = true ]; then
                print_info "Successfully installed wkhtmltopdf from downloaded package"
                return 0
            else
                print_error "Failed to install wkhtmltopdf automatically."
                echo
                echo "Please try installing manually using one of these methods:"
                echo "1. Using apt (recommended):"
                echo "   sudo apt-get update"
                echo "   sudo apt-get install -y wkhtmltopdf"
                echo
                echo "2. Download from official website:"
                echo "   Visit https://wkhtmltopdf.org/downloads.html"
                echo "   Download and install the appropriate package for your system"
                echo
                return 1
            fi
            ;;

        fedora|centos|rhel|almalinux)
            # First attempt: Try installing via package manager
            local pkg_cmd=""
            if command -v dnf &> /dev/null; then
                pkg_cmd="sudo dnf install -y wkhtmltopdf"
            elif command -v yum &> /dev/null; then
                pkg_cmd="sudo yum install -y wkhtmltopdf"
            fi

            if [ -n "$pkg_cmd" ]; then
                print_info "Attempting to install wkhtmltopdf via package manager..."
                if $pkg_cmd; then
                    print_info "Successfully installed wkhtmltopdf via package manager"
                    return 0
                fi
                print_warning "Package manager installation failed, attempting manual installation..."
            fi

            local arch="x86_64"
            local version="0.12.7-1"
            local success=false

            # Determine specific version based on OS and version
            if [[ "$OS_ID" == "almalinux" ]]; then
                if [[ "$VERSION_ID" == "9" ]]; then
                    version="0.12.7-1.almalinux9"
                elif [[ "$VERSION_ID" == "8" ]]; then
                    version="0.12.7-1.almalinux8"
                else
                    version="0.12.7-1.almalinux9" # Try latest for unknown versions
                fi
            elif [[ "$OS_ID" == "centos" ]]; then
                if [[ "$VERSION_ID" == "7" ]]; then
                    version="0.12.7-1.centos7"
                elif [[ "$VERSION_ID" == "6" ]]; then
                    version="0.12.7-1.centos6"
                else
                    version="0.12.7-1.centos7" # Try latest for unknown versions
                fi
            elif [[ "$OS_ID" == "fedora" ]]; then
                version="0.12.7-1.fedora" # Generic Fedora package
            fi

            local download_url="https://github.com/wkhtmltopdf/packaging/releases/download/0.12.7-1/wkhtmltox-${version}.${arch}.rpm"
            local temp_rpm="/tmp/wkhtmltopdf.rpm"

            print_info "Downloading wkhtmltopdf package from: $download_url"
            if wget -q -O "$temp_rpm" "$download_url"; then
                print_info "Installing downloaded wkhtmltopdf package..."
                if sudo rpm -Uvh "$temp_rpm"; then
                    success=true
                fi
                rm -f "$temp_rpm"
            fi

            if [ "$success" = true ]; then
                print_info "Successfully installed wkhtmltopdf from downloaded package"
                return 0
            else
                print_error "Failed to install wkhtmltopdf automatically."
                echo
                echo "Please try installing manually using one of these methods:"
                echo "1. Using package manager (recommended):"
                if command -v dnf &> /dev/null; then
                    echo "   sudo dnf install wkhtmltopdf"
                else
                    echo "   sudo yum install wkhtmltopdf"
                fi
                echo
                echo "2. Download from official website:"
                echo "   Visit https://wkhtmltopdf.org/downloads.html"
                echo "   Download and install the appropriate package for your system"
                echo
                return 1
            fi
            ;;

        opensuse*|"sles")
            local success=false
            print_info "Attempting to install wkhtmltopdf via zypper..."

            # First attempt: Try installing via zypper
            if sudo zypper install -y wkhtmltopdf; then
                success=true
            else
                print_warning "zypper installation failed, attempting alternative installation..."

                # Try manual RPM installation as fallback
                local arch="x86_64"
                local version="0.12.7-1.opensuse"
                local download_url="https://github.com/wkhtmltopdf/packaging/releases/download/0.12.7-1/wkhtmltox-${version}.${arch}.rpm"
                local temp_rpm="/tmp/wkhtmltopdf.rpm"

                print_info "Downloading wkhtmltopdf from: $download_url"
                if wget -q -O "$temp_rpm" "$download_url"; then
                    print_info "Installing downloaded wkhtmltopdf package..."
                    if sudo rpm -Uvh "$temp_rpm"; then
                        success=true
                    fi
                fi
                rm -f "$temp_rpm" 2>/dev/null
            fi

            if [ "$success" = true ]; then
                print_info "Successfully installed wkhtmltopdf"
                return 0
            else
                print_error "Failed to install wkhtmltopdf automatically."
                echo
                echo "Please try installing manually using one of these methods:"
                echo "1. Using zypper (recommended):"
                echo "   sudo zypper install wkhtmltopdf"
                echo
                echo "2. Download from official website:"
                echo "   Visit https://wkhtmltopdf.org/downloads.html"
                echo "   Download and install the appropriate package for your system"
                echo
                return 1
            fi
            ;;

        "arch"|"manjaro"|"endeavouros"|"garuda")
            local success=false
            print_info "Checking wkhtmltopdf in Arch repositories..."

            # First attempt: Try official repos
            if pacman -Si wkhtmltopdf &> /dev/null; then
                print_info "Found wkhtmltopdf in standard repositories. Installing..."
                if sudo pacman -S --noconfirm wkhtmltopdf; then
                    success=true
                else
                    print_warning "pacman installation failed."
                fi
            else
                print_warning "wkhtmltopdf not found in standard Arch repositories."
            fi

            # If official repos failed, try AUR
            if [ "$success" = false ]; then
                local AUR_HELPER=""
                if command -v yay &> /dev/null; then
                    AUR_HELPER="yay"
                elif command -v paru &> /dev/null; then
                    AUR_HELPER="paru"
                fi

                if [ -n "$AUR_HELPER" ]; then
                    print_warning "Detected AUR helper: $AUR_HELPER."
                    read -p "Do you want to attempt installing 'wkhtmltopdf-static' from the AUR using $AUR_HELPER? [y/N]: " INSTALL_AUR_WKHTMLTOPDF
                    INSTALL_AUR_WKHTMLTOPDF=$(echo "$INSTALL_AUR_WKHTMLTOPDF" | tr '[:upper:]' '[:lower:]')
                    if [[ "$INSTALL_AUR_WKHTMLTOPDF" == "y" ]]; then
                        print_info "Attempting installation via $AUR_HELPER..."
                        if $AUR_HELPER -S --noconfirm wkhtmltopdf-static; then
                            success=true
                        fi
                    fi
                fi
            fi

            if [ "$success" = true ]; then
                print_info "Successfully installed wkhtmltopdf"
                return 0
            else
                print_error "Failed to install wkhtmltopdf automatically."
                echo
                echo "Please try installing manually using one of these methods:"
                echo "1. Using pacman (if available in official repos):"
                echo "   sudo pacman -S wkhtmltopdf"
                echo
                echo "2. Using AUR (recommended if not in official repos):"
                echo "   yay -S wkhtmltopdf-static"
                echo "   # or"
                echo "   paru -S wkhtmltopdf-static"
                echo
                echo "3. Download from official website:"
                echo "   Visit https://wkhtmltopdf.org/downloads.html"
                echo "   Download and install the appropriate package for your system"
                echo
                return 1
            fi
            ;;

        *)
            print_error "Unsupported distribution for automated wkhtmltopdf installation: $OS_ID"
            print_error "Please install wkhtmltopdf manually from https://wkhtmltopdf.org/downloads.html"
            return 1
            ;;
    esac

    # Verify installation
    if command -v wkhtmltopdf &> /dev/null; then
        print_info "wkhtmltopdf installed successfully."
        print_info "Version: $(wkhtmltopdf --version)"
        return 0
    else
        print_error "wkhtmltopdf installation verification failed."
        return 1
    fi
}

read -p "Do you want to install wkhtmltopdf for PDF report generation? [Y/n]: " INSTALL_WKHTMLTOPDF
INSTALL_WKHTMLTOPDF=$(echo "$INSTALL_WKHTMLTOPDF" | tr '[:upper:]' '[:lower:]')
if [[ "$INSTALL_WKHTMLTOPDF" != "n" ]]; then
    install_wkhtmltopdf
else
    print_info "Skipping wkhtmltopdf installation."
fi
echo

# --- Configuration File Setup ---
print_info "Checking for root .env configuration file..."
ROOT_ENV_PATH="${ORIGINAL_DIR}/.env"
EXAMPLE_ENV_PATH="${ORIGINAL_DIR}/settings/env.example"

if [ -f "$ROOT_ENV_PATH" ]; then
    print_warning ".env file already exists in root directory. Skipping copy."
    print_warning "Please review your existing .env file: $ROOT_ENV_PATH"
else
    if [ -f "$EXAMPLE_ENV_PATH" ]; then
        cp "$EXAMPLE_ENV_PATH" "$ROOT_ENV_PATH"
        print_info "Copied settings/env.example to .env"
    else
        print_warning "settings/env.example not found. Cannot create .env."
        print_warning "Please create the .env file manually with necessary API keys."
    fi
fi

# --- Final Instructions ---
echo "---------------------------------------------"
echo " Setup Complete! "
echo "---------------------------------------------"
echo
echo "This script has set up the basic environment required for 'report_builder.py'."

# Add WSL-specific notes if in WSL environment
if grep -q Microsoft /proc/version 2>/dev/null; then
    echo
    echo "NOTE: WSL Environment Detected"
    echo "- Chrome/ChromeDriver: Use Windows Chrome installation"
    echo "- PDF Generation: wkhtmltopdf installed in WSL will work natively"
    echo "- Browser automation will use Windows Chrome through WSL integration"
fi
echo
echo "Next Steps:"
echo
echo "1. Activate the virtual environment before running the script:"
if [ "$OS_TYPE" = "windows" ]; then
    echo "   source ./host_venv/Scripts/activate"
else
    echo "   source ./host_venv/bin/activate"
fi
echo
echo "2. Run the report builder script (example):"
echo "   ${PYTHON_CMD} report_builder.py --topic \"Artificial Intelligence in Healthcare\" --keywords \"AI diagnostics, machine learning drug discovery\""
echo
echo "3. Ensure necessary API keys are correctly set in:"
echo "   - ${ROOT_ENV_PATH}"
echo "   - ${ORIGINAL_DIR}/settings/llm_settings/ai_models.yml (if modified)"
echo
echo "4. Verify Chrome/Chromium is installed if you rely on Selenium features. This script attempts to install a matching ChromeDriver in ./host_venv/bin/."
echo
echo "5. PDF report generation requires wkhtmltopdf. If you did not install it during setup,"
echo "   install it manually from https://wkhtmltopdf.org/downloads.html"
echo
echo "6. To deactivate the environment when finished:"
echo "   deactivate"
echo
