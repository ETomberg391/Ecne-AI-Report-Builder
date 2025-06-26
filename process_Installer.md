# Installer Script Comparison: Linux (Installer.sh) vs Windows (Installer.ps1)

## Functional Comparison

### 1. Core Setup
| Feature                | Installer.sh (Linux)                      | Installer.ps1 (Windows)               |
|------------------------|-------------------------------------------|----------------------------------------|
| Virtual Environment    | `host_venv` in project root              | `host_venv` in project root           |
| Python Command         | `python3` or `python`                    | `python` or `python3`                 |
| Dependency Installation| From `requirements_host.txt`              | From `requirements_host.txt`           |

### 2. OS Handling
| Feature                | Installer.sh                              | Installer.ps1                          |
|------------------------|-------------------------------------------|----------------------------------------|
| OS Detection           | Comprehensive (Linux distros + WSL)       | Windows version only                   |
| Package Manager        | Supports apt, pacman, dnf, yum, zypper    | Uses winget/choco                      |
| Admin Privileges       | Uses sudo per-command                     | Requires full admin session            |

### 3. Browser Handling
| Feature                | Installer.sh                              | Installer.ps1                          |
|------------------------|-------------------------------------------|----------------------------------------|
| Chrome Installation    | OS package manager or manual              | winget or direct download              |
| ChromeDriver Location  | `host_venv/bin/chromedriver`              | `host_venv\Scripts\chromedriver.exe`   |
| Version Matching       | Matches Chrome major version              | Matches Chrome major version           |

### 4. PDF Support (wkhtmltopdf)
| Feature                | Installer.sh                              | Installer.ps1                          |
|------------------------|-------------------------------------------|----------------------------------------|
| Installation Method    | OS-specific packages (apt, dnf, etc.)    | winget or direct download (.exe)       |
| Installation Location  | System package location                   | `C:\Program Files\wkhtmltopdf\bin\`     |
| Path Handling          | Uses existing system PATH                | Adds to Machine-level PATH             |
| Version Detection      | OS package manager versions              | 0.12.7-1.msvc2019-win64               |
| Fallback Strategy      | Multiple distro-specific attempts        | Direct GitHub release download         |

### 5. Configuration
| Feature                | Installer.sh                              | Installer.ps1                          |
|------------------------|-------------------------------------------|----------------------------------------|
| .env Setup             | Copies from env.example                   | Copies from env.example                |
| API Configuration      | Interactive for Google/Brave              | Interactive for Google/Brave           |
| LLM Setup              | Supports Gemini/OpenAI                    | Supports Gemini/OpenAI                 |

## Key Differences Summary
1. **Prerequisite Installation**:
   - Linux script installs missing dependencies automatically
   - Windows script only verifies existence

2. **Path Management**:
   - Windows script adds venv to system PATH
   - Linux script relies on manual activation

3. **Execution Context**:
   - Windows requires admin privileges upfront
   - Linux uses sudo as needed

4. **Browser Handling**:
   - Windows uses known Chrome paths
   - Linux detects various installation locations

5. **User Experience**:
   - PowerShell provides richer output formatting
   - Bash script has more detailed OS detection