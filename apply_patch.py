#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 v1.21.50 → v1.21.51 的改动重放到 元DGTF-V1.21.50.py。

幂等：已经打过的补丁会跳过。任何一条 old 匹配不到 / 不唯一就报错退出，
不做半吊子修改。

    python apply_patch.py
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.21.50.py"

PATCHES = []


def P(name, old, new):
    PATCHES.append((name, old, new))


# ---------------------------------------------------------------- 版本号 / changelog
P("changelog", r"""元 DGTF · v1.21.50

v1.21.50 相对 v1.21.49 的改动（并行模式 A/B/serial/auto）：

  [feat-94] 并行模式三选一 + auto：""", r"""元 DGTF · v1.21.51

v1.21.51 相对 v1.21.50 的改动（稳定性 + 并行展开）：

  [fix-97] 终端编码兜底：
           导入期即把 stdout/stderr 重配置为 UTF-8（errors=replace）。
           否则在 GBK 终端或 `python x.py > log.txt` 重定向下，
           第一条 emoji 日志就会抛 UnicodeEncodeError 直接崩。

  [fix-98] LLM 截断标志线程隔离：
           last_finish / last_truncated 改为 threading.local 存储，
           _call_long 不再跨线程读到别的层的截断状态
           （v1.21.50 只给计数器加了锁，这两个漏了）。

  [fix-99] self_text 按层隔离（补完设计 9.7 的并发安全清单）：
           并行模式下每层各写 _self_text_by_entry[entry]，
           全部跑完后 _merge_self_text() 合并并截断到 self_layers。
           v1.21.50 里 4 个线程共享一个 list 做 read-modify-write，会丢条目。
           顺带补上 B 模式此前完全没写 self_text 的缺失。

  [fix-100] 池写入加锁：
           新增 MetaDGTF._pool_lock（RLock），覆盖 _apply_view_to_pool /
           self_text 写入 / _totalize_all_pool。

  [fix-101] A 模式汇流不再依赖 route 含 all：
           只要拿到 >=2 份**可用**的上游 view 就跑汇流圈；
           失败占位 View 不再被当成有效上游。
           route 不含 all 时汇流结果入池 + 写进 packed["confluence"] 并落盘。

  [fix-102] B 模式 _b_pre_layer 死代码清理：
           has_zero_prod 恒假导致"修行池内部分解"分支永不执行，
           改为按上游是否就绪真实判断（与 _run_layer 一致）。

  [fix-103] 配置兜底一致化：
           all_extra_rounds 代码兜底 2 → 1（与 DEFAULT_CONFIG 一致）；
           _rounds_plan 尊重 spiral.min_rounds 与 per_entry 覆盖。

  [fix-105] --parallel 不再硬编码 default="auto"：
           命令行不给时回落配置 actions.parallel_mode（原来配置项形同虚设）。

  [perf-104] 阴阳展开并行（设计 9.1 点名的可并行点）：
           阴/阳两次独立 LLM 调用用 ThreadPoolExecutor 并行发出，
           解析仍严格按 order 顺序串行（去重 seen 依赖先后）。
           每层每圈省一次往返。可用 actions.parallel_expand 关闭。

保留 v1.21.50 全部改动（并行模式 A/B/serial/auto）：

  [feat-94] 并行模式三选一 + auto：""")

# ---------------------------------------------------------------- [fix-97] 编码兜底
P("version+utf8", r"""__version__ = "1.21.50"

logger = logging.getLogger("dgtf")""", r"""__version__ = "1.21.51"

logger = logging.getLogger("dgtf")


# ============================================================
# 终端编码兜底 [fix-97]
# ============================================================
# Windows 下 stdout 被重定向到文件时，Python 会用 locale 编码（cp936/GBK），
# 而本文件大量用 emoji 与制表符作日志前缀，第一条 print 就会
# UnicodeEncodeError 崩掉整个进程。这里在导入期把两个流切成 UTF-8。
def _force_utf8_streams() -> None:
    for stream in (getattr(sys, "stdout", None),
                   getattr(sys, "stderr", None)):
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            # 已被替换成自定义 writer / 不支持 reconfigure —— 不致命，跳过
            pass


_force_utf8_streams()""")

# ---------------------------------------------------------------- [fix-98] 截断标志
P("llm-tls", r"""        self.total_calls = 0
        self.total_tokens = 0
        self.last_finish: Optional[str] = None
        self.last_truncated: bool = False
        self._lock = threading.Lock()  # v1.21.50 并发计数锁

    @staticmethod
    def _is_reasoner(name: str) -> bool:""", r"""        self.total_calls = 0
        self.total_tokens = 0
        # [fix-98] 上一次调用的 finish_reason / 截断标志必须是**线程局部**的。
        # 并行模式 A/B 下 4 个线程共用同一个 LLM 实例，实例属性会让
        # _call_long 读到别的层刚写入的 truncated，误判续跑。
        self._tls = threading.local()
        self._lock = threading.Lock()  # v1.21.50 并发计数锁

    # ---- 线程局部的 last_finish / last_truncated ----
    @property
    def last_finish(self) -> Optional[str]:
        return getattr(self._tls, "finish", None)

    @last_finish.setter
    def last_finish(self, v) -> None:
        self._tls.finish = v

    @property
    def last_truncated(self) -> bool:
        return bool(getattr(self._tls, "truncated", False))

    @last_truncated.setter
    def last_truncated(self, v) -> None:
        self._tls.truncated = bool(v)

    @staticmethod
    def _is_reasoner(name: str) -> bool:""")

P("llm-call-reset", r"""        self.last_finish = None
        self.last_truncated = False
        last_err = None""", r"""        # [fix-98] 这两个现在写进线程局部存储，不是实例属性
        self.last_finish = None
        self.last_truncated = False
        last_err = None""")

# ---------------------------------------------------------------- _view_usable
P("view-usable", r"""class MemoryChannel:
    @staticmethod
    def check(ch: str) -> str:""", r"""def _view_usable(v) -> bool:
    '''这个 View 能不能当上游用。

    A/B 模式某层整体异常时会生成一个只有 errors 的占位 View，
    它不是 None，所以旧代码会把它算进「上游已就绪」，
    让对撞/元层拿一份空壳去撞。这里把它挡掉。
    '''
    if v is None:
        return False
    errs = getattr(v, "errors", None) or []
    if errs and not (getattr(v, "manifest", "") or "").strip():
        return False
    return True


class MemoryChannel:
    @staticmethod
    def check(ch: str) -> str:""")

# ---------------------------------------------------------------- [perf-104] 并行展开
P("expand-dispatch", r"""    def _expand(self, inp: Input, pool: Pool, anchor: str) -> List[Candidate]:
        seeds = inp.seed_probes or []
        role, rno = inp.round_role, inp.round_no
        if inp.is_base:
            return self._expand_from_question(
                inp.question, pool, anchor, seeds, role, rno, inp)
        return self._expand_from_views(
            inp.upstream_views, pool, anchor, seeds, inp.context,
            inp.upstream_pools, role, rno, inp)""", r"""    def _expand(self, inp: Input, pool: Pool, anchor: str) -> List[Candidate]:
        seeds = inp.seed_probes or []
        role, rno = inp.round_role, inp.round_no
        if inp.is_base:
            return self._expand_from_question(
                inp.question, pool, anchor, seeds, role, rno, inp)
        return self._expand_from_views(
            inp.upstream_views, pool, anchor, seeds, inp.context,
            inp.upstream_pools, role, rno, inp)

    # ---------- 阴阳展开的并行执行壳 [perf-104] ----------
    def _expand_pair(self, order, build_user) -> List[Candidate]:
        '''阴 / 阳两次展开是互不依赖的 LLM 调用，并行发出。

        设计 9.1 把「阴阳展开」列为可并行点：每层每圈省一次往返。
        **解析必须串行、且严格按 order 顺序**——去重的 seen 依赖先后，
        乱序解析会改变产物，也会让「阴在前还是阳在前」的层配置失效。
        '''
        jobs = []
        for label, prompt in order:
            key = "expand_yin" if label == "阴" else "expand_yang"
            if not _action_on(self.config, key):
                self.vp(f"\n💧 [{label}视角] 已关闭")
                continue
            jobs.append((label, prompt, build_user(label)))
        if not jobs:
            return []

        raws: Dict[str, Optional[str]] = {}
        parallel = (len(jobs) > 1
                    and _action_on(self.config, "parallel_expand"))
        if parallel:
            with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
                futs = {
                    ex.submit(self.llm.call, prompt, user, 0.9, 1500): label
                    for label, prompt, user in jobs
                }
                for f, label in futs.items():
                    try:
                        raws[label] = f.result()
                    except Exception as e:
                        logger.warning("展开失败(%s): %s", label, e)
                        self.vp(f"   ✗ {label}展开失败：{e}")
        else:
            for label, prompt, user in jobs:
                try:
                    raws[label] = self.llm.call(prompt, user, 0.9, 1500)
                except Exception as e:
                    logger.warning("展开失败(%s): %s", label, e)
                    self.vp(f"   ✗ {label}展开失败：{e}")

        seen: List[str] = []
        out: List[Candidate] = []
        for label, _prompt, _user in jobs:
            raw = raws.get(label)
            if raw is None:
                continue
            self.vp(f"\n💧 [{label}视角]")
            self.vp(f"   {raw[:200]}")
            for line in raw.splitlines():
                c = self._parse_candidate_line(line)
                if not c:
                    continue
                if any(_similar(c.desc, s, 0.85) for s in seen):
                    continue
                seen.append(c.desc)
                c.source = label
                out.append(c)
        return out""")

P("expand-from-question", r"""        pool_text = self._pool_text(pool)
        seed_text = self._seed_text(seeds)
        dec_block = self._decidability_block(inp) if inp else ""
        seen = []
        out: List[Candidate] = []

        for label, prompt in order:
            key = "expand_yin" if label == "阴" else "expand_yang"
            if not _action_on(self.config, key):
                self.vp(f"\n💧 [{label}视角] 已关闭")
                continue
            self.vp(f"\n💧 [{label}视角]")
            user = (
                f"【原始问题】\n{question}\n\n"
                f"【锚点重述】\n{anchor}\n"
                f"{self._role_text(role, round_no)}\n"
                f"{dec_block}\n\n"
                f"【上一圈没带走的自问】\n{seed_text}\n\n"
                f"【池】\n{pool_text}"
            )
            try:
                raw = self.llm.call(prompt, user, 0.9, 1500)
            except Exception as e:
                logger.warning("展开失败: %s", e)
                self.vp(f"   ✗ {label}展开失败：{e}")
                continue
            self.vp(f"   {raw[:200]}")
            for line in raw.splitlines():
                c = self._parse_candidate_line(line)
                if not c:
                    continue
                if any(_similar(c.desc, s, 0.85) for s in seen):
                    continue
                seen.append(c.desc)
                c.source = label
                out.append(c)
        return out""", r"""        pool_text = self._pool_text(pool)
        seed_text = self._seed_text(seeds)
        dec_block = self._decidability_block(inp) if inp else ""

        def build_user(label):
            return (
                f"【原始问题】\n{question}\n\n"
                f"【锚点重述】\n{anchor}\n"
                f"{self._role_text(role, round_no)}\n"
                f"{dec_block}\n\n"
                f"【上一圈没带走的自问】\n{seed_text}\n\n"
                f"【池】\n{pool_text}"
            )
        return self._expand_pair(order, build_user)""")

P("expand-from-views", r"""        dec_block = self._decidability_block(inp) if inp else ""
        seen: List[str] = []
        out: List[Candidate] = []
        for label, prompt in order:
            key = "expand_yin" if label == "阴" else "expand_yang"
            if not _action_on(self.config, key):
                self.vp(f"\n💧 [{label}视角] 已关闭")
                continue
            self.vp(f"\n💧 [{label}视角]")
            anchor_block = (
                "【原始问题 · 本层锚点（透传，不重写）】\n"
                f"{anchor}\n"
                "（下面每一项——上游 view / 四象限 / 上游池——都是**这同一个问题**"
                "的不同切面。它们只提供角度，不改写问题；"
                "展开始终回到上面的这个问题。）\n"
            )
            user = (
                f"{anchor_block}\n"
                f"{self._role_text(role, round_no)}\n"
                f"{dec_block}\n\n"
                f"【上游的 view · 同一问题下的各自显形】\n{views_text}\n\n"
                f"【上一圈没带走的自问】\n{seed_text}\n"
                f"{q_block}"
                f"{up_block}"
                f"{ctx_block}\n\n【本层的池】\n{pool_text}"
            )
            try:
                raw = self.llm.call(prompt, user, 0.9, 1500)
            except Exception as e:
                logger.warning("展开失败(%s): %s", label, e)
                self.vp(f"   ✗ {label}展开失败：{e}")
                continue
            self.vp(f"   {raw[:200]}")
            for line in raw.splitlines():
                c = self._parse_candidate_line(line)
                if not c:
                    continue
                if any(_similar(c.desc, s, 0.85) for s in seen):
                    continue
                seen.append(c.desc)
                c.source = label
                out.append(c)
        return out""", r"""        dec_block = self._decidability_block(inp) if inp else ""
        anchor_block = (
            "【原始问题 · 本层锚点（透传，不重写）】\n"
            f"{anchor}\n"
            "（下面每一项——上游 view / 四象限 / 上游池——都是**这同一个问题**"
            "的不同切面。它们只提供角度，不改写问题；"
            "展开始终回到上面的这个问题。）\n"
        )

        def build_user(label):
            return (
                f"{anchor_block}\n"
                f"{self._role_text(role, round_no)}\n"
                f"{dec_block}\n\n"
                f"【上游的 view · 同一问题下的各自显形】\n{views_text}\n\n"
                f"【上一圈没带走的自问】\n{seed_text}\n"
                f"{q_block}"
                f"{up_block}"
                f"{ctx_block}\n\n【本层的池】\n{pool_text}"
            )
        return self._expand_pair(order, build_user)""")

# ---------------------------------------------------------------- [fix-99] self_text / [fix-101] 上游过滤
P("inp-builders", r"""    def _build_inp_base(self, s, role="", rno=0):
        return Input(
            question=self._question,
            seed_probes=s,
            key_terms=self._key_terms,
            round_role=role, round_no=rno,
            self_memory=MemoryChannel.self_text_of(self.self_text),
        )

    def _build_inp_duel(self, s, role="", rno=0):
        up = []
        if self._upstream_provider is not None:
            try:
                up = list(self._upstream_provider("both") or [])
            except Exception:
                up = []
        up = [v for v in up if v is not None]
        if len(up) < 2:
            return Input(
                question=self._question,
                seed_probes=s, key_terms=self._key_terms,
                round_role=role, round_no=rno,
                self_memory=MemoryChannel.self_text_of(self.self_text),
            )
        return Input(
            upstream_views=up,
            upstream_pools=[self.pools["0"], self.pools["1"]],
            upstream_untouched=[v.untouched for v in up],
            root_question=self._question,
            seed_probes=s, key_terms=self._key_terms,
            round_role=role, round_no=rno,
            context=self._context_if_on(),
            self_memory=MemoryChannel.self_text_of(self.self_text),
        )

    def _build_inp_meta(self, s, role="", rno=0):
        up = []
        if self._upstream_provider is not None:
            try:
                up = list(self._upstream_provider("all") or [])
            except Exception:
                up = []
        up = [v for v in up if v is not None]
        if len(up) < 2:
            return Input(
                question=self._question,
                seed_probes=s, key_terms=self._key_terms,
                round_role=role, round_no=rno,
                self_memory=MemoryChannel.self_text_of(self.self_text),
            )
        return Input(
            upstream_views=up,
            upstream_pools=[self.pools[getattr(v, "entry", "0")]
                            for v in up],
            upstream_untouched=[v.untouched for v in up],
            root_question=self._question,
            seed_probes=s, key_terms=self._key_terms,
            round_role=role, round_no=rno,
            context=self._context_if_on(),
            self_memory=MemoryChannel.self_text_of(self.self_text),
        )""", r"""    def _build_inp_base(self, s, role="", rno=0, entry="0"):
        return Input(
            question=self._question,
            seed_probes=s,
            key_terms=self._key_terms,
            round_role=role, round_no=rno,
            self_memory=self._self_snapshot_for(entry),
        )

    def _build_inp_duel(self, s, role="", rno=0):
        up = []
        if self._upstream_provider is not None:
            try:
                up = list(self._upstream_provider("both") or [])
            except Exception:
                up = []
        # [fix-101] 失败占位 View 不能当上游
        up = [v for v in up if _view_usable(v)]
        if len(up) < 2:
            return Input(
                question=self._question,
                seed_probes=s, key_terms=self._key_terms,
                round_role=role, round_no=rno,
                self_memory=self._self_snapshot_for("both"),
            )
        return Input(
            upstream_views=up,
            upstream_pools=[self.pools["0"], self.pools["1"]],
            upstream_untouched=[v.untouched for v in up],
            root_question=self._question,
            seed_probes=s, key_terms=self._key_terms,
            round_role=role, round_no=rno,
            context=self._context_if_on(),
            self_memory=self._self_snapshot_for("both"),
        )

    def _build_inp_meta(self, s, role="", rno=0):
        up = []
        if self._upstream_provider is not None:
            try:
                up = list(self._upstream_provider("all") or [])
            except Exception:
                up = []
        up = [v for v in up if _view_usable(v)]
        if len(up) < 2:
            return Input(
                question=self._question,
                seed_probes=s, key_terms=self._key_terms,
                round_role=role, round_no=rno,
                self_memory=self._self_snapshot_for("all"),
            )
        return Input(
            upstream_views=up,
            upstream_pools=[self.pools[getattr(v, "entry", "0")]
                            for v in up],
            upstream_untouched=[v.untouched for v in up],
            root_question=self._question,
            seed_probes=s, key_terms=self._key_terms,
            round_role=role, round_no=rno,
            context=self._context_if_on(),
            self_memory=self._self_snapshot_for("all"),
        )""")

# ---------------------------------------------------------------- [fix-99][fix-100] MetaDGTF 状态
P("meta-init", r"""        self._self_text_by_entry: Dict[str, List[str]] = {
            e: [] for e in _ENTRIES}
        self._pack_lock = threading.Lock()
        self._parallel_mode: str = "serial"
        self._b_state: Dict[str, dict] = {}

    def vp(self, *args):
        if self.verbose:
            print(*args)""", r"""        self._self_text_by_entry: Dict[str, List[str]] = {
            e: [] for e in _ENTRIES}
        self._pack_lock = threading.Lock()
        # [fix-100] 池 / self_text 的写入锁。串行模式下等于无开销，
        # 并行模式 A/B 下保证 merge / 生命周期更新 / 汇总不会互相踩。
        self._pool_lock = threading.RLock()
        self._parallel_mode: str = "serial"
        self._b_state: Dict[str, dict] = {}

    def vp(self, *args):
        if self.verbose:
            print(*args)

    # ============================================================
    # self_text 按层隔离 [fix-99]
    # ============================================================
    # 设计 9.7 并发安全清单要求：并行模式下每层各写自己的桶，
    # 全部跑完再合并。v1.21.50 是 4 个线程往同一个 list 做
    # read-modify-write（prev[-keep:] 还会互相截断），条目会丢。
    def _append_self_text(self, entry: str, view: "View") -> None:
        with self._pool_lock:
            self._self_text_by_entry[entry] = MemoryChannel.accumulate_self(
                self._self_text_by_entry.get(entry) or [],
                entry, view, self._mcfg)

    def _self_snapshot_for(self, entry: str) -> str:
        '''给某一层构造 self_memory：读此刻所有层已累积的 self_text。

        串行模式下按 _ENTRIES 顺序拼接 == 原来的按时间累积顺序，行为不变。
        '''
        with self._pool_lock:
            blocks: List[str] = []
            for e in _ENTRIES:
                blocks.extend(self._self_text_by_entry.get(e) or [])
            return MemoryChannel.self_text_of(blocks)

    def _merge_self_text(self) -> None:
        '''所有层跑完后调用：把分层的 self_text 合并回 self.self_text。'''
        with self._pool_lock:
            blocks: List[str] = []
            for e in _ENTRIES:
                blocks.extend(self._self_text_by_entry.get(e) or [])
            keep = int(self._mcfg.get("self_layers", 4))
            self.self_text = blocks[-keep:] if keep > 0 else list(blocks)""")

# ---------------------------------------------------------------- [fix-100] 池写入锁
P("pool-lock", r"""    def _apply_view_to_pool(self, view: View, pool: Pool, entry: str,
                            rephrased_streak: int = 0,
                            meta_idle_streak: int = 0):
        pool.merge(view.amps, view.threads, view.meta, view.probes)""", r"""    def _apply_view_to_pool(self, view: View, pool: Pool, entry: str,
                            rephrased_streak: int = 0,
                            meta_idle_streak: int = 0):
        # [fix-100] 池是共享状态，写入统一走这把可重入锁
        with self._pool_lock:
            return self._apply_view_to_pool_locked(
                view, pool, entry, rephrased_streak, meta_idle_streak)

    def _apply_view_to_pool_locked(self, view: View, pool: Pool, entry: str,
                            rephrased_streak: int = 0,
                            meta_idle_streak: int = 0):
        pool.merge(view.amps, view.threads, view.meta, view.probes)""")

# ---------------------------------------------------------------- _run_layer
P("runlayer-inp", r"""            if entry == "0" or entry == "1":
                inp = self._build_inp_base(seeds, role, layer_no)
            elif entry == "both":
                inp = self._build_inp_duel(seeds, role, layer_no)
            else:
                inp = self._build_inp_meta(seeds, role, layer_no)""", r"""            if entry == "0" or entry == "1":
                inp = self._build_inp_base(seeds, role, layer_no, entry)
            elif entry == "both":
                inp = self._build_inp_duel(seeds, role, layer_no)
            else:
                inp = self._build_inp_meta(seeds, role, layer_no)""")

P("runlayer-selftest", r"""        if "self" in self.channels and view is not None:
            with self._pack_lock:
                self.self_text = MemoryChannel.accumulate_self(
                    self.self_text, entry, view, self._mcfg)

        return view""", r"""        # [fix-99] 按层写各自的桶，不再 4 个线程抢同一个 list
        if "self" in self.channels and view is not None:
            self._append_self_text(entry, view)

        return view""")

# ---------------------------------------------------------------- [fix-101] A 模式汇流
P("modeA-confluence", r"""        available = [k for k in ("0", "1", "both")
                     if k in self._results and self._results[k] is not None]
        if "all" in self._results and len(available) >= 2:
            self.vp(f"\n{'─'*60}\n🔀 汇流圈"
                    f"（上游 {available}）\n{'─'*60}")
            try:
                up = [self._results[k] for k in available]
                conf_inp = Input(
                    upstream_views=up,
                    upstream_pools=[self.pools[k] for k in available],
                    upstream_untouched=[v.untouched for v in up],
                    root_question=question,
                    seed_probes=[],
                    key_terms=self._key_terms,
                    round_role="收束", round_no=1,
                    context=self._context_if_on(),
                    self_memory=MemoryChannel.self_text_of(self.self_text),
                )
                conf_inp.pool = self.pools["all"]
                conf_inp.decidability_result = self.decidability_result
                dg = DGTF("all", self.llm, self.config)
                conf_view = dg.run(conf_inp)
                self._apply_view_to_pool(
                    conf_view, self.pools["all"], "all")
                self._merge_confluence(self._results["all"], conf_view)
                self.vp(f"   ✓ 汇流圈完成"
                        f"（view {len(conf_view.manifest or '')} 字）")
            except Exception as exc:
                logger.warning("汇流圈失败: %s", exc, exc_info=True)

        if "all" in self._results:
            self._totalize_all_pool()

        packed = self._pack_result(
            question, route, keep, rounds, self._results)
        packed["dispatch"] = {
            "requested": list(route),
            "order": list(self._results.keys()),
            "skipped": [],
            "_parallel_mode": "A",
        }
        return packed""", r"""        # [fix-101] 汇流圈不再要求 route 里必须有 all：
        # 只要拿到 >=2 份**可用**的上游 view 就跑，否则 A 模式下
        # `--route 0,1,both` 会退化成四份互不相干的独立报告。
        available = [k for k in ("0", "1", "both")
                     if _view_usable(self._results.get(k))]
        conf_view = None
        if len(available) >= 2:
            self.vp(f"\n{'─'*60}\n🔀 汇流圈"
                    f"（上游 {available}）\n{'─'*60}")
            try:
                up = [self._results[k] for k in available]
                conf_inp = Input(
                    upstream_views=up,
                    upstream_pools=[self.pools[k] for k in available],
                    upstream_untouched=[v.untouched for v in up],
                    root_question=question,
                    seed_probes=[],
                    key_terms=self._key_terms,
                    round_role="收束", round_no=1,
                    context=self._context_if_on(),
                    self_memory=self._self_snapshot_for("all"),
                )
                conf_inp.pool = self.pools["all"]
                conf_inp.decidability_result = self.decidability_result
                dg = DGTF("all", self.llm, self.config)
                conf_view = dg.run(conf_inp)
                self._apply_view_to_pool(
                    conf_view, self.pools["all"], "all")
                if _view_usable(self._results.get("all")):
                    self._merge_confluence(self._results["all"], conf_view)
                else:
                    # route 里没要 all 层：汇流结果只入池，不凭空多出一个 view
                    self.vp("   ℹ️ route 未含 all，汇流仅入池")
                self.vp(f"   ✓ 汇流圈完成"
                        f"（view {len(conf_view.manifest or '')} 字）")
            except Exception as exc:
                logger.warning("汇流圈失败: %s", exc, exc_info=True)
                conf_view = None
        else:
            self.vp(f"\n   ℹ️ 可用上游不足 2 份（{available}），跳过汇流圈")

        with self._pool_lock:
            self._totalize_all_pool()
        self._merge_self_text()

        packed = self._pack_result(
            question, route, keep, rounds, self._results)
        if conf_view is not None and not _view_usable(
                self._results.get("all")):
            packed["confluence"] = conf_view.to_dict()
        packed["dispatch"] = {
            "requested": list(route),
            "order": list(self._results.keys()),
            "skipped": [],
            "_parallel_mode": "A",
        }
        return packed""")

# ---------------------------------------------------------------- B 模式
P("modeB-prelayer", r"""            zero_view = None
            has_zero_prod = False
            use_internal = (dec_src == "pool" and has_zero_prod)
            if use_internal:""", r"""            # [fix-102] 原来是硬编码 has_zero_prod = False，
            # 导致 use_internal 恒假、"修行池内部"分支永不执行。
            # 改为与 _run_layer 一致：真的去看上游 provider 有没有 0 层产物。
            # B 模式第 1 圈 _prev_results 为空 → 自然走外部评估，行为不变；
            # 但上游一旦就绪，内部路径就能自动生效。
            zero_view = None
            if self._upstream_provider is not None:
                try:
                    ups = list(self._upstream_provider("1") or [])
                except Exception:
                    ups = []
                for v in ups:
                    if getattr(v, "entry", "") == "0":
                        zero_view = v
                        break
            has_zero_prod = self._has_pool_content_view(zero_view)
            use_internal = (dec_src == "pool" and has_zero_prod)
            if use_internal:""")

P("modeB-inp", r"""        if entry in ("0", "1"):
            inp = self._build_inp_base(state["seeds"], role, r)
        elif entry == "both":
            inp = self._build_inp_duel(state["seeds"], role, r)
        else:
            inp = self._build_inp_meta(state["seeds"], role, r)""", r"""        if entry in ("0", "1"):
            inp = self._build_inp_base(state["seeds"], role, r, entry)
        elif entry == "both":
            inp = self._build_inp_duel(state["seeds"], role, r)
        else:
            inp = self._build_inp_meta(state["seeds"], role, r)""")

P("modeB-selftest", r"""        self._b_check_stop(entry, view, r, state, st,
                           snap_amps, snap_threads)

        state["view"] = view
        return view""", r"""        self._b_check_stop(entry, view, r, state, st,
                           snap_amps, snap_threads)

        # [fix-99] B 模式此前完全没写 self_text，回来通道的 self 在
        # B 模式下是空的。与 _run_layer 保持一致：按层写各自的桶。
        if "self" in self.channels and view is not None:
            self._append_self_text(entry, view)

        state["view"] = view
        return view""")

P("modeB-tail", r"""        if "all" in self._results:
            self._totalize_all_pool()

        packed = self._pack_result(
            question, route, keep, rounds, self._results)
        packed["dispatch"] = {
            "requested": list(route),
            "order": list(self._results.keys()),
            "skipped": [],
            "_parallel_mode": "B",
        }
        return packed""", r"""        # [fix-100] _totalize_all_pool 必须串行，且在所有层跑完后执行
        with self._pool_lock:
            self._totalize_all_pool()
        self._merge_self_text()

        packed = self._pack_result(
            question, route, keep, rounds, self._results)
        packed["dispatch"] = {
            "requested": list(route),
            "order": list(self._results.keys()),
            "skipped": [],
            "_parallel_mode": "B",
        }
        return packed""")

# ---------------------------------------------------------------- serial 收尾
P("serial-tail", r"""        if "all" in self._results:
            self._totalize_all_pool()

        packed = self._pack_result(question, route, keep, rounds,
                                   self._results)
        packed["dispatch"] = dispatch
        return packed""", r"""        if "all" in self._results:
            with self._pool_lock:
                self._totalize_all_pool()
        self._merge_self_text()

        packed = self._pack_result(question, route, keep, rounds,
                                   self._results)
        packed["dispatch"] = dispatch
        return packed""")

# ---------------------------------------------------------------- [fix-103] 配置一致
P("all-extra-r1", r"""            _extra_rounds = int(sp.get("all_extra_rounds", 2))""",
  r"""            _extra_rounds = int(sp.get("all_extra_rounds", 1))""")

P("all-extra-r2", r"""        extra = int(sp.get("all_extra_rounds", 2)) if entry == "all" else 0""",
  r"""        extra = int(sp.get("all_extra_rounds", 1)) if entry == "all" else 0""")

P("rounds-plan", r"""        else:
            n = max(1, int(rounds or 0) or hard)
            per = {e: n for e in _ENTRIES}
        return {e: per.get(e, hard) for e in _ENTRIES}""", r"""        else:
            n = max(1, int(rounds or 0) or hard)
            per = {e: n for e in _ENTRIES}

        # [fix-103] 未被显式指定的层，兜底时尊重 spiral.min_rounds
        # （配置里写的是"这一层至少该跑几圈"，原来被完全忽略，
        #  一律拿 hard_max 兜底）。per_entry 覆盖同样要生效。
        min_rounds = (self.config.get("spiral") or {}).get("min_rounds") or {}
        out = {}
        for e in _ENTRIES:
            if e in per:
                out[e] = per[e]
                continue
            mr = int(min_rounds.get(e, 0) or 0)
            if mr > 0:
                out[e] = mr
            else:
                out[e] = int(_spiral_for(self.config, e).get(
                    "hard_max", hard))
        return out""")

P("cfg-parallel-expand", r"""        # v1.21.50 并行模式
        "parallel_mode": "auto",""", r"""        # v1.21.50 并行模式
        "parallel_mode": "auto",
        # v1.21.51 [perf-104] 阴/阳两次展开并行发出（每层每圈省一次往返）
        "parallel_expand": True,""")

# ---------------------------------------------------------------- [fix-105] CLI
P("cli-parallel", r"""    parser.add_argument("--parallel", default="auto",
                        choices=["serial", "A", "B", "auto"],
                        help="并行模式：serial / A / B / auto")""", r"""    # [fix-105] 默认 None：命令行没给时回落到配置文件的
    # actions.parallel_mode。原来硬编码 default="auto"，配置项形同虚设。
    parser.add_argument("--parallel", default=None,
                        choices=["serial", "A", "B", "auto"],
                        help="并行模式：serial / A / B / auto"
                             "（不给则用配置 actions.parallel_mode）")""")

P("cli-dispatch", r"""    _mode_disp = {
        "serial": "严格串行",
        "A": "A · 四层独立并行 + 汇流",
        "B": "B · 轮次并行",
        "auto": "auto · 自动决策",
    }.get(args.parallel, args.parallel)

    print(f"\n{'═'*60}")
    print(f"元 DGTF v{__version__} · {question}")
    print(f"{'═'*60}")
    print(f"调度：{' → '.join(route)}")
    if keep:
        print(f"保留：{keep}")
    print(f"螺旋上限（每层圈数）：{args.rounds}")
    print(f"并行模式：{_mode_disp}")
    ch = channels if channels is not None else cfg["memory"].get(
        "channels", ["content", "context", "self"])
    print(f"回来通道：{'、'.join(ch) if ch else '全关（历史不参与本次）'}")
    print(f"{'═'*60}")

    result = meta.run(question, route=route, keep=keep,
                      rounds=args.rounds, channels=channels,
                      parallel_mode=args.parallel)""", r"""    _pm = args.parallel or cfg.get("actions", {}).get(
        "parallel_mode", "auto") or "auto"
    _mode_disp = {
        "serial": "严格串行",
        "A": "A · 四层独立并行 + 汇流",
        "B": "B · 轮次并行",
        "auto": "auto · 自动决策",
    }.get(_pm, _pm)

    print(f"\n{'═'*60}")
    print(f"元 DGTF v{__version__} · {question}")
    print(f"{'═'*60}")
    print(f"调度：{' → '.join(route)}")
    if keep:
        print(f"保留：{keep}")
    print(f"螺旋上限（每层圈数）：{args.rounds}")
    print(f"并行模式：{_mode_disp}"
          f"{'' if args.parallel else '（来自配置）'}")
    ch = channels if channels is not None else cfg["memory"].get(
        "channels", ["content", "context", "self"])
    print(f"回来通道：{'、'.join(ch) if ch else '全关（历史不参与本次）'}")
    print(f"{'═'*60}")

    result = meta.run(question, route=route, keep=keep,
                      rounds=args.rounds, channels=channels,
                      parallel_mode=_pm)""")

# ---------------------------------------------------------------- 落盘 confluence
P("save-confluence", r"""        for t in intersect:
            f.write(f"- {t}\n")
        if not intersect:
            f.write("（无——三棵树没有共同够不到的面）\n")
        f.write("\n---\n\n")

    print(f"📁 已保存: {md}")
    return md""", r"""        for t in intersect:
            f.write(f"- {t}\n")
        if not intersect:
            f.write("（无——三棵树没有共同够不到的面）\n")
        f.write("\n---\n\n")

    # [fix-101] route 不含 all 时，A 模式的汇流圈结果也要落盘
    conf = result.get("confluence")
    if conf:
        f.write("## 汇流圈\n\n")
        f.write("_本次 route 未含 all 层，以下是汇流圈单独跑出的元层结果。_\n\n")
        f.write(f"**锚点**：{conf.get('anchor', '')}\n\n")
        if conf.get("collision"):
            f.write(f"**ing 对撞**：\n\n{conf['collision']}\n\n")
        amps = conf.get("amps") or []
        if amps:
            f.write("**& 印记**：\n")
            for a in amps:
                f.write(f"- [{AMP_TYPES.get(a.get('type', ''), '?')}] "
                        f"{a.get('desc', '')}\n")
            f.write("\n")
        if conf.get("manifest"):
            f.write(f"**view 显形**：\n\n{conf['manifest']}\n\n")
        f.write("---\n\n")

    print(f"📁 已保存: {md}")
    return md""")


def main() -> int:
    if not TARGET.exists():
        print(f"找不到目标文件：{TARGET}")
        return 1
    src = TARGET.read_text(encoding="utf-8")
    applied, skipped, failed = [], [], []

    for name, old, new in PATCHES:
        n = src.count(old)
        if n == 0:
            if src.count(new) > 0:
                skipped.append(name)
            else:
                failed.append(f"{name}: old 匹配不到")
            continue
        if n > 1:
            failed.append(f"{name}: old 出现 {n} 次，不唯一")
            continue
        src = src.replace(old, new, 1)
        applied.append(name)

    if failed:
        print("✗ 以下补丁失败，未写盘：")
        for f in failed:
            print("   -", f)
        return 1

    TARGET.write_text(src, encoding="utf-8")
    print(f"✓ 应用 {len(applied)} 条，跳过（已存在）{len(skipped)} 条")
    for a in applied:
        print("   +", a)
    if skipped:
        for s in skipped:
            print("   =", s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
