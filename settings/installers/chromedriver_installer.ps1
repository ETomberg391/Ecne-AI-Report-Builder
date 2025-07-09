# PowerShell Script to Check and Update ChromeDriver

# --- Helper Functions ---
function Write-Info {
    param([string]$Message)
    Write-Host "INFO: $Message"
}

function Write-Warning {
    param([string]$Message)
    Write-Host "WARNING: $Message"
}

function Write-Error {
    param([string]$Message)
    Write-Host "ERROR: $Message"
}

# --- Main Script ---
Write-Info "Starting ChromeDriver check for Windows..."

# --- Find Chrome ---
$chromeExePath = ""
$chromePaths = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)

foreach ($path in $chromePaths) {
    if (Test-Path $path -PathType Leaf) {
        $chromeExePath = $path
        break
    }
}

if (-not $chromeExePath) {
    Write-Error "Google Chrome is not found on this system."
    exit 1
}

Write-Info "Found Chrome at: $chromeExePath"

# --- Get Chrome Version ---
try {
    $chromeVersion = (Get-Item $chromeExePath).VersionInfo.FileVersion
    $chromeMajorVersion = $chromeVersion.Split(".")[0]
    Write-Info "Detected Chrome version: $chromeVersion (Major: $chromeMajorVersion)"
} catch {
    Write-Error "Failed to get Chrome version: $_"
    exit 1
}

# --- Check Existing ChromeDriver ---
# Determine the project root directory based on the script's location
$scriptDir = $PSScriptRoot
$projectRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$venvPath = Join-Path $projectRoot "host_venv"

if (-not (Test-Path $venvPath -PathType Container)) {
    Write-Error "Virtual environment not found at '$venvPath'. The script assumes it is in 'settings/installers' relative to the project root."
    exit 1
}

$chromedriverPath = Join-Path $venvPath "Scripts\chromedriver.exe"
$shouldInstallChromedriver = $true

if (Test-Path $chromedriverPath) {
    try {
        # The output of chromedriver --version can go to stderr, so redirect it.
        $driverVersionOutput = & $chromedriverPath --version 2>&1
        $driverVersion = $driverVersionOutput[0] -replace 'ChromeDriver\s+([0-9\.]+).*', '$1'
        
        Write-Info "Found existing ChromeDriver version: $driverVersion"
        
        if ($driverVersion -match "^$chromeMajorVersion\.") {
            Write-Info "ChromeDriver version is compatible with Chrome."
            $shouldInstallChromedriver = $false
        } else {
            Write-Warning "ChromeDriver version mismatch. Will proceed with update."
        }
    } catch {
        Write-Warning "Could not determine existing ChromeDriver version. Will proceed with update."
    }
} else {
    Write-Info "ChromeDriver not found. Will proceed with installation."
}

# --- Download and Install ---
if ($shouldInstallChromedriver) {
    Write-Info "Attempting to download and install matching ChromeDriver..."
    try {
        # Set modern security protocol to avoid connection issues
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Write-Info "Fetching latest ChromeDriver version information..."
        $versionsJsonUrl = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
        
        # Use Invoke-WebRequest for more robust download, then convert from JSON
        Write-Info "Downloading version data from $versionsJsonUrl"
        $response = Invoke-WebRequest -Uri $versionsJsonUrl -UseBasicParsing
        $versionsJson = $response.Content | ConvertFrom-Json
        Write-Info "Successfully downloaded and parsed version data."
        
        $matchingVersions = $versionsJson.versions | Where-Object { $_.version.StartsWith("$chromeMajorVersion.") -and $_.downloads.chromedriver }
        if (-not $matchingVersions) {
            throw "No matching ChromeDriver version found for Chrome $chromeMajorVersion."
        }
        
        $latestVersion = $matchingVersions | Sort-Object { [version]$_.version } -Descending | Select-Object -First 1
        Write-Info "Found best matching ChromeDriver version: $($latestVersion.version)"
        
        $downloadUrl = $latestVersion.downloads.chromedriver | Where-Object { $_.platform -eq 'win64' } | Select-Object -ExpandProperty url
        if (-not $downloadUrl) {
            throw "No win64 ChromeDriver download found for version $($latestVersion.version)."
        }
        
        Write-Info "Downloading from: $downloadUrl"
        $tempZip = "$env:TEMP\chromedriver_win64.zip"
        $tempExtractDir = "$env:TEMP\chromedriver_extract"
        
        Invoke-WebRequest $downloadUrl -OutFile $tempZip -UseBasicParsing
        
        Write-Info "Extracting archive..."
        if (Test-Path $tempExtractDir) {
            Remove-Item $tempExtractDir -Recurse -Force
        }
        Expand-Archive $tempZip -DestinationPath $tempExtractDir -Force
        
        $extractedDriver = Get-ChildItem -Path $tempExtractDir -Recurse -Filter "chromedriver.exe" | Select-Object -First 1
        if (-not $extractedDriver) {
            throw "chromedriver.exe not found in the downloaded archive."
        }
        
        $destinationDir = Join-Path $venvPath "Scripts"
        Write-Info "Installing to: $destinationDir"
        Copy-Item $extractedDriver.FullName $destinationDir -Force
        
        # Cleanup
        Remove-Item $tempZip -Force
        Remove-Item $tempExtractDir -Recurse -Force
        
        Write-Info "ChromeDriver installation successful."
        $installedVersion = & $chromedriverPath --version 2>&1
        Write-Info "Installed version: $($installedVersion[0])"
    } catch {
        Write-Error "Failed to install ChromeDriver: $_"
        exit 1
    }
} else {
    Write-Info "Update process finished. No installation was needed."
}

exit 0