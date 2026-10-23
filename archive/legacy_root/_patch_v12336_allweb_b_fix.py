# -*- coding: utf-8 -*-
"""修「联网全接 B」的**插错位置**：30 键插进了 `api.thinking.stages`（错），
应插进 `web_search.stages`（对）。

## 怎么错的
补丁用 `s.find('"web_search"')` 找位置 —— 全文件里 `"web_search"` 的**第一处**
出现在别处（不是 `DEFAULT_CONFIG` 里的那一段）⇒ 插到了
`api.thinking.stages` 里。

## 为什么必须修（不是"位置丑"而已）
`LLM.call` 的思考档优先级是：
    显式 thinking > **`thinking_stages[stage]`** > `thinking_default`
⇒ 插进去的 30 个 `False` 会让这些环节**永远返回 False**（而不是 None）
⇒ **全开（`api.thinking.default=enabled`）时它们会被强制关思考** —— 行为退化。
★ 这正是「插错位置」比「没插」更危险的地方：判据不查这个位置就发现不了。

## 修法
① 撤销错误插入（把它从 `api.thinking.stages` 里删干净）；
② 用**更精确的定位**插到 `web_search` 段的 `stages`：
   先找 `DEFAULT_CONFIG` 里 `"web_search": {` 的**起始**，再在其后找 `"stages": {`。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

BAD = '''            "stages": {
            # ★ [联网全接] 30 个环节各自的开关（默认 false ⇒ 零行为差）。
            #   名字与 `_infer_stage_from_stack` 同口径（函数名去下划线）。
            #   现有 7 个「语义名」的 stage（research_* 等）走**显式接线**，
            #   与这张表并存、互不干扰。
            **{_k: False for _k in _WEB_ALL_STAGES},
                "auto_plan": "enabled",'''

GOOD = '''            "stages": {
                "auto_plan": "enabled",'''

INSERT = '''
            # ★ [联网全接] 30 个环节各自的开关（默认 false ⇒ 零行为差）。
            #   名字与 `_infer_stage_from_stack` 同口径（函数名去下划线）。
            #   现有 7 个「语义名」的 stage（research_* 等）走**显式接线**，
            #   与这张表并存、互不干扰。
            **{_k: False for _k in _WEB_ALL_STAGES},'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")

    # ① 撤销
    n = s.count(BAD)
    assert n == 1, "错误插入块命中 %d 次（应为 1）" % n
    s = s.replace(BAD, GOOD, 1)
    assert "_WEB_ALL_STAGES}" not in s, "撤销后仍有残留"

    # ② 精确插到 web_search.stages
    _i_ws = s.find('"web_search": {', s.find("DEFAULT_CONFIG = "))
    assert _i_ws > 0, "找不到 DEFAULT_CONFIG 里的 web_search 段"
    _i_st = s.find('"stages": {', _i_ws)
    assert _i_st > 0, "web_search 段里没有 stages"
    # ★ 校验：这个 stages 必须在 web_search 段**内**（下一个 `\n    "` 之前）
    _next_sec = s.find('\n    "', _i_ws + 5)
    assert _next_sec < 0 or _i_st < _next_sec, \
        "找到的 stages 不在 web_search 段内（定位不可靠）⇒ 停手"
    _ins = _i_st + len('"stages": {')
    s = s[: _ins] + INSERT + s[_ins:]

    assert s.count("**{_k: False for _k in _WEB_ALL_STAGES}") == 1, "插入数不对"
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 已挪到 web_search.stages；行数 %d" % out.count(b"\n"))


main()
