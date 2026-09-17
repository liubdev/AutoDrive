"""启动认证：当前使用本地演示账号，后续可替换为真实认证服务。"""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from ui.widgets import RunchLogo

__all__ = ["LoginDialog"]


class LoginDialog(QDialog):
    """AutoDrive 登录窗口。

    演示阶段只验证固定账号，不写入密码，也不依赖数据库或网络。
    """

    DEMO_USERNAME = "demo"
    DEMO_PASSWORD = "123456"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LoginDialog")
        self.setWindowTitle("登录 · AutoDrive")
        self.setModal(True)
        self.setWindowModality(Qt.ApplicationModal)
        # 独立登录海报页，不显示未认证的客户端内容；保留标题栏便于拖动。
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint
                            | Qt.WindowCloseButtonHint)
        self.setFixedSize(760, 520)
        self._intro_played = False
        self._transition_anim = None
        self._build_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if self._intro_played:
            return
        self._intro_played = True
        if self.parentWidget() is not None:
            parent = self.parentWidget()
            center = parent.frameGeometry().center()
            self.move(center.x() - self.width() // 2,
                      center.y() - self.height() // 2)
        else:
            screen = self.screen()
            if screen is not None:
                geo = screen.availableGeometry()
                self.move(geo.center().x() - self.width() // 2,
                          geo.center().y() - self.height() // 2)
        end_pos = self.pos()
        self.move(end_pos.x(), end_pos.y() + 10)
        self.setWindowOpacity(0.0)
        opacity = QPropertyAnimation(self, b"windowOpacity", self)
        opacity.setDuration(240)
        opacity.setStartValue(0.0)
        opacity.setEndValue(1.0)
        opacity.setEasingCurve(QEasingCurve.OutCubic)
        self._transition_anim = opacity
        opacity.start()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        poster = QFrame()
        poster.setObjectName("LoginPoster")
        pv = QVBoxLayout(poster)
        pv.setContentsMargins(34, 34, 30, 30)
        pv.setSpacing(12)
        pv.addWidget(RunchLogo(size=46))
        eyebrow = QLabel("RUNCH TECH · DIAGNOSTIC PLATFORM")
        eyebrow.setObjectName("LoginPosterEyebrow")
        pv.addWidget(eyebrow)
        poster_title = QLabel("让每一次诊断\n都有依据。")
        poster_title.setObjectName("LoginPosterTitle")
        poster_title.setWordWrap(True)
        pv.addWidget(poster_title)
        poster_body = QLabel("连接车辆、整理数据、辅助判断，\n让维修过程更清晰、更高效。")
        poster_body.setObjectName("LoginPosterBody")
        poster_body.setWordWrap(True)
        pv.addWidget(poster_body)
        pv.addStretch(1)
        poster_note = QLabel("AutoDrive 车辆诊断与自动化工具")
        poster_note.setObjectName("LoginPosterNote")
        pv.addWidget(poster_note)
        body.addWidget(poster, 1)

        form_host = QFrame()
        form_host.setObjectName("LoginFormHost")
        hv = QVBoxLayout(form_host)
        hv.setContentsMargins(42, 34, 42, 34)
        hv.setSpacing(0)
        form = QFrame()
        form.setObjectName("LoginForm")
        form.setFixedWidth(330)
        fv = QVBoxLayout(form)
        fv.setContentsMargins(0, 0, 0, 0)
        fv.setSpacing(12)
        heading = QLabel("登录诊断平台")
        heading.setObjectName("LoginTitle")
        fv.addWidget(heading)
        hint = QLabel("登录后即可使用诊断、远程协助和报告服务")
        hint.setObjectName("LoginHint")
        fv.addWidget(hint)
        fv.addSpacing(10)

        user_label = QLabel("账号")
        user_label.setObjectName("LoginFieldLabel")
        fv.addWidget(user_label)
        self._username = QLineEdit()
        self._username.setObjectName("LoginInput")
        self._username.setPlaceholderText("请输入账号")
        self._username.setText(self.DEMO_USERNAME)
        self._username.setMinimumHeight(46)
        fv.addWidget(self._username)

        password_label = QLabel("密码")
        password_label.setObjectName("LoginFieldLabel")
        fv.addWidget(password_label)
        self._password = QLineEdit()
        self._password.setObjectName("LoginInput")
        self._password.setPlaceholderText("请输入密码")
        self._password.setEchoMode(QLineEdit.Password)
        self._password.returnPressed.connect(self._login)
        self._password.setMinimumHeight(46)
        fv.addWidget(self._password)

        self._error = QLabel("")
        self._error.setObjectName("LoginError")
        self._error.setMinimumHeight(22)
        fv.addWidget(self._error)

        self._login_btn = QPushButton("登录并进入")
        self._login_btn.setProperty("role", "primary")
        self._login_btn.setMinimumHeight(46)
        self._login_btn.setCursor(Qt.PointingHandCursor)
        self._login_btn.clicked.connect(self._login)
        fv.addWidget(self._login_btn)

        demo = QLabel("演示账号：demo    密码：123456")
        demo.setObjectName("LoginDemoHint")
        demo.setAlignment(Qt.AlignCenter)
        fv.addWidget(demo)
        hv.addStretch(1)
        hv.addWidget(form, 0, Qt.AlignHCenter)
        hv.addStretch(1)
        body.addWidget(form_host, 1)
        root.addLayout(body)

    def _login(self):
        if (self._username.text().strip() == self.DEMO_USERNAME
                and self._password.text() == self.DEMO_PASSWORD):
            self._login_btn.setEnabled(False)
            self._login_btn.setText("正在进入…")
            anim = QPropertyAnimation(self, b"windowOpacity", self)
            anim.setDuration(180)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.InCubic)
            anim.finished.connect(self.accept)
            self._transition_anim = anim
            anim.start()
            return
        self._error.setText("账号或密码不正确，请使用演示账号登录")
        self._password.selectAll()
        self._password.setFocus()
