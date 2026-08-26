"""AutoDrive 桌面端 UI 包。

分层：
  ui/theme.py   主题系统（浅色恒定 + 强调色，QSS 构建）
  ui/report.py  输出目录解析 → 故障码 / 数据流 / 文件
  ui/pages.py   主页设备选择（ct1）+ 分析页（ct2 单页诊断流 + 四节点步进器）
  ui/wizard.py  主窗口（共享顶栏 + 双视图导航 + 引擎 / AI 桥接）
"""
