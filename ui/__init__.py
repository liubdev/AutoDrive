"""AutoDrive 桌面端 UI 包。

分层（LCS700 诊断平台外壳，替换旧 ct1/ct2 双视图）：
  ui/theme.py       主题系统（深色默认 + 浅色切换，QSettings ui/mode 持久化，QSS 令牌）
  ui/theme_qss.py   LCS 版 QSS 模板（双主题共用 {token} 占位，按页分段）
  ui/lcsdata.py     演示数据常量（源自 docs/RunchTech_V01.html 的 JS 数据）
  ui/widgets.py     QPainter 控件：SvgGlyph / RunchLogo / PhaseBar / GradBar / Toast 等
  ui/appshell.py    应用外壳：顶栏 + QStackedWidget（PAGE_ORDER 19 页）+ 底栏 + Toast/模态
  ui/report.py      输出目录解析（故障码/数据流/文件）+ ReportStore 报告列表
  ui/pages/         页面包（home / ai_diag / report / settings / account / remote* / special*）
  ui/wizard.py      主窗口：构建 19 页 + AppShell 导航 + DTS 引擎 / AI 三阶段桥接
"""
