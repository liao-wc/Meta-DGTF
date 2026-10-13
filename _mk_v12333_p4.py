#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.33 补丁 P4：bandit 状态存取函数（补 P3 的引用）。

★ 用 `@@NL@@` 占位再替换成 2 字符的 `\\n` —— heredoc 会把 `\\n` 吃成真换行，
  本轮已因此踩坑 3 次（通则：凡内容含反斜杠，一律走脚本文件 + 占位替换）。
"""
from pathlib import Path
import ast

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"
BSNL = chr(92) + "n"

FN = '''_BANDIT_ARMS = ({"rounds": 3}, {"rounds": 4}, {"rounds": 6})
_BANDIT_FILE = "bandit.json"


def _load_bandit(cfg) -> "BudgetBandit":
    """从 `dgtf_memory/bandit.json` 载入 bandit 状态（缺失 ⇒ 全新）。

    ★ 默认**关**：只有 `auto.bandit.enabled=true` 才走到这里。
    ★ bandit 状态是**状态**不是账本 ⇒ 允许整体覆盖，但每次都带 `t`/`n` 供审计。
    """
    _arms = (cfg or {}).get("arms") or _BANDIT_ARMS
    bb = BudgetBandit(_arms, c=float((cfg or {}).get("c", 1.0) or 1.0),
                      cost_w=float((cfg or {}).get("cost_w", 0.3) or 0.3))
    try:
        import json as _j
        _d = Path(str((cfg or {}).get("dir") or eml_dir()))
        _f = _d / _BANDIT_FILE
        if _f.is_file():
            st = _j.loads(_f.read_text(encoding="utf-8"))
            if isinstance(st.get("n"), list) and len(st["n"]) == len(bb.arms):
                bb.n = [int(x or 0) for x in st["n"]]
                bb.mean = [float(x or 0.0) for x in st.get("mean", bb.mean)]
                bb.cost = [float(x or 0.0) for x in st.get("cost", bb.cost)]
                bb.t = int(st.get("t") or sum(bb.n))
    except Exception:
        pass
    return bb


def _save_bandit(bb, cfg) -> bool:
    """把 bandit 状态落盘（带 `t`/`n`，供审计）。"""
    try:
        import json as _j
        import time as _t
        _d = Path(str((cfg or {}).get("dir") or eml_dir()))
        _d.mkdir(parents=True, exist_ok=True)
        (_d / _BANDIT_FILE).write_text(_j.dumps({
            "t": _t.time(), "n": list(bb.n),
            "mean": [round(x, 6) for x in bb.mean],
            "cost": [round(x, 6) for x in bb.cost],
            "arms": list(bb.arms)}, ensure_ascii=False, indent=1),
            encoding="utf-8", newline="@@NL@@")
        return True
    except Exception:
        return False


'''


def main():
    b = SRC.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n") and b.count(b"\r\r\n") == 0
    s = b.decode("utf-8").replace("\r\n", "\n")
    assert "def _load_bandit(" not in s, "已存在（防重复插入）"
    anchor = "class BudgetBandit:"
    assert s.count(anchor) == 1
    s = s.replace(anchor, FN.replace("@@NL@@", BSNL) + anchor, 1)
    ast.parse(s)
    SRC.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
    s2 = SRC.read_bytes().decode("utf-8")
    assert "def _load_bandit(" in s2 and "def _save_bandit(" in s2
    assert s2.count("\r\r\n") == 0
    print("OK P4：bandit 存取函数已加；AST + CRLF 校验通过")


if __name__ == "__main__":
    main()
