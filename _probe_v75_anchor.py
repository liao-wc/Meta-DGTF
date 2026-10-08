# -*- coding: utf-8 -*-
"""
只读探针：锚点接入点的形态基线（v1.21.75 -> v1.21.76 对表用）。

    python _probe_v75_anchor.py 元DGTF-V1.21.75.py > _probe_v75_before.txt
    python _probe_v75_anchor.py 元DGTF-V1.21.76.py > _probe_v75_after.txt

输出 P1..P6 六项，期望的变化：

    P1  _anchor_round 直接调用点          1 -> 0
    P2  _before_round def / 调用点        0/0 -> 1/2
    P3  _anchor_calls 初始化 / 自增       0/0 -> 1/1
    P4  _budget_exhausted 引用 _anchor_calls   True -> False
    P5  _run_one_round_B 含 _before_round      False -> True
    P6  Pool.to_dict 挂 anchor_as_evidence     False -> True

★ 关键约定：**必须先抠掉 docstring 和注释**再扫。
  模块 docstring 的 changelog 里写着 `_before_round` / `_anchor_calls` 这些
  符号名 —— 全文扫会把"文档里提到过"当成"代码里有"，直接假通过。
  （v1.21.75 扫零触发 emoji 时 `🍽` 就这么被骗过一次。）
"""
import ast
import io
import textwrap
import re
import sys
import tokenize
from pathlib import Path


def _strip_docstrings_and_comments(src: str) -> str:
    """抠掉所有 docstring 与注释，只留可执行的代码文本。

    docstring 判定走 ast（`Expr(Constant(str))` 出现在模块/类/函数的 body[0]），
    不是按 `\"\"\"` 文本切 —— 后者会被字符串里的三引号带偏。
    """
    # ★ 必须先 dedent：`_find_method_body` 返回的是带缩进的**片段**，
    #   直接 ast.parse 会 SyntaxError（unexpected indent）→ 函数静默退回
    #   原文 → docstring 没被抠掉 → 方法体里"文档提到过的符号"被当成代码
    #   （实测：`_before_round` 体被数成 2 处 _anchor_round 调用，真值 1）。
    src = textwrap.dedent(src)
    kill = set()
    try:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Module, ast.FunctionDef,
                                     ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            body = getattr(node, "body", None) or []
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                d = body[0]
                for ln in range(d.lineno, (d.end_lineno or d.lineno) + 1):
                    kill.add(ln)
    except SyntaxError:
        pass
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                kill.add(tok.start[0])
    except Exception:
        pass
    lines = src.split("\n")
    return "\n".join("" if (i + 1) in kill else l
                     for i, l in enumerate(lines))


def _count(src: str, needle: str) -> int:
    """在**已抠文档的源码**里数 needle 的出现次数。"""
    return _strip_docstrings_and_comments(src).count(needle)


def _find_method_body(src: str, name: str) -> str:
    """取名为 name 的方法/函数体（到下一个同级 def 或文件尾）。"""
    lines = src.split("\n")
    start = None
    for i, l in enumerate(lines):
        if re.match(r"\s*def " + re.escape(name) + r"\s*\(", l):
            start = i
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"\s*def \w+\s*\(", lines[j]) and \
                len(lines[j]) - len(lines[j].lstrip()) <= \
                len(lines[start]) - len(lines[start].lstrip()):
            end = j
            break
    return "\n".join(lines[start:end])


def main() -> int:
    p = Path(sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.21.75.py")
    if not p.exists():
        print(f"找不到 {p}")
        return 1
    raw = p.read_bytes().decode("utf-8")
    crlf = raw.count("\r\n")
    lf = raw.count("\n")
    src = raw.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")

    print(f"文件: {p.name}")
    print(f"换行: CRLF={crlf} LF={lf} 纯CRLF={crlf == lf}")
    print(f"行数: {len(src.splitlines())}")
    print()

    # P1 — _anchor_round 的直接调用点（定义不算）
    #   ★ 判据修正：清单原来写「改后应为 0」，那是**错的** —— `_before_round`
    #     内部必须调 `_anchor_round`，所以全源码至少 1 处。有意义的判据是
    #     「**恰好 1 处，且它归拢在 `_before_round` 里**」（清单自己的冒烟
    #     判据 1 写的也是"恰好 1 处"，前后不一致，这里按后者）。
    p1 = _count(src, "self._anchor_round(")
    _p1_body = _strip_docstrings_and_comments(
        _find_method_body(src, "_before_round"))
    p1_in = _p1_body.count("self._anchor_round(")
    # P2 — _before_round 定义点 / 调用点
    p2_def = len(re.findall(r"^\s*def _before_round\s*\(",
                            _strip_docstrings_and_comments(src), re.M))
    p2_call = _count(src, "self._before_round(")
    # P3 — _anchor_calls 初始化 / 自增
    #   ★ 判据收紧：按**方法体**分别数，不全文正则 —— 全文会把
    #     `_anchor_crosscheck` 里那行"读取后 +1"也算成一次"初始化"。
    code = _strip_docstrings_and_comments(src)
    #   ★ 不用 `_find_method_body(src, "__init__")` —— 它返回**第一个**
    #     `def __init__`，而那是 `LLM.__init__` 不是 `MetaDGTF.__init__`
    #     （实测 init 数成 0）。改用精确字面串。
    p3_init = _count(src, "self._anchor_calls: int = 0")
    _cc_body = _strip_docstrings_and_comments(
        _find_method_body(src, "_anchor_crosscheck"))
    p3_inc = len(re.findall(r"self\._anchor_calls[^\n]*\+\s*1", _cc_body))
    # P4 — _budget_exhausted 是否引用 _anchor_calls
    be = _strip_docstrings_and_comments(_find_method_body(src,
                                                          "_budget_exhausted"))
    p4 = "_anchor_calls" in be
    # P5 — _run_one_round_B 含 _before_round
    b = _strip_docstrings_and_comments(_find_method_body(src,
                                                         "_run_one_round_B"))
    p5 = "_before_round" in b
    # P6 — Pool.to_dict 挂 anchor_as_evidence
    td = _strip_docstrings_and_comments(_find_method_body(src, "to_dict"))
    # 取最后一个 to_dict（Pool 的那个）
    all_td = re.findall(r"\n    def to_dict\(self\) -> dict:.*?(?=\n    def |\Z)",
                        code, re.S)
    p6 = any("anchor_as_evidence" in t for t in all_td) or \
        "anchor_as_evidence" in td
    # 附加：_print_polarity_snapshot 直接调用点（改后应恰好 1，在 _before_round 里）
    p_extra = _count(src, "self._print_polarity_snapshot(")

    print(f"P1  _anchor_round 直调 总/归拢在_before_round: {p1}/{p1_in}"
          f"   (期望 1/0 -> 1/1)")
    print(f"P2  _before_round def / 调用点            : {p2_def}/{p2_call}"
          f"     (期望 0/0 -> 1/2)")
    print(f"P3  _anchor_calls 初始化 / 自增           : {p3_init}/{p3_inc}"
          f"     (期望 0/0 -> 1/1)")
    print(f"P4  _budget_exhausted 引用 _anchor_calls  : {p4}"
          f"     (期望 True -> False)")
    print(f"P5  _run_one_round_B 含 _before_round     : {p5}"
          f"     (期望 False -> True)")
    print(f"P6  Pool.to_dict 挂 anchor_as_evidence    : {p6}"
          f"     (期望 False -> True)")
    print()
    print(f"附  _print_polarity_snapshot 直接调用点   : {p_extra}"
          f"     (改后期望 1，在 _before_round 里)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
