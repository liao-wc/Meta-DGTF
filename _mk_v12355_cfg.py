# -*- coding: utf-8 -*-
"""v1.23.55 配置同步 + 登记表指向（无新键、无新符号）。"""
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


UPGRADE = '''# 【v1.23.54 → v1.23.55】`paused` 时的缺层从「❌ 缺陷」改成「⏸ 待续」
#   ① 问题：A/B 真跑暂停时产物打了「❌ 缺层：请求了但这些层没有产出 —— 这份产物
#      是不完整的 / · 元：未记录原因（这是缺陷）」。可暂停时缺层是**设计**
#      （续跑会接着跑）——这条提示会让人去查一个不存在的 bug；更糟的是它把
#      `layer_gap` 写进产物，下游任何「缺层=缺陷」的判据都跟着误判。
#   ② 修法：`_layer_guard` 把缺层拆两拨 —— 在 `pending_layers` 里且 `paused`
#      ⇒ 记 `paused_gap` 并说"待续"；其余 ⇒ 仍是真缺陷，照样大声报红。
#   ★ 真缺陷**不许**被暂停豁免：暂停时某层既没产出也不在 pending 里，照样报。
#   ★ 无新配置键；非暂停路径**逐字不变**。

'''

patch("dgtf_config.yaml", [
    ("头部版本", "# 元 DGTF · v1.23.54 配置文件",
     "# 元 DGTF · v1.23.55 配置文件"),
    ("插升级段", "# 【v1.23.53 → v1.23.54】", UPGRADE + "# 【v1.23.53 → v1.23.54】"),
])

p = HERE / "_v122_ast_registry.json"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
d = json.loads(raw.decode("utf-8"))
assert d["current"] == "元DGTF-V1.23.54.py", d["current"]
d["current"] = "元DGTF-V1.23.55.py"
p.write_bytes(json.dumps(d, ensure_ascii=False, indent=1)
              .replace("\n", "\r\n").encode("utf-8"))
print("  [OK] 登记表 current → 元DGTF-V1.23.55.py（无新符号 ⇒ %d 条 / %d 符号）"
      % (len(d["registry"]), d["n_symbols_current"]))

import importlib.util
import sys


def load(py):
    spec = importlib.util.spec_from_file_location("v_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


a = load(HERE / "元DGTF-V1.23.54.py")
b = load(HERE / "元DGTF-V1.23.55.py")
ca = json.dumps(a.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True,
                ensure_ascii=False)
cb = json.dumps(b.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True,
                ensure_ascii=False)
assert ca == cb, "load_config 结果不同（本版不应有任何配置差异）"
print("  [OK] load_config 两版逐字相同（差异 0 项）")
