# 2026-10-24 连接与只读桌面验证

公钥由用户在 Windows 管理员 PowerShell 中运行现有 StockAgent 安装脚本登记，SSH BatchMode 登录成功。

远程只读检查确认 Windows Python 3.12.10 可运行，pywinauto、Pillow、win32gui 尚未安装。没有安装依赖。

临时 Interactive 任务在 session 2 成功执行 ctypes/Win32 探测；输入桌面可打开，屏幕尺寸为 1920×1080。同花顺主窗口及子控件可枚举。交易进程存在，但可见窗口只有 236×29 的小面板；不能据此判断银河账户是否登录，或宣称交易控件已经可用。

探测任务已进入成功返回及 finally 清理路径。未操作键盘鼠标，未读取账户内容，未修改 StockAgent 文件、服务、策略或配置。诊断脚本仅写入独立的 C:\AutoStockTrader\diagnostics。

已通过本机 Python 语法检查及 Windows 实际运行验证。不使用 Mac 模拟结果代替 Windows 验证。待用户显示完整交易面板后继续。

## 完整面板复查

用户打开交易页后进程已更换，探测重新解析实时 PID，完整窗口可见。资金标签与数字格式经只读 WM_GETTEXT 验证，具体金额和其他文本不保存，输入框不读取。观察映射记录在 config/ths-observed-controls.json。

持仓 CVirtualGridCtrl 的 UIAutomation 元数据为 ControlType.Pane、patterns=[]、child_count=0。当前 UIA 路径不能直接读取持仓，不得解释为空仓。后续需要验证应用自带导出或复制途径。

扩展探测在 Windows 实际运行成功，任务进入 finally 清理路径。没有点击、输入、复制剪贴板、导出数据或下单。
