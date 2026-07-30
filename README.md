# AutoDrive

Windows 应用自动化框架 — **UIA 驱动** + **OCR (Windows 内置)** + **图片模板匹配**。

## 安装

```bash
pip install pywinauto psutil opencv-python numpy pillow mss winsdk
```

## 使用

```bash
python main.py script scripts/run_dts.py
```

## 项目结构

```
AutoDrive/
├── automation/apps/     核心：BaseApp（基类）+ 各应用模块
│   ├── __init__.py      BaseApp：窗口连接/控件定位/OCR/键盘
│   └── dts.py           DTS 诊断仪自动化
├── vision/              视觉识别
│   ├── ocr.py           Windows 内置 OCR（无需安装）
│   ├── locate.py        图片模板匹配（跨分辨率）
│   └── screenshot.py    截图
├── config/settings.py   全局配置
├── scripts/             自动化脚本
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
