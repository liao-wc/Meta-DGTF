# -*- coding: utf-8 -*-
"""[v1.21.73 冒烟补丁] 加 check_v73_anchor（外部锚点）+ SRC 指向 v1.21.73。

smoke_test.py 同样是纯 CRLF，走 CRLF 往返 + 每处锚点断言出现 1 次。
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"

s = ""


def rep(old: str, new: str, tag: str) -> None:
    global s
    n = s.count(old)
    assert n == 1, f"[{tag}] 锚点出现 {n} 次（应为 1）"
    s = s.replace(old, new, 1)
    print(f"  [{tag}] ok")


raw = SMOKE.read_bytes().decode("utf-8")
assert raw.count("\r\n") == raw.count("\n"), "smoke_test 不是纯 CRLF"
s = raw.replace("\r\n", "\n")
print(f"读入 smoke_test.py：{len(s)} 字符")

# ---------------------------------------------------------------- 1) SRC
rep('SRC = HERE / "元DGTF-V1.21.72.py"', 'SRC = HERE / "元DGTF-V1.21.73.py"',
    "SRC 指向 v1.21.73")

# ---------------------------------------------------------------- 2) import inspect
rep("import importlib.util\nimport io",
    "import importlib.util\nimport inspect\nimport io",
    "import inspect")

# ---------------------------------------------------------------- 3) 插入判据
NEW = r'''def _v73_anchor_file(td, n=3):
    """写一个锚点快照到临时目录，返回路径。"""
    p = Path(td) / "anchors.json"
    items = []
    for i in range(1, n + 1):
        items.append({"id": "a%d" % i,
                      "claim": "外部事实条目 %d：产线自动化投资回收期中位约 3 年" % i,
                      "source": "某行业报告 %d" % i,
                      "url": "https://example.org/%d" % i,
                      "as_of": "2026-10-04", "kind": "数据"})
    p.write_text(json.dumps({
        "question": "现金流紧张的中小制造企业要不要上自动化产线",
        "retrieved_at": "2026-10-04T07:00:00+08:00",
        "retriever": "smoke fixture", "anchors": items,
    }, ensure_ascii=False), encoding="utf-8")
    return p


def _v73_run(cfg, q, spy, anchor_ids=None, verdict="印证"):
    """跑一次 mock run；**临时**给桩补两条分支，退出即恢复。

    ★ 为什么必须临时补：全局 fake_call 没有这两条分支，mock 里
      `decidable_product.answer` 恒空 ⇒ `_anchor_claims` 恒返回空 ⇒
      「claims >= 1」这条判据既测不出真也测不出假（永真的死判据）。
      真跑里 view 1 的 answer 是有的（`verif_V71S.full.json` 实测
      一条 200+ 字的成品答案），所以补桩是让 mock 回到真跑形态，
      不是放水。★ 只在函数内生效，不影响其它 check。
    """
    orig = mod.LLM.call
    ids = list(anchor_ids or ["a1"])

    def _p(self, system, user, *a, **kw):
        ss = system or ""
        if kw.get("stage") == "assess_decidability":
            spy.append(ss)
        if "【& · 双通道融合】" in ss:
            return json.dumps({
                "amps": [], "threads": [], "meta": [],
                "decidable_product": {
                    "answer": "冒烟桩：先做局部优化，产线自动化按回收期分阶段上",
                    "answered_sub_ids": [1],
                    "evidence": ["桩证据"], "distance": 0.4},
                "undecidable_product": {
                    "why_undecidable": "桩", "structural_amps": [],
                    "aligned_amps": [], "clarity": 0.0, "distance": 1.0},
                "covered_aspects": [], "uncovered_aspects": [],
                "distance_to_question": 0.4}, ensure_ascii=False)
        if "外部事实对照者" in ss:
            cs = re.findall(r"- \[(c\d+)\]", user or "") or ["c1"]
            return json.dumps({"items": [
                {"claim_id": c, "verdict": verdict,
                 "anchor_ids": list(ids), "note": "冒烟桩"}
                for c in cs]}, ensure_ascii=False)
        return orig(self, system, user, *a, **kw)

    mod.LLM.call = _p
    try:
        m = mod.MetaDGTF(cfg)
        res = m.run(q, route=["0", "1"], rounds={"0": 1, "1": 1},
                    parallel_mode="serial")
    finally:
        mod.LLM.call = orig
    return res, m


def check_v73_anchor():
    """[v1.21.73] 外部锚点：加性 / 挂键 / 失败留痕 / 编号校验 / 接线 / 只读。

    ★ 每组都锁**两个方向**。单方向断言会把「没接上」验成「接上了」——
      本项目的老坑：baseline 为 0 的告警判据，负对照必须写进判据本身。
    """
    bad = []

    def chk(cond, msg):
        if not cond:
            bad.append(msg)
        return bool(cond)

    td = Path(tempfile.mkdtemp(prefix="smoke73_"))
    q = "现金流紧张的中小制造企业，上自动化产线还是维持人工加局部优化？"
    af = _v73_anchor_file(td, 3)

    # ---------- [E] 接线：新方法必须真被生产路径调用（防死代码）
    chk("_load_anchors()" in inspect.getsource(mod.MetaDGTF.run),
        "[E] run() 没调 _load_anchors —— 死代码")
    chk("_anchor_report_for_pack" in inspect.getsource(mod.MetaDGTF._pack_result),
        "[E] _pack_result 没挂锚点报告 —— 死代码")
    _csrc = inspect.getsource(mod.MetaDGTF._cached_ext_assess)
    chk("anchors=" in _csrc, "[E] _cached_ext_assess 没把锚点传给外判")

    # ---------- [A] 关闭：加性（packed 键集合 / assess prompt / 产物文案）
    cfg_off = build_cfg(False)
    cfg_off["output"]["save_dir"] = str(td / "off")
    off_sys = []
    res_off, _ = _v73_run(cfg_off, q, off_sys)
    chk("external_anchor" not in res_off,
        "[A] 关闭时 packed 仍挂 external_anchor（不是加性改动）")

    # ---------- [B] 开启 + 有效锚点
    def _on_cfg(sub):
        c = build_cfg(False)
        c["output"]["save_dir"] = str(td / sub)
        c["external_anchor"] = {"enabled": True, "path": str(af),
                                "max_items": 12, "crosscheck": True}
        return c

    on_sys = []
    res_on, m_on = _v73_run(_on_cfg("on"), q, on_sys,
                            anchor_ids=["a1", "zzz"])
    ea = res_on.get("external_anchor")
    chk(isinstance(ea, dict), "[B] 开启时 packed 没有 external_anchor 键")
    if isinstance(ea, dict):
        chk(ea.get("anchors") == 3, "[B] anchors=%s（应为 3）" % ea.get("anchors"))
        chk(not ea.get("error"), "[B] 有效锚点却有 error：%s" % ea.get("error"))
        sm = ea.get("summary") or {}
        chk(int(sm.get("claims", 0) or 0) >= 1,
            "[B] claims=%s —— 结论条目取不到，对照是空转" % sm.get("claims"))
        chk(int(sm.get("supported", 0) or 0) + int(sm.get("conflicted", 0) or 0)
            + int(sm.get("unmatched", 0) or 0) == int(sm.get("claims", 0) or 0),
            "[B] 印证+冲突+无对应 不等于 claims")
        # [D] 编号校验：zzz 是模型编的，必须被滤掉
        _items = ea.get("items") or []
        _ids = (_items[0].get("anchor_ids") if _items else None) or []
        chk(_ids == ["a1"], "[D] 编造的锚点编号没被滤掉：%s" % _ids)

    # [A] 的反证：ON 的 assess system 必须是「OFF 原文 + 追加」
    chk(bool(off_sys) and bool(on_sys),
        "[A] 没抓到 assess_decidability 的 system（桩没接上，本条无判别力）")
    if off_sys and on_sys:
        chk(on_sys[0].startswith(off_sys[0]) and len(on_sys[0]) > len(off_sys[0]),
            "[A] 开启后的 assess system 不是「原文 + 追加」（加性被破坏）")

    # ---------- [D] 负对照：全给假编号 → 必须全被滤掉（不是恒等放行）
    res_d, _ = _v73_run(_on_cfg("d"), q, [], anchor_ids=["zzz"])
    ea_d = res_d.get("external_anchor") or {}
    _di = ea_d.get("items") or []
    _dids = (_di[0].get("anchor_ids") if _di else None) or []
    chk(_dids == [], "[D-负对照] 全假编号竟被接受：%s" % _dids)

    # ---------- [C] 失败留痕：path 不存在也必须挂键 + 写 error
    cfg_bad = build_cfg(False)
    cfg_bad["output"]["save_dir"] = str(td / "bad")
    cfg_bad["external_anchor"] = {"enabled": True,
                                  "path": str(td / "__nope__.json"),
                                  "max_items": 12, "crosscheck": True}
    res_bad, _ = _v73_run(cfg_bad, q, [])
    ea_b = res_b.get("external_anchor")
    chk(isinstance(ea_b, dict),
        "[C] 加载失败时 packed 没有 external_anchor —— 失败没留痕")
    chk(bool((ea_b or {}).get("error")),
        "[C] 加载失败却 error 为空 —— 静默降级成「没接入」")
    # 负对照：有效路径时 error 必须为空（修过头会把所有情况都判失败）
    if isinstance(ea, dict):
        chk(not ea.get("error"), "[C-负对照] 有效路径也被判失败")

    # ---------- 产物渲染：正文出口 + 关闭时旧文案不回归
    try:
        md_on = mod.save_result(res_on, str(td / "on"))
        t_on = Path(md_on).read_text(encoding="utf-8")
        chk("已接入 3 条" in t_on, "[B] 产物头部没有锚点接入渲染")
        chk("### 外部锚点 · 逐条对照" in t_on,
            "[B] 产物正文没有逐条对照出口（又是一个只躺在 packed 里的键）")
        md_bad = mod.save_result(res_bad, str(td / "bad"))
        t_bad = Path(md_bad).read_text(encoding="utf-8")
        chk("锚点异常" in t_bad, "[C] 失败时产物没有「锚点异常」渲染")
        md_off = mod.save_result(res_off, str(td / "off"))
        t_off = Path(md_off).read_text(encoding="utf-8")
        chk("**外部锚点**：无（本产物不含外部事实校验；" in t_off,
            "[A] 关闭时产物文案变了（旧断言会回归）")
        chk("已接入" not in t_off, "[A] 关闭时产物竟出现「已接入」")
    except Exception as exc:
        bad.append("[渲染] save_result 异常：%s: %s" % (type(exc).__name__, exc))

    # ---------- [F] 只读：对照不得改动任何池
    try:
        before = json.dumps({k: p.to_dict() for k, p in m_on.pools.items()},
                            ensure_ascii=False, sort_keys=True)
        m_on._anchor_report = None
        m_on._anchor_crosscheck({})
        after = json.dumps({k: p.to_dict() for k, p in m_on.pools.items()},
                           ensure_ascii=False, sort_keys=True)
        chk(before == after, "[F] 锚点对照改动了池 —— 不是只读")
    except Exception as exc:
        bad.append("[F] 只读性检查自身异常：%s: %s" % (type(exc).__name__, exc))

    if bad:
        for m in bad:
            print("  \u2717 [v73 锚点] " + m)
        return False
    print("  \u2713 [v73 锚点] 关闭逐字同构 / 开启挂键+对照 / 失败留痕 / "
          "编号校验 / 接线 / 只读（六组各带负对照）")
    return True


def main():'''
rep("def main():", NEW, "插入 check_v73_anchor")

# ---------------------------------------------------------------- 4) main 接入
rep("""    if not check_v72_len_anomaly_guard():
        return 1""",
    """    if not check_v72_len_anomaly_guard():
        return 1
    if not check_v73_anchor():
        return 1""",
    "main 接 check_v73_anchor")

out = s.replace("\n", "\r\n")
assert out.count("\n") == out.count("\r\n")
SMOKE.write_bytes(out.encode("utf-8"))
print(f"\n写出 smoke_test.py：{len(out)} 字符")
print("OK")
