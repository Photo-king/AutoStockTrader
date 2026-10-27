"""Read newly copied table text only when owned by the verified trading process."""
import ctypes as C
from ctypes import wintypes as W
import time


def collect_new_table(user, target_pid, previous_sequence, base):
    user.GetClipboardSequenceNumber.restype=W.DWORD
    user.OpenClipboard.argtypes=[W.HWND]
    user.GetClipboardOwner.restype=W.HWND
    user.GetClipboardData.argtypes=[W.UINT];user.GetClipboardData.restype=W.HANDLE
    for _ in range(25):
        if user.GetClipboardSequenceNumber()!=previous_sequence:break
        time.sleep(.1)
    if user.GetClipboardSequenceNumber()==previous_sequence:return {'status':'clipboard_unchanged'}
    opened=False
    for _ in range(25):
        if user.OpenClipboard(None):opened=True;break
        time.sleep(.1)
    if not opened:return {'status':'clipboard_busy'}
    try:
        owner=user.GetClipboardOwner();pid=W.DWORD()
        if owner:user.GetWindowThreadProcessId(owner,C.byref(pid))
        if pid.value!=target_pid:return {'status':'clipboard_owner_not_target'}
        handle=user.GetClipboardData(13)
        if not handle:return {'status':'no_unicode_text'}
        kernel=C.WinDLL('kernel32',use_last_error=True)
        kernel.GlobalSize.argtypes=[W.HANDLE];kernel.GlobalSize.restype=C.c_size_t
        kernel.GlobalLock.argtypes=[W.HANDLE];kernel.GlobalLock.restype=C.c_void_p
        kernel.GlobalUnlock.argtypes=[W.HANDLE]
        size=kernel.GlobalSize(handle)
        if not 0<size<=5_000_000:return {'status':'invalid_clipboard_size'}
        ptr=kernel.GlobalLock(handle)
        if not ptr:return {'status':'clipboard_lock_failed'}
        try:text=C.string_at(ptr,size).decode('utf-16le').split('\0',1)[0]
        finally:kernel.GlobalUnlock(handle)
    finally:user.CloseClipboard()
    lines=[line for line in text.splitlines() if line.strip()]
    if not lines or '\t' not in lines[0]:return {'status':'not_a_tsv_table'}
    header=[cell.strip() for cell in lines[0].split('\t')]
    if not {'证券代码','证券名称'}.issubset(header):return {'status':'unrecognized_table'}
    (base/'broker-table-private.tsv').write_text(text,encoding='utf-8')
    return {'status':'table_copied','line_count':len(lines),'columns':header,'executable':False}
