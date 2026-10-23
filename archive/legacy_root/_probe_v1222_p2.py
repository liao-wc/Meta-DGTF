# -*- coding: utf-8 -*-
"""[v1.22.2 P2] 探针：not_do 四处（schema → 白名单 → 抽取 → 渲染）是否打通。

用法：python _probe_v1222_p2.py [元DGTF-V1.22.2.py]
改前跑（v1.22.1）应当**假**：没有 _norm_schema_not_do、_extract_not_do 不认 schema。
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "元DGTF-V1.22.2.py"
if not SRC.is_absolute():
    SRC = HERE / SRC
txt = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")

spec = importlib.util.spec_from_file_location("dgtf_p2", SRC)
mod = importlib.util.module_from_spec(spec)
sys.modules["dgtf_p2"] = mod
spec.loader.exec_module(mod)

R = []


def ck(tag, cond, note=""):
    R.append((tag, bool(cond), note))


def region(t, a, b):
    i = t.find(a)
    j = t.find(b)
    return t[i:j] if (i >= 0 and j > i) else ""


# 1 prompt schema：not_do 在 decidable_product 区段内
_reg = region(txt, '"decidable_product": {', '"undecidable_product": {')
ck("P2.1 prompt schema 含 not_do", '"not_do"' in _reg,
   "取样区段长度 " + str(len(_reg)))
ck("P2.2 prompt schema not_do 有 what/why",
   '"what"' in _reg and '"why"' in _reg, "")
# 2 prompt 约束段
ck("P2.3 prompt 约束段存在", "not_do 段 · decision 取向必须产出" in txt, "")
ck("P2.4 约束段写了「明确不做的事」", "明确不做的事" in txt, "")

# 3 归一化白名单（★ 最危险的一处：不加就静默吞字段）
ck("P2.5 dec_norm 白名单含 not_do",
   '"not_do": _norm_schema_not_do(dec.get("not_do")),' in txt, "")
ck("P2.6 归一化函数存在", hasattr(mod, "_norm_schema_not_do"), "")

# 4 抽取函数双路径
ck("P2.7 _extract_not_do 存在", hasattr(mod, "_extract_not_do"), "")
ck("P2.8 _extract_not_do_lexical 保留", hasattr(mod, "_extract_not_do_lexical"), "")

# --- 行为 ---
if hasattr(mod, "_norm_schema_not_do"):
    _n = mod._norm_schema_not_do
    ck("P2.9 负对照：非 list → 空", _n(None) == [] and _n("x") == [], "")
    ck("P2.10 负对照：非 dict 条目丢弃", _n(["x", 1]) == [], "")
    ck("P2.11 负对照：空 what 丢弃",
       _n([{"what": "", "why": "y"}, {"what": "  "}]) == [], "")
    ck("P2.12 正对照：一条 what 保留",
       len(_n([{"what": "不在成因未定时动工", "why": "证据不足"}])) == 1, "")
    ck("P2.13 上限 6 条",
       len(_n([{"what": "w%d" % i} for i in range(9)])) == 6, "")

if hasattr(mod, "_extract_not_do"):
    _e = mod._extract_not_do
    # schema 优先
    _v = {"decidable_product": {"not_do": [
        {"what": "不在成因判定缺席时启动物探", "why": "判据未立"},
        {"what": "", "why": "空 what 要被丢"}]}}
    _got = _e(_v)
    ck("P2.14 schema 路径命中 + _source 标记",
       len(_got) == 1 and _got[0]["_source"] == "schema",
       repr(_got))
    ck("P2.15 负对照：空 what 被过滤（不计数）",
       all(x.get("what") for x in _got), repr(_got))
    # 无 schema → 词法兜底
    _v2 = type("V", (), {"decidable_product": {}})()
    _got2 = _e(_v2)
    ck("P2.16 无 schema → 词法兜底（_source=lexical 或空）",
       all(x.get("_source") == "lexical" for x in _got2), repr(_got2))
    # 负对照：完全空 view → 0 条
    _v3 = type("V", (), {"decidable_product": {}})()
    ck("P2.17 负对照：空 view → 0 条", _e(_v3) == [], repr(_e(_v3)))
    # 已抽过的 dict 直接返回
    ck("P2.18 已抽过（dict 带 _not_do）直接返回",
       _e({"_not_do": [{"what": "x", "_source": "schema"}]})
       == [{"what": "x", "_source": "schema"}], "")

# 5 not_do_missing 只认 schema
_i = txt.find("_nd_schema = [x for x in _nd_d")
ck("P2.19 not_do_missing 只认 schema 来源", _i > 0, "")

# 6 rubric 负对照（真调用 bench_score.score_actions）
sys.path.insert(0, str(HERE / "bench"))
try:
    from bench_score import score_actions
    _a3 = [{"fallback": "退路1"}, {"fallback": "退路2"}, {"fallback": "退路3"}]
    ck("P2.20 rubric 负对照：actions=[] 且 not_do=[] → 0/3",
       score_actions([], [])["score"] == 0, "")
    ck("P2.21 rubric：actions 满 但 not_do 空 → 2/3",
       score_actions(_a3, [])["score"] == 2, "")
    ck("P2.22 rubric：actions 满 + not_do 非空 → 3/3",
       score_actions(_a3, [{"what": "不做X"}])["score"] == 3, "")
    ck("P2.23 rubric max=3 没变（没改判据）",
       score_actions(_a3, [{"what": "x"}])["max"] == 3, "")
except Exception as e:  # noqa: BLE001
    ck("P2.20 rubric 可导入", False, type(e).__name__ + ": " + str(e))

print("═══ probe v1222 P2 ═══")
for t, ok, note in R:
    print(("  ✓ " if ok else "  ✗ ") + t + ("　" + note if note else ""))
print("PASS %d / FAIL %d" % (sum(1 for _, o, _ in R if o),
                             sum(1 for _, o, _ in R if not o)))
sys.exit(0 if all(o for _, o, _ in R) else 1)
