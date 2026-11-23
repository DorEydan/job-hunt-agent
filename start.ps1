# One-click setup + control panel for the job-hunt agent.
# First run: creates the Python environment, installs packages and config.json. Every run: opens the panel.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$venvPy = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Write-Host 'First run: creating the Python environment...'
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { & py -3 -m venv .venv }
    else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) {
            Write-Host 'Python is not installed. Get it from https://www.python.org/downloads/ (tick "Add to PATH"), then run start.bat again.' -ForegroundColor Red
            exit 1
        }
        & python -m venv .venv
    }
}

$ver = & $venvPy -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$ver -lt [version]'3.10') {
    Write-Host "Python $ver is too old. Install Python 3.10 or newer, delete the .venv folder and run start.bat again." -ForegroundColor Red
    exit 1
}

$stamp = Join-Path $PSScriptRoot '.venv\.requirements-installed'
if (-not (Test-Path $stamp) -or (Get-Item 'requirements.txt').LastWriteTime -gt (Get-Item $stamp).LastWriteTime) {
    Write-Host 'Installing packages...'
    & $venvPy -m pip install --quiet --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Write-Host 'Package install failed (see above).' -ForegroundColor Red; exit 1 }
    New-Item -ItemType File -Force $stamp | Out-Null
}

if (-not (Test-Path 'config.json')) {
    Copy-Item 'config.example.json' 'config.json'
    Write-Host 'Created config.json from the example. Fill it in on the page that opens.'
}

Write-Host 'Opening the control panel. Keep this window open while you use it; close it to stop.'
& $venvPy ui\server.py @args
