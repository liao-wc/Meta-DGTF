#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段6] 双实现收口（Step 6.2 / 6.3）。

6.2 `auto_plan` 收口
  · 模块级 `_auto_plan_once(question, config, llm)` = **原文搬过去**的方法体
    （一次调用定 mode + rounds；v1.21.61 起的行为逐字保留）。
  · 模块级 `auto_plan(question, config, config_path, llm)` 成为唯一入口：
    给了 `llm` → 走单调用路径；没给 → 保留 v1.21.62 的两次调用路径
    （外部 API 兼容）。
  · `MetaDGTF._auto_plan` 退成薄壳 `return auto_plan(question, self.config,
    llm=self.llm)`。

  ★ 为什么不是「让方法去调模块级的两调用版」：那会把一次调用变成两次，
    成本与结果都变 —— 而阶段 6 的验收恰恰要求 before/after **逐字一致**。
    所以唯一实现落在**单调用**那一支，两次调用那支原样留给外部 API。

6.3 `_rephrase_streak` 收口
  · 模块级 `_compute_rephrase_streak(view, state)` 唯一实现；
    串行 `_run_layer` 与并行 `_b_check_stop` 两个调用点都改调它。

搬运用 AST 行号定位，不手抄 —— 143 行手抄必错。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

SHELL = '''    def _auto_plan(self, question: str) -> dict:
        """[v122 P6 G6.2] 收口：唯一实现搬到模块级 `auto_plan`。

        本方法现在只是一层兼容壳 —— 签名与返回值形状都不变，`run()` 与
        外部脚本都不用改。传 `llm` 让模块级走**单调用**那条路径，于是
        行为与 v1.21.77 逐字相同（对照见 `_probe_v122_phase6.py`）。
        """
        return auto_plan(question, self.config, llm=self.llm)
'''

ONCE_HDR = '''

def _auto_plan_once(question: str, config: Optional[dict],
                    llm) -> dict:
    """[v122 P6 G6.2] 「一次调用同时定 mode + rounds」的唯一实现。

    ★ 正文原样搬自 `MetaDGTF._auto_plan`（v1.21.71 起的行为），只把
      `self.config` → `config`、`self.llm` → `llm`。搬运用 AST 行号定位，
      没有手抄。`auto_plan(..., llm=...)` 是它的唯一调用者。
    """

'''

OLD_MAXIDLE_A = ('            _mi_from_view = getattr(view, "_meta_idle_streak", 0)\n'
                 '            # [v1.21.56 P0-1] 两条来源分开成文，不再合成一个数再猜来源。\n'
                 '            #   · _rephrase_streak：真·复述（代码直检 + 自省判定）\n'
                 '            #   · carry_streak   ：自省点名的同一批问题连续没消化\n'
                 '            _rephrase_streak = max(meta_idle_streak, _mi_from_view)\n')
OLD_MAXIDLE_B = ('        _mi_from_view = getattr(view, "_meta_idle_streak", 0)\n'
                 '        _rephrase_streak = max(int(state.get("meta_idle_streak", 0) or 0),\n'
                 '                               int(_mi_from_view or 0))\n')

NEW_MAXIDLE_A = ('            # [v1.21.56 P0-1] 两条来源分开成文，不再合成一个数再猜来源。\n'
                 '            #   · _rephrase_streak：真·复述（代码直检 + 自省判定）\n'
                 '            #   · carry_streak   ：自省点名的同一批问题连续没消化\n'
                 '            # [v122 P6 G6.3] 收口：串行/并行两侧共用唯一实现。\n'
                 '            _mi_from_view = getattr(view, "_meta_idle_streak", 0)\n'
                 '            _rephrase_streak = _compute_rephrase_streak(view, {\n'
                 '                "meta_idle_streak": meta_idle_streak})\n')

NEW_MAXIDLE_B = ('        # [v122 P6 G6.3] 收口：与串行 `_run_layer` 共用唯一实现。\n'
                 '        _mi_from_view = getattr(view, "_meta_idle_streak", 0)\n'
                 '        _rephrase_streak = _compute_rephrase_streak(view, state)\n')

HELPER = '''
def _compute_rephrase_streak(view, state) -> int:
    """[v122 P6 G6.3] 「ing 连续几圈在复述」的唯一实现。

    ★ 收口前这行数在**两处**各写一份：
        · 串行 `_run_layer`：`max(meta_idle_streak, getattr(view, ...))`
        · 并行 `_b_check_stop`：`max(int(state[...]), int(getattr(view, ...)))`
      规则一样、代码两份 —— 本项目「同一条逻辑两条通道各写一份」的又一例。
      合并后这个符号在整个文件里**只有一个 def**（冒烟按 AST 数，不数字面串
      —— 文档里提到函数名会被字面串计数误当成定义，本项目踩过不止一次）。
    """
    _mi_from_view = getattr(view, "_meta_idle_streak", 0)
    _mi_state = int((state or {}).get("meta_idle_streak", 0) or 0)
    return max(_mi_state, int(_mi_from_view or 0))

'''


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")
    lines = s.split("\n")

    # ---- 用 AST 定位 _auto_plan 方法 ----
    tree = ast.parse(s)
    node = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == "_auto_plan":
            node = n
            break
    assert node is not None, "找不到 _auto_plan"
    a, z = node.lineno - 1, node.end_lineno
    body_lines = lines[a + 1:z]
    assert body_lines, "方法体为空"

    # 校验方法体里除了 config/llm 没有别的 self 依赖
    others = [ln.strip() for ln in body_lines
              if "self." in ln and "self.config" not in ln
              and "self.llm" not in ln]
    assert not others, f"方法体里还有别的 self 依赖：{others[:3]}"

    # ---- 搬运：去掉 4 格缩进，self.config → config，self.llm → llm ----
    moved = []
    for ln in body_lines:
        ln2 = ln[4:] if ln.startswith("    ") else ln
        ln2 = ln2.replace("self.config", "config").replace("self.llm", "llm")
        moved.append(ln2)
    moved_src = ONCE_HDR + "\n".join(moved).rstrip("\n") + "\n"
    print(f"  · 搬运 _auto_plan 正文 {len(moved)} 行")

    # ---- 替换方法（含 def 行与 docstring）为薄壳 ----
    lines[a:z] = SHELL.rstrip("\n").split("\n")
    s = "\n".join(lines)

    # ---- 插 _auto_plan_once 到模块级 auto_plan 之前 ----
    anchor = "def auto_plan(question: str, config: Optional[dict] = None,\n"
    assert s.count(anchor) == 1, f"模块级 auto_plan 锚点 {s.count(anchor)} 次"
    s = s.replace(anchor, moved_src.lstrip("\n") + "\n" + anchor, 1)
    print("  · 已插入 _auto_plan_once")

    # ---- 模块级 auto_plan 加 llm 形参 + 单调用分支 ----
    s = s.replace(
        "def auto_plan(question: str, config: Optional[dict] = None,\n"
        "              config_path: Optional[str] = None) -> dict:\n",
        "def auto_plan(question: str, config: Optional[dict] = None,\n"
        "              config_path: Optional[str] = None,\n"
        "              llm=None) -> dict:\n", 1)
    a2 = ('    cfg = config if config is not None else load_config(\n'
          '        str(config_path or ""))\n')
    assert s.count(a2) == 1 or s.count(a2) == 2, f"cfg 锚点 {s.count(a2)} 次"
    b2 = a2 + ('    # [v122 P6 G6.2] 给了 llm → 走**单调用**路径（run() 的\n'
               '    #   自动调度用的就是这条；行为与 v1.21.77 逐字相同）。\n'
               '    #   没给 → 保留 v1.21.62 的两次调用路径（外部 API 兼容）。\n'
               '    if llm is not None:\n'
               '        return _auto_plan_once(question, cfg, llm)\n')
    s = s.replace(a2, b2, 1)
    print("  · auto_plan 加 llm 形参与单调用分支")

    # ---- _compute_rephrase_streak ----
    for name, old, new, want in [
            ("run_layer", OLD_MAXIDLE_A, NEW_MAXIDLE_A, 1),
            ("b_check_stop", OLD_MAXIDLE_B, NEW_MAXIDLE_B, 1)]:
        got = s.count(old)
        assert got == want, f"[{name}] 锚点 {got} 次，期望 {want}"
        s = s.replace(old, new, want)
        print(f"  · {name} 改用 _compute_rephrase_streak")
    h_anchor = "def _anchor_enters_citation(anchor, cfg) -> bool:\n"
    assert s.count(h_anchor) == 1
    s = s.replace(h_anchor, HELPER.lstrip("\n") + "\n" + h_anchor, 1)
    print("  · 插入 _compute_rephrase_streak")

    assert "return auto_plan(question, self.config" in s, "薄壳没写对"
    assert s.count("def _compute_rephrase_streak") == 1, \
        f"_compute_rephrase_streak 定义 {s.count('def _compute_rephrase_streak')} 处"

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))
    print(f"✓ 阶段6 完成；行数 {len(out.splitlines())}；ast.parse OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
