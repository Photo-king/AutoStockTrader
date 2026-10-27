"""Read-only query navigation using exact OCR text and verified tree hit-testing."""
import base64
import ctypes as C
from ctypes import wintypes as W
import json
import subprocess
import time

LABELS = {'holdings': '资金股份', 'orders': '当日委托', 'trades': '当日成交'}


def navigate_query(user, root, base, page=None):
    trees = [c for c in root['children'] if c['visible'] and c['enabled'] and c['class'] == 'SysTreeView32'
             and c['rect'][2]-c['rect'][0] > 100 and c['rect'][3]-c['rect'][1] > 200]
    if len(trees) != 1:
        raise ValueError('Query tree missing or ambiguous')
    tree = trees[0]
    user.SetForegroundWindow.argtypes = [W.HWND]
    user.GetForegroundWindow.restype = W.HWND
    user.GetAncestor.argtypes = [W.HWND, W.UINT]
    user.GetAncestor.restype = W.HWND
    user.WindowFromPoint.argtypes = [W.POINT]
    user.WindowFromPoint.restype = W.HWND
    user.GetAsyncKeyState.argtypes = [C.c_int]
    user.GetAsyncKeyState.restype = C.c_short
    user.GetCursorPos.argtypes = [C.POINTER(W.POINT)]
    user.SetCursorPos.argtypes = [C.c_int, C.c_int]
    user.mouse_event.argtypes = [W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t]
    if not user.IsWindowVisible(root['handle']):
        raise ValueError('Trading window no longer visible')
    user.SetForegroundWindow(root['handle'])
    time.sleep(.2)
    if user.GetAncestor(user.GetForegroundWindow(), 2) != root['handle']:
        raise ValueError('Trading foreground verification failed')
    left, top, right, bottom = tree['rect']
    for x, y in [(left+20,top+20),(right-20,bottom-20)]:
        if user.WindowFromPoint(W.POINT(x,y)) != tree['handle']:
            raise ValueError('Query tree occluded')
    image = base / 'query-tree.png'
    ps = r"""$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue';
Add-Type -AssemblyName System.Drawing;
$b=New-Object Drawing.Bitmap(WIDTH,HEIGHT);$g=[Drawing.Graphics]::FromImage($b);
try {$g.CopyFromScreen(LEFT,TOP,0,0,$b.Size);$b.Save('IMAGE',[Drawing.Imaging.ImageFormat]::Png)}
finally {$g.Dispose();$b.Dispose()}
""".replace('WIDTH',str(right-left)).replace('HEIGHT',str(bottom-top)).replace('LEFT',str(left)).replace('TOP',str(top)).replace('IMAGE',str(image))
    encoded=base64.b64encode(ps.encode('utf-16le')).decode()
    capture=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],
                           capture_output=True,timeout=8,creationflags=0x08000000)
    if capture.returncode:
        raise ValueError('Query tree screenshot failed')
    raw_path=base / 'query-tree-ocr-private.json'
    ocr=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
        '-File',str(base/'native_ocr.ps1'),'-ImagePath',str(image),'-OutputPath',str(raw_path),
        '-Scale','3','-CropLeft','0','-CropTop','0','-CropWidth',str(right-left),'-CropHeight',str(bottom-top)],
        capture_output=True,timeout=15,creationflags=0x08000000)
    if ocr.returncode:
        (base/'navigation-ocr-error.txt').write_bytes(ocr.stderr)
        raise ValueError('Query tree OCR failed')
    raw=json.loads(raw_path.read_text(encoding='utf-8-sig'))
    from navigation_ocr import find_query_labels
    targets=find_query_labels(raw,left,top)
    samples=[''.join(w['text'] for w in sorted(line['words'],key=lambda w:w['left']))
             for line in raw['lines']]
    if (page is not None and not any(t['label']==LABELS[page] for t in targets)) or (page is None and len(targets)<3):
        fallback=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
            '-File',str(base/'native_ocr.ps1'),'-ImagePath',str(image),'-OutputPath',str(raw_path),
            '-Scale','2','-CropLeft','0','-CropTop','0','-CropWidth',str(right-left),'-CropHeight',str(bottom-top)],
            capture_output=True,timeout=15,creationflags=0x08000000)
        if fallback.returncode==0:
            second=json.loads(raw_path.read_text(encoding='utf-8-sig'))
            extra=find_query_labels(second,left,top)
            for item in extra:
                existing=[t for t in targets if t['label']==item['label']]
                if not existing:targets.append(item)
                elif len(existing)!=1 or max(abs(a-b) for a,b in zip(existing[0]['rect'],item['rect']))>5:
                    raise ValueError('Inconsistent query-label positions across OCR scales')
    result={'status':'inspected','method':'exact_ocr_tree','available':targets,
            'query_text_samples':[text for text in samples if ('委' in text or '成交' in text or '资金' in text) and len(text)<14]}
    if page is None:
        return result
    if page not in LABELS:
        raise ValueError('Unsupported query page')
    matches=[item for item in targets if item['label']==LABELS[page]]
    restore_previous = False
    if len(matches) != 1 and page == 'holdings':
        matches = [item for item in targets if item['label'] == LABELS['orders']]
        restore_previous = len(matches) == 1
    if len(matches)!=1:
        raise ValueError('Exact query label missing or ambiguous')
    if any(user.GetAsyncKeyState(k)&0x8000 for k in [0x10,0x11,0x12,0x5B,0x5C]):
        raise ValueError('Modifier held; query click refused')
    l,t,r,b=matches[0]['rect']; x,y=round((l+r)/2),round((t+b)/2)
    if user.WindowFromPoint(W.POINT(x,y))!=tree['handle']:
        raise ValueError('Query label occluded')
    if user.GetAncestor(user.GetForegroundWindow(),2)!=root['handle']:
        raise ValueError('Foreground changed before query click')
    original=W.POINT()
    if not user.GetCursorPos(C.byref(original)):
        raise ValueError('Cursor unavailable')
    try:
        user.SetCursorPos(x,y)
        user.mouse_event(2,0,0,0,0);user.mouse_event(4,0,0,0,0)
        time.sleep(.7)
        if restore_previous:
            selected = C.c_size_t(); previous = C.c_size_t(); answer = C.c_size_t()
            if not user.SendMessageTimeoutW(tree['handle'], 0x110A, 9, 0, 2, 500, C.byref(selected)) or not selected.value:
                raise ValueError('Native query selection unavailable')
            if not user.SendMessageTimeoutW(tree['handle'], 0x110A, 2, selected.value, 2, 500, C.byref(previous)) or not previous.value:
                raise ValueError('Previous native query node unavailable')
            user.SendMessageTimeoutW(tree['handle'], 0x110B, 9, previous.value, 2, 500, C.byref(answer))
            time.sleep(.7)
    finally:
        user.SetCursorPos(original.x,original.y)
    result.update(native_previous_query_selected=restore_previous, status='query_clicked_needs_page_verification',page=page,label=LABELS[page])
    return result
