# -*- coding: utf-8 -*-
"""修 `_fullrun_V1250AB.py` 的双调用：`run()` 内部已经调过 `_eml_finish`。

为什么还要改脚本（引擎侧守卫不是为了替代它）：
  · 守卫是**兜底**，它的语义是「重复调用不写库」，返回值只是一块 `dup_skipped`
    的留痕 —— 若脚本用它覆盖 `res["playbook"]`，产物里的学习块就被降级成空壳；
  · 正确做法是**根本不重复调用**：只有真的没有 playbook 块（或那块是异常兜底）
    时才补一次。
本文件是纯 LF（由生成器写出的），所以按 LF 往返，不做 CRLF 断言。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "_fullrun_V1250AB.py"
raw = p.read_bytes()
assert raw.count(b"\r\n") == 0, "本文件预期纯 LF，实际含 CRLF"
s = raw.decode("utf-8")
n0 = s.count("\n")

OLD = '''    res = m.run(QUESTION, route=list(ROUTE), rounds=dict(ROUNDS),
                parallel_mode="serial", run_id=run_id,
                resume_ckpt=_resume)
    try:
        res["playbook"] = m._eml_finish(res)
    except Exception as e:  # noqa: BLE001
        print("[%s] _eml_finish 抛错（不影响本次对表）：%r" % (tag, e))
'''
NEW = '''    res = m.run(QUESTION, route=list(ROUTE), rounds=dict(ROUNDS),
                parallel_mode="serial", run_id=run_id,
                resume_ckpt=_resume)
    # ★ [学一次] `run()` 内部**已经**调过 `_eml_finish`（`run_id` 盖进产物之后）。
    #   这里只在「真的没有 playbook 块」或「那块是异常兜底」时补一次 —— 无条件
    #   再调一次会让同一跑次写两条 episode、把 weight 罚两遍（实测脏了 5 个文件，
    #   见 `_commitmsg_dedup_20261016.txt`）。
    _pb = res.get("playbook")
    if not isinstance(_pb, dict) or _pb.get("error"):
        try:
            res["playbook"] = m._eml_finish(res)
        except Exception as e:  # noqa: BLE001
            print("[%s] _eml_finish 抛错（不影响本次对表）：%r" % (tag, e))
'''
assert s.count(OLD) == 1, "锚点命中 %d 次" % s.count(OLD)
s = s.replace(OLD, NEW)
s = s.replace('  · 全程记账：显式 `run(..., run_id=...)` + `_eml_finish`（EML 才会学这次跑）。',
              '  · 全程记账：显式 `run(..., run_id=...)`（EML 只学**有 id** 的跑次；\n'
              '    `_eml_finish` 由 `run()` 内部调用，此处**不得**重复调用）。')
ast.parse(s)
p.write_bytes(s.encode("utf-8"))
print("_fullrun_V1250AB.py：%d → %d 行（双调用改为条件补调）" % (n0, s.count("\n")))
