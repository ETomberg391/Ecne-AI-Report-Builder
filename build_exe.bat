@echo off
setlocal enabledelayedexpansion

echo Cleaning previous builds...
rmdir /s /q build_venv 2>nul
rmdir /s /q dist 2>nul
rmdir /s /q build 2>nul

echo Creating virtual environment...
python -m venv build_venv || (
    echo Failed to create virtual environment
    exit /b 1
)

call build_venv\Scripts\activate || (
    echo Failed to activate virtual environment
    exit /b 1
)

echo Installing dependencies...
pip install --upgrade pip || exit /b
pip install -r requirements_host.txt || exit /b
pip install pyinstaller || exit /b

echo Checking Chrome installation...
reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version >nul 2>&1 || (
    echo Chrome not detected. Please install Chrome first.
    exit /b 1
)

for /f "tokens=3" %%i in ('reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version') do set chrome_ver=%%i
set chrome_major=%chrome_ver:~0,1%

echo Downloading ChromeDriver v%chrome_major%...
curl -s https://chromedriver.storage.googleapis.com/LATEST_RELEASE_%chrome_major% > chromedriver-version.txt || (
    echo Failed to get ChromeDriver version
    exit /b 1
)
set /p driver_ver=<chromedriver-version.txt
del chromedriver-version.txt

echo Downloading ChromeDriver !driver_ver!...
curl -sSOL https://chromedriver.storage.googleapis.com/%driver_ver%/chromedriver_win32.zip || (
    echo Failed to download ChromeDriver
    exit /b 1
)

powershell -Command "Expand-Archive -Path chromedriver_win32.zip -DestinationPath . -Force" || (
    echo Failed to extract ChromeDriver
    exit /b 1
)
del chromedriver_win32.zip

echo Building executable...
pyinstaller report_builder.spec --clean --noconfirm || (
    echo Build failed
    exit /b 1
)

echo Cleaning up...
deactivate
rmdir /s /q build_venv

echo.
echo Build successful! EXE location: %CD%\dist\ReportBuilder.exe