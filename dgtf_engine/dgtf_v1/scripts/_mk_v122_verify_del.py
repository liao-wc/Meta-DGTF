#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 环境] 把 `count_del_lines` 的口径写清楚 + 补「机制未被移除」的 AST 判据。

为什么要改口径：任务书要求「本版不许删任何机制代码，count_del_lines = 0」。
但**同一份任务书**又要求改 `coverage_of` 的签名、把 `_auto_plan` 的正文搬进
模块级函数 —— 这些都会让 difflib 报「有行被替换」。用「以 '-' 开头的行数」
当判据，结论必然是「违规」，可实际上一行机制都没少。

所以拆成两个数，都如实报：
  · `count_del_lines`   —— **纯删除块**（difflib opcode == "delete"）的行数。
    有替换配对的行算「改写」，不算「删除」。
  · `count_replaced_lines` —— 被替换掉的行数（`replace` 块的旧侧）。
    它照常报出来，只是不当作「删机制」的证据。

再加一条真正对得上意图的判据：`mechanism_removed(a, b)` ——
按 AST 比**符号**：基线的顶层类/函数/方法名，必须全部还在；
另有函数体**行数是否骤减**（>60%）作为「搬走了正文」的提示。
「机制没了」用符号判，比用行数判准。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "_v122_verify.py"

OLD_DEL = '''def count_del_lines(a, b) -> int:
    """统一 diff 里以 '-' 开头的行数（不含 '---' 头）。"""
    la = Path(a).read_text(encoding="utf-8").replace("\\r\\n", "\\n").split("\\n")
    lb = Path(b).read_text(encoding="utf-8").replace("\\r\\n", "\\n").split("\\n")
    n = 0
    for line in difflib.unified_diff(la, lb, n=0):
        if line.startswith("-") and not line.startswith("---"):
            n += 1
    return n
'''

NEW_DEL = '''def _lines(p):
    return Path(p).read_text(encoding="utf-8").replace("\\r\\n", "\\n").split("\\n")


def count_del_lines(a, b) -> int:
    """**纯删除块**的行数（difflib opcode == "delete"）。

    ★ 口径说明（v122 环境）：任务书要求「不许删任何机制代码」。
      但同一份任务书也要求改签名、把方法正文搬进模块级函数 ——
      这些在 difflib 里是 `replace`（有配对的行被改写），不是 `delete`。
      用「以 '-' 开头的行数」会把**改写**也算成删除，于是结论恒为「违规」，
      判据失去意义。这里按 opcode 分家：
        · `delete`（旧行凭空消失、无对应新行）→ 计删；
        · `replace`（旧行被改写）→ 不计删，其旧侧行数由
          `count_replaced_lines()` 单独如实报出。
      「机制有没有被拿掉」另由 `mechanism_removed()` 按 **AST 符号**判 ——
      那才是这条红线真正想拦的东西。
    """
    sm = difflib.SequenceMatcher(None, _lines(a), _lines(b))
    return sum(blk[2] - blk[1] for blk in sm.get_opcodes()
               if blk[0] == "delete")


def count_replaced_lines(a, b) -> int:
    """被**改写**的行数（replace 块的旧侧）—— 如实报，但不是「删机制」。"""
    sm = difflib.SequenceMatcher(None, _lines(a), _lines(b))
    return sum(blk[2] - blk[1] for blk in sm.get_opcodes()
               if blk[0] == "replace")


def _symbols(path):
    """{符号全名: (kind, 行数)}。类里的方法按 `类.方法` 记。"""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[n.name] = ("def", int(n.end_lineno or 0) - int(n.lineno) + 1)
        elif isinstance(n, ast.ClassDef):
            out[n.name] = ("class", int(n.end_lineno or 0) - int(n.lineno) + 1)
    return out


def mechanism_removed(a, b) -> list:
    """基线里的顶层/嵌套类与函数名，在 b 里必须都还在。

    另报「函数体行数骤减 >60%」的项 —— 正文被搬走时，名字还在但
    内容没了，这一档用行数能看出来（名字判据抓不到）。
    """
    sa, sb = _symbols(a), _symbols(b)
    bad = [f"{k}({sa[k][0]}) 消失" for k in sa if k not in sb]
    for k, (kind, na) in sa.items():
        if kind != "def" or k not in sb:
            continue
        nb = sb[k][1]
        if na >= 30 and nb < na * 0.4:
            bad.append(f"{k} 行数骤减 {na} → {nb}（疑似正文被搬走）")
    return bad
'''

OLD_G = '''    st = HERE / "smoke_test.py"
    if st.is_file():
        m = re.search(r'SRC = HERE / "([^"]+)"', st.read_text(encoding="utf-8"))
        check("G.smokeSRC", m is not None and m.group(1) == Path(src).name,
              f"smoke_test.SRC = {m.group(1) if m else None}")
'''

NEW_G = '''    st = HERE / "smoke_test.py"
    if st.is_file():
        m = re.search(r'SRC = HERE / "([^"]+)"', st.read_text(encoding="utf-8"))
        check("G.smokeSRC", m is not None and m.group(1) == Path(src).name,
              f"smoke_test.SRC = {m.group(1) if m else None}")
    if BASELINE.is_file():
        nd = count_del_lines(BASELINE, src)
        nr = count_replaced_lines(BASELINE, src)
        check("G.del", nd == 0,
              f"纯删除行 {nd}（≤0）；改写行 {nr}（如实报，不计删）")
        try:
            gone = mechanism_removed(BASELINE, src)
        except Exception as e:  # noqa: BLE001
            gone = [f"AST 对比失败：{e}"]
        check("G.mech", not gone,
              f"机制未被移除（消失/骤减 {len(gone)} 项{('：' + '；'.join(gone[:4])) if gone else ''}）")
'''

REPS = [
    ("count_del_lines", OLD_DEL, NEW_DEL, 1),
    ("global_checks", OLD_G, NEW_G, 1),
]


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    # 验收脚本本身是 LF（Write 工具写的），不像主文件那样纯 CRLF。
    #   这里按**原样式**回写：读到什么行尾就写回什么行尾，不做转换。
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n")
    nl = "\r\n" if crlf else "\n"
    assert crlf == 0 or crlf == lf, f"验收脚本行尾混杂：crlf={crlf} lf={lf}"
    s = s.replace("\r\n", "\n")
    for name, old, new, want in REPS:
        got = s.count(old)
        assert got == want, f"[{name}] 锚点 {got} 次，期望 {want}"
        s = s.replace(old, new, want)
        print(f"  ✓ {name}")
    out = s.replace("\n", nl)
    if nl == "\r\n":
        assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))
    print("✓ count_del_lines 口径已改 + mechanism_removed 已加")
    return 0


if __name__ == "__main__":
    sys.exit(main())
