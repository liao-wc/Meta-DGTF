# -*- coding: utf-8 -*-
"""v1.23.54 配置同步 + AST 登记（新增一个符号 `_wall_clock_over`）。

判据：两版 `load_config` 逐字相同（无新键）。
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


UPGRADE = '''# 【v1.23.53 → v1.23.54】并行跑次也能被墙钟预算截住、也能续跑
#   ① 根因：`max_minutes` 原来只挂在 `_run_serial` 的**层间** ⇒ 并行模式
#      （A/B/C + D~H）设了预算也照跑到天亮（宿主一回收就全丢）；而续跑入口又
#      **硬拒非 serial** ⇒ 强杀后连"续"都续不了。**预算保护对并行是空的。**
#   ② 修法：`_wall_clock_over()` 收成唯一判据，**三个**单层执行器的圈边界都判
#      （`_run_layer` / C 模式 / `_run_layer_stage`）；到点 ⇒ 该层记进
#      `_paused_rest`，`stop_reason` 带「墙钟预算」标记 ⇒ 整跑变 `paused`。
#   ③ 续跑：`load_resume_snapshot` 不再拒绝并行快照，改为**摘掉**带标记的层
#      （截断层不算完成，要重跑）；`run()` 里并行续跑**一律按 serial 跑剩余层**，
#      产物记 `resumed_serial` —— **降级留痕，不静默**。
#   ★ 无新配置键；`max_minutes` 默认 0 / 不传 `resume_ckpt` ⇒ 逐字零行为差。
#   ★ 一个必须知道的细节：`stop_reason` 是**逐圈在循环体末尾**拼的，圈首 break
#     会跳过那一步 ⇒ 标记必须**直接盖到 view 上**（第一版只写了 note，判据当场
#     逮到"续跑什么都不重跑"）。

'''

patch("dgtf_config.yaml", [
    ("头部版本", "# 元 DGTF · v1.23.53 配置文件",
     "# 元 DGTF · v1.23.54 配置文件"),
    ("插升级段", "# 【v1.23.52 → v1.23.53】", UPGRADE + "# 【v1.23.52 → v1.23.53】"),
])

p = HERE / "_v122_ast_registry.json"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
d = json.loads(raw.decode("utf-8"))
assert d["current"] == "元DGTF-V1.23.53.py", d["current"]
d["current"] = "元DGTF-V1.23.54.py"
assert "_wall_clock_over" not in d["registry"]
d["registry"]["_wall_clock_over"] = {
    "phase": "54",
    "reason": "墙钟预算唯一判据（serial 层间 + 三个并行单层执行器共用）",
}
d["added"] = int(d["added"]) + 1
d["n_symbols_current"] = int(d["n_symbols_current"]) + 1
p.write_bytes(json.dumps(d, ensure_ascii=False, indent=1)
              .replace("\n", "\r\n").encode("utf-8"))
print("  [OK] 登记 _wall_clock_over：registry %d 条 · added %d · 符号 %d"
      % (len(d["registry"]), d["added"], d["n_symbols_current"]))

import importlib.util
import sys


def load(py):
    spec = importlib.util.spec_from_file_location("v_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


a = load(HERE / "元DGTF-V1.23.53.py")
b = load(HERE / "元DGTF-V1.23.54.py")
ca = json.dumps(a.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True,
                ensure_ascii=False)
cb = json.dumps(b.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True,
                ensure_ascii=False)
assert ca == cb, "load_config 结果不同（本版不应有任何配置差异）"
print("  [OK] load_config 两版逐字相同（差异 0 项）")
