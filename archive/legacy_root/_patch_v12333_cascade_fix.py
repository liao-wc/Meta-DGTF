# -*- coding: utf-8 -*-
"""补丁 D2：`stop_priority` 先剥**括号内转述**再匹配关键词。

★ 真跑逮到（`_fullrun_GOALRUN.log` L3122 附近）：
  走满型停因的**实际文案**是

      体力耗尽（4 圈走满；1 次停止判据被「未深入方向」推迟
      （悬置决定稳定，自然安住），是被截断不是自然停止）

  它把**被推迟的判据名原样嵌进括号**，而那两个名字（「悬置决定稳定」
  「自然安住」）正好是 `_STOP_CASCADE` **档 0** 的键 ⇒ 全文子串匹配
  把「走满被截断」误判成「自然停（档 0）」—— 语义**刚好相反**
  （截断 = 没自然停住）。

  这不是判据夹具脱节那么简单：**真产物里主因就会报错**
  （`stop_cascade` 的 `primary` 会选中 `体力耗尽…` 整串，但它此刻
   命中档 0 ⇒ 报出来的是「最优先停因」= 一个被转述的名字）。

修法（最小、且不改变「未匹配落档 3」的兜底）：
  匹配前把**全角/半角括号及其中内容**剥掉再找关键词 —— 括号里的是
  **转述**（「被谁推迟」），不是**停因本身**。
  ★ 剥掉后若为空（整条都在括号里），回退到原文匹配（不静默变档 3）。
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

ANCHOR = '''def stop_priority(reason: str) -> int:
    """把一条停因文案映射到优先级（未匹配 ⇒ 落到最低档 3，不静默丢弃）。"""
    _r = str(reason or "")
    for _p, _keys in _STOP_CASCADE:
        if any(k in _r for k in _keys):
            return int(_p)
    return 3'''

NEW = '''def stop_priority(reason: str) -> int:
    """把一条停因文案映射到优先级（未匹配 ⇒ 落到最低档 3，不静默丢弃）。

    ★ 匹配**主句**，不匹配括号里的**转述**：走满型停因的文案形如
      `体力耗尽（N 圈走满；K 次判据被「未深入方向」推迟（悬置决定稳定，
      自然安住），是被截断不是自然停止）` —— 括号里嵌的是**被推迟的
      判据名**，若全文子串匹配，会把「截断」误判成档 0「自然停」，
      语义刚好相反。⇒ 先剥括号再匹配；剥空则回退原文（不静默变档）。
    """
    _r = str(reason or "")
    _head = re.sub(r"[（(][^（()）]*[)）]", "", _r).strip()
    if not _head:
        _head = _r
    for _p, _keys in _STOP_CASCADE:
        if any(k in _head for k in _keys):
            return int(_p)
    return 3'''


def main():
    b = SRC.read_bytes()
    txt = b.decode("utf-8")
    if txt.count("\r\n") != txt.count("\n") or "\r\r\n" in txt:
        print("X 非纯 CRLF"); sys.exit(1)
    s = txt.replace("\r\n", "\n")
    if "import re" not in s.split("\n\n")[0] and "\nimport re\n" not in s[:4000]:
        print("X 头部未见 import re（需人工确认）")
    n = s.count(ANCHOR)
    if n != 1:
        print("X 锚点命中 %d 次" % n); sys.exit(1)
    s = s.replace(ANCHOR, NEW, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    if out.decode("utf-8").count("\r\r\n"):
        print("X r-r-n"); sys.exit(1)
    SRC.write_bytes(out)
    print("OK 补丁 D2 已打：stop_priority 剥括号后再匹配")


if __name__ == "__main__":
    main()
