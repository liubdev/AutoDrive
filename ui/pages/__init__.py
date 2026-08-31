"""
ui.pages 包 —— LCS700 页面集合。

PAGE_REGISTRY：page_id → 页面类（AppShell 导航；MainWindow 实例化）。
"""

from ui.pages.base import LcsPage, _prop, section_header  # noqa: F401
from ui.pages.home import HomePage  # noqa: F401
from ui.pages.ai_diag import AiDiagPage  # noqa: F401
from ui.pages.report import ReportListPage  # noqa: F401
from ui.pages.settings import SettingsPage  # noqa: F401
from ui.pages.account import AccountPage  # noqa: F401
from ui.pages.remote import RemotePage, RemoteCtrlPage, RemoteInvitePage  # noqa: F401
from ui.pages.special import (  # noqa: F401
    AdvancedPage, CanPage, EbsDataflowPage, EbsDtcPage, EbsEcuPage, EbsFuncPage,
    EbsInfoPage, EbsMatchPage, EbsTestPage, SkeletonPage, SpecialPage, UpdatePage,
)
from ui.widgets import PhaseBar  # noqa: F401  兼容旧 import from ui.pages import PhaseBar

PAGE_REGISTRY = {
    "home": HomePage,
    "ai-diagn": AiDiagPage,
    "report": ReportListPage,
    "settings": SettingsPage,
    "account": AccountPage,
    "remote": RemotePage,
    "remote-ctrl": RemoteCtrlPage,
    "remote-invite": RemoteInvitePage,
    "special": SpecialPage,
    "advanced": AdvancedPage,
    "ebs": EbsEcuPage,
    "ebs-func": EbsFuncPage,
    "ebs-info": EbsInfoPage,
    "ebs-dtc": EbsDtcPage,
    "ebs-dataflow": EbsDataflowPage,
    "ebs-test": EbsTestPage,
    "ebs-match": EbsMatchPage,
    "can": CanPage,
    "update": UpdatePage,
}
