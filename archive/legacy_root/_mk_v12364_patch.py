# -*- coding: utf-8 -*-
"""生成 元DGTF-V1.23.64.py：复制上一版 + 插入前沿内核 + 工程加固。

用法：python _mk_v12364_patch.py
★ 只做**字符串级**替换，每处都断言命中次数（0 次或多次都直接失败），
  避免「补丁静默没打上」这种本项目反复栽过的坑。
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.63.py"
DST = HERE / "元DGTF-V1.23.64.py"
KERNEL = (HERE / "_kernel_v12364.py").read_text(encoding="utf-8")

raw = SRC.read_bytes().decode("utf-8")
assert "\r\n" in raw, "源文件应是 CRLF"
txt = raw.replace("\r\n", "\n")


def rep(old: str, new: str, n: int = 1) -> None:
    global txt
    c = txt.count(old)
    assert c == n, "替换命中 %d 次（期望 %d）：%r" % (c, n, old[:90])
    txt = txt.replace(old, new)


def resub(pat: str, new: str, n: int = 1) -> None:
    global txt
    ms = list(re.finditer(pat, txt, re.S))
    assert len(ms) == n, "正则命中 %d 次（期望 %d）：%s" % (len(ms), n, pat[:90])
    txt = re.sub(pat, lambda _m: new, txt, count=n, flags=re.S)


# ── 1. 版本号 / 导入 / 编码兜底 ─────────────────────────────
rep("元 DGTF · v1.23.63", "元 DGTF · v1.23.64")
rep('__version__ = "1.23.63"', '__version__ = "1.23.64"')
rep("import os\nimport re\n", "import os\nimport random\nimport re\n")

rep(
    '''def _force_utf8_streams() -> None:
    for stream in (getattr(sys, "stdout", None),
                   getattr(sys, "stderr", None)):
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            # 已被替换成自定义 writer / 不支持 reconfigure —— 不致命，跳过
            pass''',
    '''def _force_utf8_streams() -> None:
    """把 stdout/stderr 切到 UTF-8，并给**子进程**留 UTF-8 默认值。

    ★ 只切当前进程不够：本项目大量用子进程跑门禁/审计（_run_gate、
      smoke_test、dgtf_app 的 engine_runner）。Windows 管道下子进程仍按
      locale（cp936）编码 ⇒ 打印 ✓/✗ 第一条就 UnicodeEncodeError。
      这里 setdefault 只影响「本进程之后启动的子进程」，不覆盖用户显式设置。
    """
    for stream in (getattr(sys, "stdout", None),
                   getattr(sys, "stderr", None)):
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            # 已被替换成自定义 writer / 不支持 reconfigure —— 不致命，跳过
            pass
    for _k, _v in (("PYTHONUTF8", "1"), ("PYTHONIOENCODING", "utf-8")):
        try:
            if not os.environ.get(_k):
                os.environ[_k] = _v
        except Exception:
            pass''',
)

# ── 2. eml_lock：单调钟 + pid:token + 活进程不抢锁 ──────────
EML_LOCK = '''def _eml_pid_alive(pid) -> bool:
    """锁文件里的 PID 是否还活着；判不了就保守当活着（不抢锁）。"""
    try:
        _p = int(pid)
        if _p <= 0:
            return False
        if os.name == "nt":
            import ctypes
            _h = ctypes.windll.kernel32.OpenProcess(0x1000, False, _p)
            if not _h:
                return False
            try:
                ctypes.windll.kernel32.CloseHandle(_h)
            except Exception:
                pass
            return True
        os.kill(_p, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return True


@contextlib.contextmanager
def eml_lock(base=None, dirpath=None, timeout: float = 180.0,
             stale: float = 900.0):
    """跨进程记忆库互斥锁：O_CREAT|O_EXCL + 令牌 + 单调钟。

    ★ v1.23.64 三处加固（都对应已实测的失败模式）：
      1) 超时用 monotonic：墙钟被校时会提前/延后释放；
      2) 锁文件写 pid:token，释放时**只删自己的**（防陈旧回收后误删别人的锁）；
      3) 陈旧锁回收前先问 pid 是否活着：活着就不抢。原实现只看 mtime，
         长跑持锁超过 stale 会被第二个进程直接抢走 ⇒ 互斥失效。
    ★ 拿不到锁返回 False；调用方必须据此**跳过写库**，不能裸奔继续。
    """
    try:
        d = Path(dirpath) if dirpath else eml_dir(base)
    except Exception:
        yield False
        return
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        yield False
        return
    lp = d / ".eml.lock"
    _token = "%d:%d" % (os.getpid(), int(time.time() * 1000))
    t0 = time.monotonic()
    got = False
    while time.monotonic() - t0 < float(timeout):
        try:
            fd = os.open(str(lp), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, _token.encode("ascii"))
            os.close(fd)
            got = True
            break
        except FileExistsError:
            try:
                if time.time() - lp.stat().st_mtime > float(stale):
                    try:
                        _owner = int(lp.read_text(encoding="utf-8")
                                     .strip().split(":", 1)[0])
                    except Exception:
                        _owner = 0
                    if _owner and _eml_pid_alive(_owner):
                        time.sleep(0.2)
                        continue          # 持锁进程还活着 ⇒ 不抢
                    lp.unlink(missing_ok=True)
                    continue
            except Exception:
                pass
            time.sleep(0.2)
        except Exception:
            time.sleep(0.2)
    try:
        yield got
    finally:
        if got:
            try:
                # ★ 只删自己写的锁：若已被别人回收，删除会破坏对方的互斥。
                if lp.read_text(encoding="utf-8").strip() == _token:
                    lp.unlink(missing_ok=True)
            except Exception:
                pass
'''

resub(r"@contextlib\.contextmanager\ndef eml_lock\(.*?\n\n\ndef eml_read_jsonl", EML_LOCK + "\n\ndef eml_read_jsonl")


# ── 3. eml_read_jsonl：坏行计数 + 告警（不再静默当空库）──────
EML_READ = '''def eml_read_jsonl(path, stats: dict = None) -> list:
    """读 jsonl：坏行跳过**但计数并告警**（不再静默当作空库）。

    ★ 为什么加 stats：红线「失败留痕」。原实现的 docstring 说「跳过但计数」，
      实际没有计数也没有日志 ⇒ 记忆库被写坏时，读的人只看到「条目变少」。
      stats（可选）是本函数唯一的行为扩展：不传时返回形状逐字不变。
    """
    p = Path(path)
    if not p.is_file():
        if isinstance(stats, dict):
            stats.update({"file": str(p), "rows": 0, "bad": 0, "ok": False})
        return []
    out = []
    bad = 0
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            bad += 1
            continue
    if bad:
        logger.warning("EML jsonl 有 %d 行坏行被跳过（文件仍保留）：%s", bad, p)
    if isinstance(stats, dict):
        stats.update({"file": str(p), "rows": len(out), "bad": bad, "ok": True})
    return out
'''
resub(r"def eml_read_jsonl\(.*?\n\n\ndef eml_append_jsonl", EML_READ + "\n\ndef eml_append_jsonl")


# ── 4. eml_rewrite_jsonl：原子写 + allow_grow ───────────────
EML_REWRITE = '''def eml_rewrite_jsonl(path, rows, allow_grow: bool = False) -> bool:
    """整表**原子**重写（tmp + os.replace）。

    ★ v1.23.64 两个修正：
      1) 原实现 open("w") 直接截断再写：中途崩溃会留下半截库，而
         eml_read_jsonl 会跳过坏行 ⇒ **静默丢一整库的尾部**；
      2) allow_grow=True 允许「只增行」（行数与 id 集合只许变多），
         给 _eml_finish 的新增分支复用同一套原子写，不再另开一条裸写。
    ★ 默认 allow_grow=False ⇒ 与原行为（行数/id 集合都不许变）逐字一致。
    """
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        _old = eml_read_jsonl(p)
        _old_ids = {r.get("id") for r in _old}
        _new_ids = {r.get("id") for r in rows}
        if allow_grow:
            if len(rows) < len(_old) or not _old_ids <= _new_ids:
                return False          # 只增不删：行数不减、旧 id 不丢
        else:
            if len(rows) != len(_old):
                return False          # ★ F5：行数不许变
            if _new_ids != _old_ids:
                return False          # ★ F5：id 集合不许变
        _payload = "".join(json.dumps(r, ensure_ascii=False) + "\\n"
                           for r in rows)
        _tmp = p.with_suffix(p.suffix + ".tmp")
        _tmp.write_text(_payload, encoding="utf-8", newline="\\n")
        os.replace(str(_tmp), str(p))
        return True
    except Exception:
        try:
            _tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return False
'''
resub(r"def eml_rewrite_jsonl\(.*?\n\n\ndef nogood_record", EML_REWRITE + "\n\ndef nogood_record")


# ── 5. LLM 重试：错误分类 + Retry-After + 抖动 ──────────────
rep(
    '''    def _web_need_report(self, stage: str, text) -> int:''',
    '''    @staticmethod
    def _retryable(exc) -> bool:
        """4xx（除 408/409/429）不重试：参数错/鉴权错重试只会更贵更慢。"""
        code = getattr(exc, "status_code", None)
        if isinstance(code, int) and 400 <= code < 500:
            return code in (408, 409, 429)
        return True

    def _retry_delay(self, attempt: int) -> float:
        """指数退避 + 抖动（防并行分层同拍重试）；上限 60s。"""
        d = min(60.0, float(self.backoff) ** max(1, int(attempt)))
        return d * (0.5 + 0.5 * random.random())

    def _web_need_report(self, stage: str, text) -> int:''',
)

rep(
    '''                logger.warning("返回空内容(%d/%d)", attempt, self.max_retries)
                if attempt < self.max_retries:
                    time.sleep(self.backoff ** attempt)
                    continue''',
    '''                logger.warning("返回空内容(%d/%d)", attempt, _tries)
                if attempt < _tries:
                    time.sleep(self._retry_delay(attempt))
                    continue''',
)

rep(
    '''            except Exception as e:
                last_err = e
                logger.warning("调用失败(%d/%d): %s", attempt, self.max_retries, e)
                if attempt < self.max_retries:
                    time.sleep(self.backoff ** attempt)
        raise RuntimeError(
            f"LLM 连续 {_tries} 次失败: {last_err}")''',
    '''            except Exception as e:
                last_err = e
                logger.warning("调用失败(%d/%d): %s", attempt, _tries, e)
                if attempt >= _tries:
                    break
                if not self._retryable(e):
                    # 参数错/鉴权错重试无意义：立刻抛，省下 2 次往返与等待。
                    logger.warning("不可重试错误（status=%r），不再重试",
                                   getattr(e, "status_code", None))
                    break
                _delay = self._retry_delay(attempt)
                try:
                    _ra = (getattr(e, "response", None).headers or {}).get(
                        "retry-after")
                    if _ra:
                        _delay = max(_delay, min(60.0, float(_ra)))
                except Exception:
                    pass
                time.sleep(_delay)
        raise RuntimeError(
            f"LLM 连续 {_tries} 次失败: {last_err}")''',
)

# ── 6. anytime 停止判据：按配置分派 ────────────────────────
rep(
    '''                    _any_ok = bool(anytime_majority_decided(
                        [1 if (int(r.get("new_amps", 0) or 0) > 0) else 0
                         for r in (view.round_log or [])], delta=_aa,
                        thr=0.5)[0])''',
    '''                    _any_ok = bool(anytime_decided(
                        [1 if (int(r.get("new_amps", 0) or 0) > 0) else 0
                         for r in (view.round_log or [])], delta=_aa,
                        thr=0.5,
                        mode=str(getattr(self, "_anytime_mode", "hoeffding"))
                    )[0])''',
)
rep(
    '''                _any_ok = bool(anytime_majority_decided(
                    [1 if (int(r.get("new_amps", 0) or 0) > 0) else 0
                     for r in (view.round_log or [])], delta=_aa, thr=0.5)[0])''',
    '''                _any_ok = bool(anytime_decided(
                    [1 if (int(r.get("new_amps", 0) or 0) > 0) else 0
                     for r in (view.round_log or [])], delta=_aa, thr=0.5,
                    mode=str(getattr(self, "_anytime_mode", "hoeffding")))[0])''',
)

# ── 7. 配置读取（MetaDGTF.__init__）────────────────────────
rep(
    '''        except (TypeError, ValueError):
            self._anytime_delta = 0.0''',
    '''        except (TypeError, ValueError):
            self._anytime_delta = 0.0
        # [F1] 统计口径：hoeffding（默认，逐字不变）/ evalue（e-process）。
        try:
            self._anytime_mode = str(
                (config.get("stop") or {}).get("anytime_mode", "hoeffding")
                or "hoeffding").strip().lower()
        except Exception:
            self._anytime_mode = "hoeffding"''',
)
rep(
    '''        self._eml_mode = str(_pl.get("mode", _EML_MODE_DEFAULT))''',
    '''        self._eml_mode = str(_pl.get("mode", _EML_MODE_DEFAULT))
        # [F4] 论证冲突裁决（默认关 ⇒ 出厂零行为差）。
        try:
            _arg = dict(_pl.get("argumentation") or {})
        except Exception:
            _arg = {}
        self._arg_cfg = _arg
        self._arg_enabled = bool(_arg.get("enabled", False))
        self._arg_semantics = str(_arg.get("semantics", "grounded") or "grounded")''',
)

# ── 8. eml_recall：可排除被论证裁定的败方（默认不排除）──────
rep(
    '''def eml_recall(playbook: list, kind: str, now: float,
               halflife: float = _EML_HALFLIFE_DAYS,
               top_k: int = _EML_TOP_K) -> list:''',
    '''def eml_recall(playbook: list, kind: str, now: float,
               halflife: float = _EML_HALFLIFE_DAYS,
               top_k: int = _EML_TOP_K,
               exclude_defeated: bool = False) -> list:''',
)
rep(
    '''        if str(e.get("kind")) != str(kind):
            continue''',
    '''        if str(e.get("kind")) != str(kind):
            continue
        # [F4] 被论证裁定为败方的条目：默认仍参与（零行为差），
        #   打开 playbook.argumentation 后不再被召回（标签仍在盘上）。
        if exclude_defeated and str(e.get("arg_status") or "") == "defeated":
            continue''',
)
rep(
    '''            for _it in eml_recall(_pb, _kind, _now, halflife=_h, top_k=_k):''',
    '''            for _it in eml_recall(
                    _pb, _kind, _now, halflife=_h, top_k=_k,
                    exclude_defeated=bool(getattr(self, "_arg_enabled", False))):''',
)

# ── 9. _eml_finish：锁失败不裸奔 + 原子落盘 + 论证裁决 ─────
rep(
    '''        _lk = None
        try:''',
    '''        _lk = None
        _got = False
        try:''',
)
rep(
    '''            _lk = eml_lock(dirpath=_dir)
            _lk.__enter__()''',
    '''            _lk = eml_lock(dirpath=_dir)
            _got = bool(_lk.__enter__())
            if not _got:
                # ★ 拿不到锁 ⇒ 跳过本次写库（状态不完整好过写坏库）。
                _blk["lock_timeout"] = True
                return _blk''',
)
rep(
    '''            eml_append_jsonl(_dir / _EML_EPISODES, _ep)''',
    '''            if not eml_append_jsonl(_dir / _EML_EPISODES, _ep):
                _blk["episode_append_failed"] = True''',
)
rep(
    '''            _blk["promote_trace"] = _pt''',
    '''            _blk["promote_trace"] = _pt
            # ★ [F4 论证冲突裁决] 默认关；只标不删（见内核 F4 注释）。
            if getattr(self, "_arg_enabled", False):
                _blk["argumentation"] = resolve_playbook_conflicts(
                    _pb, semantics=getattr(self, "_arg_semantics", "grounded"),
                    apply=True)''',
)
rep(
    '''            if len(_pb) > _n0:
                with (_dir / _EML_PLAYBOOK).open(
                        "w", encoding="utf-8", newline="\\n") as _f:
                    for _r in _pb:
                        _f.write(json.dumps(_r, ensure_ascii=False) + "\\n")
            elif len(_pb) == _n0:
                eml_rewrite_jsonl(_dir / _EML_PLAYBOOK, _pb)
            else:
                raise RuntimeError("EML 行数减少（%d→%d），违反只增不删"
                                   % (_n0, len(_pb)))''',
    '''            if len(_pb) < _n0:
                raise RuntimeError("EML 行数减少（%d→%d），违反只增不删"
                                   % (_n0, len(_pb)))
            # ★ 新增与不变走**同一条原子写**：原「有新行就裸 open(w)」
            #   在崩溃时会截断整库（与 F5 只增不删直接冲突）。
            if not eml_rewrite_jsonl(_dir / _EML_PLAYBOOK, _pb,
                                     allow_grow=True):
                raise RuntimeError("EML 原子落盘失败（本次不吞，盘上仍是旧库）")''',
)
rep(
    '''            if _lk is not None:
                try:
                    _lk.__exit__(None, None, None)''',
    '''            if _lk is not None and _got:
                try:
                    _lk.__exit__(None, None, None)''',
)

# ── 10. DEFAULT_CONFIG 新键（默认关/默认旧口径）────────────
rep(
    '''        "anytime_alpha": 0.0,
    },''',
    '''        "anytime_alpha": 0.0,
        # [F1 前沿] anytime 判据的统计口径：hoeffding（默认，逐字不变）
        #   / evalue（e-process：样本更省，且同样对任意停时有效）。opt-in。
        "anytime_mode": "hoeffding",
    },''',
)
rep(
    '''        "learn_from_anon": False,
    },''',
    '''        "learn_from_anon": False,
        # [F4 前沿] 论证冲突裁决：默认关 ⇒ 出厂零行为差。
        #   true 时对同 (kind, cond) 但动作不同的条目做 grounded/负担裁决，
        #   只写 arg_status / defeated_by 标签（不删行、不改 status）。
        "argumentation": {
            "enabled": False,
            "semantics": "grounded",
        },
    },''',
)

# ── 11. 插入前沿内核 ───────────────────────────────────────
rep('''class MetaDGTF:''', KERNEL + '''\n\nclass MetaDGTF:''')

out = txt.replace("\n", "\r\n")
DST.write_bytes(out.encode("utf-8"))
print("WROTE", DST.name, "bytes", len(out.encode("utf-8")))
