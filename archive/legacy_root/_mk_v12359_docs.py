# -*- coding: utf-8 -*-
"""v1.23.59：配置头 + 升级段 + 登记表 + CHANGELOG 段。"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def patch(name, edits):
    p = HERE / name
    raw = p.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n"), "%s 不是纯 CRLF" % name
    assert raw.count(b"\r\r\n") == 0
    s = raw.decode("utf-8").replace("\r\n", "\n")
    n0 = s.count("\n")
    for what, old, new in edits:
        c = s.count(old)
        assert c == 1, "%s / %s：命中 %d 次" % (name, what, c)
        s = s.replace(old, new)
        print("  [OK] %-22s %s" % (name, what))
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
    p.write_bytes(out)
    print("       %d → %d 行" % (n0, s.count("\n")))


UPGRADE = '''# 【v1.23.58 → v1.23.59】修行层增益**换信号**：Heaps 边际 → 相对新增率
#   ① 问题：`stop.gain_floor` 的输入是 `refinement_gain`，修行层取 `excavate`
#      （Heaps 边际 ΔV/Δn）。那个读数要 `len(hist)>=3` 才开算，退化增长还返回 None
#      ⇒ 实测 4 圈里 3 圈 None ⇒ 增益恒 None ⇒ **早停判据永远不触发**（信号稀疏）。
#   ② 换法：修行层增益改取**相对新增率** = max(0, Δn_aspects) / 上圈 n_aspects。
#      只要有两圈、上圈 n>0 就有值；语义仍是「新增趋零」；0..1 有界，与 α 同量纲。
#   ③ 保留：`excavate` 读数本身不动（四层目标的公开读数，目标定义是红线）；
#      其余三层方向不动（settle/fuse/crystallize 仍是「本圈 − 上圈」）；
#      **老产物没有 `n_aspects` ⇒ 退回 Heaps 算路**（逐字不变）。
#   ★ 无新配置键；`gain_floor` 默认 0 ⇒ 判据直接返回 ⇒ 出厂零行为差。

'''

patch("dgtf_config.yaml", [
    ("头部版本", "# 元 DGTF · v1.23.58 配置文件",
     "# 元 DGTF · v1.23.59 配置文件"),
    ("插升级段", "# 【v1.23.57 → v1.23.58】", UPGRADE + "# 【v1.23.57 → v1.23.58】"),
])

p = HERE / "_v122_ast_registry.json"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
d = json.loads(raw.decode("utf-8"))
assert d["current"] == "元DGTF-V1.23.58.py", d["current"]
d["current"] = "元DGTF-V1.23.59.py"
p.write_bytes(json.dumps(d, ensure_ascii=False, indent=1)
              .replace("\n", "\r\n").encode("utf-8"))
print("  [OK] 登记表 current → 元DGTF-V1.23.59.py（%d 条 / %d 符号）"
      % (len(d["registry"]), d["n_symbols_current"]))

SEC = """v1.23.59 相对 v1.23.58

【主题】修行层增益**换信号**：Heaps 边际（稀疏）→ 相对新增率（总在）。

【问题（实测，¥0.4 的探针）】`stop.gain_floor` 的输入是 `refinement_gain`，
修行层取 `excavate`（Heaps 边际 ΔV/Δn）。那个读数有两道门：
`_lg_aspect_margin` 要 `len(hist) >= 3` 才开算，退化增长还**返回 None**。
探针实测 4 圈里 **3 圈是 None**：

    圈  excavate  n_aspects
    1   None      16
    2   None      16
    3   0.0       14
    4   None      20

⇒ 增益恒 None ⇒ **早停判据永远不触发**。不是阈值问题，是**信号太稀疏**。

【换法】修行层增益 = **相对新增率** = `max(0, Δn_aspects) / 上圈 n_aspects`
  · 只要有两圈、上圈 n>0 就有值 ⇒ 不再稀疏；
  · 语义仍是「新增趋零」（新增长不动 ⇒ 增益→0 ⇒ 迭代饱和）；
  · 0..1 有界，与 `gain_floor` 同量纲。

【保留不动】
  · `excavate` 读数本身（四层目标的公开读数 —— 目标定义是红线，不改）；
  · 其余三层方向（settle / fuse / crystallize 仍是「本圈 − 上圈」）；
  · **老产物没有 `n_aspects` ⇒ 退回 Heaps 算路**（逐字不变）。
  ★ 无新配置键；`gain_floor` 默认 0 ⇒ 判据直接返回 ⇒ 出厂零行为差。

---

★ v1.23.59 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.59.py`（26782 行 / 纯 CRLF）+ 冒烟新判据
`check_v12359_gain_signal` + 变异体 M110 + 本段。

**改了什么**：`refinement_gain` 修行层分支优先用相对新增率，老产物退回 Heaps。
2 个改动块 / 增 14 行；无新符号（325 / 589）。

**验收**：冒烟 258 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 108/108（M110 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
新判据的夹具是**实测真实读数**（16, 16, 14, 20）：同一组数据旧信号全 None，
新信号算出 `[0.0, 0.0, 0.4286]` 并在连续两圈 0 后触发；另三臂：层面在长不许停 ·
老产物退回 Heaps · 其余三层方向未变。

**未做**：更细粒度检查点（圈内），见下一版。

"""
patch("CHANGELOG.md", [
    ("插本版段", "v1.23.58 相对 v1.23.57\n", SEC + "v1.23.58 相对 v1.23.57\n"),
])

import importlib.util
import sys


def load(py):
    spec = importlib.util.spec_from_file_location("v_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


a = load(HERE / "元DGTF-V1.23.58.py")
b = load(HERE / "元DGTF-V1.23.59.py")
_ca = json.dumps(a.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True)
_cb = json.dumps(b.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True)
assert _ca == _cb, "load_config 结果不同（本版不应有任何配置差异）"
print("  [OK] load_config 两版逐字相同（差异 0 项）")
