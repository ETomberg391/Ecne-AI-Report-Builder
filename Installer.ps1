# Windows Native Installer for Report Builder
# Requires PowerShell 5.1 or later

# Ensure we're running as admin
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Please run this script as Administrator. Right-click and select 'Run as Administrator'." -ForegroundColor Red
    exit 1
}

function Write-Info {
    param([string]$Message)
    Write-Host "INFO: $Message" -ForegroundColor Cyan
}

function Write-Warning {
    param([string]$Message)
    Write-Host "WARNING: $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "ERROR: $Message" -ForegroundColor Red
}

# Show header
Write-Host "-----------------------------------------------------"
Write-Host " Report Builder Environment Setup Script             "
Write-Host "-----------------------------------------------------"

# Check Windows version
$osInfo = Get-WmiObject Win32_OperatingSystem
$windowsVersion = [System.Environment]::OSVersion.Version.Major
Write-Info "Detected Windows $windowsVersion"

# Check prerequisites
Write-Info "Checking core prerequisites..."

# Check Python installation
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python 3") {
        Write-Info "Found Python: $pythonVersion"
        $pythonCmd = "python"
        $pipCmd = "pip"
    } else {
        Write-Info "Checking for python3 command..."
        $python3Version = python3 --version 2>&1
        if ($python3Version -match "Python 3") {
            Write-Info "Found Python: $python3Version"
            $pythonCmd = "python3"
            $pipCmd = "pip3"
        } else {
            Write-Error "Python 3 not found. Please install Python 3 from https://www.python.org/downloads/"
            exit 1
        }
    }
} catch {
    Write-Error "Python 3 not found. Please install Python 3 from https://www.python.org/downloads/"
    exit 1
}

# Check Git installation
try {
    $gitVersion = git --version
    Write-Info "Found Git: $gitVersion"
} catch {
    Write-Error "Git not found. Please install Git from https://git-scm.com/download/win"
    exit 1
}

Write-Info "Core prerequisites met."

# Set up Python virtual environment FIRST
Write-Info "Setting up Python virtual environment..."
$venvPath = ".\host_venv"
if (-not (Test-Path $venvPath)) {
    Write-Info "Creating virtual environment at $venvPath using $pythonCmd..."
    & $pythonCmd -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment."
        exit 1
    }
} else {
    Write-Warning "Virtual environment '$venvPath' already exists. Skipping creation."
    Write-Warning "If you encounter issues, delete the '$venvPath' directory and run this script again."
}

# Define paths within the venv
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvPip = Join-Path $venvPath "Scripts\pip.exe"

# Check if venv executables exist
if (-not (Test-Path $venvPython -PathType Leaf)) {
    Write-Error "Python executable not found in virtual environment: $venvPython"
    Write-Error "The virtual environment might be corrupted. Try deleting '$venvPath' and running the script again."
    exit 1
}

# Determine pip command to use (prefer direct executable, fallback to module)
$pipCmdToUse = if (Test-Path $venvPip -PathType Leaf) { $venvPip } else { "$venvPython -m pip" }
if (-not (Test-Path $venvPip -PathType Leaf)) {
    Write-Warning "pip executable not found at $venvPip. Using '$pipCmdToUse' instead."
}

# Install dependencies using the venv's Python/pip
Write-Info "Installing Python dependencies into the virtual environment..."

Write-Info "Upgrading pip within the virtual environment..."
& $pipCmdToUse install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Failed to upgrade pip within the virtual environment. Continuing..."
    # Continue anyway, might work with existing pip
}

if (Test-Path "requirements_host.txt") {
    Write-Info "Installing dependencies from requirements_host.txt into the virtual environment..."
    & $pipCmdToUse install -r "requirements_host.txt"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install dependencies from requirements_host.txt into the virtual environment."
        exit 1
    }
} else {
    Write-Error "requirements_host.txt not found. Cannot install dependencies."
    exit 1
}

# Chrome and ChromeDriver Installation (AFTER venv setup)
Write-Info "Checking for Chrome installation..."
$chromeInstalled = Test-Path "C:\Program Files\Google\Chrome\Application\chrome.exe" -PathType Leaf
$chromeInstalledX86 = Test-Path "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" -PathType Leaf

if (-not ($chromeInstalled -or $chromeInstalledX86)) {
    $installChrome = Read-Host "Chrome not found. Would you like to install Google Chrome? [Y/n]"
    if ($installChrome -ne 'n') {
        Write-Info "Installing Google Chrome..."
        try {
            # First try using winget
            if (Get-Command winget -ErrorAction SilentlyContinue) {
                Write-Info "Using winget to install Chrome..."
                winget install -e --accept-source-agreements --accept-package-agreements Google.Chrome
            } else {
                # Fallback to direct download
                Write-Info "Downloading Chrome installer..."
                $installer = "$env:TEMP\chrome_installer.exe"
                Invoke-WebRequest "https://dl.google.com/chrome/install/latest/chrome_installer.exe" -OutFile $installer
                Start-Process -FilePath $installer -Args "/silent /install" -Wait
                Remove-Item $installer
            }
            Write-Info "Chrome installation complete."
        } catch {
            Write-Error "Failed to install Chrome: $_"
            Write-Warning "Please install Chrome manually from https://www.google.com/chrome/"
        }
    }
}

# Check existing ChromeDriver and get Chrome version
Write-Info "Checking ChromeDriver installation..."
$chromeExe = if ($chromeInstalled) { "C:\Program Files\Google\Chrome\Application\chrome.exe" } else { "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" }
$chromeVersion = (Get-Item $chromeExe).VersionInfo.FileVersion
$chromeMajorVersion = $chromeVersion.Split(".")[0]
Write-Info "Detected Chrome version: $chromeVersion (Major: $chromeMajorVersion)"

# Check if ChromeDriver is already installed and matches Chrome version
# Note: $venvPath is defined earlier in the venv setup block
$chromedriverPath = Join-Path $venvPath "Scripts\chromedriver.exe"
$shouldInstallChromedriver = $true

if (Test-Path $chromedriverPath) {
    try {
        $driverVersion = (& $chromedriverPath --version 2>&1)[0] -replace 'ChromeDriver\s+(\d+\.\d+\.\d+\.\d+).*', '$1'
        Write-Info "Found existing ChromeDriver version: $driverVersion"
        
        if ($driverVersion -match "^$chromeMajorVersion\.") {
            Write-Info "Existing ChromeDriver is compatible with Chrome version $chromeMajorVersion"
            $shouldInstallChromedriver = $false
        } else {
            Write-Info "ChromeDriver version mismatch. Will update to match Chrome version $chromeMajorVersion"
        }
    } catch {
        Write-Info "Could not determine existing ChromeDriver version"
    }
}

# Download and install ChromeDriver if needed
if ($shouldInstallChromedriver) {
    Write-Info "Installing matching ChromeDriver..."
    try {
    Write-Info "Getting latest ChromeDriver version information..."
    $versionsJson = (Invoke-WebRequest "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json" -UseBasicParsing).Content | ConvertFrom-Json
    
    # Get the latest version that matches our Chrome major version
    $matchingVersions = $versionsJson.versions | Where-Object { $_.version.StartsWith("$chromeMajorVersion.") -and $_.downloads.chromedriver }
    if (-not $matchingVersions) {
        throw "No matching ChromeDriver version found for Chrome $chromeMajorVersion"
    }
    
    $latestVersion = $matchingVersions | Sort-Object { [version]$_.version } -Descending | Select-Object -First 1
    Write-Info "Found matching ChromeDriver version: $($latestVersion.version)"
    
    # Get download URL for win64 platform
    $downloadUrl = $latestVersion.downloads.chromedriver | Where-Object { $_.platform -eq 'win64' } | Select-Object -ExpandProperty url
    if (-not $downloadUrl) {
        throw "No win64 ChromeDriver download found for version $($latestVersion.version)"
    }
    
    Write-Info "Downloading ChromeDriver from: $downloadUrl"
    $driverZip = "$env:TEMP\chromedriver_win64.zip"
    # Use Join-Path for robustness
    $driverDir = Join-Path $venvPath "Scripts"

    Invoke-WebRequest $downloadUrl -OutFile $driverZip
    
    Write-Info "Extracting ChromeDriver..."
    Expand-Archive $driverZip -DestinationPath "$env:TEMP\chromedriver" -Force
    
    Write-Info "Installing ChromeDriver to $driverDir..."
    $chromeDriverExe = Get-ChildItem -Path "$env:TEMP\chromedriver" -Recurse -Filter "chromedriver.exe" | Select-Object -First 1
    if (-not $chromeDriverExe) {
        throw "chromedriver.exe not found in extracted contents"
    }
    
    # Ensure the target directory exists (it should, as venv created it)
    if (-not (Test-Path $driverDir -PathType Container)) {
        # This case should ideally not happen if venv creation was successful
        Write-Warning "Virtual environment Scripts directory '$driverDir' not found. Attempting to create."
        New-Item -ItemType Directory -Path $driverDir -Force | Out-Null
    }
    
    Copy-Item $chromeDriverExe.FullName $driverDir -Force
    
    # Cleanup
    Remove-Item $driverZip -ErrorAction SilentlyContinue
    Remove-Item "$env:TEMP\chromedriver" -Recurse -Force -ErrorAction SilentlyContinue

        Write-Info "ChromeDriver installation complete."
        $installedVersion = & "$driverDir\chromedriver.exe" --version
        Write-Info "Installed ChromeDriver version: $installedVersion"
    } catch {
        Write-Error "Failed to install ChromeDriver: $_"
        Write-Warning "Please install ChromeDriver manually from https://googlechromelabs.github.io/chrome-for-testing/"
    }
} else {
    Write-Info "Skipping ChromeDriver installation - existing version is compatible."
}

# Install wkhtmltopdf for PDF generation
Write-Info "Checking wkhtmltopdf installation..."
$wkhtmltopdfPath = "C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
$wkhtmltopdfInstalled = Test-Path $wkhtmltopdfPath -PathType Leaf

if (-not $wkhtmltopdfInstalled) {
    $installWkhtmltopdf = Read-Host "wkhtmltopdf not found. Would you like to install it for PDF report generation? [Y/n]"
    if ($installWkhtmltopdf -ne 'n') {
        Write-Info "Installing wkhtmltopdf..."
        try {
            # First try using winget
            if (Get-Command winget -ErrorAction SilentlyContinue) {
                Write-Info "Using winget to install wkhtmltopdf..."
                winget install wkhtmltopdf.wkhtmltopdf -e --accept-source-agreements --accept-package-agreements
            } else {
                # Fallback to direct download
                Write-Info "Downloading wkhtmltopdf installer..."
                $installerUrl = "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.7-1/wkhtmltox-0.12.7-1.msvc2019-win64.exe"
                $installer = "$env:TEMP\wkhtmltopdf_installer.exe"
                Invoke-WebRequest $installerUrl -OutFile $installer
                Start-Process -FilePath $installer -Args "/S" -Wait
                Remove-Item $installer
            }
            
            # Add to PATH if not already present
            $currentPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
            $wkhtmltopdfDir = "C:\Program Files\wkhtmltopdf\bin"
            if ($currentPath -notlike "*$wkhtmltopdfDir*") {
                [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$wkhtmltopdfDir", "Machine")
                $env:PATH = "$env:PATH;$wkhtmltopdfDir"
                Write-Info "Added wkhtmltopdf to system PATH"
            }
            
            Write-Info "wkhtmltopdf installation complete."
            # Verify installation
            $wkhtmltopdfVersion = & $wkhtmltopdfPath --version
            Write-Info "Installed wkhtmltopdf version: $wkhtmltopdfVersion"
        } catch {
            Write-Error "Failed to install wkhtmltopdf: $_"
            Write-Warning "Please install wkhtmltopdf manually from https://wkhtmltopdf.org/downloads.html"
        }
    }
} else {
    Write-Info "wkhtmltopdf is already installed at: $wkhtmltopdfPath"
    try {
        $wkhtmltopdfVersion = & $wkhtmltopdfPath --version
        Write-Info "Current wkhtmltopdf version: $wkhtmltopdfVersion"
    } catch {
        Write-Warning "Could not determine wkhtmltopdf version"
    }
}

# Set up configuration files
Write-Info "Setting up configuration files..."
$envPath = ".env"
$exampleEnvPath = ".\settings\env.example"

if (Test-Path $envPath) {
    Write-Warning ".env file already exists. Skipping copy."
    Write-Warning "Please review your existing .env file: $envPath"
} else {
    if (Test-Path $exampleEnvPath) {
        Copy-Item $exampleEnvPath $envPath
        Write-Info "Copied settings/env.example to .env"
    } else {
        Write-Warning "settings/env.example not found. Cannot create .env."
        Write-Warning "Please create the .env file manually with necessary API keys."
    }
}

# Check if ai_models.yml exists, copy from example if not
$aiModelsPath = ".\settings\llm_settings\ai_models.yml"
$exampleAiModelsPath = ".\settings\llm_settings\ai_models.example.yml"

if (-not (Test-Path $aiModelsPath)) {
    Write-Info "$aiModelsPath not found. Checking for example file..."
    if (Test-Path $exampleAiModelsPath) {
        Write-Info "Copying $exampleAiModelsPath to $aiModelsPath..."
        try {
            Copy-Item $exampleAiModelsPath $aiModelsPath -Force
            Write-Info "Successfully created $aiModelsPath from example."
        } catch {
            Write-Error "Failed to copy $exampleAiModelsPath to ${aiModelsPath}: $_"
            Write-Warning "LLM configuration might not be set correctly. Please check $aiModelsPath manually."
        }
    } else {
        Write-Warning "$exampleAiModelsPath not found. Cannot create $aiModelsPath automatically."
        Write-Warning "LLM configuration might not be set correctly. Please ensure $aiModelsPath exists and is configured."
    }
} else {
    Write-Info "$aiModelsPath already exists."
}

    if (Test-Path $envPath) {
        (Get-Content $envPath) |
# Add venv Scripts directory to User PATH if not already present
Write-Info "Ensuring venv Scripts directory is in User PATH..."
try {
    $venvScriptsPath = Resolve-Path ".\host_venv\Scripts" # Get full path
    $currentUserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($currentUserPath -notlike "*$($venvScriptsPath.Path)*") {
        Write-Info "Adding $($venvScriptsPath.Path) to User PATH."
        # Ensure no trailing semicolon if current path is empty or ends with one
        $newPath = if ([string]::IsNullOrEmpty($currentUserPath) -or $currentUserPath.EndsWith(";")) {
                       "$currentUserPath$($venvScriptsPath.Path)"
                   } else {
                       "$currentUserPath;$($venvScriptsPath.Path)"
                   }
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
        # Update current session's PATH as well
        $env:PATH = "$env:PATH;$($venvScriptsPath.Path)"
        Write-Warning "User PATH updated. You MUST restart your terminal or VS Code for this change to take full effect in new sessions."
    } else {
        Write-Info "venv Scripts directory already found in User PATH."
    }
} catch {
    Write-Error "Failed to update User PATH: $_"
    Write-Warning "ChromeDriver might not be automatically found. Ensure '.\host_venv\Scripts' is in your PATH."
}
            ForEach-Object { $_ -replace '^DEFAULT_MODEL_CONFIG=.*', 'DEFAULT_MODEL_CONFIG="default_model"' } |
            Set-Content $envPath
        Write-Info "Set DEFAULT_MODEL_CONFIG to 'default_model' in .env"
    }

# Final Instructions
Write-Host "`n---------------------------------------------"
Write-Host " Setup Complete! "
Write-Host "---------------------------------------------`n"

Write-Host "This script has set up the basic environment required for 'report_builder.py'.`n"

Write-Host "Next Steps:`n"
Write-Host "For PowerShell users:"
Write-Host "1. Activate the virtual environment:"
Write-Host "   .\host_venv\Scripts\Activate.ps1"
Write-Host "2. Run the report builder:"
Write-Host "   python report_builder.py --topic `"Artificial Intelligence in Healthcare`" --keywords `"AI diagnostics, machine learning drug discovery`"`n"

Write-Host "For Command Prompt (CMD) users:"
Write-Host "1. Activate the virtual environment:"
Write-Host "   host_venv\Scripts\activate.bat"
Write-Host "2a. Run the report builder normal web search test:"
Write-Host "   python report_builder.py --topic `"Artificial Intelligence in Healthcare`" --keywords `"AI diagnostics, machine learning drug discovery`"`n"
Write-Host "2b. Run the report builder quick documents test:"
Write-Host " python report_builder.py --topic `"What are Precise reforges in Mabinogi?`" --guidance `"Please use the following documents to find out what are Precise Reforges, how to get them with all the Free to play mechanics, what's recommended methods to acquire, what's not recommended, what do precise reforges do exactly, and a small sub section of what are journeyman reforges.`" --reference-docs-folder research\Example_Docs_Folder --no-search`"`n"

Write-Host "Other Important Steps:"
Write-Host "3. Ensure necessary API keys are correctly set in:"
Write-Host "   - .env"
Write-Host "   - .\settings\llm_settings\ai_models.yml (if modified)`n"

Write-Host "4. Verify Chrome and ChromeDriver are working if you rely on Selenium features."
Write-Host "5. PDF report generation is configured with wkhtmltopdf. If you skipped installation,"
Write-Host "   install it manually from https://wkhtmltopdf.org/downloads.html`n"

Write-Host "6. To deactivate the environment when finished (works in both PowerShell and CMD):"
Write-Host "   deactivate`n"

Write-Host "Note: The environment can be used from either PowerShell or Command Prompt (CMD)."
Write-Host "      Just remember to use the correct activation command for your terminal type.`n"
