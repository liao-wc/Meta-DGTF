# -*- coding: utf-8 -*-
"""v1.23.61：配置头 + 升级段 + 登记表 + CHANGELOG 段。"""
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


UPGRADE = '''# 【v1.23.60 → v1.23.61】`run()` 的空题守卫（拒绝运行，不凭空产出、不花钱）
#   ① 问题（健壮性探针）：退化输入 9 例没一个打挂引擎，但 **`run("")` 照样跑了、
#      产出 2 个候选** —— 空题没有可研究的东西，跑下去只会产出**凭空编造的候选**
#      （违背「没读数就不假装 / 未对齐如实说」），而且白花一次调用。
#      app 那边有挡（`server.py` 返回 400），但**引擎是库**，任何脚本都能直接传空串。
#   ② 修法：`run()` 在**任何 LLM 调用之前**检查 `str(question).strip()`；为空 ⇒
#      立刻返回结构化拒绝 `refused={reason:"empty_question", why:…}` +
#      `views={}` + `llm_calls=0`，并 `vp` 一行说明。
#      ★ 不抛异常（会打断调用方）；也不用 `paused`（那是"没跑完"，这是"不该跑"）。
#   ★ 无新配置键；题面非空 ⇒ 行为逐字不变。

'''

patch("dgtf_config.yaml", [
    ("头部版本", "# 元 DGTF · v1.23.60 配置文件",
     "# 元 DGTF · v1.23.61 配置文件"),
    ("插升级段", "# 【v1.23.59 → v1.23.60】", UPGRADE + "# 【v1.23.59 → v1.23.60】"),
])

p = HERE / "_v122_ast_registry.json"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
d = json.loads(raw.decode("utf-8"))
assert d["current"] == "元DGTF-V1.23.60.py", d["current"]
d["current"] = "元DGTF-V1.23.61.py"
p.write_bytes(json.dumps(d, ensure_ascii=False, indent=1)
              .replace("\n", "\r\n").encode("utf-8"))
print("  [OK] 登记表 current → 元DGTF-V1.23.61.py（%d 条 / %d 符号）"
      % (len(d["registry"]), d["n_symbols_current"]))

SEC = """v1.23.61 相对 v1.23.60

【主题】`run()` 空题守卫 —— 拒绝运行，不凭空产出、不花钱。

【问题（健壮性探针扫出来的）】退化输入 9 例（空 / 纯空白 / 单字 / 纯标点 /
只有问号 / 引号反斜杠 / 换行 / emoji / 5500 字长题）**没有一个把引擎打挂** ——
这部分是好的。但 **`run("")` 照样跑了，产出 2 个候选**：

· 空题没有任何可研究的东西，跑下去只会产出**凭空编造的候选**
  （违背「没有读数就不假装 / 未对齐如实说」这条红线）；
· 而且**白花一次调用**。

app 那边有挡（`server.py`：`if not question: 400`），但**引擎是库** ——
任何脚本（包括我自己的探针）都能直接传空串。

【修法】`run()` 在**任何 LLM 调用之前**检查 `str(question).strip()`：
为空 ⇒ 立刻返回结构化拒绝：

    refused = {"reason": "empty_question", "why": "…"}
    views = {}   llm_calls = 0   llm_tokens = 0

★ 不抛异常（会打断调用方）；也不用 `paused`（那是"没跑完"，这是"不该跑"）。

---

★ v1.23.61 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.61.py`（26819 行 / 纯 CRLF）+ 冒烟新判据
`check_v12361_empty_guard` + 变异体 M112 + 本段。

**改了什么**：`run()` 加空题守卫（13 行）；版本号两处。2 个改动块 / 增 13 行；
无新符号（325 / 589）；无新配置键。

**验收**：冒烟 260 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 110/110（M112 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
判据四臂：空题被拒 + **零 LLM 调用**（拒绝必须免费）+ 纯空白同样拒 +
单字题不被误拒（守卫不能变成"见谁都拒"）。

**一处判据自查**：第一版断言写成 `int(r.get("llm_calls") or -1) == 0`，
而值就是 `0` ⇒ `0 or -1` 得 `-1` ⇒ 假红。改成直接比较（`== 0`）。
**`or` 在值为 0 时会被吞 —— 这条坑我自己记过，还是踩了。**

**未做**：`shape_limit` 取值扫描（≈¥12）；圈内恢复（需先做确定性改造）。

"""
patch("CHANGELOG.md", [
    ("插本版段", "v1.23.60 相对 v1.23.59\n", SEC + "v1.23.60 相对 v1.23.59\n"),
])


def load(py):
    spec = importlib.util.spec_from_file_location("v_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


a = load(HERE / "元DGTF-V1.23.60.py")
b = load(HERE / "元DGTF-V1.23.61.py")
_ca = json.dumps(a.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True)
_cb = json.dumps(b.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True)
assert _ca == _cb, "load_config 结果不同（本版不应有任何配置差异）"
print("  [OK] load_config 两版逐字相同（差异 0 项）")
