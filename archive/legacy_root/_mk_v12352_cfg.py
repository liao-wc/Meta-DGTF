# -*- coding: utf-8 -*-
"""v1.23.52 配置同步 + AST 登记表指向（无新配置键）。

顺带两条判据：
  · 两版 `load_config` 对同一份 yaml 解析结果**逐字相同**（无新键）
  · 默认值不会让新守卫失效：`runtime.live_checkpoint` 默认 true 时 `max_minutes`
    默认 0 ⇒ 守卫条件恒假（默认行为不变）
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


UPGRADE = '''# 【v1.23.51 → v1.23.52】`paused` 跑次**不写 EML 库**（半程样本不是证据）
#   ① 根因：上一版只保证「不重复调用就不多写」。墙钟预算暂停的跑次仍写一条
#      **半程样本**；续跑跑完后同 run_id 又写一条完整样本（读数不同 ⇒ 幂等守卫
#      按设计放行）⇒ 一个跑次**两条证据**、`used_outcomes` 记两笔、weight 罚两遍。
#   ② 修法：`_eml_finish` 在 `off` 判完之后先判 `paused` / `pending_layers`，
#      命中即返回（`skipped_paused`）—— **连库目录都不建、也不去抢锁**。
#      判据取自产物本身（`run()` 在调本方法之前就写好了这两个键），
#      所以不依赖调用方传参，任何入口口径一致。
#   ③ 成本不会丢：`llm_calls` / `llm_tokens` 仍在产物与快照里 ⇒ 暂停/被杀的
#      跑次照样能结算。
#   ★ 无新配置键；`max_minutes` 默认 0 ⇒ 守卫条件恒假 ⇒ 默认行为逐字不变。

'''

patch("dgtf_config.yaml", [
    ("头部版本", "# 元 DGTF · v1.23.51 配置文件",
     "# 元 DGTF · v1.23.52 配置文件"),
    ("插升级段", "# 【v1.23.50 → v1.23.51】", UPGRADE + "# 【v1.23.50 → v1.23.51】"),
])

p = HERE / "_v122_ast_registry.json"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
d = json.loads(raw.decode("utf-8"))
assert d["current"] == "元DGTF-V1.23.51.py", d["current"]
d["current"] = "元DGTF-V1.23.52.py"
p.write_bytes(json.dumps(d, ensure_ascii=False, indent=1)
              .replace("\n", "\r\n").encode("utf-8"))
print("  [OK] _v122_ast_registry.json current → 元DGTF-V1.23.52.py"
      "（无新符号 ⇒ 仍 %d）" % d["n_symbols_current"])

# ── 判据：两版 load_config 逐字相同 ─────────────────────────────────
import importlib.util
import sys


def load(py):
    spec = importlib.util.spec_from_file_location("v_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


a = load(HERE / "元DGTF-V1.23.51.py")
b = load(HERE / "元DGTF-V1.23.52.py")
ca = json.dumps(a.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True,
                ensure_ascii=False)
cb = json.dumps(b.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True,
                ensure_ascii=False)
assert ca == cb, "load_config 结果不同（本版不应有任何配置差异）"
print("  [OK] load_config 两版逐字相同（差异 0 项 / %d 个键）"
      % len(a.load_config(str(HERE / "dgtf_config.yaml"))))
