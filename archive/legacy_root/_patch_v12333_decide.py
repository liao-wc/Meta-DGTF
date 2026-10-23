# -*- coding: utf-8 -*-
"""v1.23.33 · 第三轮 patch-3：AutoTune **三阶段自主决策** + DGM archive 开放探索。

用户战略指令：
  「让 AutoTune 自主执行决策，包括**前期配置选择 / 中期动态调整 /
    后期学习纠正并输出结论**。」

依据：
  · **Darwin Gödel Machine**（Zhang et al. 2025, arXiv:2505.22954；ICLR 2026）
    —— 消融：贪心只从最优分支 = 39.7%；**带 archive 的开放探索 = 50.0%**。
    ⇒ 后期「学习纠正」**必须**维护 archive 且**禁止贪心**：
      每个候选（连劣配）都保留非零选择概率，才能越过「适应度低谷」。
  · **Successive Halving**（Li et al. 2017）：前期用**最少预算**粗筛。
  · **anytime-valid**（Howard et al. 2021）：中期**随时看随时停**都成立。

三段式（每段都只**产出决策**，不自动改配置 —— 「建议与执行分开」红线）：
  ① `autotune_phase_select`   前期配置选择：给定题面特征 ⇒ 建议 (mode, route)
  ② `autotune_phase_adjust`   中期动态调整：跑动中按目标读数 ⇒ 继续/收敛/回滚
  ③ `autotune_phase_learn`    后期学习纠正：archive 汇总 ⇒ 纠正 + 结论
  总入口 `autotune_decide(episodes, ...)` 把三段串成一次决策并留痕。
"""
from pathlib import Path

SRC = Path("元DGTF-V1.23.33.py")


def load_crlf(p):
    t = p.read_bytes().decode("utf-8")
    assert t.count("\n") == t.count("\r\n"), "非纯 CRLF"
    return t.replace("\r\n", "\n")


def save_crlf(p, t):
    assert "\r" not in t.replace("\r\n", "")
    out = t.replace("\r\n", "\n").replace("\n", "\r\n")
    assert out.count("\r\r\n") == 0
    p.write_bytes(out.encode("utf-8"))
    chk = p.read_bytes().decode("utf-8")
    assert chk.count("\n") == chk.count("\r\n")


def sub1(t, a, r):
    n = t.count(a)
    assert n == 1, "锚点命中 %d 次（必须 1）：%r" % (n, a[:90])
    return t.replace(a, r, 1)


#: 三段决策的**新函数块**（插在 `autotune_load_episodes` 之前）
BLOCK = '''#: [DGM archive] 开放探索的**最低选择概率**：连劣配也保留一点概率。
#:   ★ 依据 DGM 消融（Zhang et al. 2025）：贪心只从最优分支 = 39.7%，
#:     带 archive = 50.0% —— **不许把劣配的路径彻底掐死**。
_AT_ARCHIVE_FLOOR = 0.05
#: [DGM archive] 归档条目的**多样性下限**：archive 里至少要有这么多种
#:   不同的 (mode, route) 组合，否则「开放探索」名存实亡（退化成单点贪心）。
_AT_ARCHIVE_MIN_DIV = 2


def autotune_archive(episodes: list) -> dict:
    """[DGM archive] 从历史 episode 建**开放探索档案**（不是只留最优）。

    依据 Darwin Gödel Machine：archive 的价值在**越过适应度低谷** ——
    最优解常常经由「比父代更差」的中间体才走到。故本函数**保留全部**
    (mode, route) 组合，只给它们算**选择概率**：

      p(c) ∝ 质量秩 × 1/(1+已探索次数)     （质量高、探索少 ⇒ 概率高）
      再夹到 `[_AT_ARCHIVE_FLOOR, 1]` 并归一化 ⇒ **每个候选非零概率**。

    ★ 「只留最优」是贪心，DGM 已证劣于带 archive 的开放探索 ⇒ 本函数
      的存在本身就是判据（M35 变异体：改成只留最优必须判红）。
    """
    rows = autotune_rank(episodes or [], min_n=1)
    if not rows:
        return {"ok": False, "why": "无任何带质量的组", "arms": [], "n": 0}
    arms = []
    for r in rows:
        key = "%s|%s" % (r["mode"], ",".join(r["route"]))
        _q = r.get("quality_med")
        _c = r.get("cost_med")
        arms.append({"key": key, "mode": r["mode"], "route": list(r["route"]),
                     "n": int(r.get("n") or 0),
                     "quality_med": _q, "cost_med": _c,
                     "explored": int(r.get("n") or 0)})
    # 质量秩（降序；质量 None 排最后但**不剔除**）。
    arms.sort(key=lambda a: -(a["quality_med"]
                              if a["quality_med"] is not None else -1.0))
    _m = len(arms)
    raw = []
    for i, a in enumerate(arms):
        _rank = float(_m - i) / float(_m)             # 1.0 最优 → 1/m 最劣
        _nov = 1.0 / (1.0 + a["explored"])            # 探索少 ⇒ 高
        raw.append(max(_AT_ARCHIVE_FLOOR, _rank * _nov))
    _s = sum(raw) or 1.0
    for a, w in zip(arms, raw):
        a["prob"] = round(w / _s, 4)
    _div = len({a["key"] for a in arms})
    return {"ok": True, "arms": arms, "n": len(arms), "diversity": _div,
            "open_ended": bool(_div >= _AT_ARCHIVE_MIN_DIV),
            "why": "archive %d 臂 / 多样性 %d（floor=%.2f）"
                   % (len(arms), _div, _AT_ARCHIVE_FLOOR)}


def autotune_phase_select(episodes: list, q_features: dict = None,
                          quality_tau: float = 0.05,
                          min_n: int = 1) -> dict:
    """**前期配置选择**：给定题面特征 ⇒ 建议 (mode, 层集)。

    做法（两层，都可判据）：
      ① 若有**同题型**的历史组（`q_features` 命中）⇒ 用它出建议
         （冷启动 → 暖启动迁移）。
      ② 无同题型历史 ⇒ 退回全体历史（并**显式标注** `basis="global"`，
         不把「别的题型的结论」冒充成「这题的结论」）。
      ★ 依据 Successive Halving：前期用**最少预算**粗筛 —— 故本段只出
        「要跑哪些臂」，不出「跑多少圈」（圈数归中期动态调整）。
    """
    eps = list(episodes or [])
    basis = "global"
    pool = eps
    if q_features:
        _key = tuple(sorted((str(k), str(v)) for k, v in q_features.items()))
        same = [e for e in eps
                if tuple(sorted((str(k), str(v))
                                for k, v in (e.get("q_features") or {}).items()))
                == _key]
        if len(same) >= max(1, int(min_n)):
            pool, basis = same, "same_type"
    rec = autotune_recommend(pool, quality_tau=float(quality_tau),
                             min_n=int(min_n))
    rec["basis"] = basis
    rec["phase"] = "select"
    if rec.get("ok"):
        rec["decision"] = {"mode": rec.get("mode"),
                           "route": rec.get("route")}
    return rec


def autotune_phase_adjust(episodes: list, min_n: int = 2) -> dict:
    """**中期动态调整**：跑动中按目标读数趋势 ⇒ 继续 / 收敛 / 回滚。

    依据：**anytime-valid**（Howard et al. 2021）—— 随时看随时停都成立；
      **CSD / 早期预警**（Scheffer et al. 2009）—— 趋势变平/退就是信号。
    ★ 只对「同一 (mode,route) 至少 min_n 次带目标读数」的组表态；
      不足 ⇒ **不表态**（返回空 arms，绝不瞎猜）。
    """
    prog = autotune_progress(episodes or [], min_n=int(min_n))
    arms = []
    for key, d in prog.items():
        arms.append(dict(d, key=key))
    # 建议优先级：先处理「回滚」（最紧急），再「收敛」，最后「继续」。
    _order = {"回滚": 0, "收敛": 1, "继续": 2}
    arms.sort(key=lambda a: _order.get(a.get("advice"), 9))
    return {"phase": "adjust", "n_arms": len(arms), "arms": arms,
            "ok": bool(arms),
            "why": ("%d 组有趋势读数" % len(arms)) if arms
                   else "无组达到 min_n=%d（不表态）" % int(min_n)}


def autotune_phase_learn(episodes: list, min_n: int = 2) -> dict:
    """**后期学习纠正 + 输出结论**：archive 汇总 ⇒ 纠正 + 可读结论。

    依据 DGM 的**开放探索**：结论**不许只报冠军** —— 必须同时报
      (a) archive 多样性、(b) 被淘汰臂的**差在哪**（可解释的纠正）、
      (c) 每个建议的**证据强度**（`n<3` ⇒ 标注薄弱）。

    输出 `corrections`（每条 = 一个臂 + 一条「纠正理由」）与 `conclusion`
    （人可读的一句话结论）。★ 无证据 ⇒ `ok=False` + why，**不编结论**。
    """
    arc = autotune_archive(episodes or [])
    if not arc.get("ok"):
        return {"phase": "learn", "ok": False, "why": arc.get("why"),
                "corrections": [], "conclusion": ""}
    arms = arc["arms"]
    corrections = []
    if arms:
        _top = arms[0]
        for a in arms[1:]:
            _why = []
            if (a.get("quality_med") is not None
                    and _top.get("quality_med") is not None
                    and a["quality_med"] < _top["quality_med"] - 1e-9):
                _why.append("质量 %.3f < 最优 %.3f"
                            % (a["quality_med"], _top["quality_med"]))
            if (a.get("cost_med") is not None
                    and _top.get("cost_med") is not None
                    and a["cost_med"] > _top["cost_med"]):
                _why.append("成本 %.0f > 最优 %.0f"
                            % (a["cost_med"], _top["cost_med"]))
            corrections.append({
                "key": a["key"], "advice": "降权但不剔除（DGM 开放探索）",
                "reasons": _why or ["质量不劣但成本/探索次数待定"],
                "prob": a.get("prob")})
    _n_top = int(arms[0].get("n") or 0) if arms else 0
    _strength = "充分" if _n_top >= 3 else ("薄弱" if _n_top >= 1 else "无")
    conclusion = ("最优臂=%s（质量 %.3f / 成本 %.0f，n=%d，证据%s）；"
                  "archive 多样性=%d（开放探索=%s）"
                  % (arms[0]["key"], arms[0].get("quality_med") or 0.0,
                     arms[0].get("cost_med") or 0.0, _n_top, _strength,
                     arc["diversity"], "开" if arc["open_ended"] else "关")
                  ) if arms else "无臂可结论"
    return {"phase": "learn", "ok": True, "corrections": corrections,
            "conclusion": conclusion, "evidence_strength": _strength,
            "archive_diversity": arc["diversity"],
            "open_ended": arc["open_ended"], "n_arms": len(arms)}


def autotune_decide(episodes: list, q_features: dict = None,
                    quality_tau: float = 0.05, min_n: int = 2) -> dict:
    """**AutoTune 三阶段自主决策总入口** —— 前期选择 / 中期调整 / 后期学习。

    三段各自独立产出决策，最后合成一份**带留痕**的决策书：
      `{select:…, adjust:…, learn:…, summary:…}`。
    ★ 三段**都不改配置**：`select` 只建议、`adjust` 只表态、`learn` 只纠正。
      要采纳必须显式 `autotune_apply_to_cfg`（红线「建议与执行分开」）。
    """
    eps = list(episodes or [])
    sel = autotune_phase_select(eps, q_features=q_features,
                                quality_tau=quality_tau, min_n=1)
    adj = autotune_phase_adjust(eps, min_n=int(min_n))
    lrn = autotune_phase_learn(eps, min_n=int(min_n))
    _bits = []
    if sel.get("ok"):
        _bits.append("前期选 %s/%s（%s）"
                     % (sel.get("mode"), sel.get("route"), sel.get("basis")))
    else:
        _bits.append("前期选择：%s" % (sel.get("why") or "无建议"))
    _bits.append("中期调整：%d 组表态（%s）"
                 % (adj["n_arms"],
                    "；".join(a["key"] + "→" + a["advice"]
                              for a in adj["arms"][:3]) or "无"))
    if lrn.get("ok"):
        _bits.append("后期结论：%s" % lrn["conclusion"])
    else:
        _bits.append("后期学习：%s" % (lrn.get("why") or "无结论"))
    return {"select": sel, "adjust": adj, "learn": lrn,
            "summary": " | ".join(_bits), "n_episodes": len(eps)}


'''

t = load_crlf(SRC)
A = "def autotune_load_episodes(base=None, dirpath=None) -> list:\n"
t = sub1(t, A, BLOCK + A)
save_crlf(SRC, t)
print("OK: patch-3 三阶段自主决策 + DGM archive 完成")
