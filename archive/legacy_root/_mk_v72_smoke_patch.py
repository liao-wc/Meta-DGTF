#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.21.72 · smoke_test.py 打补丁（SRC 换版 + 新增 4 条 check_v72_*）

用法：
    python _mk_v72_smoke_patch.py

★ smoke_test.py 是**纯 CRLF**，走同一套 CRLF 往返 + 命中唯一断言。
"""
import sys
from pathlib import Path

F = Path(__file__).resolve().parent / "smoke_test.py"
raw = F.read_bytes().decode("utf-8")
assert raw.count("\r\n") == raw.count("\n"), "smoke_test.py 不是纯 CRLF"
assert raw.count("\r") == raw.count("\r\n"), "smoke_test.py 有裸 CR"
s = raw.replace("\r\n", "\n")

REPL = []


def add(tag, old, new):
    REPL.append((tag, old, new))


add("SRC换版",
    'SRC = HERE / "元DGTF-V1.21.71.py"',
    'SRC = HERE / "元DGTF-V1.21.72.py"')

CHECKS = '''# ======================================================================
# [v1.21.72] 文档整理批 + 可观测性/形态断言窄版的判据
#   四条：#13 barrier 语义 / #20 changelog 卫生 / #22 唯一实现点 /
#         #24 长度异常告警。
# ======================================================================
def _v72_engine_src():
    """引擎全文与**抠掉模块 docstring 的**可执行源码。

    ★ 为什么必须有「抠掉 docstring」这一版：changelog 里也写着这些函数名
      与旧写法（`rounds_n > 1` 之类），在**全文**上数会把文档里的引用
      当成代码 —— v1.21.72 的探针第一版就栽在这（`old_finalize_gate_serial`
      数出 1，代码里其实是 0）。
    """
    eng = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    i = eng.index('"""')
    j = eng.index('"""', i + 3)
    return eng, eng[j + 3:]


def check_v72_bbarrier_semantics():
    """[v1.21.72 #13] B 模式预算耗尽必须**所有层一起停**（barrier 语义）。

    两个方向：
      · `max_calls=30` 的 mock B 跑 → 四层**全部**带「预算用尽」；
      · 不限预算（0）→ **0 层**带（守卫不误触发）。
    ★ 负对照就是第一方向本身：若「一起停」被改成「只停一层」，
      计数会落进 `1..n-1` 区间，立刻判红。
    """
    import inspect as _ins
    bad = []

    def _run(budget):
        cfg = build_cfg(False)
        cfg["max_calls"] = budget
        meta = mod.MetaDGTF(cfg)
        with contextlib.redirect_stdout(io.StringIO()):
            pk = meta.run(_V71_Q, route=["0", "1", "both", "all"],
                          rounds={"0": 2, "1": 2, "both": 2, "all": 2},
                          parallel_mode="B")
        views = pk.get("views") or {}
        stopped = sorted(
            e for e, v in views.items()
            if "预算用尽" in str((v or {}).get("stop_reason") or ""))
        return len(views), stopped

    n_all, st = _run(30)
    if not st:
        bad.append("[#13] 预算 30 的 B 跑没触发「预算用尽」——判据前提不成立")
    elif len(st) != n_all:
        bad.append(f"[#13] 预算耗尽只停了 {len(st)}/{n_all} 层（{st}）"
                   f"—— barrier 语义被改成了「本层截断」")
    n2, st2 = _run(0)
    if st2:
        bad.append(f"[#13] 不限预算也有层被预算停掉：{st2}")
    _src = _ins.getsource(mod.MetaDGTF._run_parallel_B)
    if "[v1.21.72 #13]" not in _src:
        bad.append("[#13] 注释没写进 _run_parallel_B（没接线）")
    if "同时停掉所有层" not in _src:
        bad.append("[#13] 注释没写明「同时停掉所有层」")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v72 #13] {m}")
        return False
    print(f"  \\u2713 [v72 #13] 预算耗尽 → {len(st)}/{n_all} 层一起停；"
          f"不限预算 → 0 层；注释在位")
    return True


def check_v72_changelog_hygiene():
    """[v1.21.72 #20] changelog 不得有重复的「★ vX 收束摘要」段，
    版本段序必须按版本号**严格递减**。

    ★ 判别力来源（也是它的负对照）：把 `SRC` 指回 v1.21.71 时，
      改前实测是「`★ v1.21.63 收束摘要` ×2 + 段序 70→68→69」，
      这条必须判红（见 `_probe_v72_before.txt` [C]）。
    """
    bad = []
    eng, _exec = _v72_engine_src()
    i = eng.index('"""')
    j = eng.index('"""', i + 3)
    doc = eng[i:j + 3]
    sums = [ln.strip() for ln in doc.split("\\n")
            if "★ v1.21." in ln and "收束摘要" in ln]
    dup = {t: sums.count(t) for t in set(sums) if sums.count(t) > 1}
    if dup:
        bad.append(f"[#20] 收束摘要标题重复：{dup}")
    secs = re.findall(r"^v(1\\.21\\.\\d+) 相对", doc, re.M)
    ver = [tuple(int(x) for x in v.split(".")) for v in secs]
    if not ver:
        bad.append("[#20] 一个版本段标题都没找到 —— 判据前提不成立")
    else:
        if len(secs) != len(set(secs)):
            bad.append(f"[#20] 版本段有重复：{secs}")
        for k in range(len(ver) - 1):
            if ver[k] <= ver[k + 1]:
                bad.append(f"[#20] 段序不是严格递减：{secs[k]} → {secs[k + 1]}")
                break
    if "_v72_engine_src" and not doc:
        bad.append("[#20] docstring 为空")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v72 #20] {m}")
        return False
    print(f"  \\u2713 [v72 #20] {len(secs)} 个版本段严格递减、"
          f"{len(sums)} 个收束摘要标题无重复（首段 v{secs[0]}）")
    return True


def check_v72_mechanism_single_source():
    """[v1.21.72 #22 窄版] 「机制 → 唯一实现点」形态断言。

    只钉本项目反复栽过的机制（**不建全局调用图框架**，那是架构批）：
      · 关键机制各只有 1 处 `def`；
      · `_assess_decidability(` 的**调用点恰好 1 处**（F6 的唯一入口）；
      · `_finalize_layer_common` / `_stop_reasons` 各 **2 个调用点、
        1 份实现**（两通道共用同一份 —— 这正是 v1.21.71 F1 的教训）；
      · v1.21.71 删掉的两处旧门**不得复活**。
    """
    bad = []
    eng, ex = _v72_engine_src()
    if not (len(ex) < len(eng)):
        bad.append("[#22] 「抠掉 docstring」没生效（可执行源码没变短）")
    _mechs = ("_normalize_decidability", "_untraced_undecidable",
              "_stop_reasons", "_finalize_layer_common", "_cached_ext_assess",
              "_dispatch_for_pack", "_layer_guard", "_quality_check",
              "_merge_decidability", "_assess_decidability_dynamic")
    for _fn in _mechs:
        _n = len(re.findall(r"^\\s*def " + _fn + r"\\b", ex, re.M))
        if _n != 1:
            bad.append(f"[#22] {_fn} 有 {_n} 处定义（应为 1）")
    _adef = len(re.findall(r"def _assess_decidability\\(", ex))
    _acall = len(re.findall(r"_assess_decidability\\(", ex)) - _adef
    if _adef != 1:
        bad.append(f"[#22] _assess_decidability 有 {_adef} 处定义（应为 1）")
    if _acall != 1:
        bad.append(f"[#22] _assess_decidability 有 {_acall} 个调用点"
                   f"（应为 1 —— F6 的唯一入口，多一个就说明又直调了）")
    if len(re.findall(r"self\\._finalize_layer_common\\(", ex)) != 2:
        bad.append("[#22] _finalize_layer_common 的调用点不是 2 个"
                   "（serial + B 各一）")
    if len(re.findall(r"self\\._stop_reasons\\(", ex)) != 2:
        bad.append("[#22] _stop_reasons 的调用点不是 2 个"
                   "（两条跑圈通道各一，但只应有 1 份实现）")
    _g1 = ex.count("if view is not None and rounds_n > 1:")
    _g2 = ex.count('state["total_rounds"] <= 1')
    if _g1 or _g2:
        bad.append(f"[#22] v1.21.71 删掉的旧门复活了：serial={_g1} / B={_g2}")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v72 #22] {m}")
        return False
    print(f"  \\u2713 [v72 #22] {len(_mechs)} 个机制各 1 处定义；"
          f"_assess_decidability 调用点=1；finalize/stop 各 2 调用点 1 实现；"
          f"旧门未复活")
    return True


def check_v72_len_anomaly_guard():
    """[v1.21.72 #24 窄版] 长度异常自动冒烟警告。

    盯的失效模式：**超长字段如果不在 `dump_view_fields` 的 `_OVERSIZED`
    里，就会被整段打进日志**（v1.21.70 [H] 有意只钉字段名、不维护清单，
    于是**新增的大字段不会被自动压缩**）。
    三方向：
      · mock 跑的真实长度谱 → 非 `_OVERSIZED` 的字符串字段里 ≥2000 字的
        个数必须为 0（基线；将来真长出这种字段时这里红，并列出字段名）；
      · **负对照**：造 `collision=6000` 字的 view 喂**生产入口**
        `dump_view_fields` → ① 输出里**有正文**（失效模式真实存在）、
        ② 同一个统计函数必须把它**检出为异常**（判据不是死的）；
      · 反向锁：同长度的 `manifest`（在 `_OVERSIZED` 里）只打长度、
        正文**不出现**。
    """
    import inspect as _ins
    bad = []
    THR = 2000
    _dvf = _ins.getsource(mod.dump_view_fields)
    _m = re.search(r"_OVERSIZED = \\{([^}]*)\\}", _dvf)
    if not _m:
        bad.append("[#24] 从 dump_view_fields 源码里解析不到 _OVERSIZED")
        ov = set()
    else:
        ov = {x.strip().strip('"').strip("'")
              for x in _m.group(1).split(",") if x.strip()}
        ov.discard("")
    if not ov:
        bad.append("[#24] _OVERSIZED 解析为空 —— 判据前提不成立")

    def _long_fields(views):
        out = {}
        for _e, _v in (views or {}).items():
            if not isinstance(_v, dict):
                continue
            for _k, _val in _v.items():
                if isinstance(_val, str) and _k not in ov and len(_val) >= THR:
                    out[_k] = max(out.get(_k, 0), len(_val))
        return out

    _pk = _v71_packed_run()
    _hit = _long_fields(_pk.get("views") or {})
    if _hit:
        bad.append(f"[#24] 长度异常：mock 跑里出现 {len(_hit)} 个"
                   f"**不在 _OVERSIZED** 的超长字段 {_hit}"
                   f"（要么并入 _OVERSIZED，要么确认它该整段落日志）")

    # ---- 负对照：合成 view 走生产入口 ----
    _cfg = build_cfg(False)
    _dg = mod.DGTF("0", mod.LLM(_cfg), _cfg)
    _dg.verbose = True
    _v1 = mod.View(entry="0")
    _v1.collision = "长正文" * 2000                    # 6000 字
    _buf = io.StringIO()
    with contextlib.redirect_stdout(_buf):
        mod.dump_view_fields(_v1, _dg.vp)
    _out1 = _buf.getvalue()
    if "长正文长正文" not in _out1:
        bad.append("[#24] 负对照失效：不在 _OVERSIZED 的超长字段"
                   "居然没把正文打进日志（失效模式不成立？）")
    _det = _long_fields({"0": _v1.to_dict()})
    if "collision" not in _det:
        bad.append(f"[#24] 统计函数是死的：合成 view 的超长 collision 没被检出"
                   f"（检出 {_det}）")
    _v2 = mod.View(entry="0")
    _v2.manifest = "M" * 6000
    _buf2 = io.StringIO()
    with contextlib.redirect_stdout(_buf2):
        mod.dump_view_fields(_v2, _dg.vp)
    _out2 = _buf2.getvalue()
    if "MMMMMM" in _out2:
        bad.append("[#24] 反向锁失效：_OVERSIZED 里的 manifest 把正文落进日志了")
    if _long_fields({"0": _v2.to_dict()}):
        bad.append("[#24] 统计函数把 _OVERSIZED 里的字段也算成异常了")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v72 #24] {m}")
        return False
    print(f"  \\u2713 [v72 #24] mock 长度谱无异常（阈值 {THR}，"
          f"_OVERSIZED={sorted(ov)}）；合成 6000 字 collision 被检出且正文落日志"
          f"（负对照有判别力）；manifest 仍只打长度")
    return True


'''

add("插入4条检查", "def check_config_parses():", CHECKS + "def check_config_parses():")

_WIRE_OLD = """    if not check_v71_auto_plan_agreement():
        return 1
"""
_WIRE_NEW = """    if not check_v71_auto_plan_agreement():
        return 1
    if not check_v72_bbarrier_semantics():
        return 1
    if not check_v72_changelog_hygiene():
        return 1
    if not check_v72_mechanism_single_source():
        return 1
    if not check_v72_len_anomaly_guard():
        return 1
"""
add("main接线", _WIRE_OLD, _WIRE_NEW)

print(f"打补丁：{F.name}（{len(REPL)} 处）")
fail = []
for tag, old, new in REPL:
    n = s.count(old)
    if n != 1:
        fail.append(f"{tag}: 命中 {n} 次（必须恰好 1 次）")
        continue
    s = s.replace(old, new, 1)
    print(f"   ✓ {tag}")
if fail:
    print("\n✗ 中止，未写文件：")
    for f in fail:
        print("   -", f)
    sys.exit(1)

import re as _re
_names = _re.findall(r"^def (check_v72_\w+)\(", s, _re.M)
assert len(_names) == 4, f"新增检查函数数 = {len(_names)}，应为 4"
assert len(set(_names)) == 4, "检查函数名有重复（重复插入）"
print(f"\n新增 check_v72_* 共 {len(_names)} 条：")
for _n in _names:
    print(f"   · {_n}")
assert 'SRC = HERE / "元DGTF-V1.21.72.py"' in s, "SRC 没换成 v72"

out = s.replace("\n", "\r\n")
assert out.count("\n") == out.count("\r\n"), "回写后有裸 LF"
assert out.count("\r") == out.count("\r\n"), "回写后有裸 CR"
F.write_bytes(out.encode("utf-8"))
print(f"\n✓ 已写出 {F.name}（{out.count(chr(10))} 行按 LF 计）")
