# -*- coding: utf-8 -*-
"""[v1.23.1 遗留收尾 · 补丁3] 三票里「空票」必须留痕。

起因（真跑数据读出）：OFF 臂 6 条子问题的 `votes` **都只有 2 条**
（`tri_consensus = [2, 0, 4]` 而 n=6 ⇒ 可用票只有 2 张）。
追代码：`_adjudicate_sub_tristate_multi` 里

    if not isinstance(data, dict): continue
    ok_votes += 1
    for it in (data.get("judgments") or []): ...

—— 某票返回**合法 dict 但 `judgments` 为空**时，
既不抛错（不进 `except`）、也不留痕，`ok_votes` 还照样 +1。
产物里只表现为「这条没人投」，**读者无从知道三票实际只有两票**，
`agree13/agree23` 也算不出来（本次分析就被这个卡住）。

★ 本补丁**只加留痕，不改票的计数语义**（`ok_votes` 的行位置不动）——
  「三票全失败」那条分支的判据因此**不受影响**。
"""
import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TGT = HERE / "元DGTF-V1.23.1.py"
src = TGT.read_bytes().decode("utf-8")
assert src.count("\r\n") == src.count("\n"), "非纯 CRLF"
src = src.replace("\r\n", "\n")

if "_empty_votes" in src:
    print("  已改，跳过")
    sys.exit(0)

O1 = """        for sysp in _sys_list:
            try:
                raw = self.llm.call(sysp, user, 0.0, 1200, json_mode=True,
                                    stage="adjudicate_sub_tristate_multi")
                data = self.llm.parse_json(raw)
            except Exception as e:
                logger.warning("三态多票：一票失败（跳过）: %s", e)
                continue
            if not isinstance(data, dict):
                continue
            ok_votes += 1"""
N1 = """        _empty_votes = 0
        for _vi, sysp in enumerate(_sys_list):
            try:
                raw = self.llm.call(sysp, user, 0.0, 1200, json_mode=True,
                                    stage="adjudicate_sub_tristate_multi")
                data = self.llm.parse_json(raw)
            except Exception as e:
                logger.warning("三态多票：一票失败（跳过）: %s", e)
                continue
            if not isinstance(data, dict):
                continue
            # [v1.23.1 遗留收尾] ★ 合法 dict 但**零条判决**也是一种「票没投」。
            #   原先它完全无声（不抛错、也不进 except），产物只表现为
            #   「这条没人投」—— 实测 OFF 臂就有一票如此：`votes` 每条只有
            #   2 条 ⇒ 名义三票、实际两票，而读者看不出原因。
            #   ★ 只加留痕，**不动 ok_votes 的位置**（不改计数语义）。
            if not (data.get("judgments") or []):
                _empty_votes += 1
                logger.warning(
                    "三态多票：第 %d 票返回 0 条判决（空票，等于弃权）",
                    _vi + 1)
            ok_votes += 1"""
assert src.count(O1) == 1, src.count(O1)
src = src.replace(O1, N1)

O2 = """        if ok_votes == 0:
            logger.warning("三态多票：三票全失败 → 保留拆解原标签")"""
N2 = """        if _empty_votes:
            _p1 = self.pools.get("1")
            if _p1 is not None:
                _p1.meta.append(
                    "[三态多票] " + str(len(_sys_list) - _empty_votes)
                    + "/" + str(len(_sys_list)) + " 票可用（空票 "
                    + str(_empty_votes) + " 张，等于弃权；一致性指标只在"
                    "**可用票**之间计算）")
        if ok_votes == 0:
            logger.warning("三态多票：三票全失败 → 保留拆解原标签")"""
assert src.count(O2) == 1, src.count(O2)
src = src.replace(O2, N2)

out = src.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r") == out.count(b"\r\n")
ast.parse(src)
TGT.write_bytes(out)
print("[done] 空票留痕已加（纯留痕，不改计数语义）")
