# -*- coding: utf-8 -*-
"""本地服务显存碎片回收判据（零 API，不需要 8772 在线）。

背景（实测 2026-10-28）：服务连跑 7 小时后 `memory_reserved` 涨到 5818MB
（冷启基线 1075MB），推理慢约 10 倍，把 `test_judge_fastfail` 从 15.5s 拖到
307s 并**判红（假红）**；重启服务后显存回到 1561MB、判据立刻恢复。
⇒ 这是会污染门禁的缺陷，不是「慢一点」。

判据分两层：
  1. **纯函数**（`should_reclaim`）：什么状态该回收、什么状态不该。
     两个方向都测 —— 只测「该回收」会放过「正常状态也回收」的过度回收，
     那会白白增加分配开销。
  2. **接线**：worker 真的调用了它（且只在队列空时调）。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

P, F = [], []

MB = 1024 * 1024


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


def main() -> int:
    # ★ 从 gates 拿纯函数（不带 torch），service 只是使用方
    from dgtf_local_llm.gates import should_reclaim

    # ---- 1. 该回收：保留量远大于实占 ----
    ck("R1 实占 1GB / 保留 5GB ⇒ 该回收", should_reclaim(1024 * MB, 5120 * MB) is True)
    ck("R2 实占 0 / 保留 600MB ⇒ 该回收（超过 slack）",
       should_reclaim(0, 600 * MB) is True)
    ck("R3 实测形态：实占 1075MB / 保留 5818MB ⇒ 该回收",
       should_reclaim(1075 * MB, 5818 * MB) is True)

    # ---- 2. 不该回收：正常态与 slack 保护 ----
    ck("R4 实占 1GB / 保留 1.1GB ⇒ 不回收", should_reclaim(1024 * MB, 1126 * MB) is False)
    ck("R5 实占 0 / 保留 400MB ⇒ 不回收（slack 兜住小量）",
       should_reclaim(0, 400 * MB) is False)
    ck("R6 实占=保留 ⇒ 不回收", should_reclaim(2048 * MB, 2048 * MB) is False)
    ck("R7 输入非法不崩、按不回收处理",
       should_reclaim(None, "x") is False)

    # ---- 3. 接线：worker 里真的调了，且受队列空门控 ----
    src = (ROOT / "dgtf_local_llm" / "service.py").read_text(encoding="utf-8")
    ck("W1 worker 调用 _maybe_empty_cache", "self._maybe_empty_cache()" in src)
    ck("W2 调用受「队列空」门控（忙时不回收，免得拖吞吐）",
       "if self.queue_depth <= 0:" in src)
    ck("W3 回收计数进 stats（可观测，不是只写日志）",
       '"mem_reclaims"' in src)
    ck("W4 service 使用 gates.py 的唯一实现（不是复制一份逻辑）",
       "from dgtf_local_llm.gates import should_reclaim" in src)
    ck("W5 _maybe_empty_cache 存在",
       "def _maybe_empty_cache" in src)

    # ---- 4. 真实服务（若在线）：确认统计字段存在 ----
    import json
    import urllib.request
    try:
        raw = urllib.request.urlopen(
            "http://127.0.0.1:8772/metrics", timeout=5).read().decode()
        m = json.loads(raw)
        st = m.get("stats") or {}
        ck("S1 在线服务 /metrics 可读", bool(m.get("ok")))
        # ★ 不能要求「有请求就必须有 mem_reclaims」：回收只在碎片多时发生，
        #   正常态本来就不该有。这里只验「字段名一旦出现就是可读的」，
        #   真正的「会回收」由 E1/E2 构造性证明。
        ck("S2 在线服务 /metrics 可读且 stats 是 mapping",
           isinstance(st, dict) and "requests_total" in st, st)
    except Exception as e:  # noqa: BLE001
        print("  · SKIP 在线服务检查（%s）" % type(e).__name__)

    # ---- 5. 构造性验证：判定为真时**真的**调了 empty_cache 并记账 ----
    #   ★ 短压测（12 个请求）不会产生足够碎片，所以「会回收」这件事必须
    #     用构造态证明，不能等到某天长跑出问题再说。打在**更下层**
    #     （torch.cuda.empty_cache 本身），不是替换被测函数。
    import subprocess
    envpy = ROOT / "local_model" / "envs" / "dgtf_llm_env" / "Scripts" / "python.exe"
    if envpy.exists():
        code = (
            "import sys, threading\n"
            "sys.path.insert(0, r'%s')\n"
            "import torch\n"
            "calls = {'n': 0}\n"
            "torch.cuda.is_available = lambda: True\n"
            "torch.cuda.empty_cache = lambda: calls.__setitem__('n', calls['n'] + 1)\n"
            "torch.cuda.memory_allocated = lambda: 1024 * 1024 * 1024\n"
            "torch.cuda.memory_reserved = lambda: 6 * 1024 * 1024 * 1024\n"
            "import dgtf_local_llm.service as S\n"
            "e = S.LocalEngine.__new__(S.LocalEngine)\n"
            "e._lock = threading.Lock()\n"
            "e.stats = {}\n"
            "e.queue_depth = 0\n"
            "e._maybe_empty_cache()\n"
            "print('RESULT %%d %%s' %% (calls['n'], e.stats.get('mem_reclaims')))\n"
        ) % str(ROOT)
        try:
            r = subprocess.run([str(envpy), "-c", code], capture_output=True,
                               text=True, timeout=180)
            line = [x for x in (r.stdout or "").splitlines() if x.startswith("RESULT")]
            got = line[0].split()[1:] if line else []
            ck("E1 碎片态下真的调用 empty_cache（不是只写日志）",
               len(got) == 2 and got[0] == "1", (r.stdout or "")[-200:] + (r.stderr or "")[-200:])
            ck("E2 回收被记账到 stats.mem_reclaims",
               len(got) == 2 and got[1] == "1", got)
        except Exception as e:  # noqa: BLE001
            ck("E1/E2 构造性验证可执行", False, type(e).__name__)
    else:
        print("  · SKIP 构造性验证（无本地 env python）")

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    for f in F:
        print("  - " + f)
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
