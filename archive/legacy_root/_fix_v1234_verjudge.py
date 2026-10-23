#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.4] 修「版本一致」判据的**会腐烂的锚**。

问题：`phase_v1233` 的 V1 把版本号写死成 `"1.23.3"`、`phase_v1234` 的 V1 写死成
`"1.23.4"`。于是 `--phase all` 跑在**下一版**上时，**上一版的 V1 必然判红**
（本轮实测：跑 v1.23.4 时 phase_v1233 的 V1 报 `ver=1.23.4`）。

这正是本项目的老坑「**判据的锚不能写死会变的东西**」——只不过这次写死的是
**版本号本身**，而 `--phase all` 会让「旧档判据」和「新主文件」同场出现。

修法：抽一个共用判据 `_version_consistent(mod, src)`，版本号**从被验文件名
推导**（`元DGTF-V1.23.4.py` → `1.23.4`），要求三处一致：
  ① 主文件 `__version__`  == 文件名里的版本
  ② `smoke_test.py` 的 SRC == 被验文件名
  ③ `dgtf_config.yaml` 头部含该版本

这比写死**更强**（多钉了「文件名与 __version__ 不许脱节」），而且**不会腐烂**。
"""
from pathlib import Path
import ast

P = Path("_v122_verify.py")
b = P.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "verify 不是纯 CRLF"
s = b.decode("utf-8").replace("\r\n", "\n")

HELPER = '''def _version_consistent(mod, src, yaml_head_n: int = 900) -> tuple:
    """[v1.23.4] 版本三处一致 —— 版本号**从被验文件名推导**，不写死。

    ★ 别把版本号写成字面量：`--phase all` 会把**旧档判据**与**新主文件**
      放在同一次运行里，写死的锚必然在升版那天翻红，而那次翻红与代码
      质量**毫无关系**（纯噪声，且很容易被误读成回归）。
    ★ 反过来说，这样写**更强**：多钉了「文件名与 `__version__` 不许脱节」。
    """
    import re as _re
    from pathlib import Path as _P

    _m = _re.search(r"V(\\d+\\.\\d+\\.\\d+)\\.py$", _P(src).name)
    _want = _m.group(1) if _m else ""
    _sm = HERE / "smoke_test.py"
    _sm_t = _sm.read_bytes().decode("utf-8") if _sm.is_file() else ""
    _y = HERE / "dgtf_config.yaml"
    _y_t = (_y.read_bytes().decode("utf-8")[0:yaml_head_n]
            if _y.is_file() else "")
    _got = str(getattr(mod, "__version__", "") or "")
    return (bool(_want), _got, _want, _want in _y_t, _P(src).name in _sm_t)


'''

A = "# ── 通用工具 ────────────────────────────────────────────────"
assert s.count(A) == 1, "工具区锚点 %d 次" % s.count(A)
s = s.replace(A, HELPER + A, 1)

# ---- 替换 phase_v1233 的 V1 ----
O1 = '''    check("V1 版本一致：主文件 __version__ / 冒烟 SRC / yaml 头",
          (getattr(mod, "__version__", "") == "1.23.3"
           and '元DGTF-V1.23.3.py' in (HERE / "smoke_test.py")
           .read_bytes().decode("utf-8")
           and "1.23.3" in (HERE / "dgtf_config.yaml")
           .read_bytes().decode("utf-8")[:600]),
          "ver=%s" % getattr(mod, "__version__", "?"))'''
N1 = '''    _vc = _version_consistent(mod, src)
    check("V1 版本一致：主文件 __version__ / 冒烟 SRC / yaml 头",
          _vc[0] and _vc[1] == _vc[2] and _vc[3] and _vc[4],
          "ver=%s want=%s yaml=%s smoke=%s" % _vc[1:])'''
assert s.count(O1) == 1, "v1233 V1 锚点 %d 次" % s.count(O1)
s = s.replace(O1, N1, 1)

# ---- 替换 phase_v1234 的 V1（同样不写死）----
O2 = '''    check("V1 版本一致：主文件 __version__ / 冒烟 SRC / yaml 头",
          (getattr(mod, "__version__", "") == "1.23.4"
           and "元DGTF-V1.23.4.py" in (HERE / "smoke_test.py")
           .read_bytes().decode("utf-8")
           and "v1.23.4" in (HERE / "dgtf_config.yaml")
           .read_bytes().decode("utf-8")[:900]),
          "ver=%s" % getattr(mod, "__version__", "?"))'''
N2 = '''    _vc = _version_consistent(mod, src)
    check("V1 版本一致：主文件 __version__ / 冒烟 SRC / yaml 头",
          _vc[0] and _vc[1] == _vc[2] and _vc[3] and _vc[4],
          "ver=%s want=%s yaml=%s smoke=%s" % _vc[1:])'''
assert s.count(O2) == 1, "v1234 V1 锚点 %d 次" % s.count(O2)
s = s.replace(O2, N2, 1)

ast.parse(s)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
P.write_bytes(out)
print("已加 _version_consistent 并替换两处 V1")
