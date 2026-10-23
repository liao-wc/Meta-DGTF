# -*- coding: utf-8 -*-
"""生成 `_fullrun_V1250AB.py`：v1.23.49 的 A/B 真跑脚本 → v1.23.50 + **自动续跑**。

与 V1249 版的唯一区别（A/B 设计一字未动）：
  · 引擎换 v1.23.50（带断点续跑）；
  · **run_id 固定**（`V1250A` / `V1250B`，不再带时间戳）⇒ 被宿主回收后**重发同一条命令**
    即可从快照续跑（不重烧已完成层）；
  · 启动时自动探测已有快照（`outputs/_run_ckpt/<rid>.json`）：
    状态可续（running/interrupted/paused）⇒ 续；已完成（done）⇒ 直接读产物出表。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
src = (HERE / "_fullrun_V1249AB.py").read_text(encoding="utf-8")
t = src

subs = [
    ('SRC = HERE / "\u5143DGTF-V1.23.49.py"',
     'SRC = HERE / "\u5143DGTF-V1.23.50.py"'),
    ('"""v1.23.49 \u771f\u8dd1\u5bf9\u8868\uff08A/B \u5bf9\u7167\uff0c\u552f\u4e00\u82b1\u94b1\u7684\u4e00\u6b65\uff0c\u7528\u6237\u5df2\u786e\u8ba4\uff09\u3002',
     '"""v1.23.50 \u771f\u8dd1\u5bf9\u8868\uff08A/B \u5bf9\u7167\uff0c\u552f\u4e00\u82b1\u94b1\u7684\u4e00\u6b65\uff0c\u7528\u6237\u5df2\u786e\u8ba4\uff09\u3002\n'
     '\n'
     '\u2605 \u4e0e `_fullrun_V1249AB.py` \u7684\u533a\u522b\uff1a\u5f15\u64ce\u6362 v1.23.50\uff0c\u4e14 **run_id \u56fa\u5b9a**\n'
     '  \uff08`V1250A` / `V1250B`\uff09+ \u542f\u52a8\u65f6**\u81ea\u52a8\u63a2\u6d4b\u5feb\u7167\u7eed\u8dd1** \u2014\u2014 \u88ab\u5bbf\u4e3b\u56de\u6536\u540e\n'
     '  **\u91cd\u53d1\u540c\u4e00\u6761\u547d\u4ee4\u5373\u53ef\u63a5\u7740\u8dd1**\uff08\u5df2\u5b8c\u6210\u7684\u5c42\u4e0d\u91cd\u8dd1\u3001\u4e0d\u91cd\u70e7\u94b1\uff09\u3002'),
    ('run_id = "V1249%s_%s" % (tag, time.strftime("%Y%m%d_%H%M%S"))',
     'run_id = "V1250%s" % tag           # \u2605 \u56fa\u5b9a id \u21d2 \u91cd\u53d1\u547d\u4ee4\u5373\u53ef\u7eed\u8dd1'),
    ('out = HERE / ("_fullrun_V1249%s.json" % tag)',
     'out = HERE / ("_fullrun_V1250%s.json" % tag)'),
    ('(HERE / "_fullrun_V1249A.sum.json").write_text(',
     '(HERE / "_fullrun_V1250A.sum.json").write_text('),
    ('(HERE / "_fullrun_V1249B.sum.json").write_text(',
     '(HERE / "_fullrun_V1250B.sum.json").write_text('),
    # ── 续跑探测 + 复用已完成产物 ──
    ('    m = eng.MetaDGTF(cfg)\n'
     '    t0 = time.time()\n'
     '    res = m.run(QUESTION, route=list(ROUTE), rounds=dict(ROUNDS),\n'
     '                parallel_mode="serial", run_id=run_id)\n',
     '    # \u2605 \u7eed\u8dd1\u63a2\u6d4b\uff1a\u540c\u4e00 run_id \u5df2\u6709\u5feb\u7167 \u21d2 \u80fd\u7eed\u5c31\u7eed\uff1b\u5df2\u5b8c\u6210\u5c31\u76f4\u63a5\u8bfb\u4ea7\u7269\u3002\n'
     '    _ck = Path(eng.run_ckpt_path(run_id))\n'
     '    _resume, _prev = "", None\n'
     '    if _ck.is_file():\n'
     '        try:\n'
     '            _d = json.loads(_ck.read_text(encoding="utf-8"))\n'
     '        except Exception:  # noqa: BLE001\n'
     '            _d = {}\n'
     '        _st = str((_d or {}).get("status") or "")\n'
     '        _done = sorted((_d or {}).get("views") or {})\n'
     '        print("[%s] \u53d1\u73b0\u5feb\u7167 %s\uff1astatus=%s \u5df2\u5b8c\u6210\u5c42=%s"\n'
     '              % (tag, _ck.name, _st, _done))\n'
     '        if _st in ("running", "interrupted", "paused"):\n'
     '            _resume = str(_ck)\n'
     '            print("[%s] \u21d2 \u4ece\u5feb\u7167**\u7eed\u8dd1**\uff08\u5df2\u5b8c\u6210\u7684\u5c42\u4e0d\u91cd\u70e7\uff09" % tag)\n'
     '        elif _st == "done" and len(_done) >= len(ROUTE):\n'
     '            _p = HERE / ("_fullrun_V1250%s.json" % tag)\n'
     '            if _p.is_file():\n'
     '                _prev = json.loads(_p.read_text(encoding="utf-8"))\n'
     '    if _prev is not None:\n'
     '        print("[%s] \u5df2\u6709\u5b8c\u6210\u4ea7\u7269\uff08%s\uff09\u21d2 \u76f4\u63a5\u7528\u5b83\u51fa\u8868"\n'
     '              % (tag, _p.name))\n'
     '        return _prev\n'
     '    m = eng.MetaDGTF(cfg)\n'
     '    t0 = time.time()\n'
     '    res = m.run(QUESTION, route=list(ROUTE), rounds=dict(ROUNDS),\n'
     '                parallel_mode="serial", run_id=run_id,\n'
     '                resume_ckpt=_resume)\n'),
]
for o, n in subs:
    c = t.count(o)
    print("\u951a\u70b9 %d: %s" % (c, o[:56].replace("\n", "\u21b5")))
    assert c == 1, "\u951a\u70b9\u4e0d\u552f\u4e00/\u4e0d\u5b58\u5728\uff1a%s" % o[:90]
    t = t.replace(o, n, 1)

assert "\u5143DGTF-V1.23.50.py" in t and "V1250" in t and "resume_ckpt=_resume" in t
assert "\u5143DGTF-V1.23.49.py" not in t
out = HERE / "_fullrun_V1250AB.py"
out.write_bytes(t.encode("utf-8"))
import py_compile
py_compile.compile(str(out), doraise=True)
print("OK ->", out.name, "|\u8bed\u6cd5 OK")
