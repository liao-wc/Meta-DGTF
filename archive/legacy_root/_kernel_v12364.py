# ============================================================
# 前沿内核 F · 任意停时统计 / 保形预测 / 贝叶斯变点 / 抽象论证
# ============================================================
# 这一节只放纯函数与无副作用对象：不读配置、不写盘、不调 LLM。
# 因此它可以被判据单独驱动（见 _chk_v12364_dev.py），也可以被引擎按需接线。
#
# 四条依据（都可复核，均不引入第三方依赖）：
#   F1 e-process / 博弈论统计（Ramdas, Grünwald, Vovk & Shafer, 2023）：
#      非负鞅 + Ville 不等式 ⇒ 对任意停时 I 类错误 ≤ α。
#      比固定样本区间强在：本项目每圈都在看读数（optional stopping）。
#   F2 保形预测（Vovk et al., 2005；Angelopoulos & Bates, 2023）：
#      可交换性下边际覆盖率 ≥ 1−α，分布无关，只需一个非一致性分数。
#   F3 BOCPD（Adams & MacKay, 2007）：贝叶斯在线变点后验，给出 P(本步变点)。
#   F4 Dung 抽象论证（Dung, 1995）+ 负担式排序（Besnard & Hunter, 2001）：
#      冲突不删除、只标 defeated；排序并列时保持 undecided
#      —— 对应红线「未对齐是合法状态」。
# ============================================================

#: e-process 的 λ 网格。★ 必须 < 1/p0（否则因子可能为负、不再是鞅）。
#: 0.5 附近的判定用满网格；求下界时用更保守的子集（见 _EV_LAMBDAS_LB）。
_EV_LAMBDAS = (0.10, 0.25, 0.40, 0.55, 0.70, 0.90, 1.10, 1.30, 1.50, 1.75)
_EV_LAMBDAS_LB = (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)


def _ev_log_wealth(xs, p0, lambdas):
    """固定 p0 下，各 λ 的对数财富 + 混合（log-sum-exp）。返回 (log_e, 用到的 λ 数)。"""
    p0 = min(max(float(p0), 1e-6), 1.0 - 1e-6)
    logs = []
    for lam in lambdas:
        lam = float(lam)
        # 1 + λ(x−p0) 必须 > 0：x∈{0,1} ⇒ λ < 1/p0 即可。
        if lam <= 0.0 or lam >= 1.0 / p0:
            continue
        s = 0.0
        for x in xs:
            # log1p 在 λ(x−p0) 接近 0 时比 log(1+·) 稳。
            s += math.log1p(lam * (float(x) - p0))
        logs.append(s)
    if not logs:
        return 0.0, 0
    m = max(logs)
    # log(mean(exp(logs)))：均匀混合本身就是非负鞅（凸组合）。
    mix = m + math.log(sum(math.exp(v - m) for v in logs) / float(len(logs)))
    return mix, len(logs)


def evalue_bernoulli(seq, p0: float = 0.5,
                     lambdas=_EV_LAMBDAS) -> dict:
    """H0: p ≤ p0 对 H1: p > p0 的任意停时 e-value。

    返回 {n, mean, p0, log_evalue, evalue, lambdas_used}。
    ★ 判定口径：evalue >= 1/alpha ⇒ 在水平 alpha 下拒绝 H0，且这个结论
      对「边跑边看、随时停」仍然有效（Ville 不等式）。样本 < 2 ⇒ evalue=1。
    ★ 只吃 0/1 序列；非 0/1 先按 >=0.5 二值化（与 stitched_hoeffding_lower 同口径）。
    """
    try:
        xs = [1.0 if float(x) >= 0.5 else 0.0 for x in (seq or [])]
    except (TypeError, ValueError):
        return {"n": 0, "mean": None, "p0": float(p0), "log_evalue": 0.0,
                "evalue": 1.0, "lambdas_used": 0}
    n = len(xs)
    mean = (sum(xs) / float(n)) if n else None
    if n < 2:
        return {"n": n, "mean": mean, "p0": float(p0), "log_evalue": 0.0,
                "evalue": 1.0, "lambdas_used": 0}
    lg, used = _ev_log_wealth(xs, p0, lambdas)
    # exp(710) 已溢出 float；留一个可比较的上界即可。
    ev = float("inf") if lg > 709.0 else math.exp(lg)
    return {"n": n, "mean": round(mean, 4), "p0": round(float(p0), 6),
            "log_evalue": round(lg, 6), "evalue": ev, "lambdas_used": used}


def anytime_decided_e(seq, delta: float = 0.05, thr: float = 0.5):
    """e-process 版的「多数已确立」：与任何时候看都有效的停止判据同口径。

    ★ 与 anytime_majority_decided（stitched Hoeffding）同签名同返回形状，
      便于在调用点按配置切换；两者都不改变停止判据的语义，只换置信方式。
    """
    d = float(delta if (delta and 0 < delta < 1) else 0.05)
    r = evalue_bernoulli(seq, p0=float(thr))
    ok = bool(r["n"] >= 2 and r["evalue"] >= 1.0 / d)
    out = dict(r)
    out.update({"alpha": d, "reject": ok})
    return ok, out


def anytime_decided(seq, delta: float = 0.05, thr: float = 0.5,
                    mode: str = "hoeffding"):
    """停止判据的统一入口：hoeffding（默认，逐字不变）/ evalue（opt-in）。

    ★ 为什么保留两条：e-process 更省样本，但它的读数（e-value）不是概率，
      人读时常误当成置信度；默认不换，打开的人要看得见 mode。
    """
    m = str(mode or "hoeffding").strip().lower()
    if m in ("evalue", "e-process", "eprocess", "e"):
        ok, info = anytime_decided_e(seq, delta=delta, thr=thr)
        info["mode"] = "evalue"
        return ok, info
    lb = stitched_hoeffding_lower(seq, delta)
    if not lb:
        return False, {"why": "样本不足（n<2）", "mode": "hoeffding"}
    out = dict(lb)
    out["mode"] = "hoeffding"
    return bool(lb["lower"] > float(thr)), out


# ── F2 保形预测 ──────────────────────────────────────────────
def conformal_quantile(cal_scores, alpha: float = 0.1) -> float:
    """(1−alpha) 保形分位数（有限样本修正：第 ceil((n+1)(1−alpha)) 个最小分数）。

    ★ 样本不足 ⇒ 返回 +inf（预测集取全集 = 全弃权），这是保守而不是错。
    """
    s = sorted(float(x) for x in (cal_scores or []) if x is not None)
    n = len(s)
    if n == 0:
        return float("inf")
    a = float(alpha if (alpha and 0 < alpha < 1) else 0.1)
    k = int(math.ceil((n + 1) * (1.0 - a)))
    if k > n:
        return float("inf")
    return s[max(0, k - 1)]


def conformal_pvalue(cal_scores, score: float) -> float:
    """交换性下的保形 p 值：(1 + #{校准分数 ≥ 新分数}) / (n+1)。"""
    s = [float(x) for x in (cal_scores or []) if x is not None]
    n = len(s)
    if n == 0:
        return 1.0
    ge = sum(1 for x in s if x >= float(score))
    return (1.0 + ge) / (n + 1.0)


def conformal_prediction_set(cal_scores, label_scores: dict,
                             alpha: float = 0.1) -> list:
    """给定各标签的非一致性分数 ⇒ 覆盖 ≥1−alpha 的预测集（可能为空/多标签）。

    ★ 空集 = 证据与校准集全不相容；调用方应把它读成「弃权」，不是「无标签」。
    """
    q = conformal_quantile(cal_scores, alpha)
    return sorted([str(k) for k, v in (label_scores or {}).items()
                   if v is not None and float(v) <= q])


# ── F3 BOCPD ────────────────────────────────────────────────
def _bocpd_pred(x, s1, s2, r, mu0, kappa0, alpha0, beta0) -> float:
    """run length = r 时 x 的 Student-t 预测密度（NIG 共轭）。"""
    k = kappa0 + r
    mu = (kappa0 * mu0 + s1) / k
    alpha = alpha0 + 0.5 * r
    beta = beta0 + 0.5 * (s2 + kappa0 * mu0 * mu0 - k * mu * mu)
    beta = max(beta, 1e-12)
    df = 2.0 * alpha
    scale = math.sqrt(max(beta * (k + 1.0) / (alpha * k), 1e-18))
    z = (float(x) - mu) / scale
    lp = (math.lgamma((df + 1.0) / 2.0) - math.lgamma(df / 2.0)
          - 0.5 * math.log(df * math.pi) - math.log(scale)
          - 0.5 * (df + 1.0) * math.log1p(z * z / df))
    return math.exp(max(min(lp, 700.0), -700.0))


def bocpd_run(series, hazard: float = 0.05, max_run: int = 240) -> dict:
    """贝叶斯在线变点检测（NIG 共轭 + run-length 后验）。

    返回：
      change_probs[i]  —— 观察到第 i 个点后「此刻发生变点」的后验概率
      map_run_length   —— 后验众数 run length（越大 = 当前制度越久）
      detected         —— change_probs ≥ max(0.5, 3×hazard) 的下标
      last_change_prob —— 末点变点概率（读数缺失回 None，不印 0）
    ★ 复杂度 O(n·R)，R 由 max_run 截断；默认 240 足够覆盖本项目圈数。
    """
    try:
        xs = [float(x) for x in (series or []) if x is not None]
    except (TypeError, ValueError):
        xs = []
    n = len(xs)
    if n < 3:
        return {"n": n, "change_probs": [], "map_run_length": [],
                "detected": [], "last_change_prob": None}
    h = min(max(float(hazard), 1e-4), 0.5)
    _m0 = sum(xs[:min(10, n)]) / float(min(10, n))
    _v0 = sum((x - _m0) ** 2 for x in xs[:min(20, n)]) / float(max(1, min(20, n) - 1))
    mu0, kappa0, alpha0, beta0 = _m0, 1.0, 1.0, max(_v0, 1e-6) * 0.5
    # 初始：只有 run length 0，权重 1；sum1/sum2 为各 run 的充分统计量。
    R = [1.0]
    s1 = [0.0]
    s2 = [0.0]
    probs, rls, shortp = [], [], []
    for i in range(n):
        x = xs[i]
        m = len(R)
        preds = [_bocpd_pred(x, s1[r], s2[r], r, mu0, kappa0,
                             alpha0, beta0) for r in range(m)]
        cp = h * sum(R[r] * preds[r] for r in range(m))
        newR = [cp] + [(1.0 - h) * R[r] * preds[r] for r in range(m)]
        Z = sum(newR)
        if not (Z > 0.0) or not math.isfinite(Z):
            # 数值塌了 ⇒ 回到均匀后验（留痕由调用方看 detected 为空判断）
            newR = [1.0 / float(m + 1)] * (m + 1)
            Z = 1.0
        newR = [v / Z for v in newR]
        R = newR
        s1 = [0.0] + [s1[r] + x for r in range(m)]
        s2 = [0.0] + [s2[r] + x * x for r in range(m)]
        if len(R) > max_run:          # 截断最久的那一端，控制内存/时延
            R, s1, s2 = R[:max_run], s1[:max_run], s2[:max_run]
        probs.append(R[0])
        rls.append(max(range(len(R)), key=lambda k: R[k]))
        # 「最近 3 步内发生过变点」的后验质量（比 P(r=0) 稳：后者被 r=1 分流）
        shortp.append(sum(R[:min(4, len(R))]))
    # ★ 判据取「MAP run length 归零」而不是 P(r=0)>=0.5：
    #   BOCPD 的 P(r_t=0) 通常被「r_t=1（上一步变点）」分流，量级只有 hazard；
    #   真正可复现的信号是**后验众数 run length 从长突然归到 1/2**。
    #   负对照：平稳序列不应出现「长→短」的跳变（见 _chk_v12364_kernel.py F5c）。
    thr = max(0.5, 3.0 * h)
    # ★ 判据取「最近 3 步内有变点的后验质量 ≥ 0.5，且此前 5 步没到过 0.5」：
    #   这是变点**起点**，不是 P(r=0)（后者被 r=1 分流，量级只有 hazard）。
    #   负对照：平稳序列不应出现该跳变（见 _chk_v12364_kernel.py F5c）。
    detected = []
    for i in range(1, n):
        if shortp[i] >= 0.5 and max(shortp[max(0, i - 5):i] or [0.0]) < 0.5:
            detected.append(i)
    return {"n": n, "change_probs": [round(v, 6) for v in probs],
            "map_run_length": rls,
            "short_run_prob": [round(v, 6) for v in shortp],
            "detected": detected,
            "last_change_prob": round(probs[-1], 6),
            "hazard": h, "threshold": round(thr, 6)}


# ── F4 Dung 抽象论证 ─────────────────────────────────────────
class ArgumentationFramework:
    """有限抽象论证框架 AF = (Args, Attacks) 的只读语义计算。

    ★ 只做三件可复核的事：
      1) grounded 扩展（唯一、怀疑论语义）；
      2) 负担式排序（Besnard & Hunter 2001 的思想：被攻击越多负担越重）；
      3) 弱连通分量（把「互不相干的冲突」分开处理，避免全局排序串味）。
    ★ 不删除任何论证；「谁赢」只是标签，不是删除。
    """

    def __init__(self, arguments, attacks):
        _seen = []
        for a in (arguments or []):
            a = str(a)
            if a and a not in _seen:
                _seen.append(a)
        self.args = _seen
        _aset = set(_seen)
        self.attacks = {(str(a), str(b)) for (a, b) in (attacks or [])
                        if str(a) in _aset and str(b) in _aset
                        and str(a) != str(b)}
        self._att = {a: set() for a in self.args}
        for a, b in self.attacks:
            self._att[b].add(a)          # 谁攻击 b

    def attackers(self, a):
        return set(self._att.get(str(a), ()))

    def grounded_extension(self) -> list:
        """标准不动点：IN 里的每个论证的所有攻击者都已在 OUT。"""
        IN, OUT = set(), set()
        changed = True
        while changed:
            changed = False
            for a in self.args:
                if a in IN or a in OUT:
                    continue
                atk = self._att.get(a, set())
                if all(b in OUT for b in atk):
                    IN.add(a)
                    changed = True
                elif any(b in IN for b in atk):
                    OUT.add(a)
                    changed = True
        return [a for a in self.args if a in IN]

    def defeated(self) -> list:
        g = set(self.grounded_extension())
        return [a for a in self.args if a not in g]

    def burdens(self, iters: int = 200, damping: float = 0.5) -> dict:
        """负担 b(a) = 1 + Σ_{x∈Att(a)} 1/b(x)；越小越强（阻尼迭代求不动点）。"""
        b = {a: 1.0 for a in self.args}
        for _ in range(max(1, int(iters))):
            nb = {}
            for a in self.args:
                s = 1.0
                for x in self._att.get(a, ()):
                    s += 1.0 / max(b.get(x, 1.0), 1e-6)
                nb[a] = min(s, 1e6)
            diff = max((abs(nb[a] - b[a]) for a in self.args), default=0.0)
            b = {a: (1.0 - damping) * b[a] + damping * nb[a] for a in self.args}
            if diff < 1e-8:
                break
        return b

    def components(self) -> list:
        """攻击关系的弱连通分量（并查集）；孤立点各自成组。"""
        parent = {a: a for a in self.args}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a, b in self.attacks:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
        out = {}
        for a in self.args:
            out.setdefault(find(a), []).append(a)
        return list(out.values())


def arguments_from_playbook(playbook) -> tuple:
    """把 playbook 条目映射成论证图：同 (kind, cond) 下动作不同 ⇒ 互相攻击。

    返回 (args, attacks, by_id)。★ 只取 active/shadow：retired 不参与现役冲突。
    """
    by_id, by_key = {}, {}
    for e in (playbook or []):
        if not isinstance(e, dict):
            continue
        if e.get("status") not in ("active", "shadow"):
            continue
        aid = str(e.get("id") or "").strip()
        if not aid or aid in by_id:
            continue
        by_id[aid] = e
        k = (str(e.get("kind") or ""),
             json.dumps(e.get("cond") or {}, ensure_ascii=False, sort_keys=True))
        by_key.setdefault(k, []).append(aid)
    attacks = set()
    for ids in by_key.values():
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                ai = json.dumps(by_id[ids[i]].get("action") or {},
                                ensure_ascii=False, sort_keys=True)
                aj = json.dumps(by_id[ids[j]].get("action") or {},
                                ensure_ascii=False, sort_keys=True)
                if ai != aj:             # 同一条件下的不同动作 = 规范冲突
                    attacks.add((ids[i], ids[j]))
                    attacks.add((ids[j], ids[i]))
    for aid, e in by_id.items():
        for t in (e.get("attacks") or []):
            if str(t) in by_id and str(t) != aid:
                attacks.add((aid, str(t)))
    return list(by_id), sorted(attacks), by_id


def resolve_playbook_conflicts(playbook, semantics: str = "grounded",
                               apply: bool = True, margin: float = 1e-6) -> dict:
    """对 playbook 做只标不删的冲突裁决。

    ★ 判据顺序（写死，可负对照）：
      ① grounded 扩展里恰好只有一个 ⇒ 它赢（怀疑论语义，最稳）；
      ② 否则比负担，唯一最小 ⇒ 它赢；
      ③ 并列 ⇒ 全部 undecided，不强行对齐（红线 3）。
    ★ apply=False 时只算不写，供审计/负对照用。
    """
    args, attacks, by_id = arguments_from_playbook(playbook)
    af = ArgumentationFramework(args, attacks)
    grounded = af.grounded_extension()
    gset = set(grounded)
    burden = af.burdens() if args else {}
    winners, defeated, undecided, comps = [], [], [], []
    for comp in af.components():
        # 只有一个论证 = 没有冲突：不裁决、不贴标签（负对照 F7d）。
        if len(comp) < 2:
            continue
        comps.append(sorted(comp))
        gin = [a for a in comp if a in gset]
        win = None
        if len(comp) > 1 and len(gin) == 1:
            win = gin[0]
        elif burden:
            mn = min(burden[a] for a in comp)
            top = [a for a in comp if burden[a] <= mn + float(margin)]
            if len(top) == 1:
                win = top[0]
            else:
                # ★ 负担并列时按「证据强度」破平（论证强度不只看攻击图）。
                #   仍是并列 ⇒ 不硬选（下面的 undecided 分支）。
                def _strength(a):
                    e = by_id.get(a) or {}
                    return (int(e.get("n_evidence", 0) or 0),
                            float(e.get("weight", 1.0) or 1.0),
                            float(e.get("quality_delta", 0.0) or 0.0)
                            - float(e.get("cost_delta", 0.0) or 0.0))
                best = max(_strength(a) for a in top)
                top2 = [a for a in top if _strength(a) == best]
                if len(top2) == 1:
                    win = top2[0]
        if win is None:
            undecided.extend(comp)
            if apply:
                for a in comp:
                    by_id[a]["arg_status"] = "undecided"
                    by_id[a].pop("defeated_by", None)
                    by_id[a]["arg_burden"] = round(burden.get(a, 0.0), 4)
            continue
        winners.append(win)
        for a in comp:
            if a == win:
                if apply:
                    by_id[a]["arg_status"] = "winner"
                    by_id[a].pop("defeated_by", None)
                    by_id[a]["arg_burden"] = round(burden.get(a, 0.0), 4)
            else:
                defeated.append(a)
                if apply:
                    by_id[a]["arg_status"] = "defeated"
                    by_id[a]["defeated_by"] = win
                    by_id[a]["arg_burden"] = round(burden.get(a, 0.0), 4)
    return {"semantics": str(semantics or "grounded"),
            "n_args": len(args), "n_attacks": len(attacks),
            "grounded": sorted(grounded), "winners": sorted(winners),
            "defeated": sorted(defeated), "undecided": sorted(set(undecided)),
            "components": comps}
