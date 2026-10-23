"""九模式对比：打点每层每圈的开始/结束，算并发度与加速比。

只做测量，不改任何被测代码。跑完自动删除。
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
run_mode = ns["run_mode"]

_lock = threading.Lock()
_orig_round = MetaDGTF._run_one_round_B
_orig_layer = MetaDGTF._run_layer

MODES = ["serial", "A", "B", "C", "D", "E", "F", "G", "H"]
Q = "测试问题：AI 在数字 IC 设计里到底能做什么，哪些已经量产？"


def measure(mode):
    t0 = time.time()
    ev = []

    done = {"0": 0, "1": 0, "both": 0, "all": 0}
    fresh = {}

    def patched_round(self, entry, r):
        st = time.time()
        with _lock:
            # 开跑那一刻，各上游已经交出了几圈 —— 语义新鲜度
            fresh[(entry, r)] = dict(done)
            ev.append((st, "s", entry, r))
        try:
            return _orig_round(self, entry, r)
        finally:
            with _lock:
                done[entry] = max(done[entry], r)
                ev.append((time.time(), "e", entry, r))

    def patched_layer(self, entry, rounds_n):
        # serial / A 走整层通道，粒度是"层"不是"圈"，记成 r=0
        st = time.time()
        with _lock:
            ev.append((st, "s", entry, 0))
        try:
            return _orig_layer(self, entry, rounds_n)
        finally:
            with _lock:
                ev.append((time.time(), "e", entry, 0))

    MetaDGTF._run_one_round_B = patched_round
    MetaDGTF._run_layer = patched_layer
    try:
        row = run_mode(mode, Q, verbose=False)
    finally:
        MetaDGTF._run_one_round_B = _orig_round
        MetaDGTF._run_layer = _orig_layer
    wall = time.time() - t0
    ev.sort(key=lambda x: x[0])
    base = ev[0][0]

    # 每层的 (start, end) 区间
    iv = {}
    for t, k, e, r in ev:
        if k == "s":
            iv[(e, r)] = [t - base, None]
        else:
            iv[(e, r)][1] = t - base
    work = sum(b - a for a, b in iv.values())
    span = max(b for a, b in iv.values()) - min(a for a, b in iv.values())

    # 峰值并发：在每圈的起点采样，数有几个区间覆盖它
    peak = 0
    for a, b in iv.values():
        n = sum(1 for x, y in iv.values() if x <= a < y)
        peak = max(peak, n)

    first = {}
    last = {}
    for (e, r), (a, b) in iv.items():
        first.setdefault(e, a)
        last[e] = max(last.get(e, 0), b)

    return {
        "mode": mode,
        "calls": row["calls"],
        "care": row["carry"],
        "self_layers": row["self_layers_n"],
        "dec": row["dec_src"],
        "warmup": row["warmup"],
        "work": work,
        "span": span,
        "wall": wall,
        "speedup": work / span if span else 0,
        "peak": peak,
        "first": first,
        "last": last,
        "fresh": fresh,
        "rounds": sorted(iv.keys()),
    }


rows = [measure(m) for m in MODES]

print()
print("=" * 78)
print("九模式对比（mock 环境，四层各 2 圈；work=各圈耗时之和，span=首圈起点→末圈终点）")
print("=" * 78)
print(f"{'模式':<7}{'调用':>5}{'care':>5}{'self层':>6}{'峰值并发':>8}"
      f"{'work(s)':>9}{'span(s)':>9}{'加速比':>7}{'预热':>5}  判定源")
print("-" * 78)
for r in rows:
    print(f"{r['mode']:<7}{r['calls']:>5}{r['care']:>5}{r['self_layers']:>6}"
          f"{r['peak']:>8}{r['work']:>9.3f}{r['span']:>9.3f}"
          f"{r['speedup']:>7.2f}{str(r['warmup']):>5}  {r['dec']}")
print("-" * 78)

print()
print("各层首圈出发 / 末圈收工（秒，相对最早一圈的起点）")
print(f"{'模式':<7}{'修行0':>16}{'研究1':>16}{'对撞both':>16}{'元all':>16}")
print("-" * 78)
for r in rows:
    cells = []
    for e in ("0", "1", "both", "all"):
        a = r["first"].get(e)
        b = r["last"].get(e)
        cells.append(f"{a:.3f}→{b:.3f}" if a is not None else "-")
    print(f"{r['mode']:<7}" + "".join(f"{c:>16}" for c in cells))
print("-" * 78)

print()
print("下游开跑时已吃到的上游圈数（第 1 圈 / 第 2 圈；'-' 表示走整层通道不吃圈）")
print(f"{'模式':<7}{'对撞both吃 0/1':>22}{'元all吃 0/1/both':>26}")
print("-" * 78)
for r in rows:
    f = r["fresh"]
    b1 = f.get(("both", 1))
    b2 = f.get(("both", 2))
    a1 = f.get(("all", 1))
    a2 = f.get(("all", 2))

    def fmt(snap, keys):
        if not snap:
            return "-"
        return "/".join(str(snap.get(k, 0)) for k in keys)

    bs = " ".join([fmt(b1, ("0", "1")), fmt(b2, ("0", "1"))])
    as_ = " ".join([fmt(a1, ("0", "1", "both")),
                    fmt(a2, ("0", "1", "both"))])
    print(f"{r['mode']:<7}{bs:>22}{as_:>26}")
print("-" * 78)
