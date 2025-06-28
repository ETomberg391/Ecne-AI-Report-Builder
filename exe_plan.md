# EXE Conversion Plan for Report Builder

## 1. Core Packaging Strategy
- **PyInstaller Configuration**: Create spec file with frozen paths
- **Dependency Bundling**: Include virtual env, ChromeDriver, NTLK data
- **Path Management**: Use `sys._MEIPASS` for resource loading

```python
# report_builder.spec
a = Analysis(
    ['app.py'],
    datas=[
        ('templates/*', 'templates'),
        ('static/*', 'static'),
        ('host_venv/Lib/site-packages', 'lib'),
        ('chromedriver.exe', '.')
    ],
    hiddenimports=['engineio', 'dotenv', 'nltk'],
    hookspath=[]
)
```

## 2. ChromeDriver Management
- **PS1 Script Preservation**:
  ```python
  # Maintain core Installer.ps1 logic in Python subprocess
  def update_chromedriver():
      ps_script = '''
      # Preserved from Installer.ps1
      $chromePath = "${Env:ProgramFiles}\Google\Chrome\Application\chrome.exe"
      $versionInfo = (Get-Item $chromePath).VersionInfo
      $chromeVersion = "$($versionInfo.Major).$($versionInfo.Minor).$($versionInfo.Build)"
      $driverVersion = (Invoke-RestMethod "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$($versionInfo.Major)").Trim()
      
      Invoke-WebRequest "https://chromedriver.storage.googleapis.com/$driverVersion/chromedriver_win32.zip" -OutFile "$env:TEMP\chromedriver.zip"
      Expand-Archive -Path "$env:TEMP\chromedriver.zip" -DestinationPath "$PSScriptRoot" -Force
      '''
      subprocess.run([
          'powershell',
          '-ExecutionPolicy', 'Bypass',
          '-Command', ps_script
      ], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
  ```
- **EXE Integration**:
  - Bundle chromedriver.exe in PyInstaller resources
  - Store in %LOCALAPPDATA% without admin requirements
  - Same path handling as original PS1 scripts

## 3. NTLK Integration
- **PS1 Script Adaptation**:
  ```python
  # Convert NTLK installer logic to Python
  def setup_ntlk():
      ps_script = '''
      # Preserved from Installer.ps1
      $nltkPath = Join-Path $env:APPDATA "nltk_data"
      if (-not (Test-Path (Join-Path $nltkPath "corpora\stopwords"))) {
          python -m nltk.downloader stopwords punkt -d $nltkPath
      }
      '''
      subprocess.run([
          'powershell',
          '-ExecutionPolicy', 'Bypass',
          '-Command', ps_script
      ], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
  ```
- **First-Run Setup**:
  - Automatic check on application launch
  - Progress display in settings UI
- **Integrated Management** in `app.py`:
  - /api/chromedriver/status endpoint
  - /api/chromedriver/update POST endpoint
  - Settings UI integration with version display
  - Error handling for missing Chrome/driver

## 3. NTLK Integration
- **PS1 Script Replacement**: Remove Installer.ps1 dependencies
- **First-Run Setup** in `utils.py`:
  - Automatic download of required datasets
  - Local storage in AppData directory
- **Manual Management**:
  - Settings page "Check NTLK" button
  - API endpoints for status checks/reinstallation
  - Progress display during downloads
```python
@app.route('/chromedriver/status')
def chromedriver_status():
    # Version checking logic
    return jsonify(status)

@app.route('/chromedriver/update', methods=['POST'])  
def update_chromedriver():
    # Download matching version
    return jsonify(result)
```

## 3. NTLK Integration
- **First-Run Setup** in `utils.py`:
```python
def setup_ntlk_data():
    nltk_data_path = os.path.join(appdata, 'nltk_data')
    required_data = ['punkt', 'stopwords', 'wordnet']
    for data in required_data:
        if not nltk.data.find(f'tokenizers/{data}'):
            nltk.download(data, download_dir=nltk_data_path)
```

- **Settings UI Integration**:
```html
<div class="component-status">
    <h3>NTLK Data <button id="check-ntlk">Check/Install</button></h3>
    <div id="ntlk-status">
        <p>Installed Packages: <span class="data-status">Loading...</span></p>
    </div>
</div>
```

- **Backend Endpoints** in `app.py`:
```python
@app.route('/api/ntlk_status')
def ntlk_status():
    installed = []
    for data in ['punkt', 'stopwords', 'wordnet']:
        installed.append(data if nltk.data.find(f'tokenizers/{data}') else None)
    return jsonify({"installed": [x for x in installed if x]})

@app.route('/api/install_ntlk', methods=['POST'])
def install_ntlk():
    try:
        setup_ntlk_data()
        return jsonify({"status": "success", "message": "NTLK data installed"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
```

## 4. Auto-Start Implementation
- **Server Thread** in EXE main:
```python
if __name__ == '__main__':
    threading.Thread(target=app.run).start()
    webbrowser.open('http://localhost:5000')
```

## 5. Settings Page Updates
```html
<!-- System Components Section -->
<div class="component-status">
    <h3>ChromeDriver Manager</h3>
    <button id="check-driver">Check Version</button>
    <div id="driver-status"></div>
</div>
```

**Implementation Checklist**:
- [ ] Create PyInstaller build script
- [ ] Modify path handling for frozen EXE
- [ ] Add ChromeDriver version API endpoints
- [ ] Implement NTLK status/install endpoints
- [ ] Add NTLK UI components to settings
- [ ] Bundle core NTLK data files
- [ ] Implement GUI management controls
- [ ] Add first-run auto-setup for NTLK

**Migration Sequence**:
```mermaid
sequenceDiagram
    User->>EXE: Launch
    EXE->>System: Check dependencies
    EXE->>Flask: Start embedded server
    EXE->>Browser: Open 127.0.0.1:5000
    User->>Settings: Manage components