# -*- coding: utf-8 -*-
"""v1.23.36 变异体：M60~M63（给联网全接 / 读数显示 / 控制面 判据背书）。"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "_mut_v12332.py"

OLD_TAIL = '''    #   ★ M56 打在**新规范接线**上（判据 ①b 数使用处 ⇒ 少一处必判红）。'''

NEW_TAIL = '''    #   ★ M60 打在**读数的输出通道**上（判据捕获 logging ⇒ 走 vp 就看不到，
    #     而 vp 受 verbose 控制 ⇒ 会「静默吞掉读数」——这正是第一版的真错）。
    ("M60 读数行改走 vp（verbose=False 时被静默吞掉）",
     "            logger.info(_readings_line(entry, view))",
     "            self.vp(_readings_line(entry, view))"),
    #   ★ M61 打在**产物出口**上（判据查 `packed["readings_table"]` ⇒ 不写必判红）。
    ("M61 读数总表不进产物（产物侧拿不到结构化读数）",
     "                packed[\\"readings_table\\"] = _readings_table(_rt_views, as_md=True)",
     "                packed[\\"readings_table\\"] = \\"\\""),
    #   ★ M62 打在**总闸**上（判据查「总闸关不增强」⇒ 去掉判断必判红）。
    ("M62 `_web_augment` 不判总闸（关了也注入 ⇒ 零行为差被破坏）",
     "        _searcher = _llm_ctx_get(\\"web_searcher\\")\\n"
     "        if not callable(_searcher):\\n"
     "            return None                       # 没接线（如独立调用 LLM）⇒ 不增强",
     "        _searcher = _llm_ctx_get(\\"web_searcher\\")\\n"
     "        if _searcher is None:\\n"
     "            _searcher = lambda *a, **kw: [{\\"claim\\": \\"M62\\"}]"),
    #   ★ M63 打在**控制面的必留痕**上（「缺 why 就拒」是可追溯性的本体 ⇒
    #     去掉它，任何写入都不需要理由 ⇒ 必判红）。
    ("M63 控制面不再要求 why（可追溯性被削弱）",
     "        if not str(why or \\"\\").strip():",
     "        if False:"),
    #   ★ M64 打在**四层都可注入**上（用户口径 ⇒ 若有人把修行层豁免加回来必判红）。
    ("M64 把修行层硬豁免加回来（破「所有层都注入」）",
     "        _st = str(stage or _infer_stage_from_stack() or \\"\\")\\n"
     "        if not _st:\\n"
     "            return None",
     "        if str(_llm_ctx_get(\\"entry\\", \\"\\")) == \\"0\\":\\n"
     "            return None\\n"
     "        _st = str(stage or _infer_stage_from_stack() or \\"\\")\\n"
     "        if not _st:\\n"
     "            return None"),

    #   ★ M56 打在**新规范接线**上（判据 ①b 数使用处 ⇒ 少一处必判红）。'''


def main():
    raw = P.read_bytes()
    s = raw.decode("utf-8")
    assert s.count(OLD_TAIL) == 1, "锚点命中 %d 次" % s.count(OLD_TAIL)
    s = s.replace(OLD_TAIL, NEW_TAIL, 1)
    P.write_bytes(s.encode("utf-8"))
    print("OK M60~M64 已加")


main()
