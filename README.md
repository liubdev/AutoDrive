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

## DTS 启动与前段导航

完整采集（GUI「开始AI智能诊断」和控制台共用流程）会先检查配置的
`dts_exe`，结束同一路径的已有实例，最多等待退出 10 秒，然后重新启动。
无法核对进程路径、没有结束权限或退出超时都会中止，避免沿用旧页面。

启动确认采用 `确认 / 1`，识别弹窗采用 `直接进入 / 1058` 精确匹配。
自绘菜单保留相对锚点定位，发动机第一项使用 Inspect 提供的窗格相对位置；
点击一次后每 200 毫秒探测可见且可用的目标控件，就绪即继续，超时停止。
前段不再重放坐标点击或重复验证旧版 `1197 / 6` 控件。
这些选择器针对提供的 DTS 20260706 页面，其他版本或「车上使用」需重新核对。

跨平台逻辑回归：`python scripts/probe_dts_startup.py` 和
`python scripts/probe_flow_order.py`。真实控件、分辨率适配和耗时需在 Windows DTS 上验证。
