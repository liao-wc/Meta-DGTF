# -*- coding: utf-8 -*-
"""修 v1.23.51 判据自身的顺序错：`used_outcomes` 那条必须在**对照组之前**判。

症状：`[E5] used_outcomes 有 run 记了两次：[('L0001', {'RUN5': 2, ...})]`
根因：E4 对照组**故意**用同一个 run_id 再写一次（模拟 paused 后的完整样本）
      ⇒ 它本来就会给 RUN5 再记一条。判据放在对照组之后就必然假红。
★ 不是放宽阈值，是把判据挪到「它要测的那件事」发生的时刻 —— 与
  「检测缺省要在补默认值之前判」同一条纪律。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "smoke_test.py"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")

BLOCK = '''        # ★ used_outcomes 必须在**对照组之前**判：E4 故意用同一 run_id 再写一次
        #   （模拟 paused 后的完整样本），那本来就该给该 run 再记一条。
        #   放在对照组之后测到的就不是幂等，而是对照本身。
        _dup = []
        for _e in (mod.eml_read_jsonl(_d / "playbook.jsonl") or []):
            _c = {}
            for _x in (_e.get("used_outcomes") or []):
                _r = str(_x.get("run") or "")
                _c[_r] = _c.get(_r, 0) + 1
            if any(v > 1 for v in _c.values()):
                _dup.append((_e.get("id"), _c))
        if _dup:
            bad.append("[E5] 同一次调用路径把 used_outcomes 记了两次：%r"
                       % (_dup[:3],))
'''

OLD_TAIL = '''        # 对照三：used_outcomes 里每个 run 至多 1 条
        _dup = []
        for _e in (mod.eml_read_jsonl(_d / "playbook.jsonl") or []):
            _c = {}
            for _x in (_e.get("used_outcomes") or []):
                _r = str(_x.get("run") or "")
                _c[_r] = _c.get(_r, 0) + 1
            if any(v > 1 for v in _c.values()):
                _dup.append((_e.get("id"), _c))
        if _dup:
            bad.append("[E5] used_outcomes 有 run 记了两次：%r" % (_dup[:3],))
'''
assert s.count(OLD_TAIL) == 1, "尾块命中 %d" % s.count(OLD_TAIL)
s = s.replace(OLD_TAIL, "")

ANCHOR = '''        _n5 = len(mod.eml_read_jsonl(_d / "episodes.jsonl"))
        if _n5 != 5:
            bad.append("[E2] 同一跑次写了两条 episode（5 跑实测 %d 条）" % _n5)
'''
assert s.count(ANCHOR) == 1, "锚点命中 %d" % s.count(ANCHOR)
s = s.replace(ANCHOR, ANCHOR + BLOCK)

ast.parse(s)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
p.write_bytes(out)
print("smoke_test.py：%d → %d 行（E5 挪到对照组之前）" % (n0, s.count("\n")))
