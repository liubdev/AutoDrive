# AutoDrive

Windows 应用自动化框架 — **UIA 驱动** + **OCR (Windows 内置)** + **图片模板匹配**。
面向 DTS650 诊断仪的自动化采集工具，交付为桌面软件（PySide6）。

## 安装

```bash
pip install pywinauto psutil opencv-python numpy pillow mss winsdk PySide6
```

## 使用

```bash
# 桌面版 GUI：极简主页 → 向导（①运行 ②数据 ③AI分析）
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
├── ui/                  桌面端 UI（PySide6）
│   ├── logo.py          品牌 Logo：仪表盘造型（主页静态展示）
│   ├── theme.py         主题：固定浅色 × 强调色（信号青），QSS 令牌渲染
│   ├── report.py        输出目录解析（故障码/数据流/文件）
│   ├── pages.py         主页(极简) + ①运行 ②数据 ③AI分析 页面
│   └── wizard.py        主窗口：主页 → 向导面板（两级导航 + 引擎桥接）
├── vision/              视觉识别
│   ├── ocr.py           Windows 内置 OCR（无需安装）
│   ├── locate.py        图片模板匹配（跨分辨率）
│   └── screenshot.py    截图
├── config/settings.py   全局配置
├── scripts/             控制台运行器
├── autogui.py           PySide6 桌面版入口（极简主页 → 主窗口，文件日志）
├── main.py              入口
└── build_exe.py         打包
```

## 自绘按钮定位策略

| 方式 | 方法 | 跨分辨率 |
|------|------|---------|
| UIA 控件 | `child_window(auto_id=...)`|
| OCR 文字 | `click_text("按钮名")`|
| 图片模板 | `click_image("模板.png")`|
| 锚点比例 | `_click_below_text(rx, ry)`|
