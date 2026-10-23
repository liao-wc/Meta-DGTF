# -*- coding: utf-8 -*-
"""v1.23.41 · P3 + P4：**归因/可观测**针对性优化（只加不删，不改停止决策）。

诊断结论：P3「体力耗尽…未触发任何停止判据」与 P4「自省连续…未消化」经深查
**都是按设计工作**（短跑各判据需 ≥2 圈方生效；项目早已修过「被推迟的判据不留痕」；
P4 走 `carry_streak>=2` + `layer_no>=soft_max` 推迟逻辑，产物已渲染
`【自省回流核对】carry_check.notes`）。⇒ 不改行为，只把**归因**补全：

· P3：只说「未触发任何停止判据」读者无从判断「离触发还有多远」⇒ 附**末圈近阈读数**
      （无新 & / 无线头 / 停滞计数，直接取自 `state["round_log"]`）。
· P4：停因若是「自省连续…未消化」，附**回流核对摘要**（具体哪批没消化）——
      原来只说「同一批问题」。

★ 红线：只 append 文本，**不删**任何既有子串（冒烟判据 805/1224/2065/2069 钉了
  前缀，追加不破坏）；停因级联先剥括号再匹配主句，追加用「｜」不带括号，不干扰。
"""
import ast
from pathlib import Path

TGT = Path("元DGTF-V1.23.41.py")


def _rw(path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s
    path.write_bytes(s2.replace("\n", "\r\n").encode("utf-8"))
    chk = path.read_bytes()
    assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
    ast.parse(chk.decode("utf-8"))
    return chk


# ── P3：无判据截断 → 附末圈近阈读数 ────────────────────────────────
P3_OLD = '''            else:
                view.stop_reason = (
                    f"体力耗尽（{_cap} 圈走满，"
                    f"未触发任何停止判据，是被截断不是自然停止）")'''
P3_NEW = '''            else:
                # ★ [P3 · 近阈归因] 只说「未触发任何停止判据」读者无从判断
                #   「离触发还有多远」⇒ 附**末圈近阈读数**（纯附加信息，不改决策）。
                _ll = (list(state.get("round_log") or []) or [{}])[-1]
                _near = ("末圈：无新& %s / 无线头 %s / 停滞 %s"
                         % (_ll.get("idle_amp", "?"),
                            _ll.get("idle_thread", "?"),
                            _ll.get("idle_stall", "?")))
                view.stop_reason = (
                    f"体力耗尽（{_cap} 圈走满，"
                    f"未触发任何停止判据，是被截断不是自然停止）\\n"
                    f"  近阈读数：{_near}")'''

# ── P4：自省未消化 → 附回流核对摘要 ────────────────────────────────
P4_OLD = '''        try:
            _is_cut = any(k in str(view.stop_reason or "")
                          for k in ("体力耗尽", "预算用尽", "截断"))
            view.cut_two_way = cut_two_way('''
P4_NEW = '''        # ★ [P4 · 未消化归因] 停因若是「自省连续…未消化」，附上**回流核对摘要**
        #   （具体哪批没消化）——原来只说「同一批问题」，读者无从知道是哪批。
        try:
            _sr4 = str(view.stop_reason or "")
            if "自省连续" in _sr4 and "未消化点名" not in _sr4:
                _ccn = str((getattr(view, "carry_check", None) or {})
                           .get("notes") or "").strip()
                if not _ccn:
                    _ctl = [str((c or {}).get("target") or (c or {}).get("desc")
                                or "").strip()
                            for c in (getattr(view, "carry", None) or [])]
                    _ccn = " / ".join(x for x in _ctl if x)[:120]
                if _ccn:
                    view.stop_reason = _sr4.rstrip() + "｜未消化点名：" + _ccn
        except Exception:
            pass

        try:
            _is_cut = any(k in str(view.stop_reason or "")
                          for k in ("体力耗尽", "预算用尽", "截断"))
            view.cut_two_way = cut_two_way('''


def apply(s):
    for nm, old, new in (("P3", P3_OLD, P3_NEW), ("P4", P4_OLD, P4_NEW)):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（要求 1）" % (nm, n)
        s = s.replace(old, new)
    # 自检：旧子串仍在（只加不删）
    assert "未触发任何停止判据，是被截断不是自然停止" in s
    assert "自省连续 {carry_streak} 圈点名同一批问题未消化" in s
    assert s.count("近阈读数：{_near}") == 1
    assert s.count("｜未消化点名：") == 1
    return s


if __name__ == "__main__":
    out = _rw(TGT, apply)
    print("[ok] P3+P4 补丁已落 | 行数", out.count(b"\n"), "| 纯 CRLF | AST OK")
