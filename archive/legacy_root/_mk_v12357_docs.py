# -*- coding: utf-8 -*-
"""v1.23.57：配置头 + 升级段 + 登记表 + CHANGELOG 段（无新键、无新符号）。"""
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


UPGRADE = '''# 【v1.23.56 → v1.23.57】把 `goal_trace` **跨圈接上**（`stop.gain_floor` 才走得到）
#   ① 缺陷：引擎**每圈新建 view**（`view = dg.run(inp)`），而目标读数只 append 到
#      **当圈那个 view** ⇒ 下一圈换对象就丢。产物实测：跑 4~7 圈，`goal_trace`
#      每层只有 **1** 条。
#   ② 后果：`layer_gain_stop_signal` 第一道门是 `len(prev) >= _LG_STOP_FLAT_N+1`（=3），
#      而它拿到的 `prev` 恒 1 条 ⇒ 门恒关 ⇒ **`stop.gain_floor` 在任何取值下都不触发**。
#      ——这是「结构性不可达」，不是阈值太严（扫 6/8/12 只会得到三个"零触发"）。
#   ③ 修法：历史挂在**引擎**上（`self._goal_hist[entry]`），每圈把完整历史挂回当前
#      view；`run()` 起跑清空（同一实例可能被复用）。
#   ★ 只搬数据、不动判据；`gain_floor` 默认 0（关）⇒ 出厂行为**逐字不变**。

'''

patch("dgtf_config.yaml", [
    ("头部版本", "# 元 DGTF · v1.23.56 配置文件",
     "# 元 DGTF · v1.23.57 配置文件"),
    ("插升级段", "# 【v1.23.55 → v1.23.56】", UPGRADE + "# 【v1.23.55 → v1.23.56】"),
])

p = HERE / "_v122_ast_registry.json"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
d = json.loads(raw.decode("utf-8"))
assert d["current"] == "元DGTF-V1.23.56.py", d["current"]
d["current"] = "元DGTF-V1.23.57.py"
p.write_bytes(json.dumps(d, ensure_ascii=False, indent=1)
              .replace("\n", "\r\n").encode("utf-8"))
print("  [OK] 登记表 current → 元DGTF-V1.23.57.py（无新符号 ⇒ %d 条 / %d 符号）"
      % (len(d["registry"]), d["n_symbols_current"]))

SEC = """v1.23.57 相对 v1.23.56

【主题】把 `goal_trace` **跨圈接上** —— `stop.gain_floor` 从此才走得到。

【问题（A/B 追查发现的结构性缺陷）】引擎**每圈新建 view**（`view = dg.run(inp)`，
旁边注释原话「每圈新建 view、只 return 最后」），而 `_layer_goal_now` 把当圈读数
只 append 到**当圈那个 view** 上 ⇒ 下一圈换对象，历史就丢。产物实测：

    层 0  跑 4 圈 → goal_trace 1 条
    层 1  跑 7 圈 → goal_trace 1 条
    both  跑 7 圈 → goal_trace 1 条
    all   跑 2 圈 → goal_trace 1 条

而 `layer_gain_stop_signal` 的第一道门是 `len(prev) >= _LG_STOP_FLAT_N + 1`（=3）
⇒ 门**恒关** ⇒ **`stop.gain_floor` 在任何取值下都不会触发**。
这是「结构性不可达」：调用点在、逻辑对，被数据流挡死 —— 不是阈值太严。
（原计划的 `gain_floor` 取值扫描 6/8/12 **因此作废**：只会扫出三个"零触发"。）

【修法】只搬数据、不动判据：
  · 每层历史挂在**引擎**上（`self._goal_hist[entry]`），`_layer_goal_now` 追加到它；
  · 每圈把**完整历史**挂回当前 view（`view.goal_trace = list(_h)`）；
  · `run()` 起跑清空（同一实例可能被复用跑多次，不清会污染本跑的早停判据）。
  ★ `gain_floor` 默认 0（关）⇒ 出厂行为**逐字不变**（那条历史根本没人看）。

---

★ v1.23.57 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.57.py`（26718 行 / 纯 CRLF）+ 冒烟新判据
`check_v12357_goal_trace_carry` + 变异体 M108 + 本段。

**改了什么**：目标读数历史挂引擎 + 每圈挂回 view + 起跑清空。4 个改动块 / 增 17 行；
无新符号（325 / 589）。

**验收**：冒烟 256 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 106/106（M108 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
新判据拆两段：真入口证「`goal_trace` 条数 == `rounds_run`」，纯函数证「3 条低增益
历史**必须触发**」—— 因为 mock 产物是固定文本，修行层第 2 圈就被"复述/空转"自然停了，
走不到第 3 圈，"触发"这一支只能靠纯函数证。开发期另有**旧版对照**（v1.23.56 同条件
仍恒 1 条）。

**未做**：`gain_floor` 取值扫描（**通道刚修好，可以做了**，但那要真跑 ≈¥12）；
`shape_limit` 扫描；更细粒度检查点。

"""
patch("CHANGELOG.md", [
    ("插本版段", "v1.23.56 相对 v1.23.55\n", SEC + "v1.23.56 相对 v1.23.55\n"),
])

import importlib.util
import sys


def load(py):
    spec = importlib.util.spec_from_file_location("v_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


a = load(HERE / "元DGTF-V1.23.56.py")
b = load(HERE / "元DGTF-V1.23.57.py")
ca = json.dumps(a.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True,
                ensure_ascii=False)
cb = json.dumps(b.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True,
                ensure_ascii=False)
assert ca == cb, "load_config 结果不同（本版不应有任何配置差异）"
print("  [OK] load_config 两版逐字相同（差异 0 项）")
