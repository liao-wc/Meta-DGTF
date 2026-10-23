# -*- coding: utf-8 -*-
"""v1.23.34 变异体：给 `check_v12334_prompt()` 背书（M56~M59）。

★ 关键：**必须把新判据接进 `run_check`** —— 否则变异体根本跑不到它，
  「全绿」只说明没跑（本项目红线：没变异体的全绿 = 假绿）。
★ 每条锚点都必须**唯一**（`_mut_v12332.py` 用 `replace(old, new, 1)` 且
  断言命中数 == 1）—— 六处视角共用的 `+ VOICE` 那种锚点**不能**直接当变异靶。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "_mut_v12332.py"

# ── A：把新判据接进 run_check 的清单 ──
OLD_RUN = '''    code += ("sys.exit(0 if (st.check_v12332_discipline() and "
             "st.check_v12333_autotune()) else 1)\\n")'''
NEW_RUN = '''    code += ("sys.exit(0 if (st.check_v12332_discipline() and "
             "st.check_v12333_autotune() and "
             "st.check_v12334_prompt()) else 1)\\n")'''

# ── B：追加 M56~M59 ──
OLD_TAIL = '''     "        _qr = getattr(view, \\"quant_readings\\", None) or {}\\n"
     "        if False:"),
]'''
NEW_TAIL = '''     "        _qr = getattr(view, \\"quant_readings\\", None) or {}\\n"
     "        if False:"),
    #   ★ M56 打在**新规范接线**上（判据 ①b 数使用处 ⇒ 少一处必判红）。
    #     ★ 锚点必须**唯一**：六处视角共用的 `+ VOICE` 不能当靶，
    #       故用 `_yin_prompt` 的独特上下文（「从锚点里看出去」那一句）。
    ("M56 阴视角漏接 VOICE（新规范只接一半）",
     "            \\"从锚点里看出去，找出还没显形的部分。\\\\n\\"\\n"
     "            + EXPLORE_FORMAT\\n"
     "            + VOICE\\n",
     "            \\"从锚点里看出去，找出还没显形的部分。\\\\n\\"\\n"
     "            + EXPLORE_FORMAT\\n"),
    #   ★ M57 打在**第四面墙的禁止清单**上（判据 ④ 查三个禁止词 ⇒ 删必判红）。
    ("M57 EVIDENCE 丢掉管道级禁止清单（第四面墙失效）",
     "- ★ 不要说\\"资料里说\\"\\"检索显示\\"\\"上下文提到\\"\\"根据提供的信息\\"这类话 ——\\n",
     "- 想怎么说就怎么说。\\n"),
    #   ★ M58 打在**输出格式契约**上（判据 ② 是「不许变」⇒ 改了必判红）。
    ("M58 EXPLORE_FORMAT 改掉格式契约（下游解析会坏）",
     "    \\"每行格式：- [kind] 描述（20-80字；说清一条算一条，\\"\\n",
     "    \\"每行随便写点，无所谓。\\"\\n"),
    #   ★ M59 打在**view 输出结构**上（判据在 ㉟ 段跑真实入口 ⇒ 去了必判红）。
    ("M59 _render 去掉「本层速览」（view 输出结构没生效）",
     "            _render_layer_glance(view),\\n",
     ""),
]'''


def main():
    raw = P.read_bytes()
    s = raw.decode("utf-8")
    for old, new, tag in ((OLD_RUN, NEW_RUN, "run_check 清单"),
                          (OLD_TAIL, NEW_TAIL, "MUTS 尾部")):
        assert s.count(old) == 1, "%s 锚点命中 %d 次" % (tag, s.count(old))
        s = s.replace(old, new, 1)
    P.write_bytes(s.encode("utf-8"))
    print("OK 变异体已加（M56~M59）+ run_check 已接 check_v12334_prompt")


main()
