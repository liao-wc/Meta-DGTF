# -*- coding: utf-8 -*-
"""给 smoke_test.py 加 v1.21.75 的锚点入池判据（双向 + 形态断言）。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"

FUNC = '''

def check_v75_anchor_pool():
    """[v1.21.75] 锚点入池 —— 双向判据（关闭态加性 / 开启态可达 / 失败留痕）。

    ★ 背景：v1.21.73/74 把锚点塞进 `_assess_decidability`（外判，题面级），
      两次真跑 claims 全判「无对应」。按外部评审方案改接**池**：
        Pool.anchors 入池 → _citation_table 出 X# → evidence 可引锚点。
    ★ 红线：**进引用表 = 获得支撑 →decidable 的资格**（`apply_decidability_change`
      只拦「证据全是 d_ 开头」一种）。那是行为变化，不是加性 → 默认关，
      判据必须能抓到"谁把它无条件打开了"。
    """
    print("\\n[v1.21.75] 外部锚点入池（接入点从外判改到池）")
    _src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    bad = []

    # [形态] 防"改了文案没改代码"
    for _frag in ("anchors: List[dict] = field(default_factory=list)",
                  "anchor_as_evidence: bool = False",
                  "self._anchor_round(entry, pool, r)",
                  'if getattr(pool, "anchor_as_evidence", False):'):
        if _frag not in _src:
            bad.append(f"[形态] 源码里找不到 {_frag!r}")

    Pool = mod.Pool

    # [A] 关闭态：Pool 默认无锚点，to_dict 一个键都不多（加性红线）
    p0 = Pool()
    d0 = p0.to_dict()
    if p0.anchors != [] or p0.anchor_as_evidence is not False:
        bad.append(f"[A] 默认 Pool 不是空锚点态：anchors={p0.anchors} "
                   f"as_evidence={p0.anchor_as_evidence}")
    if "anchors" in d0:
        bad.append("[A] 关闭态 to_dict 多出 anchors 键（加性破了）")

    # [B] 引用表：未授权 → 无 X#；授权 → 有 X# 且能解析
    p1 = Pool()
    p1.anchors = [{"id": "a1", "claim": "回本周期 1-3 年"},
                  {"id": "a5", "claim": "稼动率红线 75%"}]
    xs_off = [c for c, _ in mod._citation_table(None, p1)
              if c.startswith("X")]
    if xs_off:
        bad.append(f"[B] 未授权时引用表就出了 {xs_off}（等于偷偷给了证据资格）")
    p1.anchor_as_evidence = True
    xs_on = [c for c, _ in mod._citation_table(None, p1)
             if c.startswith("X")]
    if xs_on != ["X1", "X2"]:
        bad.append(f"[B] 授权后引用表 X 编号为 {xs_on}，期望 ['X1','X2']")
    if xs_on:
        r = mod._resolve_citation("X1", None, p1)
        if not r or r.get("resolved_to") != "X1":
            bad.append(f"[B] X1 定位不到（{r}）—— 编号进了表却引不了，等于没接")

    # [C] 分圈投放 + 元层不检索
    mt = object.__new__(mod.MetaDGTF)
    mt.config = {"external_anchor": {
        "enabled": True, "path": "x", "per_round": 2,
        "as_evidence": False, "triage": False, "retriever": "snapshot"}}
    mt._anchors = [{"id": f"a{i}", "claim": f"c{i}"} for i in range(1, 8)]
    mt.vp = lambda *a, **k: None
    mt.pools = {"0": Pool(), "1": Pool()}
    q0 = mt.pools["0"]
    mt._anchor_round("0", q0, 0)
    n1 = len(q0.anchors)
    mt._anchor_round("0", q0, 1)
    n2 = len(q0.anchors)
    if n1 != 2 or n2 != 4:
        bad.append(f"[C] 分圈投放不对：第1圈 {n1}、第2圈 {n2}，期望 2 / 4")
    mt._anchor_round("all", mt.pools["1"], 0)
    if len(mt.pools["1"].anchors) != 0:
        bad.append("[C] 元层也检索了（元层的活是清算，不是核对）")

    # [D] 非 snapshot 后端必须抛错留痕，**不静默降级**
    mt._anchor_err = ""
    mt.config["external_anchor"]["retriever"] = "web_search"
    mt._anchor_round("0", q0, 2)
    if "尚未实现" not in (mt._anchor_err or ""):
        bad.append(f"[D] 未实现的检索后端静默放过了（_anchor_err="
                   f"{mt._anchor_err!r}）—— 等于假装搜过")
    n_after = len(q0.anchors)
    if n_after != 4:
        bad.append(f"[D] 检索失败后还往池里塞了东西（{n_after} 条）")

    # [E] 预算必须把锚点调用算进去
    class _L:
        total_calls = 10
    m1 = object.__new__(mod.MetaDGTF)
    m1.llm = _L(); m1._call_budget = 10; m1._anchor_calls = 0
    m2 = object.__new__(mod.MetaDGTF)
    m2.llm = _L(); m2._call_budget = 12; m2._anchor_calls = 0
    if not m1._budget_exhausted():
        bad.append("[E] calls=10 budget=10 判成没用尽（预算守卫失灵）")
    if m2._budget_exhausted():
        bad.append("[E] calls=10 budget=12 判成用尽（预算守卫误伤）")

    # [F] 关闭态 prompt 加性：两个片段都必须是空串
    m3 = object.__new__(mod.MetaDGTF)
    m3.config = {"external_anchor": {"enabled": False}}
    m3.pools = {"0": Pool()}
    m3._anchors = []
    if m3._anchor_triage_sys() != "":
        bad.append("[F] 关闭态分诊段非空（prompt 被改了，加性破了）")
    if m3._anchor_view_ctx() != "":
        bad.append("[F] 关闭态锚点块非空（prompt 被改了，加性破了）")

    if bad:
        for b in bad:
            print(f"  \\u2717 {b}")
        return False
    print("  \\u2713 [A] 关闭态 to_dict 无 anchors 键（加性守住）")
    print("  \\u2713 [B] 未授权无 X# / 授权出 X1,X2 且能定位")
    print("  \\u2713 [C] 分圈投放 2→4，元层不检索")
    print("  \\u2713 [D] 未实现后端抛错留痕且不入池")
    print("  \\u2713 [E] 预算含锚点调用（10/10 用尽、10/12 未用尽）")
    print("  \\u2713 [F] 关闭态 triage/ctx 均为空串（prompt 逐字不变）")
    return True
'''

CALL = "    if not check_v75_anchor_pool():\n        return 1\n"


def main() -> None:
    b = SMOKE.read_bytes()
    t = b.decode("utf-8").replace("\r\r\n", "\n").replace("\r\n", "\n")
    t = t.replace("\r", "\n")
    lines = t.split("\n")

    # 1) 插函数：放在 check_v74_anchor_refs 之后（找它之后的下一个顶层 def）
    i74 = next(i for i, l in enumerate(lines)
               if l.startswith("def check_v74_anchor_refs("))
    j = i74 + 1
    while j < len(lines) and not lines[j].startswith("def "):
        j += 1
    assert j < len(lines), "找不到插入位置"
    anchor = 'def check_v74_anchor_refs():'
    assert t.count(anchor) == 1
    lines[j:j] = FUNC.split("\n")
    t2 = "\n".join(lines)
    print(f"  [判据函数] 插在第 {j+1} 行前 ✓")

    # 2) main 里接上：放在 check_v74_anchor_refs() 调用之后
    old_call = "    if not check_v74_anchor_refs():\n        return 1\n"
    assert t2.count(old_call) == 1, t2.count(old_call)
    t2 = t2.replace(old_call, old_call + CALL)
    print("  [main 接线] ✓")

    out = t2.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\n") == out.count(b"\n")
    SMOKE.write_bytes(out)
    print(f"已更新 {SMOKE.name}（{len(out)} 字节，纯 CRLF）")


if __name__ == "__main__":
    main()
