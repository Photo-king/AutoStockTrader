"""Read-only Win32 metadata probe. Reads Static labels only; never reads Edit controls or sends input."""
import ctypes as C
from ctypes import wintypes as W
import datetime
import json
import os
import base64
import subprocess
from pathlib import Path

user = C.WinDLL('user32', use_last_error=True)
kernel = C.WinDLL('kernel32', use_last_error=True)
CALLBACK = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
user.EnumWindows.argtypes = [CALLBACK, W.LPARAM]
user.EnumChildWindows.argtypes = [W.HWND, CALLBACK, W.LPARAM]
user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
user.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
user.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
user.IsWindowVisible.argtypes = [W.HWND]
user.IsWindowEnabled.argtypes = [W.HWND]
user.GetDlgCtrlID.argtypes = [W.HWND]
user.SendMessageTimeoutW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM, W.UINT, W.UINT, C.POINTER(C.c_size_t)]
user.SendMessageTimeoutW.restype = W.LPARAM
SAFE_LABELS = {'总资产', '资产总值', '可用金额', '可用资金', '可取金额', '可取资金',
               '资金余额', '股票市值', '证券市值', '总市值', '参考市值', '持仓盈亏',
               '参考盈亏', '当日盈亏', '冻结金额', '冻结资金', '资金股份', '资金股票',
               '币种', '人民币', '余额', '市值', '可用', '可取',
               '导出', '导出数据', '数据导出', '输出', '输出数据', '复制', '复制数据',
               '刷新', '查询', '资金股份', '持仓', '资金股票', '打印', '保存'}

def static_shape(hwnd):
    # WM_GETTEXT is read-only; only Static controls reach this function.
    buf = C.create_unicode_buffer(512)
    result = C.c_size_t()
    ok = user.SendMessageTimeoutW(hwnd, 13, len(buf), C.addressof(buf), 2, 200, C.byref(result))
    if not ok:
        return {'text_kind': 'unavailable'}
    text = buf.value.strip().rstrip(':：').strip()
    normalized_label = ''.join(text.split())
    if normalized_label in SAFE_LABELS:
        return {'text_kind': 'known_label', 'label': normalized_label}
    if not text:
        return {'text_kind': 'empty'}
    import re
    if re.fullmatch(r'[+−-]?[0-9,]+(?:\.[0-9]+)?%?', text):
        return {'text_kind': 'numeric_redacted'}
    return {'text_kind': 'redacted'}

user.OpenInputDesktop.argtypes = [W.DWORD, W.BOOL, W.DWORD]
user.OpenInputDesktop.restype = W.HANDLE
user.CloseDesktop.argtypes = [W.HANDLE]
kernel.ProcessIdToSessionId.argtypes = [W.DWORD, C.POINTER(W.DWORD)]

base = Path(__file__).resolve().parent
try:
    from process_integrity import integrity_report
    target_pids = set(json.loads((base / 'target_pids.json').read_text()))
    integrity = integrity_report(target_pids)
    def metadata(hwnd):
        pid = W.DWORD()
        user.GetWindowThreadProcessId(hwnd, C.byref(pid))
        cls = C.create_unicode_buffer(256)
        user.GetClassNameW(hwnd, cls, 256)
        rect = W.RECT()
        user.GetWindowRect(hwnd, C.byref(rect))
        row = {'handle': int(hwnd), 'pid': pid.value, 'class': cls.value,
                'control_id': user.GetDlgCtrlID(hwnd),
                'visible': bool(user.IsWindowVisible(hwnd)),
                'enabled': bool(user.IsWindowEnabled(hwnd)),
                'rect': [rect.left, rect.top, rect.right, rect.bottom]}
        if cls.value in ('Static', 'Button') and row['visible']:
            row.update(static_shape(hwnd))
        return row
    windows = []
    @CALLBACK
    def each_window(hwnd, unused):
        row = metadata(hwnd)
        if row['pid'] in target_pids:
            children = []
            @CALLBACK
            def each_child(child, unused):
                if len(children) < 500:
                    children.append(metadata(child))
                return True
            user.EnumChildWindows(hwnd, each_child, 0)
            row['children'] = children
            windows.append(row)
        return True
    user.EnumWindows(each_window, 0)
    import sys
    trading_pids = set(json.loads((base / 'trading_pids.json').read_text()))
    def trading_panels():
        return [w for w in windows if w['pid'] in trading_pids and w['visible'] and
                w['rect'][2]-w['rect'][0] > 400 and w['rect'][3]-w['rect'][1] > 250 and
                any(c['class'] == 'SysTreeView32' for c in w['children'])]
    navigation_inspection = None
    page = next((flag.split('=',1)[1] for flag in sys.argv if flag.startswith('--page=')), None)
    if page or '--inspect-menu' in sys.argv or '--copy-grid' in sys.argv or '--copy-menu' in sys.argv:
        from access_policy import require_input_integrity
        require_input_integrity(integrity)
    if '--inspect-navigation' in sys.argv or page:
        roots = trading_panels()
        if len(roots) != 1:
            raise ValueError('Trading root is missing or ambiguous')
        proc = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
            '-File',str(base / 'query_navigation.ps1'),'-RootHandle',str(roots[0]['handle']),
            '-Page','inspect'],capture_output=True,timeout=10,creationflags=0x08000000)
        if proc.returncode:
            (base / 'navigation-error.txt').write_bytes(proc.stderr)
            raise ValueError('Query navigation failed; inspect private navigation-error.txt')
        navigation_inspection = json.loads(proc.stdout.decode('utf-8-sig'))
        if page and any(item['label'] == {'holdings':'资金股份','orders':'当日委托','trades':'当日成交'}[page] for item in navigation_inspection.get('available', [])):
            args = ['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(base / 'query_navigation.ps1'),'-RootHandle',str(roots[0]['handle']),'-Page',page]
            proc = subprocess.run(args,capture_output=True,timeout=10,creationflags=0x08000000)
            if proc.returncode:
                (base / 'navigation-error.txt').write_bytes(proc.stderr)
                raise ValueError('Query selection failed')
            navigation_inspection = json.loads(proc.stdout.decode('utf-8-sig'))
        elif not navigation_inspection.get('available') or page:
            from query_navigation import navigate_query
            navigation_inspection = navigate_query(user, roots[0], base, page)
        windows.clear()
        user.EnumWindows(each_window, 0)
        if page == 'holdings':
            funds_roots = trading_panels()
            if len(funds_roots) != 1 or not {'资金余额','可用金额','股票市值'} <= {c.get('label') for c in funds_roots[0]['children'] if c['visible']}:
                raise ValueError('Holdings query page was not confirmed by native funds labels')
            navigation_inspection['status'] = 'funds_page_verified'
    funds_inspection = None
    if '--read-funds' in sys.argv:
        panels = trading_panels()
        if len(panels) != 1:
            raise ValueError('Funds panel missing or ambiguous')
        from funds_reader import read_funds
        funds = read_funds(user, panels[0])
        funds['observed_at'] = datetime.datetime.now().astimezone().isoformat()
        (base / 'funds-private.json').write_text(json.dumps(funds, ensure_ascii=False, indent=2), encoding='utf-8')
        funds_inspection = {key: value for key, value in funds.items() if key != 'values'}
        funds_inspection['field_count'] = len(funds['values'])
    menu_inspection = None
    if '--inspect-menu' in sys.argv or '--copy-menu' in sys.argv:
        from menu_inspection import inspect_grid_menu
        menu_inspection = inspect_grid_menu(user, windows, copy_table='--copy-menu' in sys.argv, base=base)
    copied_positions_inspection = None
    if menu_inspection and (menu_inspection.get('copy_result') or {}).get('status') == 'table_copied':
        from copied_positions import parse_copied_positions, TableParseError
        from decimal import Decimal
        try:
            copied = parse_copied_positions((base / 'broker-table-private.tsv').read_text(encoding='utf-8'))
            copied['observed_at'] = datetime.datetime.now().astimezone().isoformat()
            match = None
            if funds_inspection and copied['rows'] and all('market_value' in row for row in copied['rows']):
                match = abs(sum(Decimal(row['market_value']) for row in copied['rows']) - Decimal(funds['values']['stock_market_value'])) <= Decimal('.02')
            copied['copied_market_sum_matches_funds'] = match
            (base / 'positions-copied-private.json').write_text(json.dumps(copied, ensure_ascii=False, indent=2), encoding='utf-8')
            copied_positions_inspection = {k:v for k,v in copied.items() if k != 'rows'}
            copied_positions_inspection['candidate_rows'] = len(copied['rows'])
        except TableParseError as exc:
            copied_positions_inspection = {'status':'unreadable','reason':str(exc),'executable':False}
    copy_inspection = None
    if '--copy-grid' in sys.argv:
        from menu_inspection import inspect_grid_copy
        copy_inspection = inspect_grid_copy(user, windows, base)
    session = W.DWORD()
    kernel.ProcessIdToSessionId(os.getpid(), C.byref(session))
    desktop = user.OpenInputDesktop(0, False, 1)
    error = C.get_last_error() if not desktop else None
    if desktop:
        user.CloseDesktop(desktop)
    # Check accessibility patterns without reading table cells or account text.
    grids = [c['handle'] for w in windows for c in w['children']
             if c['visible'] and c['class'] == 'CVirtualGridCtrl']
    accessibility = []
    if grids:
        import base64
        import subprocess
        ps = r"""$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue';
[Console]::OutputEncoding=[Text.Encoding]::UTF8;
Add-Type -AssemblyName UIAutomationClient;
Add-Type -AssemblyName UIAutomationTypes;
$rows = @(foreach ($h in @(HANDLES)) {
  $e = [Windows.Automation.AutomationElement]::FromHandle([IntPtr][long]$h);
  $children = $e.FindAll([Windows.Automation.TreeScope]::Children,[Windows.Automation.Condition]::TrueCondition);
  [ordered]@{handle=$h; control_type=$e.Current.ControlType.ProgrammaticName;
    patterns=@($e.GetSupportedPatterns() | ForEach-Object { $_.ProgrammaticName });
    child_count=$children.Count}
}); ConvertTo-Json -InputObject $rows -Depth 5 -Compress
""".replace('HANDLES', ','.join(str(h) for h in grids))
        encoded = base64.b64encode(ps.encode('utf-16le')).decode()
        try:
            proc = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive',
                                   '-EncodedCommand', encoded], capture_output=True,
                                  timeout=8, creationflags=0x08000000)
            if proc.returncode == 0:
                accessibility = json.loads(proc.stdout.decode('utf-8-sig'))
            else:
                accessibility = [{'status': 'probe_failed', 'exit_code': proc.returncode}]
        except subprocess.TimeoutExpired:
            accessibility = [{'status': 'timeout'}]
        except (ValueError, UnicodeError):
            accessibility = [{'status': 'invalid_output'}]
    screenshot = None
    capture_guard = None
    captured_at = None
    if '--capture-window' in sys.argv:
        panels = trading_panels()
        if len(panels) != 1:
            raise ValueError('Capture trading panel missing or ambiguous')
        if len(panels) == 1:
            from capture_guard import validate_capture
            capture_guard = validate_capture(user, panels[0])
            l, t, r, b = panels[0]['rect']
            ps = r"""$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue';
[Console]::OutputEncoding=[Text.Encoding]::UTF8;
Add-Type -AssemblyName System.Drawing;
$bitmap=New-Object Drawing.Bitmap(WIDTH,HEIGHT);
$graphics=[Drawing.Graphics]::FromImage($bitmap);
$stream=New-Object IO.MemoryStream;
try {
 $graphics.CopyFromScreen(LEFT,TOP,0,0,$bitmap.Size);
 $bitmap.Save($stream,[Drawing.Imaging.ImageFormat]::Png);
 $bitmap.Save('C:\AutoStockTrader\diagnostics\trade-window.png',[Drawing.Imaging.ImageFormat]::Png);
 [Console]::Write([Convert]::ToBase64String($stream.ToArray()));
} finally { $stream.Dispose(); $graphics.Dispose(); $bitmap.Dispose() }
""".replace('WIDTH',str(r-l)).replace('HEIGHT',str(b-t)).replace('LEFT',str(l)).replace('TOP',str(t))
            encoded = base64.b64encode(ps.encode('utf-16le')).decode()
            captured_at = datetime.datetime.now().astimezone().isoformat()
            capture = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],
                capture_output=True, timeout=8, creationflags=0x08000000)
            if capture.returncode == 0:
                screenshot = capture.stdout.decode('utf-8-sig').strip()
            else:
                (base / 'capture-error.txt').write_bytes(capture.stderr)
    ocr_inspection = None
    if '--ocr-grid' in sys.argv and screenshot:
        panel = panels[0]
        tables = [c for c in panel['children'] if c['visible'] and c['class'] == 'CVirtualGridCtrl']
        if len(tables) != 1:
            raise ValueError('Ambiguous table crop')
        gl, gt, gr, gb = tables[0]['rect']
        pl, pt, _, _ = panel['rect']
        proc = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
            '-File',str(base / 'native_ocr.ps1'),'-ImagePath',str(base / 'trade-window.png'),
            '-OutputPath',str(base / 'holdings-ocr-private.json'),
            '-CropLeft',str(gl-pl),'-CropTop',str(gt-pt),'-CropWidth',str(gr-gl),'-CropHeight',str(gb-gt)],
            capture_output=True, timeout=15, creationflags=0x08000000)
        if proc.returncode == 0:
            ocr_inspection = json.loads(proc.stdout.decode('utf-8-sig'))
        else:
            # Only diagnostic errors, never OCR account content.
            (base / 'ocr-error.txt').write_bytes(proc.stderr)
            ocr_inspection = {'status': 'failed', 'exit_code': proc.returncode}
    query_inspection = None
    if page in ('orders','trades') and ocr_inspection and ocr_inspection.get('status') == 'recognized':
        from query_observation import describe_query
        raw = json.loads((base / 'holdings-ocr-private.json').read_text(encoding='utf-8-sig'))
        query_inspection = describe_query(raw,page)
        query_inspection['observed_at'] = captured_at
        (base / 'query-observation-private.json').write_text(json.dumps(query_inspection, ensure_ascii=False, indent=2), encoding='utf-8')
    positions_inspection = None
    if (page is None or page == 'holdings') and ocr_inspection and ocr_inspection.get('status') == 'recognized':
        from ocr_positions import parse_visible_positions, OcrParseError
        raw = json.loads((base / 'holdings-ocr-private.json').read_text(encoding='utf-8-sig'))
        try:
            candidate = parse_visible_positions(raw)
            candidate['observed_at'] = captured_at
            (base / 'positions-ocr-candidates.json').write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding='utf-8')
            positions_inspection = {'status': candidate['status'], 'visible_candidate_rows': len(candidate['rows']),
                                    'verified': False, 'executable': False, 'complete_portfolio': False}
        except OcrParseError as exc:
            positions_inspection = {'status': 'unreadable', 'reason': str(exc), 'executable': False}
            (base / 'positions-ocr-candidates.json').write_text(json.dumps(positions_inspection), encoding='utf-8')
    ocr_positions_inspection = positions_inspection
    if copied_positions_inspection is not None:
        positions_inspection = copied_positions_inspection
    report = {'copied_positions_inspection': copied_positions_inspection, 'ocr_positions_inspection': ocr_positions_inspection, 'query_inspection': query_inspection, 'funds_inspection': funds_inspection, 'integrity': integrity, 'capture_guard': capture_guard, 'navigation_inspection': navigation_inspection, 'page_requested': page, 'captured_at': captured_at, 'positions_inspection': positions_inspection,
              'actions_requested': [flag for flag in sys.argv[1:]],
              'checked_at': datetime.datetime.now().astimezone().isoformat(),
              'probe_session': session.value, 'input_desktop_accessible': bool(desktop),
              'desktop_error': error, 'screen': [user.GetSystemMetrics(0), user.GetSystemMetrics(1)],
              'target_pids': sorted(target_pids), 'windows': windows, 'grid_accessibility': accessibility, 'menu_inspection': menu_inspection, 'copy_inspection': copy_inspection, 'ocr_inspection': ocr_inspection,
              'window_screenshot_base64': screenshot,
              'privacy': 'Only allowlisted Static labels retained; numeric and unknown text redacted. No Edit text. Optional menu/copy/screenshot/OCR actions are listed in actions_requested; private artifacts stay in diagnostics.'}
except Exception as exc:
    report = {'error': type(exc).__name__ + ': ' + str(exc)}
output = base / 'desktop-report.json'
temp = output.with_suffix('.tmp')
temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
temp.replace(output)
