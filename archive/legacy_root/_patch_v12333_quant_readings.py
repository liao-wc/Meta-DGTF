# 第六期补丁 P6-1：四个量化读数纯函数（L2/L3/L4）。
# ★ 全部**纯函数、不调 LLM**（零成本）；缺输入 ⇒ 不表态（回 None）。
# 依据见 `_各环节量化与降本依据_v12333.md`。
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

A0 = '''import sys
import time'''
NEW0 = '''import sys
import time
import unicodedata'''

# 插在 `layer_goal_action_hint` 之前（同一片区，读数类纯函数聚在一起）。
A1 = '''_LG_ACT_SETTLE_LOW = 0.6      # 研究层：确定率 < 此值 ⇒ 优先答未答层面'''

NEW1 = '''# ══════════════════════════════════════════════════════════════
# [第六期 · 各环节量化] 四个**零成本**读数（纯函数、不调 LLM）
#   依据见 `_各环节量化与降本依据_v12333.md`：
#     ① BenchDrift(arXiv:2608.11694) / reliable@k(arXiv:2512.14754)
#     ② SIEV(arXiv:2510.18134) 对抗性依从率
#     ③ RASC(NAACL2025) / DeepConf(ICLR2026) / Think@n 的早停
#     ④ 信息瓶颈：语义密度（>5 个无信息 token ⇒ 性能降 15%+）
#   ★ 四条通则：**缺输入 ⇒ 不表态**（回 None，不是 0）；
#     **只出读数与线索**，不改产物、不删候选（悬置不打分）。
# ══════════════════════════════════════════════════════════════

_YY_DIV_LOW = 0.30      # 阴阳分歧度低于此 ⇒ 判「假对撞」（依据 ②）


def yin_yang_divergence(yin, yang) -> dict:
    """[依据 ②] 阴阳两臂的**分歧度** —— 它们到底有没有在「对撞」。

    SIEV 的「对抗性依从率」：反题与正题**实际不一致**的比例。过低 ⇒
    模型只是换个说法复述（pS 高但推理深度低 = **假对撞**）。

    口径（两向都算，取最大相似度作「重合」）：
      · `divergence = 1 - max_i max_j sim(yin_i, yang_j)`
        —— 只有两臂**没有任何一对**说得像，才算真分歧。
      · ★ 用 `_overlap_coef`（本仓库既有的词面重合口径）+ `_similar`
        两条并列尺子，与去重判据同源（**同一把尺子**）。

    返回 `{n_yin, n_yang, max_sim, divergence, verdict}`；
    **任一侧为空 ⇒ divergence=None 且 verdict=""**（不表态）。
    """
    _ys = [str(x) for x in (yin or []) if str(x).strip()]
    _zs = [str(x) for x in (yang or []) if str(x).strip()]
    d = {"n_yin": len(_ys), "n_yang": len(_zs)}
    if not _ys or not _zs:
        d.update({"max_sim": None, "divergence": None, "verdict": ""})
        return d
    _best = 0.0
    for a in _ys:
        for b in _zs:
            _ov = _overlap_coef(a, b, _KW_TOP_N)
            _si = 1.0 if _similar(a, b, _DUP_SIM) else 0.0
            _best = max(_best, _ov, _si)
    d["max_sim"] = round(_best, 4)
    d["divergence"] = round(1.0 - _best, 4)
    d["verdict"] = ("fake_duel" if d["divergence"] < _YY_DIV_LOW else "ok")
    return d


_RF_THIN_RATIO = 0.35   # 重述长度不到原问题的这个比例 ⇒ 判 thin（信息太薄）
_RF_DRIFT_RATIO = 0.20  # 关键词覆盖率低于此 ⇒ 判 drifted（跑偏）


def restate_fidelity(question: str, anchor: str) -> dict:
    """[依据 ①] 锚点重述对原问题的**保真度** —— 重述跑偏则下游全白跑。

    BenchDrift / reliable@k 实测：含义保持的重述会让答案漂移，
    **强模型损失更大**。所以最上游该有这道闸门（**零 LLM 成本**）。

    口径（词面代理，不调模型）：
      · `coverage` = 原问题关键词被锚点覆盖的比例（漏掉 = 换题）；
      · `ratio`    = 锚点长度 / 原问题长度（过短 = 信息被压没了）。

    返回 `{coverage, ratio, fidelity, verdict}`；
    `verdict` ∈ `ok / thin / drifted`；**任一输入为空 ⇒ 全 None + ""**。
    """
    _q = str(question or "").strip()
    _a = str(anchor or "").strip()
    if not _q or not _a:
        return {"coverage": None, "ratio": None,
                "fidelity": None, "verdict": ""}
    _kq = _kw(_q, _KW_TOP_N) or set()
    _ka = _kw(_a, _KW_TOP_N) or set()
    _cov = (len(_kq & _ka) / float(len(_kq))) if _kq else None
    _rat = len(_a) / float(len(_q)) if _q else None
    if _cov is None or _rat is None:
        return {"coverage": None, "ratio": None,
                "fidelity": None, "verdict": ""}
    _cov = round(_cov, 4)
    _rat = round(_rat, 4)
    # 保真度 = 覆盖为主、长度惩罚为辅（长度只作**上限约束**，不奖长）。
    _pen = min(1.0, _rat / _RF_THIN_RATIO) if _rat < _RF_THIN_RATIO else 1.0
    _fid = round(_cov * _pen, 4)
    if _cov < _RF_DRIFT_RATIO:
        _vd = "drifted"
    elif _rat < _RF_THIN_RATIO:
        _vd = "thin"
    else:
        _vd = "ok"
    return {"coverage": _cov, "ratio": _rat, "fidelity": _fid, "verdict": _vd}


_SD_FILLER = (
    "的", "了", "是", "在", "和", "与", "或", "及", "这", "那", "一个", "一种",
    "非常", "十分", "比较", "可能", "也许", "大概", "其实", "实际上", "总的来说",
    "综上所述", "值得注意的是", "需要指出的是", "我们可以看到", "众所周知",
    "首先", "其次", "然后", "最后", "另外", "此外", "而且", "因此", "所以",
)


def _sd_is_punct(ch: str) -> bool:
    """标点 / 符号判定（Unicode 类别 P* 或 S*）。**内联实现**，不引新依赖。"""
    try:
        return unicodedata.category(ch)[0] in ("P", "S")
    except Exception:
        return False


def semantic_density(text: str) -> "float | None":
    """[依据 ④] 内容的**语义密度** —— 每字里有多少是任务相关信息。

    信息瓶颈口径：`R = I(X;Y)/H(X)`，优秀提示 R > 0.6；**超过 5 个
    无信息 token ⇒ 性能降 15%+**。这里用**零成本**词面代理：
      · 分母 = 去掉空白后的字符数；
      · 分子 = 内容词字符数（扣掉**填充语**与**纯标点**）。
    返回 `[0,1]`；**空输入 ⇒ None**（不表态）。
    """
    _t = str(text or "")
    if not _t.strip():
        return None
    _chars = [c for c in _t if not c.isspace()]
    if not _chars:
        return None
    _body = _t
    for _f in _SD_FILLER:
        _body = _body.replace(_f, "")
    _info = sum(1 for c in _body
                if not c.isspace() and not _sd_is_punct(c))
    return round(min(1.0, _info / float(len(_chars))), 4)


_LG_ACT_SETTLE_LOW = 0.6      # 研究层：确定率 < 此值 ⇒ 优先答未答层面'''


def _apply(text, anchor, new, tag):
    n = text.count(anchor)
    if n != 1:
        print("X %s 锚点命中 %d 次" % (tag, n)); sys.exit(1)
    return text.replace(anchor, new, 1)


def main():
    b = SRC.read_bytes()
    txt = b.decode("utf-8")
    if txt.count("\r\n") != txt.count("\n") or "\r\r\n" in txt:
        print("X 非纯 CRLF"); sys.exit(1)
    s = txt.replace("\r\n", "\n")
    # 前置依赖核查：工具函数必须已存在（否则新函数会 NameError）
    for _need in ("def _kw(", "def _overlap_coef(", "def _similar(", "import re"):
        if _need not in s:
            print("X 缺依赖 %s" % _need); sys.exit(1)
    if "import unicodedata" not in s:
        s = _apply(s, A0, NEW0, "A0")
    s = _apply(s, A1, NEW1, "A1")
    out = s.replace("\n", "\r\n").encode("utf-8")
    if out.decode("utf-8").count("\r\r\n"):
        print("X r-r-n"); sys.exit(1)
    SRC.write_bytes(out)
    print("OK 第六期补丁 P6-1 已打：四个读数纯函数")


if __name__ == "__main__":
    main()
