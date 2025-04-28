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

check_command() {
    local cmd="$1"
    local install_suggestion="${2:-}" # Use default empty string if $2 is unset

    if ! command -v "$cmd" &> /dev/null; then
        local error_msg="Command '$cmd' not found."
        if [ -n "$install_suggestion" ]; then
            error_msg="$error_msg $install_suggestion"
        else
            error_msg="$error_msg Please install it first (e.g., using apt, yum, brew, pkg install, etc.)."
        fi
        print_error "$error_msg" # print_error already exits
    fi
}

# --- Main Script ---

echo "-----------------------------------------------------"
echo " Report Builder Environment Setup Script             "
echo "-----------------------------------------------------"

print_info "Checking core prerequisites..."
check_command "git" "Please install git (e.g., sudo apt install git)"
check_command "${PYTHON_CMD}" "Please install Python 3 (e.g., sudo apt install python3)"
check_command "${PIP_CMD}" "Please install pip for Python 3 (e.g., sudo apt install python3-pip)"

print_info "Core prerequisites met."
echo

# --- Optional Chrome/ChromeDriver Installation ---
print_info "Detecting operating system for optional Chrome/ChromeDriver installation..."

# Debug information
print_info "OSTYPE: ${OSTYPE:-unknown}"
print_info "uname -s: $(uname -s 2>/dev/null || echo unknown)"

# Check if we're in WSL and set flags accordingly
if grep -q Microsoft /proc/version 2>/dev/null; then
    print_info "Windows Subsystem for Linux (WSL) detected."
    print_info "Installing dependencies for WSL environment..."
    OS_TYPE="linux"
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID=$ID
    fi
fi

# Initialize variables
OS_TYPE=""
OS_ID=""
PKG_MANAGER=""
INSTALL_CMD=""
UPDATE_CMD=""
CHROME_INSTALLED_VIA_PKG_MANAGER="false" # Flag to track if we used package manager

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
    print_info "Windows environment detected"
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
    OS_TYPE="windows"
    # Detect Windows version using PowerShell
    WIN_VER=$(powershell -Command "[System.Environment]::OSVersion.Version.Major")
    if [ "$WIN_VER" -eq "10" ]; then
        OS_ID="windows10"
        print_info "Detected Windows 10"
    elif [ "$WIN_VER" -eq "11" ]; then
        OS_ID="windows11"
        print_info "Detected Windows 11"
    else
        OS_ID="windows"
        print_info "Detected Windows (version unknown)"
    fi

    # Check for package managers
    if command -v winget &> /dev/null; then
        PKG_MANAGER="winget"
        INSTALL_CMD="winget install -e --accept-source-agreements --accept-package-agreements"
        print_info "Found winget package manager"
    elif command -v choco &> /dev/null; then
        PKG_MANAGER="choco"
        INSTALL_CMD="choco install -y"
        print_info "Found Chocolatey package manager"
    else
        print_warning "No supported package manager found on Windows (winget or chocolatey)"
    fi
# Check for Linux
elif [ -f /etc/os-release ]; then
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
                    *) print_warning "Unsupported ID_LIKE ($ID_LIKE) for automatic Chrome/ChromeDriver installation."; PKG_MANAGER="";;
                esac
            else
                 print_warning "Unsupported Linux distribution ($OS_ID) for automatic Chrome/ChromeDriver installation."
                 PKG_MANAGER=""
            fi
            ;;
    esac
elif command -v lsb_release &> /dev/null; then
    OS_ID=$(lsb_release -is | tr '[:upper:]' '[:lower:]')
    print_warning "Using fallback OS detection (lsb_release). May be less accurate."
    # Add cases for lsb_release output if needed, similar to above
else
    print_warning "Could not determine Linux distribution. Cannot attempt automatic Chrome/ChromeDriver installation."
fi

# --- Removed setup_chromedriver function ---
# ChromeDriver installation is now handled automatically by the webdriver-manager Python package within the virtual environment when report_builder.py runs.

# --- End Removed setup_chromedriver function ---


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

        # ChromeDriver is handled by webdriver-manager in Python, no need to check/install manually here.

    else
        print_info "Skipping automatic Chrome/ChromeDriver installation."
        print_warning "Please ensure Chrome/Chromium and the matching ChromeDriver are installed manually for Selenium features."
    fi
else
    print_warning "Could not detect package manager. Skipping automatic Chrome/ChromeDriver installation."
    print_warning "Please ensure Chrome/Chromium and the matching ChromeDriver are installed manually for Selenium features."
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

# --- Setup Host Python Environment ---
print_info "Setting up Python virtual environment ('host_venv') for report_builder.py..."

if [ ! -d "host_venv" ]; then
    print_info "Creating Python virtual environment 'host_venv'..."
    $PYTHON_CMD -m venv "host_venv"
else
    print_warning "Host virtual environment 'host_venv' already exists. Skipping creation."
    print_warning "If you encounter issues, remove the 'host_venv' directory and re-run the script."
fi

print_info "Activating venv and installing dependencies from requirements_host.txt..."

# Set platform-specific paths
if [ "$OS_TYPE" = "windows" ]; then
    VENV_ACTIVATE="./host_venv/Scripts/activate"
    # Ensure Windows-style path handling in MSYS2/Git Bash
    export MSYS2_ARG_CONV_EXCL="*"
else
    VENV_ACTIVATE="./host_venv/bin/activate"
fi

# Use subshell to activate, install, and deactivate without affecting parent script's environment
(
    if [ ! -f "$VENV_ACTIVATE" ]; then
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
echo

# --- API Key Configuration ---
read -p "Do you want to configure Google Custom Search API? (Optional, needed for Google search in report_builder.py) [y/N]: " USE_GOOGLE_API
USE_GOOGLE_API=$(echo "$USE_GOOGLE_API" | tr '[:upper:]' '[:lower:]')
if [[ "$USE_GOOGLE_API" == "y" ]]; then
    echo "Get API Key from Google Cloud Console (Credentials page)"
    read -p "Enter GOOGLE_API_KEY= " GOOGLE_API_KEY
    echo "Get Search Engine ID (cx) from Programmable Search Engine control panel (make sure \"Search entire web\" is ON)"
    read -p "Enter GOOGLE_CSE_ID= " GOOGLE_CSE_ID

    # Update .env with Google API keys (only if .env exists)
    if [ -f "$ROOT_ENV_PATH" ]; then
        # Use # as sed delimiter to avoid issues with special chars in keys
        sed -i "s#^GOOGLE_API_KEY=.*#GOOGLE_API_KEY=\"${GOOGLE_API_KEY}\"#" "$ROOT_ENV_PATH"
        sed -i "s#^GOOGLE_CSE_ID=.*#GOOGLE_CSE_ID=\"${GOOGLE_CSE_ID}\"#" "$ROOT_ENV_PATH"
        print_info "Updated GOOGLE_API_KEY and GOOGLE_CSE_ID in .env"
    else
        print_warning ".env file does not exist. Could not save Google API keys."
    fi
fi

read -p "Do you want to configure Brave Search API? (Optional, needed for Brave search in report_builder.py) [y/N]: " USE_BRAVE_API
USE_BRAVE_API=$(echo "$USE_BRAVE_API" | tr '[:upper:]' '[:lower:]')
if [[ "$USE_BRAVE_API" == "y" ]]; then
    echo "Get Brave Search API Key from https://api.search.brave.com/"
    read -p "Enter BRAVE_API_KEY= " BRAVE_API_KEY

    # Update .env with Brave API key (only if .env exists)
     if [ -f "$ROOT_ENV_PATH" ]; then
        sed -i "s#^BRAVE_API_KEY=.*#BRAVE_API_KEY=\"${BRAVE_API_KEY}\"#" "$ROOT_ENV_PATH"
        print_info "Updated BRAVE_API_KEY in .env"
    else
        print_warning ".env file does not exist. Could not save Brave API key."
    fi
fi

# LLM Configuration (Gemini vs OpenAI)
read -p "Do you want to use the recommended free Google Gemini Flash model? (Recommended) [Y/n]: " USE_GEMINI
USE_GEMINI=$(echo "$USE_GEMINI" | tr '[:upper:]' '[:lower:]')
if [[ "$USE_GEMINI" != "n" ]]; then
    echo "You can get a Google Gemini API key from https://ai.google.dev/gemini-api/docs/api-key"
    read -p "Enter Gemini API Key: " GEMINI_API_KEY

    # Define paths and check/copy ai_models.yml
    AI_MODELS_DIR="${ORIGINAL_DIR}/settings/llm_settings"
    AI_MODELS_PATH="${AI_MODELS_DIR}/ai_models.yml"
    AI_MODELS_EXAMPLE_PATH="${AI_MODELS_DIR}/ai_models.example.yml"

    if [ ! -f "$AI_MODELS_PATH" ]; then
        if [ -f "$AI_MODELS_EXAMPLE_PATH" ]; then
            print_info "Creating $AI_MODELS_PATH from example..."
            cp "$AI_MODELS_EXAMPLE_PATH" "$AI_MODELS_PATH"
        else
            print_warning "$AI_MODELS_EXAMPLE_PATH not found. Cannot create $AI_MODELS_PATH."
            # Continue without the file, but updates will fail
        fi
    fi

    # Update ai_models.yml (only if it exists now)
    if [ -f "$AI_MODELS_PATH" ]; then
        print_info "Updating Gemini settings in $AI_MODELS_PATH..."
        # Use # as sed delimiter
        # Use awk for more robust YAML modification
        temp_yaml="${AI_MODELS_PATH}.tmp"
        awk -v key="$GEMINI_API_KEY" '
        BEGIN { in_gemini_block = 0; found_key = 0 }
        /^gemini_flash:/ { in_gemini_block = 1 }
        /^[[:alnum:]_-]+:/ && !/^gemini_flash:/ { in_gemini_block = 0 }

        in_gemini_block && /^[[:space:]]*api_key:/ {
            printf "  api_key: \"%s\"\n", key
            found_key = 1
            next
        }

        { print }

        END {
            if (found_key == 0) {
                print "Error: Could not find api_key line in gemini_flash section"
                exit 1
            }
        }
        ' "$AI_MODELS_PATH" > "$temp_yaml"

        AWK_EXIT_CODE=$?
        if [ $AWK_EXIT_CODE -eq 0 ] && [ -s "$temp_yaml" ]; then
            # Compare the files to ensure changes were made
            if diff "$AI_MODELS_PATH" "$temp_yaml" >/dev/null; then
                print_warning "No changes detected in the YAML file. API key might not have been updated."
                rm -f "$temp_yaml"
            else
                mv "$temp_yaml" "$AI_MODELS_PATH"
                print_info "Successfully updated Gemini API key in $AI_MODELS_PATH"
                # Verify the key was actually written
                if grep -q "api_key: \"${GEMINI_API_KEY}\"" "$AI_MODELS_PATH"; then
                    print_info "Verified API key was written correctly"
                else
                    print_warning "API key verification failed - key may not have been written correctly"
                fi
            fi
        else
            print_warning "awk command failed (exit code: $AWK_EXIT_CODE) or produced empty output. File not modified."
            rm -f "$temp_yaml" # Clean up temp file on failure
        fi
    else
         print_warning "$AI_MODELS_PATH not found. Could not set Gemini API key."
    fi

    if [ -f "$ROOT_ENV_PATH" ]; then
         sed -i 's#^DEFAULT_MODEL_CONFIG=.*#DEFAULT_MODEL_CONFIG="gemini_flash"#' "$ROOT_ENV_PATH"
         print_info "Set DEFAULT_MODEL_CONFIG to 'gemini_flash' in .env"
    else
         print_warning ".env file does not exist. Could not set DEFAULT_MODEL_CONFIG."
    fi
else
    # --- OpenAI API Compatible Configuration ---
    echo "Please enter the OpenAI API compatible server settings:"
    read -p "API Endpoint URL (e.g., https://api.openai.com/v1 or local server URL): " OPENAI_API_ENDPOINT
    read -p "API Key (e.g., sk-..., or leave blank if not needed): " OPENAI_API_KEY
    read -p "Model Name (e.g., gpt-4o, leave blank for default): " OPENAI_MODEL
    # OPENAI_MODEL=${OPENAI_MODEL:-"gpt-4o"} # Defaulting in python script is safer
    read -p "Temperature (e.g., 0.7, leave blank for default): " OPENAI_TEMPERATURE
    # OPENAI_TEMPERATURE=${OPENAI_TEMPERATURE:-0.7} # Defaulting in python script is safer

    # Define paths and check/copy ai_models.yml
    AI_MODELS_DIR="${ORIGINAL_DIR}/settings/llm_settings"
    AI_MODELS_PATH="${AI_MODELS_DIR}/ai_models.yml"
    AI_MODELS_EXAMPLE_PATH="${AI_MODELS_DIR}/ai_models.example.yml"

    if [ ! -f "$AI_MODELS_PATH" ]; then
        if [ -f "$AI_MODELS_EXAMPLE_PATH" ]; then
            print_info "Creating $AI_MODELS_PATH from example..."
            cp "$AI_MODELS_EXAMPLE_PATH" "$AI_MODELS_PATH"
        else
            print_warning "$AI_MODELS_EXAMPLE_PATH not found. Cannot create $AI_MODELS_PATH."
             # Continue without the file, but updates will fail
       fi
    fi

    # Update ai_models.yml (only if it exists now)
    if [ -f "$AI_MODELS_PATH" ]; then
        print_info "Updating OpenAI compatible settings in $AI_MODELS_PATH..."
        # Use # as sed delimiter
        # Update the 'default_model' section
        # Be careful with empty inputs - use conditional sed or handle defaults in python
        if [ -n "$OPENAI_API_ENDPOINT" ]; then
             sed -i "/^default_model:/,/^ [a-zA-Z_]*:/{s#api_endpoint: \".*\"#api_endpoint: \"${OPENAI_API_ENDPOINT}\"#}" "$AI_MODELS_PATH"
        fi
         if [ -n "$OPENAI_API_KEY" ]; then
             sed -i "/^default_model:/,/^ [a-zA-Z_]*:/{s#api_key: \".*\"#api_key: \"${OPENAI_API_KEY}\"#}" "$AI_MODELS_PATH"
         fi
         if [ -n "$OPENAI_MODEL" ]; then
              sed -i "/^default_model:/,/^ [a-zA-Z_]*:/{s#model: \".*\"#model: \"${OPENAI_MODEL}\"#}" "$AI_MODELS_PATH"
         fi
         if [ -n "$OPENAI_TEMPERATURE" ]; then
             sed -i "/^default_model:/,/^ [a-zA-Z_]*:/{s#temperature: .*#temperature: ${OPENAI_TEMPERATURE}#}" "$AI_MODELS_PATH"
         fi
        print_info "Attempted to update OpenAI compatible settings in $AI_MODELS_PATH"
    else
         print_warning "$AI_MODELS_PATH not found. Could not set OpenAI compatible settings."
    fi

    if [ -f "$ROOT_ENV_PATH" ]; then
         sed -i 's#^DEFAULT_MODEL_CONFIG=.*#DEFAULT_MODEL_CONFIG="default_model"#' "$ROOT_ENV_PATH"
         print_info "Set DEFAULT_MODEL_CONFIG to 'default_model' in .env"
    else
         print_warning ".env file does not exist. Could not set DEFAULT_MODEL_CONFIG."
    fi
fi
echo

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
echo "4. Verify Chrome/Chromium is installed if you rely on Selenium features. ChromeDriver will be managed automatically by the Python script."
echo
echo "5. PDF report generation requires wkhtmltopdf. If you did not install it during setup,"
echo "   install it manually from https://wkhtmltopdf.org/downloads.html"
echo
echo "6. To deactivate the environment when finished:"
echo "   deactivate"
echo
