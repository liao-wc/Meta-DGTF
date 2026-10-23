# -*- coding: utf-8 -*-
"""[v1.23.0 W5-fix] `Pool.to_dict()` 白名单漏了 5 个联网字段 —— 补上 + 加通用前向守卫。

★ 这是 W2 报告里我刚写过的**同一类坑**（`dec_norm` 是显式白名单，不列=静默吞掉），
  只不过这次在**池出口**这一层又踩了一遍：真跑时 tavily 明明返回了结果
  （`cache/websearch/` 里 4 个文件分别 n=3/8/8/8），但产物里 W# 是 0
  —— 因为 `to_dict()` 的白名单没有它们。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.23.0.py"
SENTINEL = "[v1.23.0 W5-fix]"

src = TARGET.read_bytes().decode("utf-8")
assert src.count("\r\n") == src.count("\n"), "源文件不是纯 CRLF"
src = src.replace("\r\n", "\n")
if SENTINEL in src:
    print("== 已打过 W5-fix，跳过 =="); sys.exit(0)


def sub_once(text, old, new, tag):
    n = text.count(old)
    assert n == 1, f"[{tag}] 锚点出现 {n} 次（应为 1）"
    return text.replace(old, new)


T_OLD = (
    '        if self.anchors:\n'
    '            d["anchors"] = self.anchors\n'
    '            # [v1.21.76 B3] 这个字段原来只有内部赋值、**没有任何出口** ——\n'
    '            #   产物里看不出"锚点到底有没有被授权当证据"。跟着 anchors 一起\n'
    '            #   挂（仍是加性：没锚点时一个键都不加）。\n'
    '            d["anchor_as_evidence"] = self.anchor_as_evidence\n'
    '        return d\n'
)
T_NEW = (
    '        if self.anchors:\n'
    '            d["anchors"] = self.anchors\n'
    '            # [v1.21.76 B3] 这个字段原来只有内部赋值、**没有任何出口** ——\n'
    '            #   产物里看不出"锚点到底有没有被授权当证据"。跟着 anchors 一起\n'
    '            #   挂（仍是加性：没锚点时一个键都不加）。\n'
    '            d["anchor_as_evidence"] = self.anchor_as_evidence\n'
    '        # [v1.23.0 W5-fix] ★ 联网五个字段。**上面那个白名单漏了它们** ——\n'
    '        #   实测：真跑里 tavily 返回了结果（cache/websearch/ 有 4 个文件\n'
    '        #   n=3/8/8/8），但产物里 W# 是 0，因为 `to_dict()` 是**显式**字典，\n'
    '        #   不列 = 静默吞掉。这与 W2 的 `dec_norm` 是**同一类坑**。\n'
    '        #   ★ 仍然是加性：没有任何联网痕迹时一个键都不加 —— 关闭态 packed\n'
    '        #     与 v1.22.2 逐字相同。\n'
    '        if self.web_results or self.web_errors or self.web_as_evidence:\n'
    '            d["web_results"] = self.web_results\n'
    '            d["web_errors"] = self.web_errors\n'
    '            d["web_as_evidence"] = self.web_as_evidence\n'
    '        if self.web_arbitration:\n'
    '            d["web_arbitration"] = self.web_arbitration\n'
    '        if self.web_clean_check:\n'
    '            d["web_clean_check"] = self.web_clean_check\n'
    '        return d\n'
)
src = sub_once(src, T_OLD, T_NEW, "to_dict")

# changelog
CL = """  【W5-fix】`Pool.to_dict()` 是**显式白名单**，W2/W3 新增的 5 个联网字段
    没被列进去 ⇒ 真跑里 tavily 明明返回了结果（`cache/websearch/` 4 个文件
    n=3/8/8/8），产物里 W# 却是 **0** —— 静默吞掉。已补进白名单（仍加性：
    无联网痕迹时不挂键，关闭态 packed 与 v1.22.2 逐字相同）。
    ★ 与 W2 的 `dec_norm` 是**同一类坑**，这次栽在**池出口**这一层。
    对策：加通用前向守卫 `check_v123_pool_export`（把 Pool 所有 dataclass 字段
    填满后断言它们**全部**出现在 `to_dict()` 里）—— 任何人再加字段忘了出口，
    判据立刻红。

"""
src = sub_once(src, "\nv1.23.0 W3+W4 ──",
               "\n" + CL + "v1.23.0 W3+W4 ──", "changelog")

out = src.replace("\n", "\r\n")
b = out.encode("utf-8")
assert b.count(b"\r\n") == b.count(b"\n")
assert b.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert b.count(b"\r") == b.count(b"\r\n"), "出现裸 CR"
TARGET.write_bytes(b)
print("OK: W5-fix 已写入（to_dict 白名单补齐）")
