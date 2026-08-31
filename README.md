# AutoDrive

Windows 应用自动化框架 — **UIA 驱动** + **OCR (Windows 内置)** + **图片模板匹配**。
面向 DTS650 诊断仪的自动化采集工具，交付为桌面软件（PySide6）。

## 安装

```bash
pip install pywinauto psutil opencv-python numpy pillow mss winsdk PySide6
```

## 使用

```bash
# 桌面版 GUI：主页选设备/常见故障 → 开始AI智能诊断 → 采集 + AI 三阶段 → 维修报告
# 采集完成自动结合故障码/数据流/知识库生成诊断方案，无需手动输入
python autogui.py

# 控制台版（同一份流程定义）
python main.py script scripts/run_dts.py
```

日志对用户隐藏：运行日志写入 `data/logs/autodrive_YYYYMMDD.log`，界面不展示。

## 项目结构

```
AutoDrive/
├── automation/
│   ├── apps/            应用适配：BaseApp 基类 + 各应用模块
│   │   ├── __init__.py  BaseApp：窗口连接/控件定位/OCR/键盘
│   │   └── dts.py       DTS 诊断仪自动化
│   ├── flow/            流程引擎（FlowStep + FlowEngine，事件/取消）
│   └── flows/           可配置流程定义（dts_flow.py）
├── ui/                  桌面端 UI（PySide6，LCS700 诊断平台外壳）
│   ├── appshell.py      应用外壳：顶栏 + QStackedWidget（19 页）+ 底栏 + Toast/模态
│   ├── theme.py         主题系统：深色默认 + 浅色切换（QSettings ui/mode 持久化）
│   ├── theme_qss.py     LCS 版 QSS 令牌模板（双主题共用，按页分段）
│   ├── lcsdata.py       演示数据常量（设备/症状/骨架页/演示报告，源自 RunchTech_V01.html）
│   ├── widgets.py       QPainter 控件：SvgGlyph / RunchLogo / PhaseBar / GradBar / Toast…
│   ├── report.py        输出目录解析（故障码/数据流/文件）+ ReportStore 报告列表
│   ├── pages/           页面包（19 页：home / ai_diag / report / settings / account /
│   │                    remote* / special* / update，骨架页复用 SkeletonPage 基类）
│   └── wizard.py        主窗口：构建页面 + AppShell + DTS 引擎 / AI 三阶段桥接
├── vision/              视觉识别
│   ├── ocr.py           Windows 内置 OCR（无需安装）
│   ├── locate.py        图片模板匹配（跨分辨率）
│   └── screenshot.py    截图
├── config/settings.py   全局配置
├── scripts/             控制台运行器 + GUI 冒烟测试
├── docs/                设计源（RunchTech_V01.html）
├── autogui.py           PySide6 桌面版入口（LCS700 外壳，文件日志）
├── main.py              入口
└── build_exe.py         Nuitka onefile 打包
```

## 自绘按钮定位策略

| 方式 | 方法 | 跨分辨率 |
|------|------|---------|
| UIA 控件 | `child_window(auto_id=...)`|
| OCR 文字 | `click_text("按钮名")`|
| 图片模板 | `click_image("模板.png")`|
| 锚点比例 | `_click_below_text(rx, ry)`|
