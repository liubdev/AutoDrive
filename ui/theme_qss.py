"""
LCS700 版 QSS 模板 —— 单一文本文件 `ui/theme.qss`，全部 {token} 占位。

设计源：docs/RunchTech_V01.html（远驰科技·智能诊断平台 LCS700）。
双模式主题通过 ui/theme.py 的 build_tokens() 生成令牌后 render_qss() 替换。

外部化到文本文件的目的：
  - scripts/dev_run.py 用 QFileSystemWatcher 监听本文件，改样式保存即热更新，无需重启；
  - Nuitka 打包时需补 `--include-data-file=ui/theme.qss=ui/theme.qss`。

控件契约（与 ui/widgets.py / ui/pages/ 对齐）：
  - 顶部栏 #TBar：#BrandBtn（RunchLogo + #BrandCn/#BrandEn，点击回首页）+ #PageTitlePill + #CnPill + #ExitBtn
  - 底部栏 #BBar：#AccountBtn（#AvatarLabel+#AccountName）+ #bbRight 上下文按钮 #bbBtn[bb="primary"]
  - 按钮 role 属性：primary（渐变）/ ghost / mini / danger / link
  - 卡片 role 属性：glass（毛玻璃）/ grid-card / list-row / set-row / ec-row / quick
  - 标签 QLabel[role="tag"][kind=ok|warn|crit|acc|muted]
  - 状态胶囊 QLabel#dynStatus[state=running|thinking|done|error]
  - 相控步进器 QFrame#stepsBar QLabel#StepDot[stepState=done|current|next]
  - 概率条 GradBar 由 QPainter 自绘（#gradBar 只做背景/边框）
"""

from pathlib import Path

_QSS_FILE = Path(__file__).resolve().parent / "theme.qss"

QSS_TEMPLATE = _QSS_FILE.read_text(encoding="utf-8")


def reload_template() -> str:
    """重新从磁盘读取 ui/theme.qss（热重载入口）。

    修改文件后调用本函数 + ThemeManager.apply() 即生效。
    返回新模板内容。
    """
    global QSS_TEMPLATE
    QSS_TEMPLATE = _QSS_FILE.read_text(encoding="utf-8")
    return QSS_TEMPLATE
