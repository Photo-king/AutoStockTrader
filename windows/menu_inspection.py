"""Open and dismiss only the verified funds-page grid context menu; never select an item."""
import ctypes as C
from ctypes import wintypes as W
import time


def inspect_grid_menu(user, windows, copy_table=False, base=None):
    candidates = []
    for window in windows:
        labels = {c.get('label') for c in window['children'] if c['visible']}
        if window['visible'] and {'资金余额', '可用金额', '股票市值'} <= labels:
            for child in window['children']:
                if child['visible'] and child['enabled'] and child['class'] == 'CVirtualGridCtrl':
                    candidates.append((window, child))
    if len(candidates) != 1:
        return {'status': 'refused_ambiguous_grid', 'candidates': len(candidates)}
    parent, grid = candidates[0]
    left, top, right, bottom = grid['rect']
    if right - left < 100 or bottom - top < 70:
        return {'status': 'refused_small_grid'}
    user.SetForegroundWindow.argtypes = [W.HWND]
    user.GetForegroundWindow.restype = W.HWND
    user.GetAncestor.argtypes = [W.HWND, W.UINT]
    user.GetAncestor.restype = W.HWND
    user.WindowFromPoint.argtypes = [W.POINT]
    user.WindowFromPoint.restype = W.HWND
    user.IsChild.argtypes = [W.HWND, W.HWND]
    user.GetCursorPos.argtypes = [C.POINTER(W.POINT)]
    user.SetCursorPos.argtypes = [C.c_int, C.c_int]
    user.GetMenuItemCount.argtypes = [W.HMENU]
    user.GetMenuStringW.argtypes = [W.HMENU, W.UINT, W.LPWSTR, C.c_int, W.UINT]
    user.GetMenuItemID.argtypes = [W.HMENU, C.c_int]
    user.GetMenuItemID.restype = W.UINT
    user.GetSubMenu.argtypes = [W.HMENU, C.c_int]
    user.GetSubMenu.restype = W.HMENU
    user.GetMenuState.argtypes = [W.HMENU, W.UINT, W.UINT]
    user.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    user.SetForegroundWindow(parent['handle'])
    time.sleep(.2)
    foreground = user.GetForegroundWindow()
    if user.GetAncestor(foreground, 2) != parent['handle']:
        return {'status': 'refused_foreground_not_verified'}
    old_cursor = W.POINT()
    if not user.GetCursorPos(C.byref(old_cursor)):
        return {'status': 'refused_cursor_unavailable'}
    point = (left + min(140, (right-left)//2), top + min(32, (bottom-top)//2))
    copy_owner = None
    copy_command = None
    menus = []
    before_clipboard = user.GetClipboardSequenceNumber()
    report = {'status': 'no_menu', 'items': []}
    try:
        user.SetCursorPos(*point)
        hit = user.WindowFromPoint(W.POINT(*point))
        if hit != grid['handle'] and not user.IsChild(grid['handle'], hit):
            return {'status': 'refused_grid_occluded'}
        # Real right-click is required by this custom grid; no left-click or key entry.
        user.mouse_event.argtypes = [W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t]
        user.mouse_event(0x0008, 0, 0, 0, 0)
        user.mouse_event(0x0010, 0, 0, 0, 0)
        time.sleep(.3)
        CALLBACK = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        @CALLBACK
        def find_menu(hwnd, unused):
            pid = W.DWORD()
            user.GetWindowThreadProcessId(hwnd, C.byref(pid))
            if pid.value != parent['pid'] or not user.IsWindowVisible(hwnd):
                return True
            name = C.create_unicode_buffer(128)
            user.GetClassNameW(hwnd, name, 128)
            if name.value == '#32768':
                menus.append(int(hwnd))
            return True
        user.EnumWindows(find_menu, 0)
        if menus:
            class GUIINFO(C.Structure):
                _fields_ = [('cbSize', W.DWORD), ('flags', W.DWORD), ('hwndActive', W.HWND), ('hwndFocus', W.HWND), ('hwndCapture', W.HWND), ('hwndMenuOwner', W.HWND), ('hwndMoveSize', W.HWND), ('hwndCaret', W.HWND), ('rcCaret', W.RECT)]
            user.GetGUIThreadInfo.argtypes = [W.DWORD, C.POINTER(GUIINFO)]
            info = GUIINFO(); info.cbSize = C.sizeof(info)
            pid = W.DWORD(); thread = user.GetWindowThreadProcessId(parent['handle'], C.byref(pid))
            if user.GetGUIThreadInfo(thread, C.byref(info)) and info.hwndMenuOwner:
                owner_pid = W.DWORD(); user.GetWindowThreadProcessId(info.hwndMenuOwner, C.byref(owner_pid))
                if owner_pid.value == parent['pid']:
                    copy_owner = info.hwndMenuOwner
        for hwnd in menus:
            menu = C.c_size_t()
            if not user.SendMessageTimeoutW(hwnd, 0x01E1, 0, 0, 2, 300, C.byref(menu)):
                continue
            count = user.GetMenuItemCount(menu.value)
            if count < 0 or count > 100:
                continue
            report['status'] = 'menu_read'
            for i in range(count):
                text = C.create_unicode_buffer(256)
                user.GetMenuStringW(menu.value, i, text, 256, 0x400)
                # Menu commands only, never account cells or input fields.
                label = text.value.strip()
                item = {'position': i, 'label': label, 'disabled': bool(user.GetMenuState(menu.value, i, 0x400) & 3)}
                sub = user.GetSubMenu(menu.value, i)
                if sub:
                    subitems = []
                    for j in range(min(max(user.GetMenuItemCount(sub), 0), 60)):
                        entry = C.create_unicode_buffer(256)
                        user.GetMenuStringW(sub, j, entry, 256, 0x400)
                        entry_label = entry.value.strip()
                        disabled = bool(user.GetMenuState(sub, j, 0x400) & 3)
                        subitems.append({'position': j, 'label': entry_label, 'disabled': disabled})
                        if label == '更多操作' and entry_label == '复制(&C)\tCtrl+C' and not disabled:
                            if copy_command is not None:
                                raise ValueError('Ambiguous copy menu command')
                            copy_command = user.GetMenuItemID(sub, j)
                    item['submenu'] = subitems
                report['items'].append(item)
    finally:
        # Cancel popup mode; do not activate any menu item or use trading hotkeys.
        for hwnd in menus:
            user.PostMessageW(hwnd, 0x0100, 0x1B, 0)
            user.PostMessageW(hwnd, 0x0101, 0x1B, 0)
        user.PostMessageW(parent['handle'], 0x001F, 0, 0)
        user.PostMessageW(grid['handle'], 0x001F, 0, 0)
        user.SetCursorPos(old_cursor.x, old_cursor.y)
        report['dismiss_requested'] = True
    if copy_table:
        if copy_owner is None or copy_command is None or not 0 < copy_command < 65536:
            report['copy_result'] = {'status':'copy_command_unavailable'}
        else:
            time.sleep(.2)
            result = C.c_size_t()
            user.SendMessageTimeoutW(copy_owner, 0x0111, copy_command, 0, 2, 2000, C.byref(result))
            from clipboard_table import collect_new_table
            report['copy_result'] = collect_new_table(user, parent['pid'], before_clipboard, base)
    return report


def inspect_grid_copy(user, windows, base):
    """Select a holdings row and try Ctrl+C. Read only newly changed clipboard text."""
    candidates = []
    for window in windows:
        labels = {c.get('label') for c in window['children'] if c['visible']}
        if window['visible'] and {'资金余额', '可用金额', '股票市值'} <= labels:
            candidates.extend((window, c) for c in window['children']
                              if c['visible'] and c['enabled'] and c['class'] == 'CVirtualGridCtrl')
    if len(candidates) != 1:
        return {'status': 'refused_ambiguous_grid'}
    parent, grid = candidates[0]
    user.GetForegroundWindow.restype = W.HWND
    user.SetForegroundWindow.argtypes = [W.HWND]
    user.GetAncestor.argtypes = [W.HWND, W.UINT]
    user.GetAncestor.restype = W.HWND
    user.WindowFromPoint.argtypes = [W.POINT]
    user.WindowFromPoint.restype = W.HWND
    user.IsChild.argtypes = [W.HWND, W.HWND]
    user.GetAsyncKeyState.argtypes = [C.c_int]
    user.GetAsyncKeyState.restype = C.c_short
    user.mouse_event.argtypes = [W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t]
    user.keybd_event.argtypes = [W.BYTE, W.BYTE, W.DWORD, C.c_size_t]
    user.GetCursorPos.argtypes = [C.POINTER(W.POINT)]
    user.SetCursorPos.argtypes = [C.c_int, C.c_int]
    user.GetClipboardSequenceNumber.restype = W.DWORD
    user.OpenClipboard.argtypes = [W.HWND]
    user.GetClipboardOwner.restype = W.HWND
    user.GetClipboardData.argtypes = [W.UINT]
    user.GetClipboardData.restype = W.HANDLE
    class GUIINFO(C.Structure):
        _fields_ = [('cbSize', W.DWORD), ('flags', W.DWORD), ('hwndActive', W.HWND),
                    ('hwndFocus', W.HWND), ('hwndCapture', W.HWND), ('hwndMenuOwner', W.HWND),
                    ('hwndMoveSize', W.HWND), ('hwndCaret', W.HWND), ('rcCaret', W.RECT)]
    user.GetGUIThreadInfo.argtypes = [W.DWORD, C.POINTER(GUIINFO)]
    if any(user.GetAsyncKeyState(k) & 0x8000 for k in [0x10, 0x11, 0x12, 0x5B, 0x5C]):
        return {'status': 'refused_modifier_held'}
    user.SetForegroundWindow(parent['handle'])
    time.sleep(.2)
    if user.GetAncestor(user.GetForegroundWindow(), 2) != parent['handle']:
        return {'status': 'refused_foreground_not_verified'}
    left, top, right, bottom = grid['rect']
    if right-left < 200 or bottom-top < 70:
        return {'status': 'refused_small_grid'}
    point = W.POINT(left+145, top+32)
    hit = user.WindowFromPoint(point)
    if hit != grid['handle'] and not user.IsChild(grid['handle'], hit):
        return {'status': 'refused_grid_occluded'}
    cursor = W.POINT()
    if not user.GetCursorPos(C.byref(cursor)):
        return {'status': 'refused_cursor_unavailable'}
    before = user.GetClipboardSequenceNumber()
    try:
        user.SetCursorPos(point.x, point.y)
        user.mouse_event(2, 0, 0, 0, 0)
        user.mouse_event(4, 0, 0, 0, 0)
        time.sleep(.2)
        info = GUIINFO()
        info.cbSize = C.sizeof(info)
        pid = W.DWORD()
        thread = user.GetWindowThreadProcessId(grid['handle'], C.byref(pid))
        if not user.GetGUIThreadInfo(thread, C.byref(info)):
            return {'status': 'refused_focus_unavailable'}
        if info.hwndFocus != grid['handle'] and not user.IsChild(grid['handle'], info.hwndFocus):
            return {'status': 'refused_focus_not_grid'}
        if user.GetAncestor(user.GetForegroundWindow(), 2) != parent['handle']:
            return {'status': 'refused_foreground_changed'}
        try:
            user.keybd_event(0x11, 0, 0, 0)
            user.keybd_event(0x43, 0, 0, 0)
        finally:
            user.keybd_event(0x43, 0, 2, 0)
            user.keybd_event(0x11, 0, 2, 0)
        for _ in range(15):
            if user.GetClipboardSequenceNumber() != before:
                break
            time.sleep(.1)
        if user.GetClipboardSequenceNumber() == before:
            return {'status': 'clipboard_unchanged', 'shortcut_sent': True}
        kernel = C.WinDLL('kernel32', use_last_error=True)
        kernel.GlobalLock.argtypes = [W.HANDLE]
        kernel.GlobalLock.restype = C.c_void_p
        kernel.GlobalSize.argtypes = [W.HANDLE]
        kernel.GlobalSize.restype = C.c_size_t
        kernel.GlobalUnlock.argtypes = [W.HANDLE]
        opened = False
        for _ in range(25):
            if user.OpenClipboard(None):
                opened = True
                break
            time.sleep(.1)
        if not opened:
            return {'status': 'clipboard_busy'}
        try:
            owner = user.GetClipboardOwner()
            owner_pid = W.DWORD()
            if owner:
                user.GetWindowThreadProcessId(owner, C.byref(owner_pid))
            if owner_pid.value != parent['pid']:
                return {'status': 'clipboard_owner_not_target'}
            handle = user.GetClipboardData(13)
            if not handle:
                return {'status': 'no_unicode_text'}
            size = kernel.GlobalSize(handle)
            if not 0 < size <= 5_000_000:
                return {'status': 'invalid_clipboard_size'}
            ptr = kernel.GlobalLock(handle)
            if not ptr:
                return {'status': 'clipboard_lock_failed'}
            try:
                text = C.string_at(ptr, size).decode('utf-16le').split('\0', 1)[0]
            finally:
                kernel.GlobalUnlock(handle)
        finally:
            user.CloseClipboard()
        lines = [line for line in text.splitlines() if line.strip()]
        headers = lines[0].split('\t') if lines else []
        expected = {'证券代码', '证券名称', '股票余额', '实际数量', '可用余额', '成本价', '市价'}
        matched = sorted(expected.intersection(h.strip() for h in headers))
        if len(matched) < 3:
            return {'status': 'changed_text_not_recognized', 'shortcut_sent': True}
        path = base / 'positions-copy.txt'
        path.write_text(text, encoding='utf-8')
        return {'status': 'holdings_text_copied', 'matched_headers': matched,
                'line_count': len(lines), 'private_path': str(path), 'shortcut_sent': True}
    finally:
        user.SetCursorPos(cursor.x, cursor.y)
