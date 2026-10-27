"""Read Windows process integrity levels; do not elevate or change tokens."""
import ctypes as C
from ctypes import wintypes as W
import os


def process_integrity(pid):
    kernel=C.WinDLL('kernel32',use_last_error=True)
    adv=C.WinDLL('advapi32',use_last_error=True)
    kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
    kernel.CloseHandle.argtypes=[W.HANDLE]
    adv.OpenProcessToken.argtypes=[W.HANDLE,W.DWORD,C.POINTER(W.HANDLE)]
    adv.GetTokenInformation.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.POINTER(W.DWORD)]
    adv.GetSidSubAuthorityCount.argtypes=[C.c_void_p];adv.GetSidSubAuthorityCount.restype=C.POINTER(W.BYTE)
    adv.GetSidSubAuthority.argtypes=[C.c_void_p,W.DWORD];adv.GetSidSubAuthority.restype=C.POINTER(W.DWORD)
    process=kernel.OpenProcess(0x1000,False,pid)
    if not process:return {'status':'unavailable','winerror':C.get_last_error()}
    token=W.HANDLE()
    try:
        if not adv.OpenProcessToken(process,8,C.byref(token)):
            return {'status':'unavailable','winerror':C.get_last_error()}
        size=W.DWORD()
        adv.GetTokenInformation(token,25,None,0,C.byref(size))
        buf=C.create_string_buffer(size.value)
        if not adv.GetTokenInformation(token,25,buf,size,C.byref(size)):
            return {'status':'unavailable','winerror':C.get_last_error()}
        sid=C.cast(buf,C.POINTER(C.c_void_p))[0]
        count=adv.GetSidSubAuthorityCount(sid)[0]
        rid=adv.GetSidSubAuthority(sid,count-1)[0]
        level='system' if rid>=0x4000 else 'high' if rid>=0x3000 else 'medium' if rid>=0x2000 else 'low'
        return {'status':'read','level':level,'rid':rid}
    finally:
        if token:kernel.CloseHandle(token)
        kernel.CloseHandle(process)


def integrity_report(pids):
    return {'probe':process_integrity(os.getpid()),'targets':{str(pid):process_integrity(pid) for pid in pids}}
