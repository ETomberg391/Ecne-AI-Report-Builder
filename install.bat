@echo off
setlocal enabledelayedexpansion

echo.
echo =====================================================
echo  Report Builder Environment Setup Script (Windows)
echo =====================================================
echo.

:: Change to the directory where this batch file is located
cd /d "%~dp0"

:: Check admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator privileges...
    echo This is required to install system components and add paths.
    echo.
    set "args=%*"
    set "args=!args:"=\"!"
    PowerShell -Command "Start-Process -FilePath \"%~s0\" -ArgumentList \"!args!\" -Verb RunAs -WorkingDirectory \"%~dp0\""
    exit /b
)

echo Running with administrator privileges...
echo Working directory: %CD%
echo.

:: Check if PowerShell is available
PowerShell -Command "Write-Host 'PowerShell is available'" >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: PowerShell is not available on this system.
    echo Please install PowerShell 5.1 or later.
    pause
    exit /b 1
)

:: Check if we're in the correct directory (should contain Installer.ps1 and requirements_host.txt)
if not exist "Installer.ps1" (
    echo ERROR: Installer.ps1 not found in current directory: %CD%
    echo Please ensure install.bat is in the project root directory.
    pause
    exit /b 1
)

if not exist "requirements_host.txt" (
    echo ERROR: requirements_host.txt not found in current directory: %CD%
    echo Please ensure install.bat is in the project root directory.
    pause
    exit /b 1
)

echo Verified project files found in: %CD%
echo.

echo Executing PowerShell installer script...
echo.

:: Run PowerShell script with execution policy bypass and correct working directory
PowerShell -ExecutionPolicy Bypass -Command "Set-Location '%CD%'; & '.\Installer.ps1'"

:: Check if PowerShell script succeeded
if %errorLevel% neq 0 (
    echo.
    echo ERROR: PowerShell installer script failed with exit code %errorLevel%
    echo Please review the error messages above.
    pause
    exit /b %errorLevel%
)

echo.
echo =====================================================
echo  Installation completed successfully!
echo =====================================================
echo.
echo You can now close this window and use the environment from:
echo - Command Prompt (CMD)
echo - PowerShell 
echo - VS Code Terminal
echo.
echo To activate the environment in any terminal:
echo   host_venv\Scripts\activate.bat    (for CMD)
echo   .\host_venv\Scripts\Activate.ps1  (for PowerShell)
echo.

:: Pause to allow user to read the completion message
pause
