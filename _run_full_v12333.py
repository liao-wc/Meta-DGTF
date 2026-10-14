#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全开真跑（v1.23.33+）：**一次性把所有开关打开**跑一轮，用于①补待办验收
②积累真跑数据以调优默认配置 ③让 EML 在真跑里学习。

口径（用户要求）：
  · 默认每次真跑**全开**；只有做针对性验收时才收窄。
  · **不动出厂 yaml** —— 全开是在内存里就地覆盖（守住「新能力默认关 ⇒ 零行为差」纪律）；
    等真跑数据出来后再按数据决定「哪些键值得改出厂默认」，那时才动 yaml。

全开清单（会打印留痕）：
  route = 0,1,both,all（四层齐）· rounds = 4/4/4/5（CSD/发散需 ≥4 圈）
  web=on · thinking=on · effort=high
  playbook.mode=on（EML 生效）· stop.anytime_alpha=0.05（anytime 停止生效）
  auto.bandit.enabled=True · belief.merge_semantic=True · sem_entropy_thr=rel
  duty.* = 出厂（0.35/0.02/2/1）· auto.enabled=True（自适应调度）

★ 看门狗：日志 **900 秒无新增** ⇒ 判停滞、打印 STALL、退出码 9
  （本轮 API 侧连续两次停滞，必须能自动识别并重试）。
"""
import argparse
import contextlib
import importlib.util
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
_NOISY = ("openai", "httpx", "httpcore", "urllib3", "asyncio", "jieba",
          "charset_normalizer", "filelock")


class _Cap:
    def __init__(self, path, tag):
        self.path, self.tag, self.n = path, tag, 0

    def write(self, s):
        if not s:
            return
        self.n += 1
        try:
            with open(self.path, "a", encoding="utf-8", errors="replace") as f:
                f.write(s)
        except Exception:
            pass

    def flush(self):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="元DGTF-V1.23.33.py")
    ap.add_argument("--tag", default="FULL")
    ap.add_argument("--question", required=True)
    ap.add_argument("--stall-sec", type=int, default=900)
    a = ap.parse_args()

    log = HERE / ("_fullrun_%s.log" % a.tag)
    log.write_bytes(b"")
    lock = threading.Lock()

    def emit(s):
        with lock:
            with open(log, "a", encoding="utf-8", errors="replace") as f:
                f.write(str(s) + "\n")
            print(s)

    # ── 载入引擎 ──
    spec = importlib.util.spec_from_file_location("dgtf_full", HERE / a.src)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_full"] = mod
    spec.loader.exec_module(mod)
    emit("[module] %s  __version__=%s" % (a.src, getattr(mod, "__version__", "?")))

    # ── 全开（**单一真相源**：一律走引擎 `_ALL_ON_ITEMS`，本脚本不另存清单）──
    #   ★ 血泪教训：本脚本曾自带一份 `_set(...)` 手写清单，与引擎 `_ALL_ON_ITEMS`
    #     双份漂移 ⇒ 写成 `api.thinking=True`（本该是 dict）⇒ 真跑首圈即
    #     `AttributeError: 'bool' object has no attribute 'get'`。凡「同一语义两处
    #     定义」必漂移，故这里**只读引擎的清单**并回读实际生效值。
    cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
    cfg.setdefault("output", {})["verbose"] = True
    if not cfg.get("all_on"):
        # 出厂 yaml 若被改成 false，脚本侧兜底再显式展开一次（同样走引擎函数）。
        cfg, _ao = mod._apply_all_on(dict(cfg, all_on=True))
    emit("[全开清单]（单一真相源 = 引擎 _ALL_ON_ITEMS；本脚本只回读，不另存）")

    def _get(path):
        d = cfg
        for k in str(path).split("."):
            if not isinstance(d, dict):
                return "<路径断>"
            d = d.get(k, "<缺>")
        return d

    for p, v, w in mod._ALL_ON_ITEMS:
        got = _get(p)
        flag = "✓" if got == v else "✗(实际=%r)" % (got,)
        emit("   %-28s 期望=%-10s %s  # %s" % (p, repr(v), flag, w))

    # ★ 题型矩阵可通过环境变量收窄 route/rounds（默认=四层全开）。
    _r = os.environ.get("FULLRUN_ROUTE")
    route = ([x.strip() for x in _r.split(",") if x.strip()]
             if _r else ["0", "1", "both", "all"])
    _rd = os.environ.get("FULLRUN_ROUNDS")
    if _rd:
        try:
            rounds = {str(k): int(v) for k, v in json.loads(_rd).items()}
        except Exception:
            rounds = {"0": 4, "1": 4, "both": 4, "all": 5}
    else:
        rounds = {"0": 4, "1": 4, "both": 4, "all": 5}
    emit("[route] %s | [rounds] %s（CSD/发散需 ≥4 圈）" % (route, rounds))
    mode = os.environ.get("FULLRUN_MODE", "serial")
    emit("[mode] %s" % mode)

    for _n in _NOISY:
        logging.getLogger(_n).setLevel(logging.WARNING)
    logging.basicConfig(level=logging.INFO,
                        handlers=[logging.FileHandler(log, encoding="utf-8")],
                        format="[%(levelname)s] %(name)s: %(message)s", force=True)

    # ── 停滞看门狗 ──
    stop = {"v": False}

    def _watch():
        last, t_last = -1, time.time()
        while not stop["v"]:
            time.sleep(20)
            try:
                sz = log.stat().st_size
            except Exception:
                continue
            if sz != last:
                last, t_last = sz, time.time()
            elif time.time() - t_last > a.stall_sec:
                emit("[STALL] 日志 %d 秒无新增（size=%d）⇒ 判停滞，退出码 9"
                     % (a.stall_sec, sz))
                os._exit(9)

    threading.Thread(target=_watch, daemon=True).start()

    res = None
    t0 = time.time()
    cap = _Cap(log, "out")
    # ★ 真跑**必须显式给 run_id**：否则 EML 写库闸判匿名 ⇒ 跳过 ⇒ 跨跑学习失效。
    _run_id = "%s_%s" % (a.tag, time.strftime("%Y%m%d_%H%M%S"))
    emit("[run_id] %s（真跑记账；无 id 的调用被 EML 闸判匿名跳过）" % _run_id)
    try:
        with contextlib.redirect_stdout(cap), contextlib.redirect_stderr(cap):
            meta = mod.MetaDGTF(cfg)
            res = meta.run(a.question, parallel_mode=mode, rounds=rounds,
                           route=route, orientation="auto", run_id=_run_id)
    except Exception:
        import traceback
        emit("[异常]\n" + traceback.format_exc())
    stop["v"] = True
    dt = time.time() - t0
    emit("[timing] %.0fs = %.1fmin" % (dt, dt / 60))

    if res is not None:
        emit("[counts] calls=%s tokens=%s" % (res.get("llm_calls"),
                                             res.get("llm_tokens")))
        try:
            p = mod.save_result(res, str(HERE / "outputs"))
            emit("[artifacts] %s" % p)
        except Exception:
            import traceback
            emit("[save_result 异常]\n" + traceback.format_exc())
        try:
            (HERE / ("_fullrun_%s.json" % a.tag)).write_text(
                json.dumps({k: res.get(k) for k in
                            ("llm_calls", "llm_tokens", "llm_ops_calls",
                             "llm_eval_calls", "tri_state", "tri_alpha",
                             "diversity", "compact", "belief_staleness",
                             "bandit", "playbook")},
                           ensure_ascii=False, indent=1, default=str),
                encoding="utf-8")
            emit("[摘要] _fullrun_%s.json" % a.tag)
        except Exception:
            pass
        # ★ [层目标] 额外落一份四层目标读数（**第九轮验收要点**：读数是用户
        #   战略指令的落点，必须在**真实产物**里有值，不能只在纯函数里绿）。
        try:
            _gr = {}
            for _L, _v in (res.get("views") or {}).items():
                try:
                    _vd = _v.to_dict() if hasattr(_v, "to_dict") else _v
                except Exception:
                    _vd = {}
                _gr[_L] = _vd
            _sum = mod.layer_goal_readings(_gr)
            (HERE / ("_fullrun_%s.goals.json" % a.tag)).write_text(
                json.dumps(_sum, ensure_ascii=False, indent=1, default=str),
                encoding="utf-8")
            emit("[层目标] _fullrun_%s.goals.json" % a.tag)
            for _L in ("0", "1", "both", "all"):
                _d = _sum.get(_L) or {}
                emit("   %-5s %s" % (_L, json.dumps(
                    {k: _d.get(k) for k in
                     ("key", "value", "excavate", "settle", "fuse",
                      "crystallize", "pseudo_convergence", "sem_stagnation",
                      "converging", "n_aspects", "n_new", "n_hits")
                     if k in _d}, ensure_ascii=False)))
        except Exception:
            import traceback
            emit("[层目标 异常]\n" + traceback.format_exc())
    emit("[DONE] 退出码 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
