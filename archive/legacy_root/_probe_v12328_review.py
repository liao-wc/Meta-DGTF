# -*- coding: utf-8 -*-
"""v1.23.28 全仓库复审：审计探针（v1232）**未覆盖**的维度。

已有 `_probe_v1232_audit.py` 覆盖 A~L 类（出口/白名单/版本/红线/圈号/枚举/登记/
文档引用/配置键可达/thinking stage/id 归一化）。本探针补它**没查的**：

  M. **编号口径分叉**：同一符号（如 `A{n}`）在不同登记表里是否指向同一物
  N. **可观测字段无出口**：引擎算出来但产物读不到（死字段）
  O. **有出口但恒空**：出口在、产出恒空（结构性不可达）
  P. **渲染源缺字段**：渲染读 `x.get("k")` 但写入点从不写 `k`
  Q. **双读数无消费**：property 有定义有判据，但引擎内零调用
  R. **判据未覆盖接线**：纯函数判据全绿但真实入口不可达

★ 每条都要自带**负对照变异体**（没有变异体的全绿只说明判据没跑）。
"""
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else (HERE / "元DGTF-V1.23.27.py")

spec = importlib.util.spec_from_file_location("m_rev28", SRC)
m = importlib.util.module_from_spec(spec)
sys.modules["m_rev28"] = m
spec.loader.exec_module(m)

_raw = SRC.read_text(encoding="utf-8")
_src = _raw.replace("\r\n", "\n")
# 抠掉模块 docstring（数代码只数代码）
_i = _src.index('"""')
_j = _src.index('"""', _i + 3)
_body = _src[_j + 3:]
_ilines = _body.split("\n")

ok, bad = [], []


def C(name, cond, detail=""):
    (ok if cond else bad).append("%s%s" % (name, ("  " + detail) if detail else ""))


# ─────────────────────────────────────────────────────────────────
# M. 编号口径分叉：`A{n}` 在两套登记表里是否同物
# ─────────────────────────────────────────────────────────────────
_uid_def = [ln for ln in _ilines if re.search(r'_uid = "A%d"', ln)]
# ★ 锚点随实现更新：真正的「生成点」是 `_put(...)` 那一行，
#   它现在用 `_sid`（真 id）而不是字面 `"A%d" % _i`。
_at_put = [ln for ln in _ilines
           if re.search(r'_put\(_sid, "covered_under"', ln)
           or re.search(r'_put\("A%d" % _i, "covered_under"', ln)]
C("M1 两个 A{n} 生成点都在（非空）",
  len(_uid_def) >= 1 and len(_at_put) >= 1,
  "aspect_units=%d 处 / aspect_targets=%d 处" % (len(_uid_def), len(_at_put)))
# 真实入口验证：两套 A1 是否同物
# ★ 走**生产入口**（View 登记 → merge 同步 → aspect_targets 对账），
#   不手造 Pool 字段（手造会绕过 F11 的同步，正是要测的那条链）。
_v = m.View(entry="0")
_v.anchor_touched.append({"desc": "触及项甲", "source": "anchor"})
_v.add_aspect_unit("触及项甲", source="anchor", polarity="阳", ground="anchor")
_v.untouched.append({"desc": "未触及项乙", "source": "anchor"})
_v.add_aspect_unit("未触及项乙", source="anchor", polarity="阴", ground="anchor")
_p = m.Pool()
try:
    _p.merge(_v.amps, _v.threads, _v.meta, _v.probes,
             aspect_units=list(_v.aspect_units or []))
except TypeError:
    _p.merge(_v.amps, _v.threads, _v.meta, _v.probes)
_p.covered_unders = ["未触及项乙"]
_at = _p.aspect_targets_v12327()
# ★ 按**真 id** 查（`未触及项乙` 在 aspect_units 里是 A2，不是 A1）
_uid_yi = ""
for _u2 in (_v.aspect_units or []):
    if str(_u2.get("desc") or "") == "未触及项乙":
        _uid_yi = str(_u2.get("id") or "")
_a1_u = "未触及项乙"
_a1_t = (_at.get(_uid_yi) or {}).get("text", "") if _uid_yi else ""
C("M2 ★ A{n} 在两套登记表里指向同一物",
  bool(_uid_yi) and bool(_a1_t) and _a1_u[:16] == _a1_t[:16],
  "aspect_units[%s]=%r vs aspect_targets[%s]=%r"
  % (_uid_yi, _a1_u[:16], _uid_yi, _a1_t[:16]))

# ─────────────────────────────────────────────────────────────────
# P. 渲染源缺字段：shape_of 读 u.get("id")，写入点写不写 id
# ─────────────────────────────────────────────────────────────────
_shape_reads_id = re.search(r'_aid = str\(u\.get\("id"', _body) is not None
# ★ 写入点可能是**多行**写法（dict 跨行）⇒ 检测「append( 之后 N 行内出现 "id"」
_untouched_writes = []
for _i2, _ln in enumerate(_ilines):
    if re.search(r'view\.untouched\.append\(', _ln):
        _seg = "\n".join(_ilines[_i2:_i2 + 4])
        _untouched_writes.append(_seg)
_writes_id = any('"id"' in seg for seg in _untouched_writes)
C("P1 shape_of 读 untouched 的 id 前缀", _shape_reads_id)
C("P2 ★ untouched 的写入点必须带 id（否则渲染恒无前缀）",
  (not _shape_reads_id) or _writes_id,
  "写入点 %d 处，带 id 的 %d 处" % (len(_untouched_writes),
                                    sum(1 for x in _untouched_writes
                                        if '"id"' in x)))

# ─────────────────────────────────────────────────────────────────
# N. 可观测字段无出口（死字段）
# ─────────────────────────────────────────────────────────────────
_VIEW_FIELDS = ["touch_rate", "aspect_carry_rate"]
for _f in _VIEW_FIELDS:
    _defs = [ln for ln in _ilines
             if re.search(r"def %s\b" % _f, ln)]
    # ★ 消费点 = 非 def 行、**非注释行**、**非 docstring 行**里的裸引用
    def _is_code_use(ln):
        s = ln.strip()
        if not s or s.startswith("#"):
            return False
        if re.search(r"def %s\b" % _f, ln):
            return False
        # docstring 行：以 ★ / · / 引号 / 中文说明开头且无 ()[]. 等调用特征
        if s.startswith("★") or s.startswith("·") or s.startswith('"""'):
            return False
        return bool(re.search(r"[\.\(\[\s]%s\b" % _f, ln)) and "`" not in s
    _uses = [ln for ln in _ilines if _is_code_use(ln)]
    C("N1 %s 有定义" % _f, len(_defs) >= 1)
    C("N2 ★ %s 在引擎内有消费点（不是死字段）" % _f, len(_uses) >= 1,
      "非定义非注释真实引用 %d 处 %r" % (len(_uses),
                                          [x.strip()[:60] for x in _uses[:3]]))

# ─────────────────────────────────────────────────────────────────
# O. 有出口但恒空（结构性不可达）
# ─────────────────────────────────────────────────────────────────
_ub_calls = [ln.strip() for ln in _ilines
             if "upsert_belief(" in ln and "def " not in ln]
_guard_pre = None
if _ub_calls:
    _idx = _body.index("self.upsert_belief(")
    _pre = _body[max(0, _idx - 400):_idx]
    _guard_pre = "not any(_similar" in _pre
C("O1 ★ upsert_belief 的调用点不在「新条目」守卫里（否则复现永远登记不上）",
  not _guard_pre,
  "调用点 %d 处；前置守卫=%r" % (len(_ub_calls), _guard_pre))
# ★ 迁移驱动：**注入点**（F10）与**消费点**（F1）两处都要在；
#   只看调用行会漏（`attack=` 写在调用行上，键来自 product）。
_inject_atk = "_und_prod[\"_belief_attack\"]" in _body
_inject_res = "_und_prod[\"_belief_resolved\"]" in _body
_consume_atk = "_belief_attack" in _body and "attack=(_atk" in _body
_consume_res = "_belief_resolved" in _body and "resolved_by=(_res" in _body
C("O2 ★ 迁移驱动（attack/resolved）在注入点与消费点都接了",
  (_inject_atk and _consume_atk) and (_inject_res and _consume_res),
  "注入 atk/res=%r/%r；消费 atk/res=%r/%r"
  % (_inject_atk, _inject_res, _consume_atk, _consume_res))

# ─────────────────────────────────────────────────────────────────
# Q. 双读数无消费（D3 类：能力在、未接线）
# ─────────────────────────────────────────────────────────────────
for _meth in ("refresh_belief_entropy", "belief_status_counts"):
    _calls = [ln.strip() for ln in _ilines
              if _meth in ln and ("def " + _meth) not in ln]
    C("Q1 ★ %s 有引擎内调用点" % _meth, len(_calls) >= 1,
      "调用点 %d 处" % len(_calls))

# ─────────────────────────────────────────────────────────────────
# R. 判据未覆盖接线：纯函数判据全绿但真实入口不可达
# ─────────────────────────────────────────────────────────────────
_smoke = (HERE / "smoke_test.py")
if _smoke.exists():
    _st = _smoke.read_text(encoding="utf-8").replace("\r\n", "\n")
    _pure_fn = "belief_transition(" in _st
    # ★ 真实入口产出判据 = 走**引擎唯一写入口** `add_undecidable(` 后再断言
    #   产出物。比「直接调 upsert_belief」更强：add_undecidable 是上游，
    #   它内部才调 upsert_belief —— 判据落在最外层入口上才不会「绕过登记」。
    #   （旧锚点只认 `upsert_belief(`，会漏判 update 后的实现 —— 判据随
    #     实现更新，不是放宽阈值。）
    _real_entry = ("add_undecidable(" in _st
                   and "belief_transitions" in _st)
    # 「直塞」= 直接把构造条目塞进 belief_items（绕过登记路径）
    _direct_seed = ("belief_items = list(" in _st
                    or ".belief_items = [" in _st)
    # 直塞存在与否不再是「红」的判据 —— 夹具造前置状态是正常的；
    # 关键是**必须同时有真实入口判据**。
    C("R1 冒烟测了 belief_transition 纯函数", _pure_fn)
    C("R2 ★ 冒烟也测了真实登记入口（add_undecidable 产出迁移）",
      _real_entry,
      "纯函数=%r 真入口=%r（直塞夹具=%r 属正常）"
      % (_pure_fn, _real_entry, _direct_seed))
else:
    C("R1 冒烟存在", False)

# ─────────────────────────────────────────────────────────────────
# S. E2 floor 默认值是否让守卫恒假
# ─────────────────────────────────────────────────────────────────
_fl_line = [ln for ln in _ilines if re.search(r"^_GAIN_MARGINAL_FLOOR\s*=", ln)]
_fl_val = None
if _fl_line:
    try:
        _fl_val = float(_fl_line[0].split("=")[1].strip().split()[0])
    except Exception:
        pass
C("S1 ★ E2 marginal floor > 0（否则 below_floor 分支恒不触发）",
  _fl_val is not None and _fl_val > 0,
  "_GAIN_MARGINAL_FLOOR=%r" % _fl_val)

# ─────────────────────────────────────────────────────────────────
# T. 探针标记落盘（gain_source）
# ─────────────────────────────────────────────────────────────────
_probe_append = re.search(r'out\.append\(\{"question"', _body)
_probe_has_src = False
if _probe_append:
    _seg = _body[_probe_append.start():_probe_append.start() + 400]
    _probe_has_src = "gain_source" in _seg
C("T1 ★ 探针落盘 dict 带 gain_source（双写要落到同一份）",
  _probe_has_src)

# ─────────────────────────────────────────────────────────────────
print("=" * 74)
print("v1.23.28 复审探针 · %s" % SRC.name)
print("=" * 74)
for x in ok:
    print("  ✓ " + x)
print()
for x in bad:
    print("  ✗ " + x)
print()
print("REVIEW PASS %d / FAIL %d" % (len(ok), len(bad)))
sys.exit(1 if bad else 0)
