# -*- coding: utf-8 -*-
"""v1.23.51 配置同步 + AST 登记表指向（无新配置键，只有头部版本与升级段）。

三件事：
  1) `dgtf_config.yaml` 头部版本 → v1.23.51
  2) 升级段【v1.23.50 → v1.23.51】插在既有段之前（本文件「最新在最前」）
  3) `_v122_ast_registry.json` 的 `current` → 新文件名（无新符号 ⇒ 计数不变）

外加一条判据：两版 `load_config` 对**同一份 yaml** 的解析结果必须逐字相同
（本版没有新键 ⇒ 差异 0 项；这证明「同步」没顺手改坏任何值）。
"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def patch(name, edits):
    p = HERE / name
    raw = p.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n"), "%s 不是纯 CRLF" % name
    assert raw.count(b"\r\r\n") == 0, "%s 有 CRCRLF" % name
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


UPGRADE = '''# 【v1.23.50 → v1.23.51】`_eml_finish` 幂等：**一个跑次只学一条 episode**
#   ① 根因（真跑逮到）：A/B 脚本把 `_eml_finish` 调了两次（`run()` 内部已调过一次）
#      ⇒ 每个跑次写出两条**完全相同**的 episode、`used_outcomes` 与 `weight` 被罚两遍
#      （实测 7 个条目 weight 多扣 0.05/次，事后要写清账脚本才能收拾）。
#      为什么 v1.23.48/49 没暴露：「run_id 必须在 `_eml_finish` 之前盖章」是上一版才修的
#      —— 在那之前内部那次拿到空 id，被「匿名跑次一律不写库」的闸挡掉。
#   ② 修法：拿到跨进程锁之后、写 episode 之前加守卫 —— 已有**同 run_id 且除 `t`
#      外逐字相同**的 episode ⇒ 直接返回（`dup_skipped`），不写库、不再罚 weight。
#   ③ 为什么判据不是「只看 run_id」：墙钟预算 `paused` 的跑次也会写一条半程样本，
#      续跑完成时它的读数不同 ⇒ **必须能写**，否则完整样本永远进不了库。
#   ★ 无新配置键；单次调用的行为**逐字不变**（不重复调用 ⇒ 守卫从不触发）。
#     想回到旧行为不需要改配置：多调一次 `_eml_finish` 即可（那正是要防的事）。

'''

patch("dgtf_config.yaml", [
    ("头部版本", "# 元 DGTF · v1.23.50 配置文件",
     "# 元 DGTF · v1.23.51 配置文件"),
    ("插升级段", "# 【v1.23.49 → v1.23.50】", UPGRADE + "# 【v1.23.49 → v1.23.50】"),
])

# ── AST 登记表 ──────────────────────────────────────────────────────
p = HERE / "_v122_ast_registry.json"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
d = json.loads(raw.decode("utf-8"))
assert d["current"] == "元DGTF-V1.23.50.py", d["current"]
d["current"] = "元DGTF-V1.23.51.py"
txt = json.dumps(d, ensure_ascii=False, indent=1)
out = txt.replace("\n", "\r\n").encode("utf-8")
p.write_bytes(out)
print("  [OK] _v122_ast_registry.json current → 元DGTF-V1.23.51.py"
      "（无新符号 ⇒ n_symbols_current 仍 %d）" % d["n_symbols_current"])

# ── 判据：两版 load_config 对同一份 yaml 解析结果逐字相同 ─────────────
import importlib.util
import sys


def load(py):
    spec = importlib.util.spec_from_file_location("v_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


a, b = load(HERE / "元DGTF-V1.23.50.py"), load(HERE / "元DGTF-V1.23.51.py")
for y in ("dgtf_config.yaml",):
    ca = json.dumps(a.load_config(str(HERE / y)), sort_keys=True, ensure_ascii=False)
    cb = json.dumps(b.load_config(str(HERE / y)), sort_keys=True, ensure_ascii=False)
    assert ca == cb, "load_config 结果不同（本版不应有任何配置差异）"
    print("  [OK] load_config(%s) 两版逐字相同（差异 0 项）" % y)
print("  [OK] 无新配置键：%d 个键两版一致"
      % len(a.load_config(str(HERE / "dgtf_config.yaml"))))
