# -*- coding: utf-8 -*-
"""v1.23.62 → v1.23.63：`json_mode` 下**解析失败**要留痕（非 JSON / null）。

问题（故障注入 v2，打的是底层 `client.chat.completions.create`）：
  | 故障 | 表现 |
  |---|---|
  | 抛异常 | 重试→抛→调用点记 errors（留痕 ✓） |
  | 空内容 | 同上（留痕 ✓） |
  | 非 JSON 文本 | 内容非空、但解析失败 ⇒ 调用点当空处理，零留痕 ✗ |
  | null | 同上 ✗ |
  | 类型不对 | 调用点报错（留痕 ✓） |

  即：模型「答了但答不成结构」这一类故障**静默丢失**。产物看起来只是「内容少」，
  读的人分不清「模型不配合」与「题本身没什么可写」—— 违反红线「失败留痕」。

修法（**只加计数与日志，不改控制流**）：
  · `LLM` 增 `bad_json` 计数；
  · `call()` 在 `json_mode=True` 且解析不出时 +1 并 warning（带片段）；
  · 产物顶层增 `llm_bad_json`（与 `llm_calls` 同一处出口）；
  · 产物 md 在「本次记忆」之后加一行提示（>0 时才出现）。

★ 不改任何判定：解析失败仍走原兜底路径；只是这件事**现在会被记下来**。
★ 无新配置键。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.62.py"
DST = HERE / "元DGTF-V1.23.63.py"

raw = SRC.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")


def rep(old, new, what, expect=1):
    global s
    c = s.count(old)
    assert c == expect, "%s：命中 %d 次（要求 %d）" % (what, c, expect)
    s = s.replace(old, new)
    print("  [OK] %s" % what)


NEW_INIT = (
    "        self.total_calls = 0\n"
    "        # ★ [失败留痕] `json_mode` 下解析失败的次数。模型「答了但答不成结构」时，\n"
    "        #   调用点会当空处理走兜底 —— 但**不留痕**的话，产物看起来只是「内容少」，\n"
    "        #   读的人分不清「模型不配合」与「题本身没什么可写」。\n"
    "        self.bad_json = 0\n"
)
rep("        self.total_calls = 0\n", NEW_INIT, "LLM 增 bad_json 计数")

NEW_CALL = (
    "                    try:\n"
    "                        self._web_need_report(stage, content)\n"
    "                    except Exception:\n"
    "                        pass\n"
    "                    # ★ [失败留痕] 要求 JSON 却解析不出 ⇒ 记一次，别静默。\n"
    "                    #   不改控制流：调用点照旧走兜底，只是这件事现在**有记录**。\n"
    "                    if json_mode:\n"
    "                        try:\n"
    "                            _ok_json = self.parse_json(content) is not None\n"
    "                        except Exception:\n"
    "                            _ok_json = False\n"
    "                        if not _ok_json:\n"
    "                            with self._lock:\n"
    "                                self.bad_json += 1\n"
    "                            logger.warning(\n"
    "                                \"json_mode 但解析失败（累计 %d 次，stage=%s）：%r\",\n"
    "                                self.bad_json, stage, content[:80])\n"
    "                    return content"
)
rep(
    "                    try:\n"
    "                        self._web_need_report(stage, content)\n"
    "                    except Exception:\n"
    "                        pass\n"
    "                    return content",
    NEW_CALL, "call() 记 bad_json + warning")

rep(
    '            "llm_calls": self.llm.total_calls,\n'
    '            "llm_tokens": self.llm.total_tokens,',
    '            "llm_calls": self.llm.total_calls,\n'
    '            "llm_tokens": self.llm.total_tokens,\n'
    '            # ★ [失败留痕] `json_mode` 解析失败次数（0 = 全跑都拿到结构化输出）\n'
    '            "llm_bad_json": int(getattr(self.llm, "bad_json", 0) or 0),',
    "产物增 llm_bad_json")

NEW_MD = (
    '            _bj = int(result.get("llm_bad_json") or 0)\n'
    '            if _bj > 0:\n'
    '                f.write(f"  - ⚠️ **模型返回了非结构化内容** {_bj} 次"\n'
    '                        f"（要求 JSON 但解析失败）—— 这些环节走了兜底，"\n'
    '                        f"读数可能偏低。这是**留痕**，不是缺陷判定。\\n")\n'
    '            _go = _pbk.get("gated_out") or []'
)
rep('            _go = _pbk.get("gated_out") or []', NEW_MD, "产物 md 加提示行")

rep("元 DGTF · v1.23.62\n", "元 DGTF · v1.23.63\n", "docstring 标题")
rep('__version__ = "1.23.62"\n', '__version__ = "1.23.63"\n', "__version__")

ast.parse(s)
assert s.count("self.bad_json += 1") == 1
assert s.count('"llm_bad_json": int(getattr(self.llm, "bad_json", 0) or 0),') == 1
assert s.count("模型返回了非结构化内容") == 1
print("  [OK] 结构性自检：计数 · 日志 · 产物出口 · md 提示")

n1 = s.count("\n")
print("  [OK] 行数 %d → %d（+%d）" % (n0, n1, n1 - n0))

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
DST.write_bytes(out)
print("\n写出 %s（%d 字节 / %d 行 / 纯 CRLF）"
      % (DST.name, len(out), out.count(b"\r\n")))
