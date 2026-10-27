#!/usr/bin/env python3
"""Deploy an isolated read-only desktop probe and run once in the logged-in session."""
import argparse
import base64
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--inspect-menu', action='store_true')
parser.add_argument('--capture-window', action='store_true')
parser.add_argument('--copy-grid', action='store_true')
parser.add_argument('--copy-menu', action='store_true')
parser.add_argument('--ocr-grid', action='store_true')
parser.add_argument('--inspect-navigation', action='store_true')
parser.add_argument('--read-funds', action='store_true')
parser.add_argument('--elevated', action='store_true', help='Run one temporary interactive diagnostic task at Highest integrity')
parser.add_argument('--page', choices=['holdings','orders','trades'])
args = parser.parse_args()
if args.ocr_grid:
    args.capture_window = True
copied_parser_payload = base64.b64encode((root / 'app/copied_positions.py').read_bytes()).decode()
nav_parser_payload = base64.b64encode((root / 'app/navigation_ocr.py').read_bytes()).decode()
access_payload = base64.b64encode((root / 'app/access_policy.py').read_bytes()).decode()
query_parser_payload = base64.b64encode((root / 'app/query_observation.py').read_bytes()).decode()
clipboard_payload = base64.b64encode((root / 'windows/clipboard_table.py').read_bytes()).decode()
funds_payload = base64.b64encode((root / 'windows/funds_reader.py').read_bytes()).decode()
integrity_payload = base64.b64encode((root / 'windows/process_integrity.py').read_bytes()).decode()
guard_payload = base64.b64encode((root / 'windows/capture_guard.py').read_bytes()).decode()
nav_python_payload = base64.b64encode((root / 'windows/query_navigation.py').read_bytes()).decode()
navigation_payload = base64.b64encode((root / 'windows/query_navigation.ps1').read_text().encode('utf-8-sig')).decode()
parser_payload = base64.b64encode((root / 'app/ocr_positions.py').read_bytes()).decode()
ocr_payload = base64.b64encode((root / 'windows/native_ocr.ps1').read_bytes()).decode()
menu_payload = base64.b64encode((root / 'windows/menu_inspection.py').read_bytes()).decode()
payload = base64.b64encode((root / 'windows/desktop_probe.py').read_bytes()).decode()
script = r'''
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$base = 'C:\AutoStockTrader\diagnostics'
$python = 'C:\StockAgent\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Existing Python missing' }
$processes = @(Get-Process -Name hexin,xiadan -ErrorAction SilentlyContinue)
if ($processes.Count -eq 0) { throw 'No THS processes found' }
$activeSessions = @($processes | Select-Object -ExpandProperty SessionId -Unique)
if ($activeSessions.Count -ne 1 -or $activeSessions[0] -eq 0) { throw 'Ambiguous desktop session' }
$taskName = 'AutoStockTrader-ReadOnlyProbe'
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw 'Probe task already exists; refusing to overwrite' }
New-Item -ItemType Directory -Path $base -Force | Out-Null
[IO.File]::WriteAllBytes((Join-Path $base 'desktop_probe.py'), [Convert]::FromBase64String('PAYLOAD'))
[IO.File]::WriteAllBytes((Join-Path $base 'menu_inspection.py'), [Convert]::FromBase64String('MENU_PAYLOAD'))
[IO.File]::WriteAllBytes((Join-Path $base 'native_ocr.ps1'), [Convert]::FromBase64String('OCR_PAYLOAD'))
[IO.File]::WriteAllBytes((Join-Path $base 'ocr_positions.py'), [Convert]::FromBase64String('PARSER_PAYLOAD'))
[IO.File]::WriteAllBytes((Join-Path $base 'query_navigation.ps1'), [Convert]::FromBase64String('NAVIGATION_PAYLOAD'))
[IO.File]::WriteAllBytes((Join-Path $base 'query_navigation.py'), [Convert]::FromBase64String('NAV_PYTHON_PAYLOAD'))
[IO.File]::WriteAllBytes((Join-Path $base 'capture_guard.py'), [Convert]::FromBase64String('GUARD_PAYLOAD'))
[IO.File]::WriteAllBytes((Join-Path $base 'process_integrity.py'), [Convert]::FromBase64String('INTEGRITY_PAYLOAD'))
[IO.File]::WriteAllBytes((Join-Path $base 'funds_reader.py'), [Convert]::FromBase64String('FUNDS_PAYLOAD'))
[IO.File]::WriteAllBytes((Join-Path $base 'clipboard_table.py'), [Convert]::FromBase64String('CLIPBOARD_PAYLOAD'))
[IO.File]::WriteAllBytes((Join-Path $base 'query_observation.py'), [Convert]::FromBase64String('QUERY_PARSER_PAYLOAD'))
[IO.File]::WriteAllBytes((Join-Path $base 'access_policy.py'), [Convert]::FromBase64String('ACCESS_PAYLOAD'))
[IO.File]::WriteAllBytes((Join-Path $base 'navigation_ocr.py'), [Convert]::FromBase64String('NAV_PARSER_PAYLOAD'))
[IO.File]::WriteAllBytes((Join-Path $base 'copied_positions.py'), [Convert]::FromBase64String('COPIED_PARSER_PAYLOAD'))
ConvertTo-Json -InputObject @($processes | Select-Object -ExpandProperty Id) | Set-Content -Encoding ASCII (Join-Path $base 'target_pids.json')
ConvertTo-Json -InputObject @($processes | Where-Object { $_.ProcessName -eq 'xiadan' } | Select-Object -ExpandProperty Id) | Set-Content -Encoding ASCII (Join-Path $base 'trading_pids.json')
$report = Join-Path $base 'desktop-report.json'
if (Test-Path $report) { Move-Item $report ($report + '.' + (Get-Date -Format 'yyyyMMddHHmmss') + '.bak') }
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $python -Argument ('"' + (Join-Path $base 'desktop_probe.py') + '"MODE_ARGS') -WorkingDirectory $base
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel TASK_RUN_LEVEL
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings | Out-Null
    Start-ScheduledTask -TaskName $taskName
    for ($i = 0; $i -lt 45; $i++) {
        if (Test-Path $report) { break }
        Start-Sleep -Seconds 1
    }
    if (-not (Test-Path $report)) {
        $info = Get-ScheduledTaskInfo -TaskName $taskName
        throw ('Probe timed out; task result ' + $info.LastTaskResult)
    }
    $r = Get-Content -Raw -Encoding UTF8 $report | ConvertFrom-Json
    if ('FETCH_TABLE' -eq 'yes' -and $r.menu_inspection.copy_result.status -eq 'table_copied') {
        $r | Add-Member -NotePropertyName table_private -NotePropertyValue ([IO.File]::ReadAllText((Join-Path $base 'broker-table-private.tsv'),[Text.Encoding]::UTF8))
    }
    if ('FETCH_OCR' -eq 'yes' -and $r.ocr_inspection.status -eq 'recognized') {
        $private = Get-Content -Raw -Encoding UTF8 (Join-Path $base 'holdings-ocr-private.json') | ConvertFrom-Json
        $r | Add-Member -NotePropertyName ocr_private -NotePropertyValue $private
        $r | ConvertTo-Json -Depth 15
    } else {
        $r | ConvertTo-Json -Depth 15
    }
} finally {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
}
'''.replace('TASK_RUN_LEVEL', 'Highest' if args.elevated else 'Limited').replace('COPIED_PARSER_PAYLOAD', copied_parser_payload).replace('NAV_PARSER_PAYLOAD', nav_parser_payload).replace('ACCESS_PAYLOAD', access_payload).replace('QUERY_PARSER_PAYLOAD', query_parser_payload).replace('CLIPBOARD_PAYLOAD', clipboard_payload).replace('FUNDS_PAYLOAD', funds_payload).replace('INTEGRITY_PAYLOAD', integrity_payload).replace('GUARD_PAYLOAD', guard_payload).replace('NAV_PYTHON_PAYLOAD', nav_python_payload).replace('NAVIGATION_PAYLOAD', navigation_payload).replace('PARSER_PAYLOAD', parser_payload).replace('FETCH_TABLE', 'yes' if args.copy_menu else 'no').replace('FETCH_OCR', 'yes' if args.ocr_grid else 'no').replace('OCR_PAYLOAD', ocr_payload).replace('MENU_PAYLOAD', menu_payload).replace('PAYLOAD', payload).replace('MODE_ARGS', (' --inspect-menu' if args.inspect_menu else '') + (' --capture-window' if args.capture_window else '') + (' --copy-grid' if args.copy_grid else '') + (' --copy-menu' if args.copy_menu else '') + (' --read-funds' if args.read_funds else '') + (' --ocr-grid' if args.ocr_grid else '') + (' --inspect-navigation' if args.inspect_navigation else '') + (' --page='+args.page if args.page else ''))
bootstrap = "$n = [int][Console]::In.ReadLine(); $b = New-Object Text.StringBuilder; for ($i=0; $i -lt $n; $i++) { [void]$b.Append([Console]::In.ReadLine()) }; & ([scriptblock]::Create([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b.ToString()))))"
encoded = base64.b64encode(bootstrap.encode('utf-16le')).decode()
wire = base64.b64encode(script.encode('utf-8'))
chunks = [wire[i:i+2048] for i in range(0, len(wire), 2048)]
framed = str(len(chunks)).encode('ascii') + b'\n' + b'\n'.join(chunks) + b'\n'
result = subprocess.run(['/Users/photo-king/Projects/StockAgent/scripts/windows-ssh.sh',
    '-o', 'BatchMode=yes', 'powershell -NoProfile -NonInteractive -EncodedCommand ' + encoded],
    input=framed, capture_output=True, timeout=90)
if result.returncode:
    sys.stderr.buffer.write(result.stderr)
    sys.stdout.buffer.write(result.stdout)
else:
    import json
    report = json.loads(result.stdout.decode('utf-8-sig'))
    import datetime
    import uuid
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    run_folder = root / '.local/runs' / run_id
    run_folder.mkdir(parents=True, exist_ok=False)
    report['run_id'] = run_id
    table = report.pop('table_private', None)
    if table is not None:
        (run_folder / 'broker-table-private.tsv').write_text(table, encoding='utf-8')
        (root / '.local/query-table-private.tsv').write_text(table, encoding='utf-8')
        print('Saved copied table privately to .local/query-table-private.tsv')
    ocr = report.pop('ocr_private', None)
    if ocr:
        ocr['observed_at'] = report.get('captured_at')
        folder = root / '.local'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'query-ocr-private.json').write_text(json.dumps(ocr, ensure_ascii=False, indent=2), encoding='utf-8')
        (run_folder / 'ocr-private.json').write_text(json.dumps(ocr, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Saved OCR privately to .local/query-ocr-private.json')
    screenshot = report.pop('window_screenshot_base64', None)
    if screenshot:
        folder = root / '.local/screenshots'
        folder.mkdir(parents=True, exist_ok=True)
        png = base64.b64decode(screenshot)
        (folder / 'trade-window.png').write_bytes(png)
        (run_folder / 'trade-window.png').write_bytes(png)
        print('Saved private screenshot to .local/screenshots/trade-window.png')
    (run_folder / 'metadata.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (root / 'reports/desktop-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Saved desktop metadata to reports/desktop-report.json; run:', run_id)
    if 'error' in report:
        print('Remote probe failed:', report['error'], file=sys.stderr)
        raise SystemExit(1)
raise SystemExit(result.returncode)
