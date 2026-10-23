#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.6：把变异体 M3 的锚点从「注释 + 代码」改成**只锚代码行**。

原锚点含两行注释（`# [v1.23.0 W2] 外部检索摘要…`）—— 注释已被「代码正文不留
版次批注」清掉 ⇒ `src.count(old) == 0`，断言炸（`变异体 M3 摘要注入 锚点 0 次`）。
变异体的**意图**（把摘要注入那段变成空操作）一字未改，只是锚点不再依赖注释。

幂等：NEW 已在文件里就跳过。CRLF 往返。
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE / "smoke_test.py"
BAK = HERE / "_bak_smoke_test.pre_v1236_m3"

OLD = ("            (\"M3 摘要注入\",\n"
       "             '                # [v1.23.0 W2] 外部检索摘要（**参照**）。未开联网时\\n'\n"
       "             '                #   它是空串 ⇒ prompt 逐字不变（加性）。\\n'\n"
       "             '                + (getattr(self, \"_web_digest\", \"\") or \"\"))\\n',\n"
       "             '                )\\n'),\n")
NEW = ("            # [v1.23.6] 锚点从「注释 + 代码」改成**只锚代码行**：原锚点里的两行\n"
       "            #   注释已被「代码正文不留版次批注」清掉 ⇒ 锚点 0 次。变异体意图\n"
       "            #   （把摘要注入那段变成空操作）一字未改。\n"
       "            (\"M3 摘要注入\",\n"
       "             '                + (getattr(self, \"_web_digest\", \"\") or \"\"))\\n',\n"
       "             '                )\\n'),\n")


def main():
    raw = SK.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
    t = raw.decode("utf-8").replace("\r\n", "\n")
    if NEW in t:
        print("[skip] 已改过")
        return 0
    n = t.count(OLD)
    assert n == 1, "锚点命中 %d 次" % n
    t = t.replace(OLD, NEW, 1)
    if not BAK.exists():
        shutil.copy2(SK, BAK)
        print("回滚点：%s" % BAK.name)
    out = t.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
    SK.write_bytes(out)
    print("已改 M3 锚点")
    # 顺带量一下代码碎片在 v1.23.6 里出现几次（与 _exp=2 对齐）
    src = (HERE / "元DGTF-V1.23.6.py").read_bytes().decode("utf-8").replace("\r\n", "\n")
    frag = '                + (getattr(self, "_web_digest", "") or ""))\n'
    print("代码锚点在 v1.23.6 里出现 %d 次（_exp 应为 2）" % src.count(frag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
