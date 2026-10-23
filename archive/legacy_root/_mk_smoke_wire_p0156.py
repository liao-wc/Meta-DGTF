# -*- coding: utf-8 -*-
"""把**已存在但从未接线**的 `check_p0_156_units(src)` 接进 `main()`。

发现方式：`_audit_unwired_checks.py`（AST 比「定义集合」与「main 里调用的集合」）。
它签名吃 `src`（其他判据都是无参），所以当年写完后一直没被 main 调到 ——
**判据存在但从不运行 = 假覆盖**（看代码的人会以为测过）。

它本身是有效的（单跑返回 True），所以接上而不是删掉。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "smoke_test.py"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")

OLD = """    if not check_v12361_empty_guard():
        return 1
"""
NEW = """    if not check_v12361_empty_guard():
        return 1
    # ★ [补线] 这条判据早就写好了（v1.21.56 的 P0/P1 单元），但签名吃 `src`、
    #   与其余无参判据不同，所以**从来没被 main 调到** —— 存在≠在跑。
    #   审计脚本 `_audit_unwired_checks.py` 逮到，这里接上。
    if not check_p0_156_units(SRC.read_text(encoding="utf-8")):
        return 1
"""
assert s.count(OLD) == 1, "锚点命中 %d 次" % s.count(OLD)
s = s.replace(OLD, NEW)
ast.parse(s)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
p.write_bytes(out)
print("已接线；%d → %d 行" % (n0, s.count("\n")))

# 接线后复查
import subprocess
import sys
r = subprocess.run([sys.executable, "_audit_unwired_checks.py"], cwd=str(HERE),
                   capture_output=True, text=True)
print(r.stdout.strip())
