#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段4c] 修 `external_anchor` 的**重复键**静默覆盖。

症状：阶段 4 验收 4.1.1 报 `as_evidence=False ∈ 五档` 失败 —— 我明明写了
`"as_evidence": "off"`。根因：同一个 dict 里 `as_evidence` 出现了**两次**
（我在 `crosscheck` 后面加了一次，v1.21.75 原有的 `False` 在后面又一次），
Python 的 dict 字面量**后者胜**，于是新值被静默丢掉。

教训：往已有 dict 里加键之前先确认**这个键还不存在**。
改法：不再新增重复键 —— 直接改旧键的值，把新键（tier_floor /
api_key_env / cache_ttl_hours）挂在旧键旁边。

另外补一个**全局结构判据**（进冒烟）：全文件 AST 扫描，任何 dict 字面量
的**常量键重复**都判红。这个坑不只 `external_anchor` 一处可能踩。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

# 1) 摘掉我这次加的两个重复键（连同注释块一起收窄）
OLD_ADDED = '''        # [v122 P4 G4.1] 锚点分五档。旧布尔写法仍兼容：
        #   True → "evidence"，False → "off"（见 _anchor_tier）。
        #   off      不给模型看
        #   record   只记录，不进引用表
        #   crosscheck 只做收尾对照（v1.21.75 的默认行为）
        #   evidence 进引用表 X#，可支撑 →decidable / →partial
        #   gate     evidence + 冲突即阻断该结论
        "as_evidence": "off",
        # [v122 P4 G4.2] 引用表只收 tier ≤ 此值的锚点（1 最硬）。
        "tier_floor": 2,
        # [v122 P4 G4.3] 真检索要用的环境变量名（不落盘 key）。
        "api_key_env": "TAVILY_API_KEY",
        "cache_ttl_hours": 24,
        # snapshot | tavily
        "retriever": "snapshot",
'''
NEW_ADDED = '''        # [v122 P4 G4.1] 引用表只收 tier ≤ 此值的锚点（1 最硬）。
        "tier_floor": 2,
        # [v122 P4 G4.3] 真检索要用的环境变量名（不落盘 key）。
        "api_key_env": "TAVILY_API_KEY",
        "cache_ttl_hours": 24,
'''

# 2) 改旧键：布尔 → 五档字符串（就地改，不新增键）
OLD_KEY = '        "as_evidence": False,\n'
NEW_KEY = ('        # [v122 P4 G4.1] 锚点五档（旧布尔兼容：True→evidence，\n'
           '        #   False→off，见 _anchor_tier）。\n'
           '        #   off / record / crosscheck / evidence / gate\n'
           '        "as_evidence": "off",\n')

REPS = [
    ("drop_dup_keys", OLD_ADDED, NEW_ADDED, 1),
    ("retag_as_evidence", OLD_KEY, NEW_KEY, 1),
]

CHECK_SRC = '''

def check_v122_dup_dict_keys(SRC=None):
    """[v122 结构] 全文件 AST 扫描：任何 dict 字面量的常量键重复都判红。

    ★ 为什么要有这条：阶段 4 往 `DEFAULT_CONFIG["external_anchor"]` 加
      `as_evidence`，而那个键**已经存在** —— Python 的 dict 字面量后者胜，
      新值被静默丢掉，直到验收报 `as_evidence=False ∈ 五档` 才暴露。
      「同一个键写两遍」在 20k 行的配置块里靠人眼是查不出来的。
    """
    print("  · v1.22 结构：dict 字面量无重复常量键")
    try:
        import ast as _ast
        m = _v122_mod(SRC)
        f = getattr(m, "__file__", None) or SRC
        tree = _ast.parse(Path(f).read_text(encoding="utf-8"))
        dups = []
        for node in _ast.walk(tree):
            if not isinstance(node, _ast.Dict):
                continue
            seen = {}
            for k in node.keys:
                if k is None:
                    continue
                try:
                    kk = _ast.literal_eval(k)
                except Exception:
                    continue
                if not isinstance(kk, (str, int, float, bool, tuple)):
                    continue
                if kk in seen:
                    dups.append(f"line {getattr(k, 'lineno', '?')}: {kk!r}")
                seen[kk] = True
        assert not dups, "dict 重复键 " + str(len(dups)) + " 处：" + "；".join(dups[:6])
        print("  ✓ v1.22 结构：dict 字面量无重复常量键")
        return True
    except Exception as e:
        print(f"  ✗ v1.22 结构 失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
'''


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")
    for name, old, new, want in REPS:
        got = s.count(old)
        assert got == want, f"[{name}] 锚点 {got} 次，期望 {want}"
        s = s.replace(old, new, want)
        print(f"  ✓ {name}")

    # 写结构判据进 _v122_checks.py（冒烟与验收共用的事实源）
    repo = HERE / "_v122_checks.py"
    rs = repo.read_text(encoding="utf-8").replace("\r\n", "\n")
    if "def check_v122_dup_dict_keys" not in rs:
        rs = rs.rstrip("\n") + "\n" + CHECK_SRC
        repo.write_bytes(rs.replace("\n", "\r\n").encode("utf-8"))
        print("  ✓ _v122_checks.py += check_v122_dup_dict_keys")

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))

    # 自检：external_anchor 里 noway 再有重复键
    import re
    i = out.replace("\r\n", "\n").index('"external_anchor": {')
    lines = out.replace("\r\n", "\n")[i:].split("\n")
    depth, buf = 0, []
    for ln in lines:
        buf.append(ln)
        depth += ln.count("{") - ln.count("}")
        if depth == 0 and len(buf) > 1:
            break
    ks = [re.match(r'\s*"([^"]+)":', l).group(1)
          for l in buf if re.match(r'\s*"[^"]+":', l)]
    assert len(ks) == len(set(ks)), f"仍有重复键：{ks}"
    print(f"✓ 阶段4c 完成；external_anchor 键 {len(ks)} 个且无重复；行数 "
          f"{len(out.splitlines())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
