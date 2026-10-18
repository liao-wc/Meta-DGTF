# -*- coding: utf-8 -*-
"""v1.23.60：配置头 + 升级段 + 登记表 + CHANGELOG 段。"""
import importlib.util
import json
import pathlib
import sys

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


UPGRADE = '''# 【v1.23.59 → v1.23.60】快照记**层内进度**（只记录，不改续跑行为）
#   ① 问题：检查点原来只在**层完成**时才有该层状态 ⇒ 一层跑到第 5 圈被杀，
#      快照里只知道"这层没完成"，**不知道死在第几圈**；估预算也只能按层不按圈
#      （实测一层 4~7 圈，时长差 2 倍）。
#   ② 修法：`_layer_goal_now`（三个执行器每圈都走到这一处）顺手记
#      `_layer_progress[entry]` = rounds_done / candidates / amps / threads / 本圈读数；
#      `_ckpt_snapshot` 把它与 `goal_hist` 一起写进快照。
#   ③ **不做圈内恢复**：`seeds`/`carry` 由上一圈 View 派生、**不是纯函数** ⇒
#      中途恢复会得到"另一条轨迹"却挂着同一 run_id —— 比整层重跑更危险。
#      详见 `docs/圈内检查点-设计.md` §三。续跑侧**一个字没改**。
#   ★ 无新配置键。

'''

patch("dgtf_config.yaml", [
    ("头部版本", "# 元 DGTF · v1.23.59 配置文件",
     "# 元 DGTF · v1.23.60 配置文件"),
    ("插升级段", "# 【v1.23.58 → v1.23.59】", UPGRADE + "# 【v1.23.58 → v1.23.59】"),
])

p = HERE / "_v122_ast_registry.json"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
d = json.loads(raw.decode("utf-8"))
assert d["current"] == "元DGTF-V1.23.59.py", d["current"]
d["current"] = "元DGTF-V1.23.60.py"
p.write_bytes(json.dumps(d, ensure_ascii=False, indent=1)
              .replace("\n", "\r\n").encode("utf-8"))
print("  [OK] 登记表 current → 元DGTF-V1.23.60.py（%d 条 / %d 符号）"
      % (len(d["registry"]), d["n_symbols_current"]))

SEC = """v1.23.60 相对 v1.23.59

【主题】快照记**层内进度** —— 被杀之后能看见"死在第几圈"。

【问题】检查点原来只在**层完成**时才有该层状态。一层跑到第 5 圈被杀，
快照里只知道"这层没完成"，`rounds_run` 只有已完成层的；**死在第几圈查不到**。
估预算也只能按层算，不能按圈算（实测一层 4~7 圈，时长差 2 倍）。

【修法（只记录，不恢复）】
  · `_layer_goal_now` —— 三个执行器（serial / 并行 / 分层阶段）**每圈都会走到这一处**
    ⇒ 在这一处记 `_layer_progress[entry]`：
    `rounds_done` / `candidates` / `amps` / `threads` / 本圈目标读数；
  · `_ckpt_snapshot` 把它与 `goal_hist`（跨圈目标读数历史）一起写进快照；
  · `run()` 起跑清空 `_layer_progress`（同一实例可能被复用）。
  ★ **续跑一个字没改**：`load_resume_snapshot` 不读这两个字段，截断层照旧"整层重跑"。

【为什么不做圈内恢复】`seeds` / `carry` 由**上一圈 View** 派生、**不是纯函数** ⇒
中途恢复会得到"另一条轨迹"，却挂着同一个 `run_id` 和正常完成标记 ——
这比"整层重跑"更危险（整层重跑至少是一次干净、自洽的跑次）。
详见 `docs/圈内检查点-设计.md` §三（含两步走方案与第 2 步的前置条件）。

---

★ v1.23.60 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.60.py`（26806 行 / 纯 CRLF）+ 冒烟新判据
`check_v12360_layer_progress` + 变异体 M111 + 本段。

**改了什么**：每圈记层内进度；快照多两个字段（`layer_progress` / `goal_hist`）；
起跑清空。4 个改动块 / 增 24 行；无新符号（325 / 589）；无新配置键。

**验收**：冒烟 259 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 109/109（M111 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
判据四臂：快照里 `rounds_done == rounds_run` · `goal_hist` 条数 == 圈数 ·
**续跑侧返回键集合没变且函数体里没有这两个字段**（AST 取体，不用字符串切）·
已完成的快照仍拒绝续跑。

**一处判据自查**：第一版判据说"续跑侧没读"用了 `split("\\ndef ")` 切函数体，
结果把后面 **7700 行**（类方法缩进 4 格）全吞进来 ⇒ 判据测的是整份文件、永远判红。
改用 **AST** 精确取（76 行）后通过。**抠函数体一律走 AST。**

**未做**：圈内**恢复**（要先把 `seeds`/`carry` 改成只依赖 pool 的纯函数，再证等价性）；
`shape_limit` 取值扫描。

"""
patch("CHANGELOG.md", [
    ("插本版段", "v1.23.59 相对 v1.23.58\n", SEC + "v1.23.59 相对 v1.23.58\n"),
])


def load(py):
    spec = importlib.util.spec_from_file_location("v_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


a = load(HERE / "元DGTF-V1.23.59.py")
b = load(HERE / "元DGTF-V1.23.60.py")
_ca = json.dumps(a.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True)
_cb = json.dumps(b.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True)
assert _ca == _cb, "load_config 结果不同（本版不应有任何配置差异）"
print("  [OK] load_config 两版逐字相同（差异 0 项）")
