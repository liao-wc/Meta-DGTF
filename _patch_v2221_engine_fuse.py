# -*- coding: utf-8 -*-
"""[V2.2.21 / App 2.0.46] 道生模式与标准模式融合：道生成为标准模式（单一链路）。"""
from pathlib import Path
import py_compile

# 1) 引擎 V2.2.21：由 V2.2.20 复制，仅版本/说明（零行为差；App 侧融合发版）
ENG = Path("dgtf_engine/dgtf_v2/engine")
SRC = ENG / "Meta-DGTF-V2.2.20.py"
DST = ENG / "Meta-DGTF-V2.2.21.py"
raw = SRC.read_bytes()
assert raw[:3] != b"\xef\xbb\xbf" and raw.count(b"\n") == raw.count(b"\r\n")
t = raw.decode("utf-8").replace("\r\n", "\n")


def rep(a, b):
    global t
    c = t.count(a)
    assert c == 1, "引擎锚点命中 %d 次: %r" % (c, a[:60])
    t = t.replace(a, b)


rep("Meta-DGTF-道生三阶模型 · V2.2.20\n", "Meta-DGTF-道生三阶模型 · V2.2.21\n")
rep('__version__ = "2.2.20"', '__version__ = "2.2.21"')
rep("★ V2.2.20 补丁（道生支路接入统一模式体系，方案 A）：",
"""★ V2.2.21 补丁（道生模式与标准模式融合 · 引擎侧零行为差）：
      本版为 App 融合发版：App 侧 auto/standard 统一解析为 daosheng 模式
      （道生模式成为标准模式），引擎参数通道（--mode/--parallel/--thinking/
      --rounds/--config）完全复用 V2.2.20 已验收的机制，源码除版本号/本说明外
      与 V2.2.20 逐字相同。全链路由 App 2.0.46 的 fused_full_chain 判据验证。

★ V2.2.20 补丁（道生支路接入统一模式体系，方案 A）：""")
out = t.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)
chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(DST), doraise=True)
print("OK", DST.name, len(chk))

# 2) daosheng_mode：auto/standard 统一解析为 daosheng（融合）
D = Path("dgtf_app/daosheng_mode.py")
t = D.read_text(encoding="utf-8")
old = '''    if req == "auto":
        if _prj:
            return {"id": "daosheng", "requested": req, "source": "auto-rule",
                    "project_related": _prj,
                    "reason": "auto 分流：项目相关题 → 道生专属模式（质量优先）"}
        return {"id": "standard", "requested": req, "source": "auto-rule",
                "project_related": _prj,
                "reason": "auto 分流：非项目题 → 既有 quality_policy 全自动链路"}
    if req == "standard":
        return {"id": "standard", "requested": req, "source": "explicit",
                "project_related": _prj,
                "reason": "显式 standard：保持既有 quality_policy 全自动链路"}
'''
new = '''    # ★ [V2.2.21 融合] 道生模式 = 标准模式：auto/standard 统一解析为 daosheng，
    #   全项目只有一条调度链路（道生 plan：预设 + M4 + 预算守卫 + MODE_CONFIGS +
    #   运行期动态调整）。project_related 只决定是否注入项目背景，不改链路。
    if req == "auto":
        return {"id": "daosheng", "requested": req, "source": "auto-fused",
                "project_related": _prj, "fused": True,
                "reason": ("auto → 道生模式（已融合为标准模式；项目相关题注入项目背景）"
                           if _prj else
                           "auto → 道生模式（已融合为标准模式；非项目题不注入项目背景）")}
    if req == "standard":
        return {"id": "daosheng", "requested": req, "source": "fused-standard",
                "project_related": _prj, "fused": True,
                "reason": "standard 已并入道生模式（融合为标准模式，单一链路）"}
'''
assert t.count(old) == 1
t = t.replace(old, new)
old2 = '''        "tier": tier,
        "engine_mode": engine_mode,
'''
new2 = '''        "tier": tier,
        "engine_mode": engine_mode,
        # ★ [V2.2.21] 融合标记：道生模式即标准模式；requested 保留原始入口
        "fused": True,
        "fused_from": str(resolved.get("requested") or ""),
'''
assert t.count(old2) == 1
t = t.replace(old2, new2)
D.write_text(t, encoding="utf-8")
py_compile.compile(str(D), doraise=True)
print("OK daosheng_mode fused standard")

# 3) server：注释 + mode_info 融合标记
S = Path("dgtf_app/server.py")
t = S.read_text(encoding="utf-8")
old3 = '''            #   mode 默认 auto：项目相关题 → daosheng；其它 → 既有 quality_policy 全自动链路。'''
new3 = '''            #   [V2.2.21 融合] mode 默认 auto 一律走道生模式（道生=标准模式，单一链路）；
            #   standard 入口作为别名解析到 daosheng；仅 plan 生成失败时 fail-open 回旧链路。'''
assert t.count(old3) == 1
t = t.replace(old3, new3)
old4 = '''                    "id": _ds_plan.get("mode_id") or _mode_resolved.get("id"),
                    "requested": _mode_req,
                    "tier": _ds_plan.get("tier"),
                    "policy": _ds_plan.get("policy"),'''
new4 = '''                    "id": _ds_plan.get("mode_id") or _mode_resolved.get("id"),
                    "requested": _mode_req,
                    # ★ [V2.2.21] 融合标记：id=daosheng 即标准模式
                    "fused": True,
                    "fused_from": _ds_plan.get("fused_from") or _mode_req,
                    "tier": _ds_plan.get("tier"),
                    "policy": _ds_plan.get("policy"),'''
assert t.count(old4) == 1
t = t.replace(old4, new4)
S.write_text(t, encoding="utf-8")
py_compile.compile(str(S), doraise=True)
print("OK server fused mode_info")
