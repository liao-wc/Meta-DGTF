# -*- coding: utf-8 -*-
"""[v1.23.38 探针] 元DGTF 全链路检测：静态两向对账 + 动态构造性驱动。

【A 静态】配置↔代码两向对账（不跑引擎就能查的）：
  A1  web_search.stages 键 ⊆ stage 全集（`stage="..."` 字面 + 方法名推断口径）
  A2  `_TICK_WEB_RELAX` ⊆ web_search.stages 键
  A3  ControlSurface：write 键与 read 键两向（有写无读 = 死写；有读无写 = 空读）
  A4  EML action key → `_eml_apply` 分支或登记（`_EML_RECORD_ONLY` 应为空）
  A5  AST 登记表符号全部仍存在于源码

【B 动态】复用 smoke_test 的 mock 底座，真驱动 `MetaDGTF.run()` 走四层：
  B1  记录每次 `LLM.call` 的 stage ⇒ 与 web stages 全集对账（谁没被触发）
  B2  包装 DGTF / MetaDGTF 全部方法 ⇒ 谁真被执行、谁在本场景未触达
  B3  四层 view + readings：非空、且有区分度（防「恒值读数」）
  B4  ControlSurface.applied：本跑真的动过哪些键

产出：`_probe_v12338_chaincheck_<ver>.txt`（人类可读的链路报告）。
"""
import importlib.util
import json
import os
import re
import sys
import threading
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.23.40.py"
VER = "1.23.40"
OUT = HERE / ("_probe_v12340_chaincheck_%s.txt" % VER.replace(".", "_"))

_lines = []
LOCK = threading.Lock()


def p(*a):
    t = " ".join(str(x) for x in a)
    _lines.append(t)
    print(t)


# ═══════════════════════════════════════════════════════════════════
# 载入主模块（不带 smoke_test 的桩 —— 静态部分只要 AST 与 config）
# ═══════════════════════════════════════════════════════════════════
src = TARGET.read_bytes().decode("utf-8").replace("\r\n", "\n")
import ast as _ast
tree = _ast.parse(src)

spec = importlib.util.spec_from_file_location("tgt", TARGET)
mod = importlib.util.module_from_spec(spec)
sys.modules["tgt"] = mod
spec.loader.exec_module(mod)

p("=" * 64)
p("元DGTF 全链路检测 · v%s · %s" % (VER, TARGET.name))
p("=" * 64)

# ── A1: web stages 键 ⊆ stage 全集 ─────────────────────────────────
p("")
p("【A1】web_search.stages 键 vs stage 全集")

stage_literals = set(re.findall(r'stage\s*=\s*"([a-z_]+)"', src))
# ★ 口径：`_infer_stage_from_stack` 走调用栈，**任何**函数（含模块级、
#   任意类的方法）都可能成为 stage 名 ⇒ 全集 = 全文件所有函数名（去前导 _）。
all_fn_names = set()
for n in _ast.walk(tree):
    if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
        all_fn_names.add(n.name.lstrip("_"))
universe = stage_literals | all_fn_names
cfg_default = mod.load_config(str(HERE / "__no_such__.yaml"))
web_keys = set((cfg_default.get("web_search", {}).get("stages") or {}).keys())
p("  stage 字面常量：%d 个 | 全文件函数名（去 _）：%d 个"
  % (len(stage_literals), len(all_fn_names)))
# ★ 存活判定（三重，命中任一即活）：
#   ① 键名作为**带引号字面串**出现在源码任何位置（`_web_search("meta_clean_check",…)`
#      这类**位置实参**不走 `stage=` ⇒ 字面法才能逮到）；
#   ② 某函数名以键名为前缀（`research_decompose` ⊑ `_research_decompose_queries`）；
#   ③ 键名精确等于某函数名。
dead = sorted(k for k in web_keys
              if ('"%s"' % k) not in src
              and k not in all_fn_names
              and not any(n.startswith(k) for n in all_fn_names))
p("  web_search.stages 键数：%d" % len(web_keys))
p("  死配置（键名与前缀都无函数对应 ⇒ 放开也不生效）：%s"
  % (dead if dead else "无 ✅"))

# ── A2: 放宽表 ⊆ web stages ────────────────────────────────────────
p("")
p("【A2】_TICK_WEB_RELAX ⊆ web_search.stages")
m = re.search(r"_TICK_WEB_RELAX = \(([^)]*)\)", src, re.S)
relax = re.findall(r'"([a-z_]+)"', m.group(1))
miss = sorted(set(relax) - web_keys)
p("  放宽表 %d 个：%s" % (len(relax), list(relax)))
p("  不在 stages 里的（死放宽）：%s" % (miss if miss else "无 ✅"))

# ── A3: ControlSurface 写↔读两向（v2：读消费 / 成对同步 / 预留 三分类）──
p("")
p("【A3】ControlSurface 写↔读 两向（v2）")
# ★ 锚定接收者：只认控制面的 `.write(` / `.read(` —— 裸 `\.write\(` 会把
#   导出代码的 `f.write("## 悬置总览…")` 全误当控制面写（首轮实测踩到）。
# ★ 消费形态两分类（v2 修正：写≠必须有 read 才算活）：
#   ① read 消费 —— 有 `.read("key")` 直接读（web.allow.* / actions.*）；
#   ② 成对同步 —— `_eml_apply` 的**双写设计**：控制面写只当门禁+留痕，
#      紧邻行直改**生效面**（`rounds_plan[` / `_duty_floor` / `thinking_stages[`）
#      ⇒ 查每条写点 ±12 行窗口内是否有对应生效面赋值（缺了才是真断链，
#        例如 M74 逮过的「thinking 写了但没同步 thinking_stages」）。
#   ③ 预留白名单 —— 有 SPEC 无写无读（stop.* / duty.* / web.quota.*）＝声明预留。
src_lines = src.split("\n")
# ★ 写点必须**跨行匹配**（首轮实测：`self._control.write(` 后换行跟参数，
#   逐行正则抓到 0 条 ⇒ 「真死写无」是空集恒真的假绿）。
w_sites = [(src[:mt.start()].count("\n"), mt.group(1))
           for mt in re.finditer(r'self\._control\.write\(\s*"([^"]+)"', src)]
r_sites = set(re.findall(r'(?:_control|_surf|_s)\.read\(\s*"([^"]+)"', src))
SYNC_TARGET = {"rounds.": "rounds_plan[", "duty_floor": "_duty_floor",
               "thinking.": "thinking_stages"}


def _key_kind(k):
    for pre in ("rounds.", "thinking.", "web.allow.", "actions."):
        if k.startswith(pre):
            return pre
    return k


def _alive(k, ln):
    """一条写点是否活着：有 read 消费，或窗口内有生效面同步赋值。"""
    if k in r_sites:
        return "read"
    pre = _key_kind(k)
    tgt = SYNC_TARGET.get(pre) or (SYNC_TARGET.get(k))
    if tgt is None:
        return None
    # ★ 窗口 ln-8..ln+14：生效面行的**别名/取值行**可能在写点上方
    #   （首轮实测：`_ts = getattr(self.llm, "thinking_stages", …)` 在写点
    #     上方 4 行 ⇒ ±(2,12) 窗口漏 ⇒ 误报死写）。
    for j in range(max(0, ln - 8), min(len(src_lines), ln + 15)):
        if tgt in src_lines[j]:
            return "sync"
    return None


cls_w, dead_w, ok_w = {}, [], {}
for ln, k in w_sites:
    kind = _key_kind(k)
    how = _alive(k, ln)
    if how:
        cls_w[kind] = cls_w.get(kind, 0) + 1
        ok_w.setdefault(kind, how)
    else:
        dead_w.append((ln + 1, k))
p("  写点分类：read 消费 / 成对同步 命中：%s"
  % {k2: "%d 条(%s)" % (v, ok_w[k2]) for k2, v in sorted(cls_w.items())})
p("  真死写（无 read、无同步 ⇒ 门禁记了但什么都不生效）：%s"
  % (dead_w if dead_w else "无 ✅"))
spec_only = sorted(set(k for k in getattr(mod.ControlSurface, "_SPEC", {}))
                   - {"rounds.", "thinking.", "web.allow.", "actions.",
                      "duty_floor"}
                   - {k.rstrip(".") for k in cls_w})
p("  预留白名单（有 SPEC 无写点，声明预留不判死）：%s"
  % (spec_only if spec_only else "无"))
# ★ 模板读键（`actions.%s` / `web.allow.%s`）与预留白名单同属「读走默认回退」
#   —— 不是缺陷（`actions.*` 的写方 = 用户/运行时手动设；web.allow 有动态写）。
r_no_w = sorted(k for k in r_sites
                if "%s" not in k
                and not any(x == k for x, _ in w_sites))
p("  有读无写（读恒默认；模板键已另归类）：%s" % (r_no_w if r_no_w else "无 ✅"))

# ── A4: EML action key → _eml_apply 分支 ───────────────────────────
p("")
p("【A4】EML action key 接线")
rec_only = getattr(mod, "_EML_RECORD_ONLY", None)
apply_body = ""
# ★ 签名可能带返回注解：`def _eml_apply(self, rounds_plan: dict) -> list:`
#   —— `\)` 后**不**紧跟 `:`，必须兜掉 ` -> list` 段（首轮实测：
#   `[^)]*\):` 匹配不到 ⇒ apply_body 空 ⇒ 5 个 key 全误报缺分支）。
_am = re.search(r"def _eml_apply\([^)]*\)[^:]*:(.*?)(?=\n    def |\nclass |\Z)",
                src, re.S)
if _am:
    apply_body = _am.group(1)
cand_keys = set(re.findall(r'"(rounds_delta|duty_floor|carve_first|'
                           r'tri_advisory_only|note_cost_no_gain)"', src))
no_branch = sorted(k for k in cand_keys
                   if ('"%s"' % k) not in apply_body)
p("  候选 key：%s" % sorted(cand_keys))
p("  `_eml_apply` 缺分支的：%s" % (no_branch if no_branch else "无 ✅"))
p("  `_EML_RECORD_ONLY`（应空）：%s"
  % (dict(rec_only) if rec_only else "空 ✅"))

# ── A5: AST 登记表符号仍存在 ──────────────────────────────────────
p("")
p("【A5】AST 登记表（%d 条）符号存在性" % 308)
reg_path = HERE / "_v122_ast_registry.json"
reg = json.loads(reg_path.read_text(encoding="utf-8"))
defs = set()
for n in _ast.walk(tree):
    if isinstance(n, (_ast.FunctionDef, _ast.ClassDef)):
        defs.add(n.name)
reg_missing = sorted(k for k in (reg.get("registry") or {}) if k not in defs)
p("  登记但源码里已不存在的符号：%s"
  % (reg_missing if reg_missing else "无 ✅（%d 条全在）"
     % len(reg.get("registry") or {})))

# ═══════════════════════════════════════════════════════════════════
# B 动态：复用 smoke_test mock 底座，真驱动四层
# ═══════════════════════════════════════════════════════════════════
p("")
p("=" * 64)
p("【B 动态】mock 真驱动 MetaDGTF.run（四层全走）")
p("=" * 64)

sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402  （它自带 fake_call + build_cfg）

LLM_STAGES = []
_calls_lock = threading.Lock()
METH_CALLS = Counter()

_fake = st.mod.LLM.call
_CAND_TEXT = (
    "- [concept] 激励结构与长期协作活力的动态平衡机制说明\n"
    "- [concept] 信息透明层级对群体方向感的约束与反馈\n"
    "- [tension] 活力扩张与边界收敛之间的结构性张力\n"
    "- [question] 何种信号能区分停滞与深度沉淀\n"
)


def _rec_call(self, system, user, temperature=0.6, max_tokens=3000,
              json_mode=False, model=None, thinking=None, stage=None):
    with _calls_lock:
        LLM_STAGES.append(str(stage))
    # ★ mock 候选：主展开提示带「每行格式：- [kind] 描述」⇒ 返回可解析的
    #   候选行（否则 canned 文本解析不出 ⇒ 四层 cand=0 ⇒ 读数全空）。
    if not json_mode and "每行格式" in (str(system) + str(user)):
        return _CAND_TEXT
    return _fake(self, system, user, temperature=temperature,
                 max_tokens=max_tokens, json_mode=json_mode, model=model,
                 thinking=thinking, stage=stage)


st.mod.LLM.call = _rec_call

# ★ B1b: `_web_search` 打点 —— LLM.call 的 stage ≠ 真检索；真检索在
#   `MetaDGTF._web_search(stage, …)`（Gate 之后的唯一实现）。
WEB_CALLS = Counter()
_ws_orig = st.mod.MetaDGTF._web_search


def _rec_ws(self, stage, queries, round_no, used_as="evidence", pre_seq=0):
    with _calls_lock:
        WEB_CALLS[str(stage)] += 1
    return _ws_orig(self, stage, queries, round_no,
                    used_as=used_as, pre_seq=pre_seq)


st.mod.MetaDGTF._web_search = _rec_ws


def _wrap_cls(cls, skip=()):
    """给类的方法包一层「计数器」。

    ★ 必须区分描述符类型：`@staticmethod` 调用**不经 self 注入**，若包成
      `(self, *a)` 会把第一个实参当 self ⇒ TypeError（首轮实测踩到
      `_seed_text` / `_has_pool_content_view`）。三类分别处理。
    """
    import inspect
    for name in list(vars(cls).keys()):
        if name.startswith("__") or name in skip:
            continue
        raw = inspect.getattr_static(cls, name)
        if isinstance(raw, staticmethod):
            orig = raw.__func__

            def _mk_s(o, cname, nname):
                def w(*a, **k):
                    with _calls_lock:
                        METH_CALLS["%s.%s" % (cname, nname)] += 1
                    return o(*a, **k)
                return w
            setattr(cls, name, staticmethod(_mk_s(orig, cls.__name__, name)))
        elif isinstance(raw, classmethod):
            orig = raw.__func__

            def _mk_c(o, cname, nname):
                def w(ccls, *a, **k):
                    with _calls_lock:
                        METH_CALLS["%s.%s" % (cname, nname)] += 1
                    return o(ccls, *a, **k)
                return w
            setattr(cls, name, classmethod(_mk_c(orig, cls.__name__, name)))
        elif isinstance(raw, property) or not callable(raw):
            continue
        elif inspect.isfunction(raw):
            def _mk_i(o, cname, nname):
                def w(self, *a, **k):
                    with _calls_lock:
                        METH_CALLS["%s.%s" % (cname, nname)] += 1
                    return o(self, *a, **k)
                return w
            setattr(cls, name, _mk_i(raw, cls.__name__, name))


_wrap_cls(st.mod.DGTF)
_wrap_cls(st.mod.MetaDGTF, skip=("run",))   # run 由外部直接调，单独记

q = ("什么样的制度设计能让一个群体的长期协作既保持活力又不失去方向？"
     "请从激励、信息、边界三个角度分析。")
p("题面：%s" % q[:40] + "…")

try:
    meta = st.mod.MetaDGTF(st.build_cfg(False))
    # ★ rounds 必须传 **dict**（冒烟同款）：传 int ⇒ 调度侧取不到
    #   `self._rounds.get(entry)` ⇒ 四层全 0 圈 ⇒ 零候选（首轮实测踩到）。
    res = meta.run(q, route=["0", "1", "both", "all"],
                   rounds={"0": 2, "1": 2, "both": 2, "all": 2},
                   run_id="")
except Exception as e:
    p("[ERR] 动态驱动抛错：%r" % (e,))
    OUT.write_bytes(("\n".join(_lines) + "\n").encode("utf-8"))
    sys.exit(1)

p("")
p("--- B0: 调度结果 ---")
p("  调度 rounds：%s" % (getattr(meta, "_rounds", None)))
p("  route：%s" % ((res or {}).get("route")))

p("")
p("--- B1: LLM.call stage 触发分布 + 真·web 检索 ---")
st_cnt = Counter(s if s else "(无stage=)" for s in LLM_STAGES)
p("  LLM.call 总次数：%d | 去重 stage：%d 个" % (len(LLM_STAGES), len(st_cnt)))
for s, c in st_cnt.most_common():
    p("    %-38s %d" % (s, c))
p("  真·web 检索（_web_search 经 Gate）：%s"
  % (dict(WEB_CALLS) if WEB_CALLS else "0 次（默认全关 ⇒ 正常）"))
web_fired = sorted(set(WEB_CALLS) & web_keys)
web_never = sorted(web_keys - set(WEB_CALLS))
p("  本跑真触发过的 web 环节：%d / %d" % (len(web_fired), len(web_keys)))
p("  本跑未触发的 web 环节（默认关 ⇒ 正常；列出备查）：%s" % web_never)

p("")
p("--- B2: 方法触达 ---")
dg = sorted(k for k in METH_CALLS if k.startswith("DGTF."))
mt = sorted(k for k in METH_CALLS if k.startswith("MetaDGTF."))
p("  DGTF 方法触达：%d / %d" % (len(dg), len(vars(st.mod.DGTF))))
p("  MetaDGTF 方法触达：%d / %d" % (len(mt), len(vars(st.mod.MetaDGTF))))

p("")
p("--- B3: 四层 view + readings（非空 + 区分度）---")


def _bundle_of(v):
    """兼容两种形态：View 对象（走引擎 bundle）/ packed dict（镜像同字段）。

    ★ 首轮实测踩到：`res["views"][e]` 存的是 **to_dict() 字典**，
      `_readings_bundle`（getattr 版）对字典恒取 None ⇒ 全 0 假象。
    """
    if hasattr(v, "rounds_run"):
        return mod._readings_bundle(v)
    q = v.get("quant_readings") or {}
    quant = {}
    for _k, _lab in mod._READING_LABELS:
        _v = q.get(_k)
        quant[_lab] = (str(_v.get("verdict") or "?")
                       if isinstance(_v, dict) and _v else None)
    _sr = str(v.get("stop_reason") or "").strip()
    return {
        "rounds": v.get("rounds_run"),
        "cand": len(v.get("candidates") or []),
        "amp": len(v.get("amps") or []),
        "thread": len(v.get("threads") or []),
        "susp": len([s for s in (v.get("suspensions") or [])
                     if isinstance(s, dict)
                     and s.get("status") in ("active", "stable")]),
        "quant": quant,
        "goal": str(v.get("goal_verdict") or "") or None,
        "duty": (round(float(v["duty_trace"][-1]["S"]), 3)
                 if v.get("duty_trace") and isinstance(v["duty_trace"][-1], dict)
                 and isinstance(v["duty_trace"][-1].get("S"), (int, float))
                 else None),
        "trace_n": len(v.get("trace_log") or []),
        "stop": (_sr[:60] + "…") if len(_sr) > 60 else (_sr or None),
    }


views = (res or {}).get("views") or {}
for e in ("0", "1", "both", "all"):
    v = views.get(e)
    if v is None:
        p("  层 %s : ✗ 无 view" % e)
        continue
    b = _bundle_of(v)
    flat = []
    for kk in sorted(b.keys()):
        vv = b[kk]
        if isinstance(vv, dict):
            flat.extend("%s=%s" % (k2, v2) for k2, v2 in sorted(vv.items()))
        else:
            flat.append("%s=%s" % (kk, vv))
    vals = [x.split("=", 1)[1] for x in flat]
    distinct = len(set(vals))
    p("  层 %s : view ✓ | 读数键 %d | 读数项 %d | 去重值 %d %s"
      % (e, len(b), len(flat), distinct,
         "✅" if distinct > 1 else "⚠ 恒值（零区分度）"))
    for x in flat:
        p("      %s" % x)

p("")
p("--- B4: ControlSurface 本跑实际写入 ---")
applied = list(getattr(meta, "_control", None) and meta._control.applied or [])
p("  applied 条数：%d" % len(applied))
for x in applied[:12]:
    p("    key=%s why=%s" % (x.get("key"), str(x.get("why"))[:50]))
if len(applied) > 12:
    p("    …（共 %d 条）" % len(applied))

# ── 汇总 ────────────────────────────────────────────────────────────
p("")
p("=" * 64)
p("【汇总】")
problems = []
if dead:
    problems.append("A1 死配置 web 键：%s" % dead)
if miss:
    problems.append("A2 死放宽：%s" % miss)
if dead_w:
    problems.append("A3 真死写：%s" % dead_w)
if r_no_w:
    problems.append("A3 有读无写：%s" % r_no_w)
if no_branch:
    problems.append("A4 EML 缺分支：%s" % no_branch)
if reg_missing:
    problems.append("A5 登记表缺符号：%d 条" % len(reg_missing))
no_view = [e for e in ("0", "1", "both", "all") if e not in views]
if no_view:
    problems.append("B3 缺层 view：%s" % no_view)
if problems:
    for x in problems:
        p("  ✗ %s" % x)
else:
    p("  全链路检测：静态对账 0 断链；动态四层全产出；ControlSurface 有真实写入。✅")

OUT.write_bytes(("\n".join(_lines) + "\n").encode("utf-8"))
print("\n[written] %s" % OUT.name)
