# -*- coding: utf-8 -*-
"""v1.23.62 开发期验证：`contra` 接活（反向证据会累积，晋升闸会真拦）。

判据：
  A `eml_note_contra` 现在真有调用点（死代码审计从 4 个降到 3 个）
  B 纯函数：连记 3 次反向证据 ⇒ `contra == 3`，且 `contra_last` 留了原因
  C 晋升闸：一条**本该升级**的 shadow（证据够、质量升）在 `contra=3` 时**不许升**
  D 对照：同一条 `contra=0` 时必须升级（闸不是"见谁都拦"）
  E 旧版对照：v1.23.61 里 `contra` 只有定义、没有调用（审计计数 == 1）
"""
import ast
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
bad, ok = [], []


def ck(cond, msg):
    (ok if cond else bad).append(msg)
    print(("  [OK]   " if cond else "  [BAD]  ") + msg)
    return bool(cond)


def load(py):
    spec = importlib.util.spec_from_file_location("c62_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


new = load(HERE / "元DGTF-V1.23.62.py")

print("=" * 62)
print("【A】死代码审计：eml_note_contra 不再只有定义")
src_new = (HERE / "元DGTF-V1.23.62.py").read_text(encoding="utf-8")
src_old = (HERE / "元DGTF-V1.23.61.py").read_text(encoding="utf-8")
ck(src_old.count("eml_note_contra") == 1,
   "旧版只出现 1 次（= 只有定义）：%d" % src_old.count("eml_note_contra"))
ck(src_new.count("eml_note_contra") >= 2,
   "新版出现 %d 次（有调用点）" % src_new.count("eml_note_contra"))

print("\n【B】纯函数：连记 3 次 ⇒ contra == 3 且留了原因")
_pb = [{"id": "L1", "status": "active", "contra": 0}]
for _ in range(3):
    new.eml_note_contra(_pb, [{"id": "L1"}], why="used_but_duty_low")
ck(_pb[0]["contra"] == 3, "contra=%r" % (_pb[0]["contra"],))
ck(_pb[0].get("contra_last") == "used_but_duty_low",
   "contra_last=%r" % (_pb[0].get("contra_last"),))

print("\n【C】晋升闸：该升的条目在被记 3 次反向证据后**不许升**")
def mk(contra):
    return [{"id": "S1", "status": "shadow", "n_evidence": 5,
             "quality_delta": 0.2, "contra": contra}]

_pb_c = mk(3)
_ch_c = new.eml_promote(_pb_c, promote_n=3)
ck(_ch_c == [], "contra=3 ⇒ 变更列表为空：%r" % (_ch_c,))
ck(_pb_c[0]["status"] == "shadow", "状态仍是 shadow：%r" % (_pb_c[0]["status"],))

print("\n【D】对照：contra=0 时必须升级")
_pb_ok = mk(0)
_ch_ok = new.eml_promote(_pb_ok, promote_n=3)
ck([x.get("to") for x in _ch_ok] == ["active"], "变更=%r" % (_ch_ok,))
ck(_pb_ok[0]["status"] == "active", "状态=%r" % (_pb_ok[0]["status"],))

print("\n【E】写入点仍在（`contra` 不能又被别的分支绕过）")
_tree = ast.parse(src_new)
_body = ""
for _n in ast.walk(_tree):
    if isinstance(_n, ast.FunctionDef) and _n.name == "_eml_note_use":
        _body = ast.get_source_segment(src_new, _n) or ""
        break
ck("eml_note_contra(" in _body, "_eml_note_use 里确实调用了它")

print("\n" + "=" * 62)
print("通过 %d / 判红 %d" % (len(ok), len(bad)))
for b in bad:
    print("  ! " + b)
sys.exit(1 if bad else 0)
