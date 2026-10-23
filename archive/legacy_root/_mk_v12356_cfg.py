# -*- coding: utf-8 -*-
"""v1.23.56 配置同步 + 登记表指向（无新键、无新符号）。"""
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


UPGRADE = '''# 【v1.23.55 → v1.23.56】快照记账改成**跨窗口累计**
#   ① 问题：快照里的 `llm_calls` / `llm_tokens` 取自 `self.llm.total_calls`，那是
#      **按实例**的计数器。续跑新建实例就归零 ⇒ 第二个窗口的快照只记本窗口。
#      实测（A/B 真跑）：这条 run_id 实际花了 230 calls，快照里写的 **97**。
#      按这个数结算成本，前面那个窗口的钱**查不到** —— 直接打穿 v1.23.50 立命的
#      「被杀跑次也能结算成本」。
#   ② 修法：`load_resume_snapshot` 把快照里的计数一起返回；`run()` 记进
#      `self._ck_base`；`_ckpt_snapshot` 落盘写 **累计 = 基线 + 本实例**，
#      并**另存** `window_calls` / `window_tokens` 保留本窗口读数
#      （结算看累计，分析看窗口）。
#   ★ 无新配置键；不传 `resume_ckpt` ⇒ 基线为 0 ⇒ 数值与旧版**逐字相同**。

'''

patch("dgtf_config.yaml", [
    ("头部版本", "# 元 DGTF · v1.23.55 配置文件",
     "# 元 DGTF · v1.23.56 配置文件"),
    ("插升级段", "# 【v1.23.54 → v1.23.55】", UPGRADE + "# 【v1.23.54 → v1.23.55】"),
])

p = HERE / "_v122_ast_registry.json"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
d = json.loads(raw.decode("utf-8"))
assert d["current"] == "元DGTF-V1.23.55.py", d["current"]
d["current"] = "元DGTF-V1.23.56.py"
p.write_bytes(json.dumps(d, ensure_ascii=False, indent=1)
              .replace("\n", "\r\n").encode("utf-8"))
print("  [OK] 登记表 current → 元DGTF-V1.23.56.py（无新符号 ⇒ %d 条 / %d 符号）"
      % (len(d["registry"]), d["n_symbols_current"]))

import importlib.util
import sys


def load(py):
    spec = importlib.util.spec_from_file_location("v_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


a = load(HERE / "元DGTF-V1.23.55.py")
b = load(HERE / "元DGTF-V1.23.56.py")
ca = json.dumps(a.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True,
                ensure_ascii=False)
cb = json.dumps(b.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True,
                ensure_ascii=False)
assert ca == cb, "load_config 结果不同（本版不应有任何配置差异）"
print("  [OK] load_config 两版逐字相同（差异 0 项）")
