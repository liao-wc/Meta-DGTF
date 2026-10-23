# -*- coding: utf-8 -*-
"""v1.23.58：配置头 + 升级段 + 登记表 + CHANGELOG 段。"""
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


UPGRADE = '''# 【v1.23.57 → v1.23.58】晋升门槛 `_eff_n` 与 shadow 拦截原因**进产物**
#   ① 问题：`eml_promote` 里自适应后的实际门槛 `_eff_n` 只活在函数内部，产物里查不到
#      ⇒「库 11 < 冷启 20 ⇒ 门槛降到 1，但被质量闸挡下」只能**推断**。
#      「我推断它降到了 1」与「产物里写着 1」是两件事。
#   ② 修法：`eml_promote(..., trace=None)` 多收一个 dict，填 `eff_n` / `promote_n` /
#      `adaptive` / `n_lib` / `cold_lib` / `shadow`（逐条 verdict）/ `shadow_verdicts`；
#      调用方挂成 `_blk["promote_trace"]`，产物 md 正文加一行「晋升门槛 ≥N（自适应…）
#      ｜shadow 拦截：n_short×2、quality_down×1…」。
#   ③ 五类 verdict：`n_short` / `contra` / `quality_down` / `cost_only` / `promoted`
#      —— 否则「0 升级」分不清是"没东西可升"还是"有但被挡住"。
#   ★ 无新配置键；不传 `trace` ⇒ 行为**逐字不变**（默认 None）。

'''

patch("dgtf_config.yaml", [
    ("头部版本", "# 元 DGTF · v1.23.57 配置文件",
     "# 元 DGTF · v1.23.58 配置文件"),
    ("插升级段", "# 【v1.23.56 → v1.23.57】", UPGRADE + "# 【v1.23.56 → v1.23.57】"),
])

p = HERE / "_v122_ast_registry.json"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
d = json.loads(raw.decode("utf-8"))
assert d["current"] == "元DGTF-V1.23.57.py", d["current"]
d["current"] = "元DGTF-V1.23.58.py"
p.write_bytes(json.dumps(d, ensure_ascii=False, indent=1)
              .replace("\n", "\r\n").encode("utf-8"))
print("  [OK] 登记表 current → 元DGTF-V1.23.58.py（%d 条 / %d 符号）"
      % (len(d["registry"]), d["n_symbols_current"]))

SEC = """v1.23.58 相对 v1.23.57

【主题】晋升门槛 `_eff_n` 与每个 shadow 的**拦截原因**进产物。

【问题（可达性审计留下的洞）】`eml_promote` 里自适应后的实际门槛 `_eff_n` 只活在
函数内部，产物里查不到。于是「库 11 < 冷启阈值 20 ⇒ 门槛从 3 降到 1，但 3 个 shadow
仍被质量闸挡下」这句话**只能是推断**。
**「我推断它降到了 1」与「产物里写着 1」是两件事。**

【修法】`eml_promote(..., trace: dict = None)`：
  · 传了就填 `eff_n` / `promote_n` / `adaptive` / `n_lib` / `cold_lib` /
    `shadow`（逐条 verdict）/ `shadow_verdicts`（分类计数）；
  · 调用方挂成 `_blk["promote_trace"]`；
  · 产物 md 正文加一行：
    `↳ 晋升门槛 ≥1（名义 3；自适应：库 11 < 冷启 20 ⇒ 降到 1）｜shadow 拦截：n_short×3`
  ★ 五类 verdict：`n_short` / `contra` / `quality_down` / `cost_only` / `promoted`
    —— 否则「0 升级」分不清是「没东西可升」还是「有但被挡住」。
  ★ 无新配置键；不传 `trace` ⇒ 行为**逐字不变**。

---

★ v1.23.58 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.58.py`（26768 行 / 纯 CRLF）+ 冒烟新判据
`check_v12358_promote_trace` + 变异体 M109 + 本段。

**改了什么**：`eml_promote` 增加可选 `trace` 参数并逐条记录拦截原因；调用方挂进产物；
产物 md 加一行晋升门槛。3 个改动块 / 增 50 行；无新符号（325 / 589）。

**验收**：冒烟 257 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 107/107（M109 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
开发期 15 项全过，含**旧版对照**（不传 `trace` 时返回值与条目状态含 weight **逐字相同**）。

**未做**：`gain_floor` 去留（A 承认不可用 / B 换信号改语义）；`shape_limit` 取值扫描；
更细粒度检查点。

"""
patch("CHANGELOG.md", [
    ("插本版段", "v1.23.57 相对 v1.23.56\n", SEC + "v1.23.57 相对 v1.23.56\n"),
])

import importlib.util
import sys


def load(py):
    spec = importlib.util.spec_from_file_location("v_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


a = load(HERE / "元DGTF-V1.23.57.py")
b = load(HERE / "元DGTF-V1.23.58.py")
_ca = json.dumps(a.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True)
_cb = json.dumps(b.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True)
assert _ca == _cb, "load_config 结果不同（本版不应有任何配置差异）"
print("  [OK] load_config 两版逐字相同（差异 0 项）")
