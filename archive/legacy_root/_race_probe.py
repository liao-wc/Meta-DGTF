"""竞态探针：研究层读修行池的时刻，是否落在修行层写池区间内。

读 = DGTF._decompose_from_pool（无锁，直接读 self.pools["0"]）
写 = MetaDGTF._apply_view_to_pool（有 _pool_lock）
圈 = MetaDGTF._run_one_round_B
"""
import os
import sys
import time
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("DGTF_API_KEY", "sk-x")

src = open(os.path.join(HERE, "smoke_test.py"), encoding="utf-8").read()
ns = {"__file__": os.path.join(HERE, "smoke_test.py")}
exec(compile(src.replace(
    'if __name__ == "__main__":\n    sys.exit(main())', ''),
    "smoke_test.py", "exec"), ns)

mod = ns["mod"]
MetaDGTF = mod.MetaDGTF
DGTF = mod.DGTF
run_mode = ns["run_mode"]

_lock = threading.Lock()
_o_round = MetaDGTF._run_one_round_B
_o_write = MetaDGTF._apply_view_to_pool
_o_read = DGTF._decompose_from_pool
_o_layer = MetaDGTF._run_layer
_o_has = MetaDGTF._has_pool_content_view
_o_decq = DGTF._decompose_question

MODES = ["serial", "A", "B", "C", "D", "E", "F", "G", "H"]
Q = "测试问题：AI 在数字 IC 设计里到底能做什么，哪些已经量产？"


def probe(mode):
    ev = []

    def p_round(self, entry, r):
        t = time.time()
        with _lock:
            ev.append((t, "R", entry, r))
        try:
            return _o_round(self, entry, r)
        finally:
            with _lock:
                ev.append((time.time(), "R", entry, -r))

    def p_layer(self, entry, rounds_n):
        t = time.time()
        with _lock:
            ev.append((t, "L", entry, 0))
        try:
            return _o_layer(self, entry, rounds_n)
        finally:
            with _lock:
                ev.append((time.time(), "L", entry, -1))

    def p_write(self, view, pool, entry, *a, **k):
        t = time.time()
        with _lock:
            ev.append((t, "W", entry, getattr(view, "entry", "?")))
        try:
            return _o_write(self, view, pool, entry, *a, **k)
        finally:
            with _lock:
                ev.append((time.time(), "W", entry, -1))

    def p_read(self, question, pool, view, *a, **k):
        # 读发生在函数最开头（拼 prompt），这里取入口时刻
        t = time.time()
        with _lock:
            ev.append((t, "D", "1", len(pool.amps or [])))
        try:
            return _o_read(self, question, pool, view, *a, **k)
        finally:
            with _lock:
                ev.append((time.time(), "D", "1", -1))

    diag = {"has_call": 0, "has_true": 0, "ext": 0}

    def p_has(view):
        diag["has_call"] += 1
        r = _o_has(view)
        if r:
            diag["has_true"] += 1
        return r

    def p_decq(self, question, *a, **k):
        diag["ext"] += 1
        return _o_decq(self, question, *a, **k)

    MetaDGTF._has_pool_content_view = staticmethod(p_has)
    DGTF._decompose_question = p_decq
    MetaDGTF._run_one_round_B = p_round
    MetaDGTF._run_layer = p_layer
    MetaDGTF._apply_view_to_pool = p_write
    DGTF._decompose_from_pool = p_read
    try:
        run_mode(mode, Q, verbose=False)
    finally:
        MetaDGTF._run_one_round_B = _o_round
        MetaDGTF._has_pool_content_view = _o_has
        DGTF._decompose_question = _o_decq
        MetaDGTF._run_layer = _o_layer
        MetaDGTF._apply_view_to_pool = _o_write
        DGTF._decompose_from_pool = _o_read

    ev.sort(key=lambda x: x[0])

    # 修行层写池区间（entry=="0" 的 W）
    w0 = []
    open_w = {}
    for t, k, a, b in ev:
        if k == "W" and a == "0" and b != -1:
            open_w[id(a)] = t
        elif k == "W" and a == "0" and b == -1:
            w0.append((open_w.pop(next(iter(open_w), None), t), t)) \
                if open_w else w0.append((t, t))
    # 修行层跑圈区间
    r0 = []
    open_r = {}
    for t, k, a, b in ev:
        if k == "R" and a == "0" and b > 0:
            open_r[b] = t
        elif k == "R" and a == "0" and b < 0:
            r0.append((open_r.pop(-b, t), t))
    # 读池时刻
    reads = [t for t, k, a, b in ev if k == "D" and b != -1]

    def overlap(t, spans):
        return [s for s in spans if s[0] <= t <= s[1]]

    return {
        "mode": mode,
        "reads": reads,
        "w0": w0,
        "r0": r0,
        "hit_w": sum(1 for t in reads if overlap(t, w0)),
        "hit_r": sum(1 for t in reads if overlap(t, r0)),
        "amp_at_read": [b for t, k, a, b in ev if k == "D" and b != -1],
        "diag": diag,
    }


print()
print("=" * 74)
print("研究层读修行池 × 修行层写池 —— 重叠检测（mock 环境）")
print("=" * 74)
print(f"{'模式':<7}{'读池次数':>9}{'撞上写池':>10}{'撞上跑圈':>10}"
      f"{'读时池内&数':>13}  结论")
print("-" * 74)
for m in MODES:
    d = probe(m)
    verdict = ("竞态成立" if d["hit_r"] else "无重叠") \
        if d["reads"] else "未走池路径"
    print(f"{d['mode']:<7}{len(d['reads']):>9}{d['hit_w']:>10}"
          f"{d['hit_r']:>10}{str(d['amp_at_read']):>13}  {verdict}"
          f"  [has0 {d['diag']['has_true']}/{d['diag']['has_call']}"
          f" ext {d['diag']['ext']}]")
print("-" * 74)
