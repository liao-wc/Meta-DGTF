# -*- coding: utf-8 -*-
"""v1.23.63：配置头 + 升级段 + 登记表 + CHANGELOG 段。"""
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


UPGRADE = '''# 【v1.23.62 → v1.23.63】非结构化输出要留痕 + `max_retries=0` 脚枪
#   ① 问题（故障注入，打底层 `client.chat.completions.create`）：
#      抛异常 / 空内容 ⇒ 重试→抛→调用点记 errors（**留痕**）；
#      但 **非 JSON 文本 / "null"** ⇒ 内容非空、解析失败 ⇒ 当空处理、**零留痕**。
#      「答了但答不成结构」这一类静默丢失：产物看起来只是"内容少"，
#      读的人分不清"模型不配合"与"题本身没什么可写" ⇒ 违反红线「失败留痕」。
#   ② 修法：`LLM` 增 `bad_json` 计数；`call()` 在 `json_mode=True` 且解析不出时
#      +1 并 warning（带片段）；产物顶层增 `llm_bad_json`；md 在 >0 时加一行提示。
#      **不改控制流**：解析失败仍走原兜底，只是这件事现在有记录。
#   ③ 顺带脚枪：重试循环是 `range(1, max_retries+1)` ⇒ `max_retries=0` 是**空循环**
#      ⇒ 所有调用必失败且报错 `last_err=None`（看不出根因）。改成至少尝试 1 次；
#      默认 3 次**行为完全不变**。
#   ★ 无新配置键。

'''

patch("dgtf_config.yaml", [
    ("头部版本", "# 元 DGTF · v1.23.62 配置文件",
     "# 元 DGTF · v1.23.63 配置文件"),
    ("插升级段", "# 【v1.23.61 → v1.23.62】", UPGRADE + "# 【v1.23.61 → v1.23.62】"),
])

p = HERE / "_v122_ast_registry.json"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
d = json.loads(raw.decode("utf-8"))
assert d["current"] == "元DGTF-V1.23.62.py", d["current"]
d["current"] = "元DGTF-V1.23.63.py"
p.write_bytes(json.dumps(d, ensure_ascii=False, indent=1)
              .replace("\n", "\r\n").encode("utf-8"))
print("  [OK] 登记表 current → 元DGTF-V1.23.63.py（%d 条 / %d 符号）"
      % (len(d["registry"]), d["n_symbols_current"]))

SEC = """v1.23.63 相对 v1.23.62

【主题】非结构化输出要留痕；`max_retries=0` 不该等于"一次都不试"。

【问题（故障注入 v2，打的是底层 `client.chat.completions.create`）】

| 故障 | 改前表现 |
|---|---|
| 抛异常 / 空内容 | 重试 → 抛 → 调用点记 `errors`（**留痕** ✓） |
| **非 JSON 文本 / "null"** | 内容非空、解析失败 ⇒ **当空处理、零留痕** ✗ |
| 类型不对 | 调用点报错（留痕 ✓） |

「答了但答不成结构」这一类**静默丢失** —— 产物看起来只是"内容少"，
读的人分不清「模型不配合」与「题本身没什么可写」⇒ 违反红线「失败留痕」。

【修法 · 留痕】`LLM` 增 `bad_json` 计数；`call()` 在 `json_mode=True` 且解析不出时
+1 并 `logger.warning`（带内容片段）；产物顶层增 `llm_bad_json`；
产物 md 在 >0 时加一行「模型返回了非结构化内容 N 次」。
**不改控制流**：解析失败仍走原兜底路径，只是这件事现在**有记录**。

【修法 · 脚枪】重试循环原是 `range(1, self.max_retries + 1)` ⇒ `max_retries=0`
是**空循环** ⇒ 所有调用必然失败，且报错是 `LLM 连续 0 次失败: None`（看不出根因）。
改成 `_tries = max(1, int(self.max_retries or 0))`：
· 默认 3 ⇒ 3 次尝试，**与改前完全一样**；
· 0 ⇒ 1 次尝试（修好脚枪）。
同文件的 `WebSearchGate` 本来就写 `range(max_retries + 1)`，两处语义现在一致了。

---

★ v1.23.63 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.63.py`（26852 行 / 纯 CRLF）+ 冒烟新判据
`check_v12363_bad_json_visible` + 变异体 M114/M115 + 本段。

**改了什么**：`LLM` 增 `bad_json` 计数与 warning；产物增 `llm_bad_json` 与 md 提示；
重试循环至少 1 次。4 个改动块 / 增 24 行；无新符号（325 / 589）；无新配置键。

**验收**：冒烟 264 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 113/113（M114、M115 均判红）；app 自检 368/0；两版 `load_config` 逐字相同。
判据五臂：`json_mode+散文` 计数且**返回原文**（控制流不变）· `null` 同样计数 ·
`json_mode=False` **不误记** · 合法 JSON 不计数 · `max_retries=0` **仍能调通**。

**两次测试设计自查**：
1. 故障注入 v1 直接替换 `LLM.call` ⇒ 把它自己的重试包装一起换掉了，
   测到的只是"调用点对空串的反应"。改打底层 `create` 才测到生产路径。
2. 判据第一次在 smoke 里红：因为 smoke 已把 `LLM.call` 换成桩 ⇒ 必须调
   `LLM._real_call`。**同一个坑一天踩两次：整体替换外层包装 = 把被测对象换掉。**

**未做**：`shape_limit` 取值扫描（≈¥12）；圈内恢复（需先做确定性改造）。

"""
patch("CHANGELOG.md", [
    ("插本版段", "v1.23.62 相对 v1.23.61\n", SEC + "v1.23.62 相对 v1.23.61\n"),
])


def load(py):
    spec = importlib.util.spec_from_file_location("v_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


a = load(HERE / "元DGTF-V1.23.62.py")
b = load(HERE / "元DGTF-V1.23.63.py")
_ca = json.dumps(a.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True)
_cb = json.dumps(b.load_config(str(HERE / "dgtf_config.yaml")), sort_keys=True)
assert _ca == _cb, "load_config 结果不同（本版不应有任何配置差异）"
print("  [OK] load_config 两版逐字相同（差异 0 项）")
