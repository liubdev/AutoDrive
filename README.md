# AutoDrive

Windows 应用自动化框架 — **UIA 驱动** + **OCR (Windows 内置)** + **图片模板匹配**。
面向 DTS650 诊断仪的自动化采集工具，交付为桌面软件（PySide6）。

## 安装

```bash
pip install pywinauto psutil opencv-python numpy pillow mss winsdk PySide6
```

## 使用

```bash
# 桌面版 GUI：主页选车型/常见问题 → 运行 DTS 诊断仪 → 分析页（描述问题 → 采集 + AI 诊断 → 维修报告）
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
├── ui/                  桌面端 UI（PySide6）
│   ├── logo.py          品牌 Logo：仪表盘造型
│   ├── theme.py         主题：固定浅色 × 强调色（科技蓝 azure），QSS 令牌渲染
│   ├── report.py        输出目录解析（故障码/数据流/文件）
│   ├── pages.py         主页设备选择（ct1）+ 分析页（ct2 单页诊断流 + 进度指示）
│   └── wizard.py        主窗口：双视图（主页 → 分析页）+ 引擎/ AI 桥接
├── vision/              视觉识别
│   ├── ocr.py           Windows 内置 OCR（无需安装）
│   ├── locate.py        图片模板匹配（跨分辨率）
│   └── screenshot.py    截图
├── config/settings.py   全局配置
├── scripts/             控制台运行器
├── autogui.py           PySide6 桌面版入口（单页诊断流，文件日志）
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
