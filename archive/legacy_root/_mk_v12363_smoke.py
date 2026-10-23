# -*- coding: utf-8 -*-
"""v1.23.63 接线：smoke 新判据 + 变异体 M114/M115 + SRC 指向。"""
import ast
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
        print("  [OK] %-18s %s" % (name, what))
    if name.endswith(".py"):
        ast.parse(s)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
    p.write_bytes(out)
    print("       %d → %d 行" % (n0, s.count("\n")))


NEW_CHECK = '''def check_v12363_bad_json_visible():
    """[v1.23.63] `json_mode` 解析失败要留痕；`max_retries=0` 不许等于"一次都不试"。

    ★ 为什么（故障注入 v2，打底层 `client.chat.completions.create`）：

      | 故障 | 改前表现 |
      |---|---|
      | 抛异常 / 空内容 | 重试→抛→调用点记 errors（**留痕**） |
      | **非 JSON 文本 / "null"** | 内容非空、解析失败 ⇒ 当空处理，**零留痕** ✗ |
      | 类型不对 | 调用点报错（留痕） |

      「答了但答不成结构」这一类**静默丢失**：产物看起来只是"内容少"，
      读的人分不清"模型不配合"与"题本身没什么可写" ⇒ 违反红线「失败留痕」。

    ★ 顺带修一条脚枪：`LLM.call` 的重试循环是 `range(1, max_retries+1)`
      ⇒ `max_retries=0` 是**空循环**，所有调用必失败且报错是 `last_err=None`。
      改成至少尝试 1 次（默认 3 次行为不变）。

    ★ 这一支直接驱动 `LLM.call`：修行层 1 圈**根本不走 json_mode 环节**
      （实测注入散文后计数仍 0）—— 又是"触发条件在测试路径上到不了"的老坑。
    """
    import ast as _ast
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    for _tk in ("self.bad_json += 1", '"llm_bad_json": int(getattr(self.llm',
                "_tries = max(1, int(self.max_retries or 0))"):
        if _tk not in src:
            bad.append("[B1] 源码缺：%s" % _tk)

    class _R:
        def __init__(self, c):
            self.choices = [type("C", (), {
                "message": type("M", (), {"content": c})(),
                "finish_reason": "stop"})()]
            self.usage = type("U", (), {"total_tokens": 11})()

    def _llm(text, retries=3):
        c = build_cfg(False)
        c.setdefault("api", {})["max_retries"] = retries
        _l = mod.LLM(c)
        _l.client.chat.completions.create = lambda **kw: _R(text)
        _l.max_retries = retries
        _l.backoff = 1.0
        return _l

    try:
        _l = _llm("答案大概是这样……一段散文。")
        _out = _l.call("sys", "usr", json_mode=True)
        if _l.bad_json != 1:
            bad.append("[B2] json_mode+散文 未计数：%r" % (_l.bad_json,))
        if not _out.startswith("答案大概是这样"):
            bad.append("[B2] 返回值被改了（控制流不该动）：%r" % (_out[:20],))
        _l2 = _llm("null")
        _l2.call("sys", "usr", json_mode=True)
        if _l2.bad_json != 1:
            bad.append("[B2] json_mode+null 未计数：%r" % (_l2.bad_json,))
        _l3 = _llm("一段散文，本来就不是 JSON 请求。")
        _l3.call("sys", "usr", json_mode=False)
        if _l3.bad_json != 0:
            bad.append("[B3] json_mode=False 被误记：%r" % (_l3.bad_json,))
        _l4 = _llm('{"ok": 1}')
        _l4.call("sys", "usr", json_mode=True)
        if _l4.bad_json != 0:
            bad.append("[B3] 合法 JSON 被误记：%r" % (_l4.bad_json,))
        # 脚枪：max_retries=0 必须仍能调通（不是 0 次尝试）
        _l5 = _llm("好", retries=0)
        try:
            _l5.call("sys", "usr")
        except RuntimeError as _e:
            bad.append("[B4] max_retries=0 仍抛错（等于不尝试）：%r" % (_e,))
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[B2] 异常：%r" % (_ex,))
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.63 故障留痕（%d 项）" % len(bad))
        return False
    print("✓ v1.23.63 故障留痕：非JSON/null 计数 · 不误记 · max_retries=0 仍能调通")
    return True


'''

patch("smoke_test.py", [
    ("SRC 指 v1.23.63",
     'SRC = HERE / "元DGTF-V1.23.62.py"',
     'SRC = HERE / "元DGTF-V1.23.63.py"'),
    ("插新判据",
     "def check_v12362_contra_live():",
     NEW_CHECK + "def check_v12362_contra_live():"),
    ("main 接线",
     "    if not check_v12362_judges_wired():\n        return 1\n",
     "    if not check_v12362_judges_wired():\n        return 1\n"
     "    if not check_v12363_bad_json_visible():\n        return 1\n"),
])

M114 = ('    ("M114 非结构化输出不留痕（答了但答不成结构被静默吞掉）",\n'
        '     \'                                self.bad_json += 1\',\n'
        '     \'                                pass  # MUT\'),\n')
M115 = ('    ("M115 max_retries=0 变成一次都不尝试",\n'
        '     \'        _tries = max(1, int(self.max_retries or 0))\',\n'
        '     \'        _tries = int(self.max_retries or 0)  # MUT\'),\n')

patch("_mut_v12332.py", [
    ("SRC 指 v1.23.63",
     'SRC = HERE / "元DGTF-V1.23.62.py"',
     'SRC = HERE / "元DGTF-V1.23.63.py"'),
    ("末尾插 M114/M115",
     "     '                    pass  # MUT'),\n]",
     "     '                    pass  # MUT'),\n" + M114 + M115 + "]"),
    ("链上新判据",
     '             "st.check_v12362_contra_live() and "',
     '             "st.check_v12362_contra_live() and "\n'
     '             "st.check_v12363_bad_json_visible() and "'),
])
print("\n接线完成。")
