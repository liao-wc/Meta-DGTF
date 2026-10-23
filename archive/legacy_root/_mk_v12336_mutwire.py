# -*- coding: utf-8 -*-
"""把本轮两条新判据接进变异体的 `run_check` 清单。

★ 红线：**没接进清单的判据，变异体根本跑不到** ⇒ 「全绿」只说明没跑
  （本项目已栽过：`check_v12334_prompt` 第一版就漏了接）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "_mut_v12332.py"

OLD = '''    code += ("sys.exit(0 if (st.check_v12332_discipline() and "
             "st.check_v12333_autotune() and "
             "st.check_v12334_prompt()) else 1)\\n")'''
NEW = '''    code += ("sys.exit(0 if (st.check_v12332_discipline() and "
             "st.check_v12333_autotune() and "
             "st.check_v12334_prompt() and "
             "st.check_v12336_allweb() and "
             "st.check_v12336_readings()) else 1)\\n")'''


def main():
    s = P.read_text(encoding="utf-8")
    assert s.count(OLD) == 1, "锚点命中 %d 次" % s.count(OLD)
    s = s.replace(OLD, NEW, 1)
    for _t in ("check_v12336_allweb", "check_v12336_readings"):
        assert _t in s, "缺 %s" % _t
    P.write_text(s, encoding="utf-8")
    print("OK 判据清单已更新")


main()
