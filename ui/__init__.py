"""AutoDrive 桌面端 UI 包。

分层：
  ui/theme.py   主题系统（浅色恒定 + 强调色，QSS 构建）
  ui/report.py  输出目录解析 → 故障码 / 数据流 / 文件
  ui/pages.py   单页连续诊断流（①采集运行 ②采集结果 ③AI 诊断）+ 进度指示 PhaseBar
  ui/wizard.py  主窗口（顶栏 + 进度指示 + 单页诊断流）
"""
