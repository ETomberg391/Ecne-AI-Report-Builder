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
print_info "Detecting Linux distribution for optional Chrome/ChromeDriver installation..."
OS_ID=""
PKG_MANAGER=""
INSTALL_CMD=""
UPDATE_CMD=""
CHROME_INSTALLED_VIA_PKG_MANAGER="false" # Flag to track if we used package manager

if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID=$ID
    print_info "Detected OS ID: $OS_ID"

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

# Function to download and install ChromeDriver manually
setup_chromedriver() {
    print_info "Attempting manual ChromeDriver setup..."
    local browser_version=""
    local browser_cmd=""

    if command -v google-chrome &> /dev/null; then
        browser_cmd="google-chrome"
    elif command -v chromium &> /dev/null; then
        browser_cmd="chromium"
    elif command -v chromium-browser &> /dev/null; then
         browser_cmd="chromium-browser" # Some systems use this
    fi

    if [ -n "$browser_cmd" ]; then
         # Try to extract major version number
         browser_version=$($browser_cmd --version | grep -oP '(\d+)\.\d+\.\d+\.\d+' | head -n 1 | cut -d '.' -f 1 || echo "0")
         print_info "Detected Browser ($browser_cmd) Major Version: $browser_version"
    else
         print_warning "Could not find google-chrome or chromium command to determine version for manual ChromeDriver download."
         print_warning "Please install ChromeDriver manually to match your installed Chrome/Chromium version."
         return 1 # Indicate failure
    fi

    if [ "$browser_version" == "0" ] || [ -z "$browser_version" ]; then
        print_error "Could not automatically detect Chrome/Chromium version for manual ChromeDriver download. Please install ChromeDriver manually."
    fi

    print_info "Using browser major version: $browser_version for ChromeDriver download."

    # Create a temporary directory
    local temp_dir
    temp_dir=$(mktemp -d -t chromedriver-XXXXXX)
    if [ ! -d "$temp_dir" ]; then
        print_error "Failed to create temporary directory for ChromeDriver download."
    fi
    print_info "Using temporary directory: $temp_dir"
    cd "$temp_dir"

    # Get the LATEST_RELEASE version for the detected major browser version
    local latest_release_url="https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${browser_version}"
    local latest_chromedriver_version=""
    print_info "Fetching latest ChromeDriver version string from: $latest_release_url"
    set +e # Don't exit if curl fails here
    latest_chromedriver_version=$(curl -s "$latest_release_url")
    local curl_exit_code=$?
    set -e
    if [ $curl_exit_code -ne 0 ] || [ -z "$latest_chromedriver_version" ]; then
        print_error "Failed to fetch ChromeDriver version for Chrome/Chromium version $browser_version. Please check network or install manually."
        rm -rf "$temp_dir" # Clean up temp dir
        return 1
    fi
    print_info "Latest available ChromeDriver version for Chrome $browser_version: $latest_chromedriver_version"

    # Construct download URL (new JSON endpoint)
    local download_url="https://storage.googleapis.com/chrome-for-testing-public/${latest_chromedriver_version}/linux64/chromedriver-linux64.zip"
    print_info "Downloading ChromeDriver from: $download_url"

    # Download and extract
    set +e # Don't exit if wget/unzip fails
    wget -q "$download_url" -O chromedriver_linux64.zip
    if [ $? -ne 0 ]; then
        print_error "Failed to download ChromeDriver zip file. Please check the URL or install manually."
        rm -rf "$temp_dir" # Clean up temp dir
        return 1
    fi

    unzip -o chromedriver_linux64.zip
    if [ $? -ne 0 ]; then
        print_error "Failed to unzip ChromeDriver archive."
        rm -rf "$temp_dir" # Clean up temp dir
        return 1
    fi
    set -e # Re-enable exit on error

    # Find the executable within the extracted folder (it's now inside a subfolder)
    local chromedriver_path=$(find . -name chromedriver -type f -print -quit)
    if [ -z "$chromedriver_path" ] || [ ! -f "$chromedriver_path" ]; then
         print_error "Could not find 'chromedriver' executable within the downloaded zip archive."
         rm -rf "$temp_dir" # Clean up temp dir
         return 1
    fi
    print_info "Found chromedriver executable at: $chromedriver_path"

    # Install to /usr/local/bin with proper permissions
    print_info "Moving chromedriver to /usr/local/bin/ (requires sudo)..."
    sudo mv "$chromedriver_path" /usr/local/bin/chromedriver
    sudo chown root:root /usr/local/bin/chromedriver
    sudo chmod +x /usr/local/bin/chromedriver

    # Cleanup
    cd "$ORIGINAL_DIR" # Go back to original dir
    rm -rf "$temp_dir"

    print_info "Manual ChromeDriver setup attempt complete."
    # Verify installation
    if command -v chromedriver &> /dev/null; then
        print_info "ChromeDriver command is now available."
        local installed_version=$(chromedriver --version | grep -oP 'ChromeDriver\s+\K\d+\.\d+\.\d+\.\d+' || echo "N/A")
        print_info "Installed ChromeDriver Version: $installed_version"
        return 0 # Success
    else
        print_error "Manual ChromeDriver installation failed. Command 'chromedriver' still not found."
        return 1 # Failure
    fi
}


if [ -n "$PKG_MANAGER" ] && [ -n "$INSTALL_CMD" ]; then
    echo
    read -p "Do you want to attempt to install/update Google Chrome/Chromium and ChromeDriver? (Required for Selenium features) [y/N]: " INSTALL_CHROME
    INSTALL_CHROME=$(echo "$INSTALL_CHROME" | tr '[:upper:]' '[:lower:]')

    if [[ "$INSTALL_CHROME" == "y" ]]; then
        GOOGLE_CHROME_INSTALLED_FLAG="false" # Track if google-chrome was installed specifically
        print_info "Attempting to install/update Chrome/Chromium and ChromeDriver using $PKG_MANAGER..."
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
                # Install Chromium and driver
                sudo $INSTALL_CMD chromium chromium-driver
                INSTALL_EXIT_CODE=$?
                CHROME_INSTALLED_VIA_PKG_MANAGER="true"
                ;;
            pacman)
                 # Use --needed to only install if missing or outdated
                sudo $INSTALL_CMD --needed chromium chromium-driver
                INSTALL_EXIT_CODE=$?
                CHROME_INSTALLED_VIA_PKG_MANAGER="true"
                ;;
            zypper)
                sudo $INSTALL_CMD chromium chromium-driver
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

        # Check if chromedriver command exists now
        CHROMEDRIVER_FOUND="false"
        if command -v chromedriver &> /dev/null; then
            print_info "ChromeDriver command found after installation attempt."
            CHROMEDRIVER_FOUND="true"
        else
             print_warning "ChromeDriver command not found after package manager installation attempt."
        fi

        # Attempt manual download if Google Chrome was installed via apt OR if chromedriver is still missing
        if [[ "$GOOGLE_CHROME_INSTALLED_FLAG" == "true" ]] || [[ "$CHROMEDRIVER_FOUND" == "false" ]]; then
             print_warning "Attempting manual ChromeDriver download/setup as fallback or required step..."
             setup_chromedriver # Attempt manual setup
             # setup_chromedriver prints its own success/failure
        fi

    else
        print_info "Skipping automatic Chrome/ChromeDriver installation."
        print_warning "Please ensure Chrome/Chromium and the matching ChromeDriver are installed manually for Selenium features."
    fi
else
    print_warning "Could not detect package manager. Skipping automatic Chrome/ChromeDriver installation."
    print_warning "Please ensure Chrome/Chromium and the matching ChromeDriver are installed manually for Selenium features."
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
# Use subshell to activate, install, and deactivate without affecting parent script's environment
(
    source "./host_venv/bin/activate"
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

    # Update ai_models.yml and .env (check if files exist)
    AI_MODELS_PATH="${ORIGINAL_DIR}/settings/llm_settings/ai_models.yml"
    if [ -f "$AI_MODELS_PATH" ]; then
        # Use # as sed delimiter
        sed -i "s#api_key: \"Somethingsomethinggminigapikey\"#api_key: \"${GEMINI_API_KEY}\"#g" "$AI_MODELS_PATH"
        print_info "Updated Gemini API key in $AI_MODELS_PATH"
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

    # Update ai_models.yml and .env (check if files exist)
    AI_MODELS_PATH="${ORIGINAL_DIR}/settings/llm_settings/ai_models.yml"
    if [ -f "$AI_MODELS_PATH" ]; then
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
echo
echo "Next Steps:"
echo
echo "1. Activate the virtual environment before running the script:"
echo "   source ./host_venv/bin/activate"
echo
echo "2. Run the report builder script (example):"
echo "   ${PYTHON_CMD} report_builder.py --topic \"Artificial Intelligence in Healthcare\" --keywords \"AI diagnostics, machine learning drug discovery\""
echo
echo "3. Ensure necessary API keys are correctly set in:"
echo "   - ${ROOT_ENV_PATH}"
echo "   - ${ORIGINAL_DIR}/settings/llm_settings/ai_models.yml (if modified)"
echo
echo "4. Verify Chrome/Chromium and a compatible ChromeDriver are installed if you rely on Selenium features."
echo
echo "5. To deactivate the environment when finished:"
echo "   deactivate"
echo