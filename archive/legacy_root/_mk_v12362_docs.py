# -*- coding: utf-8 -*-
"""v1.23.62：配置头 + 升级段 + 登记表 + CHANGELOG 段。"""
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


UPGRADE = '''# 【v1.23.61 → v1.23.62】把 `contra`（反向证据）**接活**
#   ① 问题（死代码审计）：`contra` 唯一的写入点是 `eml_note_contra()`，而它
#      **全项目没人调用**（AST 审计：名字全文只出现 1 次）⇒ `contra` 恒 0
#      ⇒ `eml_promote` 里「反向证据够了不许升级」那条**永远不触发**。
#      判据在、输入没人产出 —— 与"读数无出口"是同一类死法。
#   ② 修法：`_eml_note_use()` 的**负面分支**（用了但本跑读数不达标）除了降
#      weight，再记一次 contra。这样 `contra` 才有来源，晋升闸才是活的。
#   ★ 行为变化：`playbook.mode` 默认 shadow/off ⇒ 默认路径零影响；打开 EML 时，
#     被反复证明"用了没用"的条目会在 3 次负面后不再被升级（正是文档写的语义）。
#   ★ 无新配置键。

'''

patch("dgtf_config.yaml", [
    ("头部版本", "# 元 DGTF · v1.23.61 配置文件",
     "# 元 DGTF · v1.23.62 配置文件"),
    ("插升级段", "# 【v1.23.60 → v1.23.61】", UPGRADE + "# 【v1.23.60 → v1.23.61】"),
])

p = HERE / "_v122_ast_registry.json"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
d = json.loads(raw.decode("utf-8"))
assert d["current"] == "元DGTF-V1.23.61.py", d["current"]
d["current"] = "元DGTF-V1.23.62.py"
p.write_bytes(json.dumps(d, ensure_ascii=False, indent=1)
              .replace("\n", "\r\n").encode("utf-8"))
print("  [OK] 登记表 current → 元DGTF-V1.23.62.py（%d 条 / %d 符号）"
      % (len(d["registry"]), d["n_symbols_current"]))

SEC = """v1.23.62 相对 v1.23.61

【主题】`contra`（反向证据）接活 —— 一条从没被喂过数据的闸。

【问题（死代码审计）】`contra` **唯一的写入点**是 `eml_note_contra()`，
而它**全项目没人调用**（AST 审计：名字全文只出现 1 次）。于是：

· `contra` 恒为 0；
· `eml_promote()` 里 `if int(e.get("contra", 0)) >= int(promote_n): continue`
  **永远不触发** —— 判据写着"反向证据够了不许升级"，可反向证据从不累积；
· `_eml_note_use()` 的负面分支只降 `weight`，不记 `contra`。

判据在、输入没人产出 —— **与「读数无出口」是同一类死法**（第 ④ 次遇到）。

【修法】只补一行（不新增机制）：负面分支除了降 weight，再记一次 `contra`：

    eml_note_contra([_e], [_e], why="used_but_duty_low")

★ 行为变化要说清：`playbook.mode` 默认 `shadow`/`off` ⇒ **默认路径零影响**；
  打开 EML 时，一个被反复证明"用了没用"的条目，会在 3 次负面后**不再被升级**。
  这正是 `eml_promote` 文档里写的语义（"反向证据够 ⇒ 降级"）。

---

★ v1.23.62 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.62.py`（26828 行 / 纯 CRLF）+ 冒烟新判据
`check_v12362_contra_live` + 变异体 M113 + 本段。

**改了什么**：`_eml_note_use` 负面分支补记 `contra`（9 行）；版本号两处。
3 个改动块 / 增 9 行；无新符号（325 / 589）；无新配置键。

**验收**：冒烟 262 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 111/111（M113 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
判据四臂：`contra` 会累积（3 次 → 3，且留 `contra_last` 原因）·
`contra=3` **拦住**升级 · `contra=0` **放行**（两向对照，证明闸不是见谁都拦）·
`_eml_note_use` 里确实有调用点（AST 取体）。

**顺带**：本版同时把**从未接线**的 `check_p0_156_units(src)` 接进 `main()`
（157/157 全接），并提供审计脚本 `_audit_unwired_checks.py` 防复发。

**未做**：`shape_limit` 取值扫描（≈¥12）；圈内恢复（需先做确定性改造）。

"""
patch("CHANGELOG.md", [
    ("插本版段", "v1.23.61 相对 v1.23.60\n", SEC + "v1.23.61 相对 v1.23.60\n"),
])


def load(py):
    spec = importlib.util.spec_from_file_location("v_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


a = load(HERE / "元DGTF-V1.23.61.py")
b = load(HERE / "元DGTF-V1.23.62.py")
_ca = json.dumps(a.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True)
_cb = json.dumps(b.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True)
assert _ca == _cb, "load_config 结果不同（本版不应有任何配置差异）"
print("  [OK] load_config 两版逐字相同（差异 0 项）")
