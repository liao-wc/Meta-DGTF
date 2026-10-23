# -*- coding: utf-8 -*-
"""v1.23.36 变异体：M65~M68（心跳 + EML 对账）+ 接判据进清单。"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "_mut_v12332.py"

OLD_TAIL = '''    #   ★ M56 打在**新规范接线**上（判据 ①b 数使用处 ⇒ 少一处必判红）。'''

NEW_TAIL = '''    #   ★ M65 打在**心跳的触发条件**上（判据 ③ 查「读数正常不该放宽」⇒
    #     去掉 verdict 判断 ⇒ 正常也放宽 ⇒ 必判红）。
    ("M65 心跳不看读数就放宽（默认零行为差被破坏）",
     "        if str(_q.get(\\"候选\\") or \\"\\") == \\"collapsed\\":",
     "        if True:"),
    #   ★ M66 打在**控制面的必留痕**上（心跳不带 why ⇒ 控制面应拒 ⇒
    #     放宽不生效 ⇒ 判据 ① 判红）。
    ("M66 心跳写入不带 why（控制面应当拒 ⇒ 放宽不生效）",
     "                    why=\\"心跳：本层候选产出率 collapsed（复述多）⇒ \\"\\n"
     "                        \\"放宽该环节联网，让它能问外面\\",",
     "                    why=\\"\\","),
    #   ★ M67 打在**豁免表的完整性**上（判据两向对账 ⇒ 删一项必判红）。
    ("M67 EML 豁免表丢一项（carve_first 又变成学而不做）",
     "    \\"carve_first\\":\\n"
     "        \\"跨跑类：它要的是「**下一跑**这些层优先雕」，而本引擎没有跨跑调度\\"",
     "    \\"carve_first_DISABLED\\":\\n"
     "        \\"跨跑类：它要的是「**下一跑**这些层优先雕」，而本引擎没有跨跑调度\\""),
    #   ★ M68 打在**放宽能否落地**上（不同步进 Gate ⇒ 放宽只是内存里的一个数，
    #     检索照旧被拒 ⇒ 判据源码级判红）。
    ("M68 放宽不同步进 Gate（放宽永远不生效）",
     "                gate._relaxed = _relaxed",
     "                gate._relaxed = set()"),

    #   ★ M56 打在**新规范接线**上（判据 ①b 数使用处 ⇒ 少一处必判红）。'''

OLD_RUN = '''             "st.check_v12336_readings()) else 1)\\n")'''
NEW_RUN = '''             "st.check_v12336_readings() and "
             "st.check_v12336_tick() and "
             "st.check_v12336_eml()) else 1)\\n")'''


def main():
    raw = P.read_bytes()
    s = raw.decode("utf-8")
    # ★ 幂等：第一次跑时 MUTS 尾部那段已替换成功，重跑会「命中 0」⇒ 先查
    if "M65 心跳不看读数就放宽" in s:
        print("M65~M68 已存在（跳过 MUTS 部分）")
    else:
        assert s.count(OLD_TAIL) == 1, "MUTS 尾部锚点命中 %d 次" % s.count(OLD_TAIL)
        s = s.replace(OLD_TAIL, NEW_TAIL, 1)
    if "st.check_v12336_tick()" in s:
        print("run_check 清单已更新（跳过）")
    else:
        assert s.count(OLD_RUN) == 1, "run_check 锚点命中 %d 次" % s.count(OLD_RUN)
        s = s.replace(OLD_RUN, NEW_RUN, 1)
    P.write_bytes(s.encode("utf-8"))
    print("OK M65~M68 + 判据清单均已就位")


main()
