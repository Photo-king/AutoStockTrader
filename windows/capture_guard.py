"""Conservative screen-capture guard; screenshots are still observations, not trusted orders."""
import ctypes as C
from ctypes import wintypes as W
import time


def validate_capture(user, panel):
    user.SetForegroundWindow.argtypes=[W.HWND]
    user.GetForegroundWindow.restype=W.HWND
    user.GetAncestor.argtypes=[W.HWND,W.UINT]
    user.GetAncestor.restype=W.HWND
    user.WindowFromPoint.argtypes=[W.POINT]
    user.WindowFromPoint.restype=W.HWND
    left,top,right,bottom=panel['rect']
    if left<0 or top<0 or right>user.GetSystemMetrics(0) or bottom>user.GetSystemMetrics(1):
        raise ValueError('Trading window is outside primary screen')
    if right-left<400 or bottom-top<250:
        raise ValueError('Trading window is too small')
    user.SetForegroundWindow(panel['handle'])
    time.sleep(.15)
    if user.GetAncestor(user.GetForegroundWindow(),2)!=panel['handle']:
        raise ValueError('Trading capture foreground not confirmed')
    for x,y in [(left+10,top+40),(right-10,top+40),((left+right)//2,(top+bottom)//2),
                (left+10,bottom-10),(right-10,bottom-10)]:
        hit=user.WindowFromPoint(W.POINT(x,y))
        if user.GetAncestor(hit,2)!=panel['handle']:
            raise ValueError('Trading window is occluded')
    return {'status':'sampled_hit_tests_passed','scope':'five_points_not_a_full_occlusion_proof'}
