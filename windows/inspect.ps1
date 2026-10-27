$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$apps = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('hexin.exe','xiadan.exe') } | Select-Object Name,ProcessId,SessionId,ExecutablePath)
$python = 'C:\StockAgent\.venv\Scripts\python.exe'
$pythonVersion = if (Test-Path $python) { & $python --version 2>&1 | Out-String } else { 'not found' }
$modules = if (Test-Path $python) { & $python -c "import importlib.util,json; print(json.dumps({m: importlib.util.find_spec(m) is not None for m in ['pywinauto','PIL','win32gui']}))" | Out-String } else { '' }
[ordered]@{
    checked_at = (Get-Date -Format o)
    identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    probe_session = (Get-Process -Id $PID).SessionId
    applications = $apps
    python = $pythonVersion.Trim()
    optional_modules = $modules.Trim()
    sessions = (query user 2>&1 | Out-String).Trim()
} | ConvertTo-Json -Depth 5
