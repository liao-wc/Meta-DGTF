# -*- coding: utf-8 -*-
"""v1.23.49 · 修「run() 只在返回后写盘 ⇒ 中断全丢」。

**根因**：`MetaDGTF.run()` 是 60 分钟级长跑，`packed` 只在 `return` 前才组装、
调用方只在 `run()` **返回后**才写盘 ⇒ 宿主一回收进程，连层 0 的五圈都消失
（今天 12:37 真跑就这么丢了 ~24 分钟 / ~¥2）。

**解法（三层，SOTA 的 checkpoint + WAL + orphan recovery）**：
  1. **跑中快照**：`run()` 起一个 daemon 心跳线程，每 `runtime.ckpt_interval` 秒把
     `self._results`（各层 View 的 `to_dict()`）+ 元信息**原子**落盘
     （tmp + `os.replace` ⇒ 被强杀也不会写坏一半）。
  2. **一处插入、覆盖所有模式**：serial / A / B / C / graph 全走同一处 dispatch，
     在 dispatch 前起、dispatch 后停 ⇒ 不碰那 5 个实现（避开「同一逻辑两份」坑）。
  3. **孤儿回收**：`recover_orphan_runs()` 把「起跑过但没收尾」的快照回填
     `interrupted` + 原因（幂等）—— 红线「失败留痕」的加强，不是新规矩。

★ 配置式：`runtime.live_checkpoint` **默认 false** ⇒ 不起线程、逐字零行为差。
"""
import ast
from pathlib import Path

TGT = Path("元DGTF-V1.23.49.py")

FNS = '''

_RUN_CKPT_DIRNAME = "_run_ckpt"     # 跑中快照目录名（挂在 outputs/ 下）
_RUN_CKPT_INTERVAL = 30.0           # 心跳间隔（秒）
_RUN_CKPT_STALE = 900.0             # 超过这么久还 `running` ⇒ 判孤儿


def run_ckpt_dir(base=None) -> Path:
    """跑中快照目录（默认 `<repo>/outputs/_run_ckpt/`；建不动也不抛）。"""
    _b = Path(base) if base else (Path(__file__).resolve().parent / "outputs")
    _d = _b / _RUN_CKPT_DIRNAME
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return _d


def run_ckpt_path(run_id: str, base=None) -> Path:
    return run_ckpt_dir(base) / ("%s.json" % str(run_id or "anon"))


def write_run_ckpt(run_id: str, payload: dict, base=None) -> Path:
    """**原子**写跑中快照：先写 `.tmp` 再 `os.replace` ⇒ 被强杀也不会留半份。"""
    p = run_ckpt_path(run_id, base)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1,
                              default=str), encoding="utf-8")
    os.replace(str(tmp), str(p))
    return p


def _ckpt_snapshot(engine, run_id: str, status: str, extra: dict = None) -> dict:
    """从引擎抽一份可恢复状态（各层 View 的 `to_dict()` + 元信息）。

    ★ `to_dict()` 拿不到 ⇒ 该层记 `{"_unserializable": ...}`，**不静默丢层**。
    """
    views = {}
    for _e, _v in (getattr(engine, "_results", None) or {}).items():
        try:
            views[str(_e)] = _v.to_dict() if hasattr(_v, "to_dict") else dict(_v)
        except Exception as _e2:  # noqa: BLE001
            views[str(_e)] = {"_unserializable": "%s: %s"
                              % (type(_e2).__name__, _e2)}
    out = {"id": str(run_id), "status": str(status),
           "engine": ENGINE_VERSION,
           "question": str(getattr(engine, "_question", "") or "")[:400],
           "route": list(getattr(engine, "_route", None) or []),
           "n_views": len(views), "views": views,
           "t": time.time()}
    if extra:
        out.update(extra)
    return out


def start_run_ckpt(engine, run_id: str, interval: float = _RUN_CKPT_INTERVAL):
    """起**daemon** 心跳线程（返回 stop 回调；`interval<=0` ⇒ 不起，返回 None）。

    ★ daemon=True：进程被强杀时它跟着死，**不会挡住退出**；
      且每 `interval` 秒落一次 ⇒ 最多丢一个间隔的状态，不是整跑。
    """
    _rid = str(run_id or "").strip()
    _iv = float(interval or 0.0)
    if not _rid or _iv <= 0:
        return None
    import threading
    _stop = threading.Event()

    def _beat():
        while not _stop.wait(_iv):
            try:
                write_run_ckpt(_rid, _ckpt_snapshot(engine, _rid, "running"))
            except Exception:  # noqa: BLE001
                pass            # 写盘失败绝不能弄崩跑本身

    _th = threading.Thread(target=_beat, name="run_ckpt_%s" % _rid,
                           daemon=True)
    _th.start()
    return _stop


def stop_run_ckpt(stop_evt, engine=None, run_id: str = "",
                  status: str = "done") -> None:
    """停心跳并落**最后一份**（`status=done` 或调用方给的原因）。"""
    if stop_evt is not None:
        try:
            stop_evt.set()
        except Exception:  # noqa: BLE001
            pass
    if engine is not None and str(run_id or "").strip():
        try:
            write_run_ckpt(str(run_id),
                           _ckpt_snapshot(engine, str(run_id), str(status)))
        except Exception:  # noqa: BLE001
            pass


def recover_orphan_runs(base=None, stale_sec: float = _RUN_CKPT_STALE,
                        now: float = None) -> list:
    """把「起跑过但没收尾」的快照回填 `interrupted` + 原因（**幂等**）。

    口径与 `dgtf_app` 的 `recover_orphans()` 一致：痕迹本身就是那份文件，
    状态字段从 `running` 改 `interrupted`，已 `interrupted` 的不再改。
    """
    _now = float(now if now is not None else time.time())
    out = []
    for p in sorted(run_ckpt_dir(base).glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(d, dict) or str(d.get("status")) != "running":
            continue
        _age = _now - float(d.get("t") or 0.0)
        if _age < float(stale_sec):
            continue
        d["status"] = "interrupted"
        d["interrupted_why"] = ("起跑后 %.0f 秒无更新（超过 %.0f）—— 进程被回收/崩溃"
                                % (_age, float(stale_sec)))
        try:
            write_run_ckpt(str(d.get("id") or p.stem), d, base=base)
        except Exception:  # noqa: BLE001
            continue
        out.append({"id": d.get("id"), "why": d["interrupted_why"]})
    return out

'''

START_OLD = '''        if mode == "A":
            packed = self._run_parallel_A(question, route, keep,
                                          rounds_plan, channels)'''
START_NEW = '''        # ★ [v1.23.49 · 跑中快照] 长跑中断不再全丢。配置式：默认关 ⇒ 零行为差。
        #   （今天 12:37 的真跑被宿主回收，24 分钟 / ~¥2 连层 0 都没留下。）
        _ck_stop = None
        _ck_rid = str(getattr(self, "_run_id", "") or "").strip()
        _ck_on = False
        try:
            _ck_on = bool((self.config.get("runtime") or {}).get(
                "live_checkpoint", False))
        except Exception:
            _ck_on = False
        if _ck_on and _ck_rid:
            try:
                _ck_iv = float((self.config.get("runtime") or {}).get(
                    "ckpt_interval", _RUN_CKPT_INTERVAL) or _RUN_CKPT_INTERVAL)
            except Exception:
                _ck_iv = _RUN_CKPT_INTERVAL
            _ck_stop = start_run_ckpt(self, _ck_rid, _ck_iv)
        if mode == "A":
            packed = self._run_parallel_A(question, route, keep,
                                          rounds_plan, channels)'''

STOP_OLD = '''        else:
            packed = self._run_serial(question, route, keep,
                                      rounds_plan, channels)
        if isinstance(packed, dict):'''
STOP_NEW = '''        else:
            packed = self._run_serial(question, route, keep,
                                      rounds_plan, channels)
        # ★ 停心跳 + 落最后一份（dispatch 已返回 ⇒ 这一跑有了结果）
        if _ck_stop is not None:
            stop_run_ckpt(_ck_stop, self, _ck_rid, "done")
        if isinstance(packed, dict):'''

CFG_OLD = '    "runtime": {\n'
CFG_NEW = ('    "runtime": {\n'
           '        # [v1.23.49] 跑中快照（心跳线程周期落盘）：默认 false = 不起线程。\n'
           '        #   true ⇒ 每 ckpt_interval 秒把各层 View 原子落一份到\n'
           '        #   outputs/_run_ckpt/<run_id>.json；崩了由 recover_orphan_runs()\n'
           '        #   回填 interrupted（失败留痕的加强）。\n'
           '        "live_checkpoint": False,\n'
           '        "ckpt_interval": 30.0,\n')


def _rw(path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s
    ast.parse(s2)
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\n") == out.count(b"\r\n")
    path.write_bytes(out)
    return out.decode("utf-8")


def apply(s):
    a = "class MetaDGTF:"
    assert s.count(a) == 1, "类锚点 %d" % s.count(a)
    s = s.replace(a, FNS.strip("\n") + "\n\n\n" + a, 1)
    for nm, old, new in (("起", START_OLD, START_NEW), ("停", STOP_OLD, STOP_NEW),
                         ("配置", CFG_OLD, CFG_NEW)):
        n = s.count(old)
        assert n == 1, "%s 锚点 %d" % (nm, n)
        s = s.replace(old, new)
    return s


if __name__ == "__main__":
    t = _rw(TGT, apply)
    for tok, want in (("def run_ckpt_dir(base=None) -> Path:", 1),
                      ("def write_run_ckpt(run_id: str", 1),
                      ("def start_run_ckpt(engine, run_id: str", 1),
                      ("def stop_run_ckpt(stop_evt, engine=None", 1),
                      ("def recover_orphan_runs(base=None", 1),
                      ('"live_checkpoint": False,', 1),
                      ('"ckpt_interval": 30.0,', 1),
                      ("start_run_ckpt(self, _ck_rid, _ck_iv)", 1),
                      ('stop_run_ckpt(_ck_stop, self, _ck_rid, "done")', 1)):
        assert t.count(tok) == want, "自检 %r = %d" % (tok, t.count(tok))
    print("[ok] v1.23.49 补丁已落 | 纯 CRLF | AST OK")
