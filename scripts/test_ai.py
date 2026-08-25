#!/usr/bin/env python3
"""AI 链路验证脚本（本机可跑，无需真车、无需真实 API key）。

用法: python scripts/test_ai.py
"""
import io
import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

PASS, FAIL = 0, 0


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


# ═══════════════════════════════════════════════════════════
#  0. 模块导入
# ═══════════════════════════════════════════════════════════

def test_imports():
    print("\n[0] 模块导入")
    from ai import AiDiagnosticChain, DeepSeekClient, AiError  # noqa
    from ai.context import build_slots, csv_to_markdown, fault_codes_table, supported_streams  # noqa
    from ai.prompts import load_template, render, build_messages  # noqa
    from ai.chain import extract_json  # noqa
    from ai.knowledge import load_default_knowledge  # noqa
    ok("ai 包导入", True)
    for stage in (1, 2, 3):
        tpl = load_template(stage)
        ok(f"模板{stage}加载", len(tpl) > 500, f"len={len(tpl)}")
        assert "{placeholder}" not in tpl, "模板里残留示例占位"
    # UI 模块冒烟（PySide6 导入，不建窗口）
    try:
        import ui.pages, ui.wizard, ui.report, ui.theme  # noqa
        ok("ui 模块导入", True)
    except Exception as e:
        ok("ui 模块导入", False, f"{type(e).__name__}: {e}")


# ═══════════════════════════════════════════════════════════
#  1. DeepSeek 客户端（本地 HTTP 桩）
# ═══════════════════════════════════════════════════════════

class _Stub(BaseHTTPRequestHandler):
    responses = []        # [(status, json_body), ...]，按顺序消费
    requests = []         # 收到的请求体
    auths = []            # 收到的 Authorization 头
    log_message = lambda *a, **k: None

    def do_POST(self):
        n = len(self.__class__.requests)
        self.__class__.requests.append(self._read_body())
        self.__class__.auths.append(self.headers.get("Authorization", ""))
        status, body = self.__class__.responses[min(n, len(self.__class__.responses) - 1)]
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length).decode("utf-8", errors="replace")

    def do_GET(self):  # 兜底
        self.send_response(404)
        self.end_headers()


def _start_stub(responses):
    srv = HTTPServer(("127.0.0.1", 0), _Stub)
    _Stub.responses = responses
    _Stub.requests = []
    _Stub.auths = []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def test_deepseek_client():
    print("\n[1] DeepSeek 客户端")
    from ai.deepseek import DeepSeekClient, AiError

    # 1a. 正常返回 + 请求体
    body = {"choices": [{"message": {"content": "你好，DTS"}}]}
    srv, port = _start_stub([(200, body)])
    c = DeepSeekClient(api_key="test-key", base_url=f"http://127.0.0.1:{port}", retries=1)
    out = c.chat([{"role": "user", "content": "hi"}])
    ok("chat 返回内容", out == "你好，DTS", out)
    req = json.loads(_Stub.requests[0])
    ok("请求含 model/messages", req.get("model") == "deepseek-chat"
       and req["messages"][0]["role"] == "user")
    ok("请求含 Bearer 鉴权", _Stub.auths and _Stub.auths[0] == "Bearer test-key",
       _Stub.auths[:1])

    # 1b. 401 → AiError
    srv2, port2 = _start_stub([(401, {"error": {"message": "bad key"}})])
    c2 = DeepSeekClient(api_key="bad", base_url=f"http://127.0.0.1:{port2}", retries=1)
    try:
        c2.chat([{"role": "user", "content": "x"}])
        ok("401 抛 AiError", False)
    except AiError as e:
        ok("401 抛 AiError", "鉴权" in str(e), str(e))

    # 1c. 500 → 重试 → 200
    srv3, port3 = _start_stub([(500, {}), (200, body)])
    c3 = DeepSeekClient(api_key="k", base_url=f"http://127.0.0.1:{port3}", retries=2)
    out3 = c3.chat([{"role": "user", "content": "x"}])
    ok("500 重试后成功", out3 == "你好，DTS", out3)
    ok("重试发出 2 次请求", len(_Stub.requests) == 2, len(_Stub.requests))

    # 1d. 超时
    class _Slow(BaseHTTPRequestHandler):
        log_message = lambda *a, **k: None
        def do_POST(self):
            time.sleep(2.0)
            self.send_response(200)
            self.end_headers()
    srv4 = HTTPServer(("127.0.0.1", 0), _Slow)
    threading.Thread(target=srv4.serve_forever, daemon=True).start()
    c4 = DeepSeekClient(api_key="k", base_url=f"http://127.0.0.1:{srv4.server_address[1]}",
                        timeout=1, retries=1)
    try:
        c4.chat([{"role": "user", "content": "x"}])
        ok("超时抛 AiError", False)
    except AiError as e:
        ok("超时抛 AiError", "超时" in str(e), str(e))
    srv4.shutdown()

    for s in (srv, srv2, srv3):
        s.shutdown()


# ═══════════════════════════════════════════════════════════
#  2. 夹具：构造一个最小 Report + out_dir
# ═══════════════════════════════════════════════════════════

def make_fixture():
    """构造临时 out_dir：故障码 + 数据流清单 + 长表 CSV"""
    tmp = Path(tempfile.mkdtemp(prefix="ai_fix_"))
    (tmp / "fault_codes.txt").write_text(
        "P2135 节气门位置传感器1/2电压相关性故障\n"
        "P0100F9 空气流量计(HFM)的电器线过高\n",
        encoding="utf-8")
    (tmp / "DataFlow_List_1.txt").write_text(
        "发动机转速\n油门踏板位置\n车速\n共轨压力\n", encoding="utf-8")
    csv_lines = [
        "参数,值,单位,参考范围",
        "发动机转速,750,r/min,650-850",
        "发动机转速,780,r/min,650-850",
        "共轨压力,320,bar,250-400",
        "共轨压力,340,bar,250-400",
    ]
    (tmp / "DataFlow_1.csv").write_text("\n".join(csv_lines), encoding="utf-8")

    from ui.report import ReportLoader
    report = ReportLoader().load(tmp)
    return report, tmp


def test_context():
    print("\n[2] 槽位数据组装")
    report, tmp = make_fixture()

    from ai.context import build_slots, csv_to_markdown, fault_codes_table, supported_streams
    tbl = fault_codes_table(report)
    ok("故障码表含描述", "空气流量计" in tbl and "P2135" in tbl, tbl)

    md = csv_to_markdown(tmp)
    ok("CSV 转置含参数行", "发动机转速(r/min)" in md, md[:200])
    ok("CSV 转置含帧列", "| 750 | 780 |" in md, " | ".join(md.split("\n")[2:4])[:80])

    sup = supported_streams(report)
    arr = json.loads(sup)
    ok("支持清单 JSON", "发动机转速" in arr and "车速" in arr, arr)

    slots = build_slots(report, "动力不足", "爬坡无力", None)
    ok("槽位含现象", slots["fault_phenomenon"] == "动力不足")
    ok("槽位含补充", slots["user_notes"] == "爬坡无力")
    ok("槽位含故障码", "P2135" in slots["engine_fault_codes"])
    ok("槽位含 CSV", "发动机转速" in slots["actual_data_csv"])
    ok("槽位含支持清单", "共轨压力" in slots["supported_streams_list"])
    ok("槽位含知识", len(slots["diagnostic_guide"]) > 200 and len(slots["pin_info"]) > 200)
    ok("未填现象兜底", build_slots(report, "", "", None)["symptom"].strip() != "")


def test_prompts():
    print("\n[3] 模板渲染")
    from ai.context import build_slots
    from ai.prompts import render, build_messages
    report, tmp = make_fixture()
    slots = build_slots(report, "动力不足", "爬坡无力", None)

    rendered = render(1, slots)
    ok("stage1 渲染无残留占位", "{{" not in rendered, [l for l in rendered.splitlines() if "{{" in l][:2])
    ok("stage1 含现象与知识", "动力不足" in rendered and "诊断证据链" in rendered)
    ok("stage1 含支持清单内容", "共轨压力" in rendered)

    msgs = build_messages(2, slots)
    ok("build_messages 结构", len(msgs) == 2 and msgs[0]["role"] == "system")
    ok("stage2 渲染无残留", "{{" not in msgs[0]["content"])

    msgs3 = build_messages(3, slots)
    ok("stage3 渲染无残留", "{{" not in msgs3[0]["content"])
    ok("stage3 含报告约束", "核心病灶" in msgs3[0]["content"])


# ═══════════════════════════════════════════════════════════
#  4. 结果解析
# ═══════════════════════════════════════════════════════════

def test_parsing():
    print("\n[4] JSON 解析 / 防幻觉过滤")
    from ai.chain import extract_json, _as_bool

    ok("围栏 JSON", extract_json('```json\n{"a": 1}\n```') == {"a": 1})
    ok("前导文本", extract_json('好的，结果如下：{"a": {"b": [1, 2]}} 请查收') == {"a": {"b": [1, 2]}})
    ok("布尔变体", _as_bool("是") is True and _as_bool("false") is False
       and _as_bool(True) is True and _as_bool("不可") is False)

    from ai.context import build_slots, supported_stream_set
    from ai.prompts import build_messages
    from ai.chain import AiDiagnosticChain
    report, tmp = make_fixture()
    slots = build_slots(report, "动力不足", "", None)

    class _Fake1:
        def chat(self, messages, **kw):
            return ('{"streams": ["发动机转速", "共轨压力", "不存在的流", "车速"], '
                    '"working_conditions": "原地怠速后急加速"}')
    chain = AiDiagnosticChain(client=_Fake1())
    plan = chain.stage1_collection_plan(slots, report=report)
    ok("stage1 streams 解析", "发动机转速" in plan.streams)
    ok("stage1 防幻觉过滤", "不存在的流" not in plan.streams
       and "车速" in plan.streams, plan.streams)


# ═══════════════════════════════════════════════════════════
#  5. 离线全链路（mock client）
# ═══════════════════════════════════════════════════════════

def test_full_chain():
    print("\n[5] 离线全链路")
    report, tmp = make_fixture()

    class _Fake:
        calls = 0

        def chat(self, messages, **kw):
            _Fake.calls += 1
            if _Fake.calls == 1:
                return ('{"streams": ["发动机转速", "共轨压力", "车速"], '
                        '"working_conditions": "原地挂空挡，怠速稳定后急加速到最大油门并保持 5 秒"}')
            if _Fake.calls == 2:
                return '{"is_locatable": true, "reason": "共轨压力与转速数据完整，足以定位"}'
            return ('{"overallConclusion": "发动机的大脑（ECU）在报警，怀疑燃油计量单元的神经（线束）接触不良。",'
                    ' "diagnosisList": [{"faultPoint": "燃油计量单元(IMV)", "probability": "可能性最大",'
                    ' "simpleExplanation": "故障码 P2135 + 共轨压力波动明显，指向计量单元",'
                    ' "guideSteps": ["第一步，拔下 IMV 插头，<b>测量 1 号针脚</b>对地电压。<br>正常应为 5V。",'
                    ' "第二步，测信号线与 ECU 侧 A23 针脚通断。"]}]}')

    from ai import AiDiagnosticChain
    chain = AiDiagnosticChain(client=_Fake())
    events = []
    result = chain.run_full(
        report, "动力不足", "爬坡无力",
        callbacks={
            "stage_start": lambda no, name: events.append((no, "start")),
            "stage_done": lambda no, name, obj: events.append((no, "done")),
        })

    ok("三段事件顺序", events == [(1, "start"), (1, "done"), (2, "start"),
                                  (2, "done"), (3, "start"), (3, "done")], events)
    ok("plan 解析", result["plan"].streams == ["发动机转速", "共轨压力", "车速"])
    ok("locatability 解析", result["locatability"].is_locatable is True
       and "定位" in result["locatability"].reason)
    ok("report 结构化", result["report"]["diagnosisList"]
       and result["report"]["diagnosisList"][0]["faultPoint"] == "燃油计量单元(IMV)")
    for name in ("ai_collection_plan.json", "ai_locatability.json", "ai_report.json"):
        p = tmp / name
        ok(f"结果落盘 {name}", p.exists())
    plan_json = json.loads((tmp / "ai_collection_plan.json").read_text(encoding="utf-8"))
    ok("落盘 JSON 可读", plan_json["streams"][0] == "发动机转速")


# ═══════════════════════════════════════════════════════════
#  6. 知识库 / 设置
# ═══════════════════════════════════════════════════════════

def test_knowledge_settings():
    print("\n[6] 知识库 / 设置默认值")
    from ai.knowledge import load_default_knowledge, load_knowledge
    k = load_default_knowledge()
    ok("默认知识 guide", len(k.guide) > 200, len(k.guide))
    ok("默认知识 pin_info", len(k.pin_info) > 1000, len(k.pin_info))
    ok("默认知识 system_principle", len(k.system_principle) > 1000, len(k.system_principle))
    ok("默认知识 mandatory", len(k.mandatory_streams) > 0, len(k.mandatory_streams))

    from config.settings import settings
    ok("settings provider", settings.ai_provider == "deepseek")
    ok("settings model", settings.ai_model == "deepseek-chat")
    ok("settings base", "deepseek.com" in (settings.api_base or ""))
    ok("settings timeout", settings.ai_timeout == 120)


if __name__ == "__main__":
    test_imports()
    test_deepseek_client()
    test_context()
    test_prompts()
    test_parsing()
    test_full_chain()
    test_knowledge_settings()
    print(f"\n══ PASS {PASS} / FAIL {FAIL} ══")
    sys.exit(1 if FAIL else 0)
