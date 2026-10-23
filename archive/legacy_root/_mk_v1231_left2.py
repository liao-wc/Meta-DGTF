# -*- coding: utf-8 -*-
"""[v1.23.1 遗留2 · 补丁2] `_web_tier_proposal` 同时接受完整 config 与 web_search 子段。

起因（探针 L2.2 判红）：函数原先只认 `config["web_search"]` 子段，而
`WebSearchGate(config)` 收的是**完整** config —— 两种写法都常见，只认一种
会让另一种**静默**拿到空规则表 ⇒ 全部落回保守档 3（看着"正常"，其实规则
一条没生效）。这是本项目反复踩的「静默吞掉」形态，故在函数内做兼容。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
TGT = HERE / "元DGTF-V1.23.1.py"
src = TGT.read_bytes().decode("utf-8")
assert src.count("\r\n") == src.count("\n"), "非纯 CRLF"
src = src.replace("\r\n", "\n")

O1 = """    _cfg = cfg or {}
    _rules = _cfg.get("domain_tier_rules") or []"""
N1 = """    # ★ 同时接受「完整 config」与「config["web_search"] 子段」：两种写法
    #   都常见（`WebSearchGate(config)` 收完整、原先本函数收子段），只认一种
    #   会让另一种**静默**拿到空规则表 ⇒ 全部落回保守档 3。
    _cfg = cfg if isinstance(cfg, dict) else {}
    if isinstance(_cfg.get("web_search"), dict):
        _cfg = _cfg["web_search"]
    _rules = _cfg.get("domain_tier_rules") or []"""
if "同时接受「完整 config」" in src:
    print("  已改，跳过")
else:
    assert src.count(O1) == 1, src.count(O1)
    src = src.replace(O1, N1)
    print("  · _web_tier_proposal 兼容两种入参")

O2 = "                _pr = _web_tier_proposal(out, _ws_cfg, _known)"
N2 = "                _pr = _web_tier_proposal(out, self.config, _known)"
if "_web_tier_proposal(out, self.config" in src:
    print("  调用点已改，跳过")
else:
    assert src.count(O2) == 1, src.count(O2)
    src = src.replace(O2, N2)
    print("  · 调用点改传完整 config（与 WebSearchGate 同款）")

out = src.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r") == out.count(b"\r\n")
TGT.write_bytes(out)
import ast  # noqa: E402
ast.parse(out.decode("utf-8"))
print("[done] 补丁2 应用完毕")
