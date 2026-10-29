# -*- coding: utf-8 -*-
"""[V2.2.21 / App 2.0.46] 判据更新：道生=标准模式（融合后单一链路）。"""
from pathlib import Path
import py_compile

# 1) selftest：mode 解析 / 端到端两处
P = Path("dgtf_app/selftest.py")
t = P.read_text(encoding="utf-8")

old = '''    m_auto_prj = dm.resolve_mode("auto", q_prj)
    m_auto_gen = dm.resolve_mode("auto", "1+1等于几？")
    check("★T3 mode=auto：项目相关题 → daosheng（auto-rule）",
          m_auto_prj["id"] == "daosheng" and m_auto_prj["source"] == "auto-rule",
          m_auto_prj.get("reason"))
    check("★T3 mode=auto：非项目题 → standard（既有 quality_policy 链路不变）",
          m_auto_gen["id"] == "standard", m_auto_gen.get("reason"))
    check("★T3 显式 mode=daosheng / daosheng_fast / standard 都能解析",
          all(dm.resolve_mode(x, q_prj)["id"] == x
              for x in ("daosheng", "daosheng_fast", "standard")), "")'''
new = '''    m_auto_prj = dm.resolve_mode("auto", q_prj)
    m_auto_gen = dm.resolve_mode("auto", "1+1等于几？")
    # ★ [V2.2.21 融合] 道生模式 = 标准模式：auto 一律解析为 daosheng
    check("★T3 mode=auto：统一解析为 daosheng（融合后道生=标准模式）",
          m_auto_prj["id"] == "daosheng" and m_auto_prj["source"] == "auto-fused"
          and m_auto_gen["id"] == "daosheng"
          and m_auto_gen.get("fused") is True,
          m_auto_gen.get("reason"))
    check("★T3 mode=auto：project_related 只决定背景注入，不改链路",
          m_auto_prj.get("project_related") is True
          and m_auto_gen.get("project_related") is False
          and "非项目题不注入" in str(m_auto_gen.get("reason")),
          m_auto_gen.get("reason"))
    check("★T3 显式 mode：daosheng/daosheng_fast 保持，standard 融合为 daosheng",
          dm.resolve_mode("daosheng", q_prj)["id"] == "daosheng"
          and dm.resolve_mode("daosheng_fast", q_prj)["id"] == "daosheng_fast"
          and (lambda r: r["id"] == "daosheng"
               and r.get("requested") == "standard"
               and r.get("fused") is True)(dm.resolve_mode("standard", q_prj)),
          "")'''
assert t.count(old) == 1
t = t.replace(old, new)

old2 = '''    check("★T3 mode=auto 非项目题 → standard（既有链路/质量策略不变）",
          s_gen == 201 and _mg.get("id") == "standard"
          and str(r_gen.get("quality_policy") or "").startswith("auto:"),
          "id=%s qp=%s" % (_mg.get("id"), r_gen.get("quality_policy")))'''
new2 = '''    check("★T3 mode=auto 非项目题 → 也走道生模式（融合后单一链路）",
          s_gen == 201 and _mg.get("id") == "daosheng"
          and (_mg.get("plan") or {}).get("policy") == "daosheng.v1"
          and _mg.get("fused") is True,
          "id=%s fused=%s" % (_mg.get("id"), _mg.get("fused")))'''
assert t.count(old2) == 1
t = t.replace(old2, new2)

old3 = '''    s_sd, r_sd = _post_status("/api/tasks", {
        "question": q_prj, "mode": "standard", "opts": {"mock": True}})
    check("★T3 显式 mode=standard：不改用道生 plan（mode.id=standard）",
          s_sd == 201 and ((r_sd.get("mode") or {}).get("id") == "standard"), "")'''
new3 = '''    s_sd, r_sd = _post_status("/api/tasks", {
        "question": q_prj, "mode": "standard", "opts": {"mock": True}})
    _m_sd = r_sd.get("mode") or {}
    check("★T3 显式 mode=standard：融合为道生 plan（id=daosheng/fused=True）",
          s_sd == 201 and _m_sd.get("id") == "daosheng"
          and _m_sd.get("fused") is True
          and ((_m_sd.get("plan") or {}).get("policy") == "daosheng.v1"),
          "id=%s requested=%s" % (_m_sd.get("id"), _m_sd.get("requested")))'''
assert t.count(old3) == 1
t = t.replace(old3, new3)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK selftest fused expectations")

# 2) app_daosheng_check：auto 非项目题改为 daosheng
P2 = Path("scripts/app_daosheng_check.py")
t2 = P2.read_text(encoding="utf-8")
old4 = '''    check("mode=auto 非项目题 → standard（既有链路）",
          s3 == 201 and m3.get("id") == "standard"
          and str(r3.get("quality_policy") or "").startswith("auto:"),
          "id=%s qp=%s" % (m3.get("id"), r3.get("quality_policy")))'''
new4 = '''    check("mode=auto 非项目题 → daosheng（融合后道生=标准模式）",
          s3 == 201 and m3.get("id") == "daosheng"
          and m3.get("fused") is True
          and str(m3.get("plan", {}).get("policy") or "") == "daosheng.v1",
          "id=%s qp=%s" % (m3.get("id"), r3.get("quality_policy")))'''
assert t2.count(old4) == 1
t2 = t2.replace(old4, new4)
P2.write_text(t2, encoding="utf-8")
py_compile.compile(str(P2), doraise=True)
print("OK app_daosheng_check fused")

# 3) app.js：模式标签体现"道生=标准"
P3 = Path("dgtf_app/static/app.js")
t3 = P3.read_text(encoding="utf-8")
old5 = """    const _label = { daosheng: '道生专属', daosheng_fast: '道生专属·省档',
                     standard: '标准模式' }[_mode.id] || _mode.id;"""
new5 = """    const _label = { daosheng: (_mode.fused ? '标准·道生' : '道生专属'),
                     daosheng_fast: '道生专属·省档',
                     standard: '标准模式' }[_mode.id] || _mode.id;"""
assert t3.count(old5) == 1
t3 = t3.replace(old5, new5)
P3.write_text(t3, encoding="utf-8")
print("OK app.js fused label")
