@echo off
setlocal enabledelayedexpansion

echo.
echo ===============================================
echo  Report Builder Flask App Launcher
echo ===============================================
echo.

:: Change to the directory where this batch file is located
cd /d "%~dp0"

:: Show current directory for debugging
echo Current directory: %CD%
echo.

:: Check if virtual environment exists
set "VENV_PATH=host_venv"
if not exist "%VENV_PATH%" (
    echo ERROR: Virtual environment not found at %VENV_PATH%
    echo.
    echo Please create a virtual environment first:
    echo   python -m venv host_venv
    echo   host_venv\Scripts\activate.bat
    echo   pip install -r requirements_host.txt
    echo.
    echo Or run install.bat to set up the complete environment.
    pause
    exit /b 1
)

:: Check if activation script exists
set "ACTIVATE_SCRIPT=%VENV_PATH%\Scripts\activate.bat"
if not exist "%ACTIVATE_SCRIPT%" (
    echo ERROR: Virtual environment activation script not found at %ACTIVATE_SCRIPT%
    echo The virtual environment may be corrupted. Try deleting %VENV_PATH% and running install.bat
    pause
    exit /b 1
)

:: Activate the virtual environment
echo Activating virtual environment
call "%ACTIVATE_SCRIPT%"

:: First verify requirements_host.txt exists before any dependency checks
echo Verifying requirements_host.txt exists...
if exist "requirements_host.txt" (
    echo Found requirements_host.txt at: %CD%\requirements_host.txt
) else (
    echo ERROR: requirements_host.txt not found in: %CD%
    echo Please ensure the file exists in the project root directory.
    pause
    exit /b 1
)

:: Check if required modules are installed
echo Checking required dependencies
set "need_install=0"

python -c "import flask" >nul 2>&1
if %errorLevel% neq 0 (
    echo - Flask: MISSING
    set "need_install=1"
) else (
    echo - Flask: OK
)

python -c "import newspaper" >nul 2>&1
if %errorLevel% neq 0 (
    echo - newspaper4k: MISSING
    set "need_install=1"
) else (
    echo - newspaper4k: OK
)

python -c "import selenium" >nul 2>&1
if %errorLevel% neq 0 (
    echo - selenium: MISSING
    set "need_install=1"
) else (
    echo - selenium: OK
)

if %need_install% equ 1 (
    echo.
    echo Some dependencies are missing. Installing from requirements_host.txt
    echo Installing requirements (this may take a few minutes)
    pip install -r requirements_host.txt
    if %errorLevel% neq 0 (
        echo ERROR: Failed to install requirements
        echo Try running: pip install -r requirements_host.txt manually
        pause
        exit /b 1
    )
    echo Dependencies installed successfully.
    echo.
) else (
    echo All key dependencies found.
    echo.
)

:: Check if .env file exists
if not exist ".env" (
    echo WARNING: .env file not found. You may need to configure API keys.
    echo You can copy settings\env.example to .env and fill in your API keys.
    echo.
)

:: Check if app.py exists
if not exist "app.py" (
    echo ERROR: app.py not found in current directory
    echo Please ensure you are running this script from the project root directory.
    pause
    exit /b 1
)

:: Diagnostic: Check Python environment and module imports
echo.
echo Diagnostic: Python environment information
python -c "import sys; print(sys.executable)"
python -c "import sys; print('\n'.join(sys.path))"

echo Testing newspaper import...
python -c "import newspaper; print('newspaper version:', newspaper.__version__)" || echo Newspaper import failed

echo Testing Flask import...
python -c "import flask; print('Flask version:', flask.__version__)" || echo Flask import failed

echo.

:: Run the Flask application
echo Starting Flask application
echo The app will be available at: http://localhost:5000
echo Press Ctrl+C to stop the application
echo.

start http://127.0.0.1:5000
python app.py

:: Pause on exit so user can see any error messages
if %errorLevel% neq 0 (
    echo.
    echo Application exited with error code %errorLevel%
    pause
)