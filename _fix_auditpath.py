# -*- coding: utf-8 -*-
"""[v1.23.3] 修 `check_v1232_audit`：被测文件不能**写死版本名**。

原写法 `str(SRC or HERE / "元DGTF-V1.23.2.py")` —— 而冒烟里调的是
`check_v1232_audit()`（不带参）⇒ SRC=None ⇒ 永远拿 v1.23.2 去跑审计，
于是升版后 C2「smoke SRC 指向本版」必判红（**判据的锚写死了版本**，
本项目老坑：判据的锚不能是移动靶 / 不能写死会变的东西）。
正解：取**已加载模块**的 `__file__`。
"""
from pathlib import Path
import ast

HERE = Path(__file__).resolve().parent
P = HERE / "_mk_v1230_smoke_checks.py"
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

O = '''        _r = subprocess.run([_s.executable, str(_pp), str(SRC or HERE / "元DGTF-V1.23.2.py")],'''
N = '''        # ★ 被测文件取**已加载模块**的 __file__，不写死版本名 ——
        #   否则升版后 C2「smoke SRC 指向本版」必判红（判据的锚写死了）。
        _tgt = str(SRC or getattr(globals().get("mod"), "__file__", "")
                   or (HERE / "元DGTF-V1.23.3.py"))
        _r = subprocess.run([_s.executable, str(_pp), _tgt],'''
assert s.count(O) == 1, "锚点命中 %d 次" % s.count(O)
s = s.replace(O, N)
ast.parse(s)
P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("check_v1232_audit 的被测文件改为「已加载模块的 __file__」")
