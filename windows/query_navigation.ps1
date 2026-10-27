param([Parameter(Mandatory=$true)][long]$RootHandle, [ValidateSet('inspect','holdings','orders','trades')][string]$Page='inspect')
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$labels=@{holdings='资金股份'; orders='当日委托'; trades='当日成交'}
$root=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]$RootHandle)
$condition=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::TreeItem)
$nodes=$root.FindAll([Windows.Automation.TreeScope]::Descendants,$condition)
$available=@()
$target=@()
foreach($node in $nodes) {
    if ($labels.Values -contains $node.Current.Name -and -not $node.Current.IsOffscreen) {
        $r=$node.Current.BoundingRectangle
        $available+=@{label=$node.Current.Name; rect=@($r.Left,$r.Top,$r.Right,$r.Bottom)}
        if ($Page -ne 'inspect' -and $node.Current.Name -eq $labels[$Page]) { $target+=,$node }
    }
}
if($Page -eq 'inspect') { @{status='inspected'; available=$available} | ConvertTo-Json -Depth 5 -Compress; exit }
if($target.Count -ne 1) { throw 'Query navigation item is missing or ambiguous' }
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class AstQueryNative {
 [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; public POINT(int x,int y){X=x;Y=y;} }
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr h,uint flags);
 [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
 [DllImport("user32.dll")] public static extern short GetAsyncKeyState(int k);
 [DllImport("user32.dll")] public static extern void mouse_event(uint flags,uint dx,uint dy,uint data,UIntPtr extra);
}
'@
foreach($key in @(0x10,0x11,0x12,0x5b,0x5c)) {
 if(([AstQueryNative]::GetAsyncKeyState($key) -band 0x8000) -ne 0) { throw 'Modifier held; query navigation refused' }
}
[void][AstQueryNative]::SetForegroundWindow([IntPtr]$RootHandle)
Start-Sleep -Milliseconds 200
if([AstQueryNative]::GetAncestor([AstQueryNative]::GetForegroundWindow(),2).ToInt64() -ne $RootHandle) { throw 'Foreground verification failed' }
$rectangle=$target[0].Current.BoundingRectangle
$x=[int](($rectangle.Left+$rectangle.Right)/2)
$y=[int](($rectangle.Top+$rectangle.Bottom)/2)
$point=New-Object AstQueryNative+POINT($x,$y)
$hit=[AstQueryNative]::WindowFromPoint($point)
$element=[Windows.Automation.AutomationElement]::FromHandle($hit)
if($element.Current.ClassName -ne 'SysTreeView32' -or [AstQueryNative]::GetAncestor($hit,2).ToInt64() -ne $RootHandle) { throw 'Query tree is occluded or changed' }
$old=New-Object AstQueryNative+POINT
if(-not [AstQueryNative]::GetCursorPos([ref]$old)) { throw 'Cursor unavailable' }
try {
 [void][AstQueryNative]::SetCursorPos($x,$y)
 [AstQueryNative]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
 [AstQueryNative]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
 Start-Sleep -Milliseconds 600
 $pattern=$target[0].GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern)
 if(-not $pattern.Current.IsSelected) { throw 'Query item selection not confirmed' }
 @{status='query_selected'; page=$Page; label=$labels[$Page]; selected=$true} | ConvertTo-Json -Compress
} finally { [void][AstQueryNative]::SetCursorPos($old.X,$old.Y) }
