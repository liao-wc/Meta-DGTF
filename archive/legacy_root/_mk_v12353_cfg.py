# -*- coding: utf-8 -*-
"""v1.23.53 配置同步 + AST 登记（**新增一个符号** eml_store_dir）。

判据：两版 `load_config` 对同一份 yaml 逐字相同（无新键）。
"""
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


UPGRADE = '''# 【v1.23.52 → v1.23.53】记忆库目录**一处解析**（bandit 不再偷偷写回仓库）
#   ① 根因（挂账「目录两处解析未收敛」）：episode/playbook 走 `playbook.dir`，
#      bandit 却只看 `auto.bandit.dir`、空则 `eml_dir()`（**恒指仓库**）⇒ 任何设了
#      `playbook.dir` 的调用方（冒烟、A/B 脚本、想隔离库的人）都会让 bandit
#      偷偷写生产库。冒烟隔离因此要三个旋钮，**漏一个就污染**。
#   ② 修法：新增唯一解析 `eml_store_dir(cfg)`，三处都走它：
#      `auto.bandit.dir`（显式，仍优先） ＞ `playbook.dir` ＞ 仓库根 `dgtf_memory/`。
#   ③ 为什么是**模块级函数**：bandit 的**载入**发生在实例属性 `_eml_cfg` 赋值
#      **之前**，用实例状态会静默回落到 `eml_dir()` —— 那正是要修的 bug。
#   ★ 无新配置键；生产默认（`playbook.dir` 空）解析结果与旧版**逐字相同**。
#     想给 bandit 单独指定目录仍然可以：`auto.bandit.dir` 优先级不变。

'''

patch("dgtf_config.yaml", [
    ("头部版本", "# 元 DGTF · v1.23.52 配置文件",
     "# 元 DGTF · v1.23.53 配置文件"),
    ("插升级段", "# 【v1.23.51 → v1.23.52】", UPGRADE + "# 【v1.23.51 → v1.23.52】"),
])

p = HERE / "_v122_ast_registry.json"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
d = json.loads(raw.decode("utf-8"))
assert d["current"] == "元DGTF-V1.23.52.py", d["current"]
d["current"] = "元DGTF-V1.23.53.py"
assert "eml_store_dir" not in d["registry"]
d["registry"]["eml_store_dir"] = {
    "phase": "EML",
    "reason": "记忆库目录唯一解析（playbook.dir ＞ eml_dir；bandit 也跟着走）",
}
d["added"] = int(d["added"]) + 1
d["n_symbols_current"] = int(d["n_symbols_current"]) + 1
p.write_bytes(json.dumps(d, ensure_ascii=False, indent=1)
              .replace("\n", "\r\n").encode("utf-8"))
print("  [OK] 登记 eml_store_dir：registry %d 条 · added %d · n_symbols_current %d"
      % (len(d["registry"]), d["added"], d["n_symbols_current"]))

import importlib.util
import sys


def load(py):
    spec = importlib.util.spec_from_file_location("v_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


a = load(HERE / "元DGTF-V1.23.52.py")
b = load(HERE / "元DGTF-V1.23.53.py")
ca = json.dumps(a.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True,
                ensure_ascii=False)
cb = json.dumps(b.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True,
                ensure_ascii=False)
assert ca == cb, "load_config 结果不同（本版不应有任何配置差异）"
print("  [OK] load_config 两版逐字相同（差异 0 项）")
