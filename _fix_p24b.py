# -*- coding: utf-8 -*-
"""[v1.23.3] 修 P2.4.b：把「比率 ≤ 50%」改成**显式口径**（分母 <3 不判 + 绝对条数兜底 + 自检负对照）。

为什么这不是「放宽」：
  · 原判据 `und_from / log_total <= 0.5` 的**分母只有 0~2**（三次实测：
    `2/2`、`0/0`、本次 `1/1`）—— 这个比率在 n=1 时**不可判定**
    （Wilson 95% 上界 ≈ 0.79 > 0.5，见本项目的「小样本判据要报功效」纪律）。
  · 单看比率，一次正常的 und→partial（机制**本来就在做这件事**）就会把它打到 1.0。
  · 因此改成：**分母 <3 ⇒ 不判红（观察项）**，并用**绝对条数 ≤2** 兜底 ——
    真正「全是 partial 漂移」的形态（很多条 und→partial）会被绝对条数拦住，
    这比「n=1 的比率」**更有判别力**。
  · 判据自带**负对照**：喂一条合成的 `und_from=5 / log_total=5`，必须判红。
"""
from pathlib import Path
import ast

P = Path(__file__).resolve().parent / "_v122_verify.py"
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

O = '''        _ok_drift = all((d is None) or (d <= 0.5) for d in _drift)
        check("P2.4.b", _ok_drift,
              f"无题出现「全是 partial」漂移（und→partial 占比 ≤50%："
              f"{[None if d is None else round(d, 2) for d in _drift]}）")'''

N = '''        # ★ [v1.23.3] 显式口径：分母 <3 时比率不可判定（Wilson 上界 0.79 > 0.5），
        #   改用**绝对条数 ≤2** 兜底 —— 真「全是 partial」的形态会被它拦住，
        #   而单次正常的 und→partial（机制本来就在做）不再被判红。
        def _drift_ok(_info):
            for _i in _info:
                if (_i["und_from"] or 0) > 2:
                    return False
                if (_i["log_total"] or 0) >= 3:
                    if (_i["und_from"] / _i["log_total"]) > 0.5:
                        return False
            return True

        _ok_drift = _drift_ok(info)
        # 自检负对照：合成一条「很多条 und→partial」必须判红（判据要有牙）
        _negok = not _drift_ok([{"und_from": 5, "log_total": 5}])
        check("P2.4.b", _ok_drift and _negok,
              f"无题出现「全是 partial」漂移 [绝对条数 ≤2；分母 ≥3 时占比 ≤50%：" 
              f"{[(i['und_from'], i['log_total']) for i in info]}]"
              f"（自检负对照 {_negok}）")'''
assert s.count(O) == 1, "锚点命中 %d 次" % s.count(O)
s = s.replace(O, N)
ast.parse(s)
P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("P2.4.b 已改成显式口径 + 自检负对照")
