#!/usr/bin/env python3
"""验证修复：
  110. ai_diag reset() 全量清空（动态信息/车辆信息/故障码/结果）→ 重新执行等新内容
  111. report 页 prepare_run()/finish_run() 采集中等待态 ↔ 收尾刷新
"""
import os, sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import QSettings
QSettings("AutoDrive", "AutoDrive").clear()

from ui.theme import ThemeManager
from ui.pages.ai_diag import AiDiagPage
from ui.pages.report import ReportListPage

app = QApplication([])
ThemeManager(app).apply()

ok = True
def check(name, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ ") + name)
    ok = ok and cond

# ── #110：reset 全量清空 ─────────────────────────────
ai = AiDiagPage()
# 模拟上一次诊断的残留内容
ai.append_dyn("上一次的动态消息 1", cls="done")
ai.append_dyn("上一次的动态消息 2")
ai.set_vin({"vin": "LSVOLDVIN", "model": "旧车型", "mileage": "123", "ecu": "EDC17"})
ai.set_faults([{"code": "P0401", "desc": "旧故障", "status": "cur"}])
ai.show_report({"diagnosisList": [{"faultPoint": "旧原因", "probability": "最大"}],
                "_meta": "旧报告摘要"})

check("模拟残留：动态 2 条", ai._dyn_list.count() == 2)
check("模拟残留：故障码 1 条", ai._veh_dtc_list.count() == 1)
check("模拟残留：结果摘要非空", bool(ai._result_meta.text()))

ai.reset()

check("#110 动态信息清空", ai._dyn_list.count() == 0)
check("#110 车辆信息回 '—'",
      all(v.text() == "—" for v in ai._veh_vals.values()))
check("#110 故障码清空", ai._veh_dtc_list.count() == 0)
check("#110 结果摘要清空", ai._result_meta.text() == "")
check("#110 result 复位 None", ai._result is None)
check("#110 vin 标签隐藏", ai._vin_tag.isHidden())
check("#110 结果标签隐藏", ai._result_tag.isHidden())
check("#110 原因条清空", ai._causes_lay.count() == 0)

# ── #111：report 采集中 / 收尾 ────────────────────────
rp = ReportListPage()
rp.refresh()   # 真实 store 扫描（可能含历史报告）→ 表头 + N 行
n_before = rp._list.count()
check("refresh 后列表 ≥2 项（表头+行）", n_before >= 2)
check("refresh 后计数含 份报告", "份报告" in rp._count_tag.text())

rp.prepare_run()
check("#111 prepare_run 置 running", rp._running is True)
check("#111 旧列表清空（仅等待提示）", rp._list.count() == 1
      and rp._list.itemAt(0).widget().objectName() == "rlEmpty")
check("#111 计数标签变 采集中", rp._count_tag.text() == "采集中…")
check("#111 白纸详情隐藏", rp._paper.isHidden())

rp.finish_run()
check("#111 finish_run 复位 running", rp._running is False)
check("#111 收尾刷新恢复列表（与刷新前一致）", rp._list.count() == n_before)
check("#111 计数标签恢复", "份报告" in rp._count_tag.text())

# 采集中态下 on_enter 不覆盖等待提示
rp.prepare_run()
rp.on_enter()
check("#111 采集中 on_enter 保持等待态", rp._list.count() == 1
      and rp._list.itemAt(0).widget().objectName() == "rlEmpty")
rp.finish_run()
rp.on_enter()
check("#111 收尾后 on_enter 正常刷新", rp._list.count() == n_before)

print(f"== RE-RESET PROBE {'PASS' if ok else 'FAIL'} ==")
sys.exit(0 if ok else 1)
