# -*- coding: utf-8 -*-
"""[_run_verif.py] 真跑 wrapper（v1.21.67 起：**日志收全**）。

职责：
  load_dotenv → import 指定版本 → run → 边跑边写日志 → 追加元信息 →
  落三份产物（md / 摘要 json / packed 全量 json）。

★ v1.21.67 的日志收全（用户要求「让日志显示所有内容并完整输出」）：
  旧版只 `redirect_stdout`，于是**三类内容根本不进日志**：
    1. 引擎的 6 条 `logger.info`（模块方式导入时 `basicConfig` 没被调用 →
       根 logger 只剩 lastResort，INFO 被整条丢弃）；
    2. 49 条 `logger.warning` + 9 条 `logger.error`（只落到 stderr）；
    3. 引擎写到 stderr 的其它内容。
  新版：stdout / stderr **分流捕获并各自计数**、logging 挂显式 handler
  （INFO 起，写入同一日志）、wrapper 自己的消息也进日志、
  首尾打 BEGIN/END 哨兵，末尾输出一段**完整性统计**。
  并显式把 openai/httpx/httpcore 等降到 WARNING —— 否则 DEBUG 会把
  请求体（含 key）整个倒进日志。

用法：
  python _run_verif.py --src 元DGTF-V1.21.67.py \
      --route 0,1 --rounds "0:4,1:5" --mode serial \
      --orientation decision --tag C_tension --question "..."
"""
import argparse
import contextlib
import importlib.util
import io
import json
import logging
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

_REAL_OUT = sys.stdout          # 回显用（重定向期间也能写控制台）

# 降噪：这些库在 INFO/DEBUG 下会把请求体（含 key）整个倒出来
_NOISY = ("openai", "httpx", "httpcore", "urllib3", "asyncio",
          "jieba", "charset_normalizer", "filelock")


class _Cap:
    """把写入搬到日志文件，同时按行计数（用于日志完整性自检）。

    ★ 补齐 stream 的常见属性（encoding / errors / buffer / mode）：
      引擎与第三方库会读 `sys.stdout.encoding`、也可能走 `.buffer`，
      缺属性会在深处抛 AttributeError，把「日志收全」变成新的故障源。
    """

    encoding = "utf-8"
    errors = "replace"
    mode = "w"

    def __init__(self, fh, tag, counter):
        self._fh, self._tag, self._c = fh, tag, counter

    @property
    def buffer(self):
        return getattr(self._fh, "buffer", self._fh)

    def write(self, s):
        if s:
            self._fh.write(s)
            self._c[self._tag] = self._c.get(self._tag, 0) + s.count("\n")
        return len(s) if s else 0

    def flush(self):
        try:
            self._fh.flush()
        except Exception:
            pass

    def isatty(self):
        return False

    def fileno(self):
        return self._fh.fileno()


class _CountHandler(logging.Handler):
    """logging → 同一个日志文件，并按级别计数。"""

    def __init__(self, fh, counter):
        super().__init__()
        self._fh, self._c = fh, counter

    def emit(self, record):
        try:
            self._c[record.levelname] = \
                self._c.get(record.levelname, 0) + 1
            self._fh.write(self.format(record) + "\n")
        except Exception:
            pass


def load_dotenv(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8",
                               errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="元DGTF-V1.21.67.py")
    ap.add_argument("--route", default="0,1,both,all")
    ap.add_argument("--rounds", default="0")
    ap.add_argument("--mode", default="serial")
    ap.add_argument("--orientation", default="auto")
    ap.add_argument("--tag", default="verif")
    ap.add_argument("--min-rounds", default=None,
                    help='按层的圈数下限（JSON，如 \'{"1": 5}\'）。'
                         "★ 必须在 load_config **之后**显式改 cfg —— "
                         "yaml 一旦写了某个键，_deep_merge 会让环境变量失效"
                         "（本项目的老坑）。")
    ap.add_argument("--question", required=True)
    a = ap.parse_args()

    log_path = HERE / f"verif_{a.tag}.log"
    LOG = io.open(log_path, "w", encoding="utf-8", buffering=1)
    counters = {"out": 0, "err": 0}

    def emit(msg):
        """wrapper 自己的消息：同时进日志与控制台。"""
        LOG.write(str(msg) + "\n")
        LOG.flush()
        try:
            print(msg, file=_REAL_OUT, flush=True)
        except Exception:
            pass

    t0 = time.time()
    emit(f"############ LOG BEGIN {time.strftime('%Y-%m-%dT%H:%M:%S')} ############")
    emit(f"[banner] src={a.src} route={a.route} rounds={a.rounds} "
         f"mode={a.mode} orientation={a.orientation} tag={a.tag}")
    emit(f"[question] {a.question}")
    emit(f"[cwd] {HERE}")

    load_dotenv(HERE / ".env")
    spec = importlib.util.spec_from_file_location("dgtf_verif", HERE / a.src)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_verif"] = mod
    spec.loader.exec_module(mod)
    emit(f"[module] {a.src}  __version__={getattr(mod, '__version__', '?')}")

    cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
    cfg["output"]["verbose"] = True
    if a.min_rounds:
        _mr = json.loads(a.min_rounds)
        _cur = dict((cfg.get("spiral") or {}).get("min_rounds") or {})
        _cur.update({str(k): int(v) for k, v in _mr.items()})
        cfg.setdefault("spiral", {})["min_rounds"] = _cur
        emit(f"[min_rounds] 运行时覆盖 → {_cur}"
             "（刻意不写回出厂配置）")

    route = [x.strip() for x in a.route.split(",") if x.strip()]
    rounds = a.rounds
    if ":" not in str(rounds):
        try:
            rounds = int(rounds)
        except ValueError:
            pass

    # ★ logging 全量进同一个日志（INFO 起；噪声库显式降级）
    logging.basicConfig(level=logging.INFO,
                        handlers=[_CountHandler(LOG, counters)],
                        format="[%(levelname)s] %(name)s: %(message)s",
                        force=True)
    for _n in _NOISY:
        logging.getLogger(_n).setLevel(logging.WARNING)
    emit(f"[logging] 根 logger=INFO，handler 写入本日志；"
         f"降噪：{'、'.join(_NOISY)}")

    res, err, meta = None, None, None
    cap_out = _Cap(LOG, "out", counters)
    cap_err = _Cap(LOG, "err", counters)
    emit("--- engine 输出开始（stdout 与 stderr 都进本日志）---")
    try:
        with contextlib.redirect_stdout(cap_out), \
                contextlib.redirect_stderr(cap_err):
            meta = mod.MetaDGTF(cfg)
            res = meta.run(a.question, parallel_mode=a.mode, rounds=rounds,
                           route=route, orientation=a.orientation)
    except Exception:
        import traceback
        err = traceback.format_exc()
    emit("--- engine 输出结束 ---")
    dt = time.time() - t0

    emit(f"[timing] {dt:.0f}s = {dt / 60:.1f}min")
    emit(f"[served_by] {sorted(meta.llm.SERVED_SEEN) if meta else '?'}")
    emit(f"[completeness] stdout 行 {counters.get('out', 0)}｜"
         f"stderr 行 {counters.get('err', 0)}｜"
         f"logging "
         + "、".join(f"{k}={v}" for k, v in sorted(counters.items())
                     if k not in ("out", "err"))
         + f"｜异常：{'无' if not err else '有（见文末）'}")

    if res is not None:
        emit(f"[counts] llm_calls={res['llm_calls']} "
             f"tokens={res['llm_tokens']}")
        emit(f"[dispatch] order={res['dispatch'].get('order')} "
             f"missing={res['dispatch'].get('missing')} "
             f"skipped={res['dispatch'].get('skipped')}")
        emit(f"[views] {sorted(res['views'])}｜tri_state={res.get('tri_state')}")
        try:
            with contextlib.redirect_stdout(cap_out):
                p = mod.save_result(res, str(HERE / "outputs"))
            emit(f"[artifacts] 产物={p}")
        except Exception:
            import traceback as _tb
            emit("❌ 产物落盘失败：\n" + _tb.format_exc())
    if err:
        emit("[exception traceback]\n" + err)

    # ---- packed 全量侧车（与产物 md 的附录同源，便于工具链读取） ----
    if res is not None:
        try:
            _full = json.dumps(res, ensure_ascii=False, indent=1, default=str)
            _fp = HERE / f"verif_{a.tag}.full.json"
            _fp.write_text(_full, encoding="utf-8")
            emit(f"[artifacts] packed 全量={_fp.name}"
                 f"（{len(_full)} 字符）")
        except Exception:
            import traceback
            emit("⚠️ packed 全量落盘失败：\n" + traceback.format_exc())
        # ---- 摘要侧车（原有，保留） ----
        try:
            _views = res.get("views") or {}
            _pools = res.get("pools") or {}
            summary = {
                "tag": a.tag, "src": a.src, "route": a.route,
                "rounds": a.rounds, "mode": a.mode,
                "orientation": a.orientation,
                "llm_calls": res.get("llm_calls"),
                "tri_state": res.get("tri_state"),
                "meta_closure_all": (_views.get("all") or {}).get(
                    "meta_closure"),
                "duel_suspensions_both": [
                    {"id": s.get("id"), "target": s.get("target"),
                     "status": s.get("status"),
                     "quadrant": s.get("quadrant")}
                    for s in ((_pools.get("both") or {}).get(
                        "duel_suspensions") or [])],
                "engagements_by_view": {
                    k: [{"target": e.get("target"),
                         "tension_id": e.get("tension_id")}
                        for e in ((v or {}).get("engagements") or [])]
                    for k, v in _views.items()},
                "suspensions_with_tid": {
                    k: [{"target": x.get("target"),
                         "tension_id": x.get("tension_id"),
                         "status": x.get("status")}
                        for x in ((v or {}).get("suspensions") or [])]
                    for k, v in _views.items()},
                "pools_all_engagements": [
                    {"target": e.get("target"),
                     "tension_id": e.get("tension_id")}
                    for e in ((_pools.get("all") or {}).get(
                        "engagements") or [])],
                "views_errors": {k: list((v or {}).get("errors") or [])
                                 for k, v in _views.items()},
                "pools_meta_p16": {
                    k: [m for m in ((p or {}).get("meta") or [])
                        if "[P1-6]" in m]
                    for k, p in _pools.items()},
                "pools_meta_len": {k: len((p or {}).get("meta") or [])
                                   for k, p in _pools.items()},
            }
            _sp = HERE / f"verif_{a.tag}.json"
            _sp.write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            emit(f"[artifacts] 摘要={_sp.name}")
        except Exception:
            import traceback
            emit("⚠️ packed 摘要落盘失败：\n" + traceback.format_exc())

    emit(f"############ LOG END {time.strftime('%Y-%m-%dT%H:%M:%S')} ############")
    LOG.close()

    print(f"[{a.tag}] {'OK' if res else 'FAIL'}  {dt / 60:.1f}min  calls="
          f"{res['llm_calls'] if res else '-'}  → {log_path.name}")
    return 0 if res else 1


if __name__ == "__main__":
    sys.exit(main())
