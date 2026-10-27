# AutoStockTrader

Windows 11 同花顺／银河证券交易自动化原型。当前完成远程接入、资金字段读取、查询页导航、持仓直接复制文本，以及 Windows 本机 OCR 实验路径。**没有下单功能，也没有自动交易策略。**

## 实际验证结果

- N150 通过 StockAgent 已固定主机密钥的 SSH 入口连接。SSH 在会话 0，同花顺在交互桌面会话 2。
- 使用已有 Python 3.12.10：`C:\StockAgent\.venv\Scripts\python.exe`。未安装第三方依赖，未修改 StockAgent 服务、源码或配置。
- 临时交互式计划任务可枚举同花顺及交易窗口。交易程序为 `xiadan.exe`；每次重新解析 PID 和句柄。
- 8 个资金 Static 字段可读取并保存于 Windows 私有文件；标准报告只保留白名单标签、字段数和一致性，具体值脱敏，不读取 Edit 输入框。现金余额加股票市值与总资产的一次核对通过。
- 持仓 `CVirtualGridCtrl` 没有暴露 UIA 表格模式和子元素。发现交易客户端为管理员权限，普通任务的输入会被隔离；高权限任务已能切换查询页并读到包含复制／保存的右键菜单，已通过向实际菜单所属窗口调用精确复制命令取得新持仓 TSV，当前一条持仓可解析，复制出的持仓市值合计与资金页一致；尚未验收多行和完整账户范围。
- Windows 自带 `zh-Hans-CN` OCR 可用。对表格区域裁切、放大 2 倍并增强红色文字对比度后，能解析当前可见持仓记录的代码、名称、数量、可用数量。
- OCR 结果仅为候选：`verified=false`、`executable=false`、`complete_portfolio=false`。尚未验证滚动翻页、多行、其他字体／缩放、多账户、委托和成交页。

## 运行

在 Mac 项目目录执行，远程命令需要网络执行权限：

```sh
# 后台只读结构检查，不发送键鼠事件
python3 scripts/windows-readonly.py
python3 scripts/windows-desktop-probe.py
python3 scripts/summarize-probe.py

# 可选：验证持仓表格右键菜单，只打开和取消，不选择项目
python3 scripts/windows-desktop-probe.py --elevated --inspect-menu

# 可选：调用已核验菜单的复制功能，可能替换剪贴板
python3 scripts/windows-desktop-probe.py --elevated --read-funds --copy-menu

# 可选：确认表格焦点后测试快捷键复制，可能替换剪贴板
python3 scripts/windows-desktop-probe.py --elevated --copy-grid

# 可选：截图、Windows 本机 OCR、解析可见持仓候选，不发送交易指令
python3 scripts/windows-desktop-probe.py --elevated --ocr-grid
python3 scripts/parse-positions.py

# 查询导航及只读观测
python3 scripts/windows-desktop-probe.py --elevated --page orders --ocr-grid
python3 scripts/windows-desktop-probe.py --elevated --page trades --ocr-grid
python3 scripts/windows-desktop-probe.py --elevated --page holdings --read-funds --ocr-grid

# 解析器异常处理测试（合成数据）
python3 -m unittest discover -s tests -v
```

只读窗口枚举不移动鼠标，因此桌面上通常看不到动作。菜单和复制模式会短暂移动鼠标，应避免同时手动操作。操作前检查页面标签、唯一目标表格、前台窗口和鼠标命中控件；复制前还检查键盘焦点和修饰键。

## 文件与隐私

连接复用 `/Users/photo-king/Projects/StockAgent/scripts/windows-ssh.sh`，不复制私钥，不保存密码。

本项目诊断脚本部署于 `C:\AutoStockTrader\diagnostics`。临时 `AutoStockTrader-ReadOnlyProbe` 计划任务使用已登录用户的交互式令牌，执行后 finally 停止并注销。`--elevated` 显式使用 Highest，与管理员客户端匹配；默认 Limited 下检测到权限低于目标时拒绝输入。如果 SSH／PowerShell 被强制终止，需检查是否有遗留任务；已有同名任务时拒绝覆盖。脚本与诊断数据保留在 Windows，并非后台常驻服务。

本机原始报告位于 `reports/desktop-report.json`；截图和 OCR 原始内容位于 `.local/`。两者均已被 Git 忽略。每次新运行还在 `.local/runs/<run_id>` 保存独立证据；最新通用 OCR 位于 `.local/query-ocr-private.json`，带截图时间以避免误用旧数据。Windows diagnostics 中同样保留截图和原始 OCR，包含真实账户数据，应作为私有文件管理。聊天和普通验证报告不复述账户、持仓或金额。

`config/ths-observed-controls.json` 仅为观察映射。不能仅凭控件编号判断页面；客户端更新后需重新验证标签、范围、可见性和唯一性。

## 尚待完成

1. 核对 OCR 与原始持仓的一致性，覆盖多行、滚动、遮挡、缩放、读数错误；目前不将无读数解释为空仓。
2. 资金读取适配器已完成当前页面验证；继续完善委托、成交记录读取，确认券商身份、登录失效和锁屏状态。
3. 独立实现策略回测及模拟账本，纳入费用、滑点、复权、停牌、涨跌停和 T+1。
4. 实现订单状态持久化及幂等，未知状态先查委托，不重试提交。
5. 验证人工确认订单后，再考虑小额自动执行。

输入桌面可读取不代表无人值守已验收。远程桌面断开、重启、休眠、锁屏、断网恢复均未验证，电源与开机启动设置未修改。

## 最新查询验证

见 [账户与查询页验证](reports/account-query-validation.md)。已实际切换当日委托／成交页；当前为空表或“没有可撤委托单”视图，机器读取返回 inconclusive，不推断全账户零订单。29 项测试通过。还需非空订单状态及多行读取验收，不能连接实盘执行。

持仓优先使用直接复制文本；OCR 仍是未验收备选。最后一次被选中高亮的持仓行使 OCR 数量读取失败，结果已正确标记为 unreadable，不应覆盖成功取得的直接复制数据。两条来源分别记录，均不连接实盘执行。

最近完成的直接复制验证：`20261025T005950Z-4a761dbb`。`--elevated --read-funds --copy-menu` 已实际取得新 TSV，Windows 与本机解析记录数相同，持仓市值合计与资金页相符。复制内容及各次证据只存于 `.local/` 和 Windows diagnostics。
