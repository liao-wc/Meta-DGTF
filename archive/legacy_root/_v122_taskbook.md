# 元 DGTF v1.21.77 → v1.22.0 · 完整自动化改造任务提示词（全文原样存档）

> 来源：https://chat.deepseek.com/share/awfoazypfqt90zj9rs
> 落盘时间：2026-10-04 · 用途：逐条对照执行，避免二次取用失真

> **用途**：把这一整段直接喂给 AI 编程助手（Claude / GPT / DeepSeek 等）。
> **执行方式**：严格按阶段串行。前一阶段验收未通过，不许进入下一阶段。
> **输出方式**：每完成一个 Step 输出一行 `[Phase N][Step N.M] 完成：<证据>`；每阶段结束输出 `[Phase N] 验收：通过/未通过`。

---

## 0. 角色与全局约束

### 0.1 你的角色

你是本次改造的**唯一执行者**。任务是在**不改引擎可执行语义**的前提下，给单文件 `元DGTF-V1.21.77.py`（约 17k 行）**加性**地补上六件事，使系统从“机制完备但效果未证”进入“效果可测、目标分层、外部可对账、机制精简”的状态。

### 0.2 六阶段与执行顺序

```
阶段 1（1+5）：Bench 骨架 + 目标函数分层
阶段 2（3）  ：三态多票化 + 冻结 + 人工校准
阶段 3（4）  ：decision 模式强制行动闭环
阶段 4（2）  ：外部锚点变真证据
阶段 5（6A） ：机制审计（只标不删）
阶段 6（6B） ：双实现收口
附 6C       ：拆模块方案（只出报告，不落地）
全局收尾    ：全量回归 + 版本定稿 + 报告
```

### 0.3 宪法级约束（违反即任务失败）

01. **加性优先**：新键、新参数默认值、新方法，不删旧行、不改旧键语义。
02. **失败必须留痕**：任何路径失败都要进 `view.errors` 或 `pool.meta` 或日志，不许静默。
03. **先量后改**：每阶段先跑探针拿改前基线，改后跑同一支探针出对照。
04. **不改阈值 / 常量**：本次不调任何已有阈值。新阈值走配置键，给默认值。
05. **不改模型配置**：不动 `DEFAULT_CONFIG["api"]`、不动 thinking stages。
06. **不动宪法级原则**：悬置不打分、未对齐合法、停止与清算分开、输入是形状不是数据、入池前挡重复、按层覆盖参数。
07. **CRLF 一致**：脚本改完文件后逐次核对行尾；替换前归一化成 LF，写完切回 CRLF。
08. **docstring 里零反斜杠**。
09. **每个阶段必须出**：`_probe_v122_phaseN_*_before.txt` / `_after.txt` + 冒烟 `check_v122_phaseN` + `v122_phaseN_报告.md`。
10. **不许一次全做**：一个阶段跑完、报告写完、对照通过，再开下一个。
11. **重构必须给 AST 等价证明**（阶段 6 尤其）。
12. **拆模块（6C）不许顺手做**：默认只出方案与评估。
13. **本版不许删任何机制代码**：`git diff` 里 `del` 代码行数必须为 0。

### 0.4 文件命名规范

| 用途 | 命名 |
|---|---|
| 主文件（改前） | `元DGTF-V1.21.77.py` |
| 主文件（中间态） | `元DGTF-V1.22.0-rc<N>.py` |
| 主文件（定稿） | `元DGTF-V1.22.0.py` |
| 基线副本 | `_baseline_v12177.py` |
| 探针 | `_probe_v122_phase<N>.py` |
| 探针输出 | `_probe_v122_phase<N>_before.txt` / `_after.txt` |
| 快照 | `_v122_phase<N>_baseline.json` |
| 冒烟 | 追加进 `smoke_test.py`，函数名 `check_v122_phase<N>` |
| 阶段报告 | `v122_phase<N>_报告.md` |
| 机制审计脚本 | `_audit_v122_dead_mechanisms.py` |
| 机制审计报告 | `audit_v122_dead_mechanisms.md` |
| 机制审计文档 | `docs/机制审计-v122.md` |
| 拆模块方案 | `docs/拆模块方案-v122.md` |
| 验收脚本 | `_v122_verify.py` |
| 一键验收 | `_v122_final_verify.sh` |

---

## 1. 环境准备（执行任何阶段之前先做）

### Step 0.1 建目录

```bash
mkdir -p bench/questions bench/gold bench/runs bench/reports bench/calib
mkdir -p docs cache/anchors runs/v122
```

**通过判据**：`ls bench/` 显示 4 个子目录。

### Step 0.2 建立基线

```bash
cp 元DGTF-V1.21.77.py _baseline_v12177.py
python -c "import ast; ast.parse(open('_baseline_v12177.py',encoding='utf-8').read())"
```

**通过判据**：无输出（parse OK）。

### Step 0.3 建验收基础设施

新建 `_v122_verify.py`（完整代码见附录 A）。脚本支持：

```bash
python _v122_verify.py --phase 1 --src 元DGTF-V1.22.0-rc1.py
python _v122_verify.py --phase all --src 元DGTF-V1.22.0.py
```

**通过判据**：

```bash
python _v122_verify.py --phase all --src _baseline_v12177.py
# 期望：PASS N / FAIL M（M > 0，因为新功能还没加），但脚本本身能跑完
# 期望：退出码非 0
```

### Step 0.4 建一键验收

新建 `_v122_final_verify.sh`（完整内容见附录 B）。

```bash
chmod +x _v122_final_verify.sh
```

**通过判据**：`bash -n _v122_final_verify.sh` 无语法错误。

---

## 2. 阶段 1（1+5）：Bench 骨架 + 目标函数分层

### 2.1 目标表

| 编号 | 目标 | 量化验收 |
|---|---|---|
| G1.1 | 建 bench 目录与题库 | ≥ 20 题 |
| G1.2 | 建 gold | ≥ 3 题精标 |
| G1.3 | `Phase.objective` | 4 层赋值正确 |
| G1.4 | coverage 只对研究层 | entry ≠ "1" 返回 None |
| G1.5 | 修行层停止理由改写 | 含"未生质量" |
| G1.6 | 头部渲染分层目标 | 4 行 |
| G1.7 | 元层不评价修行层 | 无 `pools["0"]` 引用 |
| G1.8 | route 分层 | boundary 保留全四层 |
| G1.9 | bench_score | 4 个评分函数 |
| G1.10 | bench_run/diff/report | 3 个脚本可跑 |

### 2.2 Step 清单

#### Step 1.1 建 bench 题库

**动作**：写 20 道题 YAML 到 `bench/questions/`。

**每题字段**（严格照抄）：

```yaml
id: eng_001
domain: eng                # eng/biz/med/law/org/tech
question: "..."
orientation: decision      # boundary / decision
budget:
  profile: balanced
  max_calls: 180
  rounds: "0:5,1:5,both:5,all:6"
  mode: serial
```

**题目清单**（6 领域各 3-4 道）：

```
eng_001 老城区内涝          decision
eng_002 地铁运营效率        boundary
eng_003 桥梁维护优先级      decision
biz_001 现金流自动化        decision
biz_002 出海定价            decision
biz_003 供应链多源          decision
med_001 社区医院远程监测    decision
med_002 慢病随访分层        decision
med_003 急救资源调度        boundary
law_001 GDPR 跨境           decision
law_002 数据共享边界        boundary
law_003 合同自动审查        decision
org_001 多部门共享数据      decision
org_002 组织内推            decision
org_003 跨团队协作          boundary
tech_001 订单不超卖         decision
tech_002 CAP 取舍           decision
tech_003 分布式 ID          decision
```

**验收命令**：

```bash
ls bench/questions/*.yaml | wc -l
python - <<'EOF'
import yaml, glob, sys
req = {"id","domain","question","orientation","budget"}
budget_req = {"profile","max_calls","rounds","mode"}
bad = []
for p in glob.glob("bench/questions/*.yaml"):
    d = yaml.safe_load(open(p, encoding="utf-8"))
    if not req <= set(d): bad.append((p, "top", req - set(d)))
    elif not budget_req <= set(d["budget"]):
        bad.append((p, "budget", budget_req - set(d["budget"])))
print("BAD:", bad)
sys.exit(1 if bad else 0)
EOF
```

**期望**：`≥ 20` 且 `BAD: []`。

**通过判据**：两数都达标。

#### Step 1.2 建 gold 骨架

**动作**：写 3 题精标（eng_001 / biz_001 / tech_001）到 `bench/gold/`。

**Gold 结构**（严格照抄）：

```yaml
id: eng_001
decidability_gold:
  adjudicators: 3
  final: partial
  dec_aspects: [...]
  und_aspects: [...]
practice_target:
  min_amps: 3
  min_threads: 2
  min_suspensions: 1
  max_ing_rephrase: 0.3
  min_anchor_touch_rate: 0.4
research_target:
  min_answered: 3
  max_distance: 0.5
  min_evidence_traced: 0.8
  must_mention: [...]
  must_not_mention: [...]
collision_target:
  min_third_party: 1
  min_tensions: 2
meta_target:
  meta_clean: true
  min_coverage: 0.6
action_rubric:
  min_actions: 3
  required_fields_per_action:
    - verb
    - object
    - owner_role
    - deadline_hint
    - acceptance
  must_have_fallback: true
  must_have_not_do_list: true
anchor_gold: []
```

**验收命令**：

```bash
ls bench/gold/*.yaml | wc -l
```

**期望**：`≥ 3`。

#### Step 1.3 `Phase` 加 `objective` 字段

**文件**：`元DGTF-V1.22.0-rc1.py`

**改动 1**：`Phase` dataclass 加 `objective` 为第二个字段：

```python
@dataclass(frozen=True)
class Phase:
    name: str
    objective: str        # 新增
    anchor: str
    expand_order: str
    dual_spec: str
    ing_focus: str
    he_focus: str
    probe_focus: str
    view_focus: str
    target_hardness: str = "soft"
```

**改动 2**：四个 `PHASE_*` 常量加 `objective=`：

```python
PHASE_PRACTICE = Phase(name="修行", objective="manifest", anchor=..., ...)
PHASE_RESEARCH = Phase(name="研究", objective="truth",    anchor=..., ...)
PHASE_DUEL     = Phase(name="对撞", objective="collision",anchor=..., ...)
PHASE_META     = Phase(name="元",   objective="closure",  anchor=..., ...)
```

**验收命令**：

```bash
python _v122_verify.py --phase 1 --src 元DGTF-V1.22.0-rc1.py 2>&1 | grep "1.3"
```

**期望**：4 行 `✅`。

#### Step 1.4 `coverage_of` 只对研究层

**文件**：同上。

**改动 1**：`coverage_of` 加 entry 形参（默认 `"1"` 保兼容）：

```python
def coverage_of(pool, cfg: dict, entry: str = "1") -> Optional[float]:
    if entry != "1":
        return None
    _, _, cov = coverage_parts(pool, cfg)
    return cov
```

**改动 2**：`coverage_parts` 也加 entry 形参（默认 `"1"`）：

```python
def coverage_parts(pool, cfg: Optional[dict] = None, entry: str = "1"):
    if entry != "1":
        return 0, 0, None
    ...
```

**改动 3**：所有调用点检查：

- `_finalize_layer_common` 里只在 `entry == "1"` 调。
- `_coverage_segment` 里只对 `self.pools["1"]` 调。
- `_refresh_settlement` 里只对 `self.pools["1"]` 调。

**验收命令**：

```bash
python _v122_verify.py --phase 1 --src 元DGTF-V1.22.0-rc1.py 2>&1 | grep "1.4"
```

**期望**：4 行 `✅`。

#### Step 1.5 修行层 stop_reason 改写

**文件**：同上。

**新增函数**（放在 `_finalize_layer_common` 前）：

```python
def _classify_unsaid(view) -> str:
    """real_unsaid / lazy_unsaid"""
    ing = str(getattr(view, "collision", "") or "")
    if not ing or ing.strip() == "（此处未生）":
        return "lazy"
    has_covers = any(
        (p.get("covers") or [])
        for p in (getattr(view, "probes", None) or [])
        if isinstance(p, dict)
    )
    if not has_covers:
        return "lazy"
    return "real"
```

**在 `_finalize_layer_common` 里**，当 `entry == "0"` 且 `view.stop_reason` 以 `体力耗尽` 开头时：

```python
if entry == "0" and (view.stop_reason or "").startswith("体力耗尽"):
    n_amp = len(view.amps or [])
    n_thr = len(view.threads or [])
    n_sus = len(view.suspensions or [])
    n_prb = len(view.probes or [])
    quality = _classify_unsaid(view)
    view.stop_reason = (
        f"{view.stop_reason}\n"
        f"  本轮显形：& {n_amp} / 线头 {n_thr} / 悬置 {n_sus} / 探针 {n_prb}\n"
        f"  未生质量：{quality}"
    )
```

**验收命令**：

```bash
python _v122_verify.py --phase 1 --src 元DGTF-V1.22.0-rc1.py 2>&1 | grep "1.5"
```

**期望**：3 行 `✅`（含负对照）。

#### Step 1.6 头部渲染分层目标

**文件**：`save_result` 内，cost_profile 行之后。

**新增**：

```python
_views = result.get("views") or {}
_pools = result.get("pools") or {}
def _g(k): return (_views.get(k) or {})
def _gp(k): return (_pools.get(k) or {})
_p0 = _g("0"); _p1 = _g("1"); _pb = _g("both"); _pa = _g("all")
f.write("**分层目标**：\n")
f.write(f"  - 修行层（显形过程）：& {len(_p0.get('amps') or [])} / "
        f"线头 {len(_p0.get('threads') or [])} / "
        f"悬置 {len(_p0.get('suspensions') or [])} / "
        f"探针 {len(_p0.get('probes') or [])}\n")
_st = (_p1.get("settlement") or {})
_cov = _st.get("coverage")
_cov_s = f"{_cov:.0%}" if isinstance(_cov, (int, float)) else "N/A"
_dist = (_p1.get("decidable_product") or {}).get("distance", "?")
f.write(f"  - 研究层（逼近真理）：覆盖率 {_cov_s} · "
        f"distance {_dist}\n")
_pbi = (_pb.get("ing_structured") or {})
f.write(f"  - 对撞层（第三者）：third {'✓' if _pbi.get('third') else '✗'} · "
        f"张力 {len(_pbi.get('tensions') or [])}\n")
_clo = (_pa.get("meta_closure") or {})
f.write(f"  - 元层（闭环清算）：clean {_clo.get('clean')} · "
        f"未交代 {_clo.get('unsettled', 0)} 类\n\n")
```

**验收命令**：

```bash
python _v122_verify.py --phase 1 --src 元DGTF-V1.22.0-rc1.py 2>&1 | grep "1.6"
# 真跑核对
python 元DGTF-V1.22.0-rc1.py "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵措施？怎么权衡？" \
  --route 0,1 --rounds "0:3,1:3" --parallel serial --orientation decision --quiet
LATEST=$(ls -t outputs/*.md | head -1)
grep -A5 "分层目标" $LATEST
```

**期望**：4 行 `- 修行层 / 研究层 / 对撞层 / 元层`。

#### Step 1.7 元层不评价修行层

**动作**：检查 `_settle_meta` 是否引用 `self.pools["0"]`。若有，删掉；若无，加注释 `# [v122 P1] 元层只清算对撞张力，不评价修行层`。

**验收命令**：

```bash
python _v122_verify.py --phase 1 --src 元DGTF-V1.22.0-rc1.py 2>&1 | grep "1.7"
```

**期望**：1 行 `✅`。

#### Step 1.8 `_route_by_decidability` 按 orientation 分层

**动作**：改 `_route_by_decidability`：

```python
def _route_by_decidability(self, question, route, orientation="auto"):
    if not route or len(route) <= 2:
        return route
    _o = (orientation or "auto").strip().lower()
    if _o == "boundary":
        self.vp("\n📐 取向=boundary → 保留全四层")
        return route
    try:
        ext = self._cached_ext_assess(question)
    except Exception:
        return route
    if str(ext.get("decidability", "")).lower() == "undecidable":
        dropped = [k for k in route if k not in ("0", "1")]
        self.vp(f"\n📉 decision + 外判 undecidable，route {route} → [0,1]")
        return ["0", "1"]
    return route
```

**验收命令**：

```bash
python - <<'EOF'
import importlib.util
spec = importlib.util.spec_from_file_location("dgtf", "元DGTF-V1.22.0-rc1.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
meta = m.MetaDGTF(m.DEFAULT_CONFIG)
r1 = meta._route_by_decidability("Q", ["0","1","both","all"], "boundary")
assert r1 == ["0","1","both","all"], r1
print("boundary 保留全四层 ✅")
EOF
```

**期望**：`boundary 保留全四层 ✅`。

#### Step 1.9 `bench_score.py` 分层指标

**文件**：`bench/bench_score.py`

**完整代码**（关键函数）：

```python
import json, sys
from pathlib import Path

def score_practice(res):
    v = (res.get("views") or {}).get("0") or {}
    return {
        "amps": len(v.get("amps") or []),
        "threads": len(v.get("threads") or []),
        "suspensions": len(v.get("suspensions") or []),
        "probes": len(v.get("probes") or []),
        "rephrase_ratio": v.get("rephrase_ratio"),
    }

def score_research(res):
    v = (res.get("views") or {}).get("1") or {}
    st = v.get("settlement") or {}
    dp = v.get("decidable_product") or {}
    return {
        "coverage": st.get("coverage"),
        "answered_xy": f"{st.get('answered','?')}/{st.get('total','?')}",
        "distance": dp.get("distance"),
    }

def score_collision(res):
    v = (res.get("views") or {}).get("both") or {}
    ing = v.get("ing_structured") or {}
    return {"third": bool(ing.get("third")),
            "tensions": len(ing.get("tensions") or [])}

def score_meta(res):
    v = (res.get("views") or {}).get("all") or {}
    clo = v.get("meta_closure") or {}
    return {"clean": clo.get("clean"),
            "unsettled": clo.get("unsettled")}

def score_decision_rubric(res, gold):
    v = (res.get("views") or {}).get("1") or {}
    actions = v.get("_actions") or []
    score = 0
    if len(actions) >= gold["action_rubric"]["min_actions"]:
        score += 1
    if actions and all(a.get("fallback") and a["fallback"] != "（未指定）"
                       for a in actions):
        score += 1
    if v.get("_not_do"):
        score += 1
    return {"score": score, "max": 3, "n_actions": len(actions)}

def score_run(run_dir, gold_path):
    res = json.loads((Path(run_dir) / "result.json").read_text(encoding="utf-8"))
    import yaml
    g = yaml.safe_load(Path(gold_path).read_text(encoding="utf-8")) if Path(gold_path).exists() else {}
    return {
        "practice": score_practice(res),
        "research": score_research(res),
        "collision": score_collision(res),
        "meta": score_meta(res),
        "decision": score_decision_rubric(res, g) if g else None,
    }

if __name__ == "__main__":
    print(json.dumps(
        score_run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "bench/gold/x.yaml"),
        ensure_ascii=False, indent=2))
```

**验收命令**：

```bash
python _v122_verify.py --phase 1 --src 元DGTF-V1.22.0-rc1.py 2>&1 | grep "1.9"
```

**期望**：3 行 `✅`。

#### Step 1.10 `bench_run.py` / `bench_diff.py` / `bench_report.py`

**`bench_run.py`**：

```python
import sys, yaml, json, subprocess, time
from pathlib import Path
from datetime import datetime

def main():
    qdir = Path("bench/questions")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path("bench/runs") / ts
    out.mkdir(parents=True, exist_ok=True)
    for q in sorted(qdir.glob("*.yaml")):
        spec = yaml.safe_load(q.read_text(encoding="utf-8"))
        cmd = [sys.executable, "元DGTF-V1.22.0.py", spec["question"],
               "--route", "0,1,both,all",
               "--rounds", spec["budget"]["rounds"],
               "--parallel", spec["budget"]["mode"],
               "--orientation", spec["orientation"],
               "--profile", spec["budget"]["profile"], "--quiet"]
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
        dt = time.time() - t0
        d = out / spec["id"]
        d.mkdir(exist_ok=True)
        (d / "stdout.log").write_text(r.stdout, encoding="utf-8")
        (d / "stderr.log").write_text(r.stderr, encoding="utf-8")
        (d / "meta.json").write_text(json.dumps(
            {"elapsed": dt, "returncode": r.returncode},
            ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"runs -> {out}")

if __name__ == "__main__":
    main()
```

**`bench_diff.py`**：

```python
import sys, json
from pathlib import Path

def load_all(run_dir):
    out = {}
    for d in Path(run_dir).iterdir():
        if not d.is_dir(): continue
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8")) if (d / "meta.json").exists() else {}
        out[d.name] = meta
    return out

def main(a, b):
    ra, rb = load_all(a), load_all(b)
    keys = sorted(set(ra) & set(rb))
    print(f"{'id':<12}{'metric':<16}{'before':<16}{'after':<16}")
    for k in keys:
        for m in ("elapsed", "returncode"):
            va, vb = ra[k].get(m), rb[k].get(m)
            if va != vb:
                print(f"{k:<12}{m:<16}{str(va):<16}{str(vb):<16}")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

**`bench_report.py`**：

```python
import sys, json, yaml
from pathlib import Path
sys.path.insert(0, "bench")
from bench_score import score_run

def main(run_dir):
    out = ["# v122 全量回归报告\n", "",
           "| id | 判定 | 一致率 | 修行 | 研究 | 对撞 | 元 | rubric |",
           "|---|---|---|---|---|---|---|---|"]
    run = Path(run_dir)
    for d in sorted(run.iterdir()):
        if not d.is_dir(): continue
        gid = d.name
        gold = Path("bench/gold") / f"{gid}.yaml"
        if (d / "result.json").exists():
            res = json.loads((d / "result.json").read_text(encoding="utf-8"))
        else:
            res = {}
        if gold.exists():
            s = score_run(str(d), str(gold))
        else:
            s = {}
        out.append(f"| {gid} | ? | ? | ? | ? | ? | ? | ? |")
    print("\n".join(out))

if __name__ == "__main__":
    main(sys.argv[1])
```

**验收命令**：

```bash
python _v122_verify.py --phase 1 --src 元DGTF-V1.22.0-rc1.py 2>&1 | grep "1.10"
```

**期望**：3 行 `✅`。

### 2.3 阶段 1 探针

**文件**：`_probe_v122_phase1.py`

```python
import sys, json, importlib.util

spec = importlib.util.spec_from_file_location("dgtf", sys.argv[1])
dgtf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dgtf)

out = {
    "A_objective": {k: dgtf.PHASES[k].objective for k in ("0","1","both","all")},
    "B_cov_entry": {e: dgtf.coverage_of(dgtf.Pool(), {}, entry=e)
                    for e in ("0","1","both","all")},
    "C_classify": {
        "empty_ing": dgtf._classify_unsaid(dgtf.View(entry="0", collision="")),
        "real": dgtf._classify_unsaid(dgtf.View(
            entry="0", collision="一、让两端各自把话说完\n二、各推到极端",
            probes=[{"question":"Q","covers":["T1"]}])),
    },
    "E_settle_meta_ref_p0": 'pools["0"]' in open(sys.argv[1],encoding="utf-8").read(),
}
print(json.dumps(out, ensure_ascii=False, indent=2))
```

**跑 before / after**：

```bash
python _probe_v122_phase1.py _baseline_v12177.py > _probe_v122_phase1_before.txt
python _probe_v122_phase1.py 元DGTF-V1.22.0-rc1.py > _probe_v122_phase1_after.txt
diff -u _probe_v122_phase1_before.txt _probe_v122_phase1_after.txt
```

### 2.4 阶段 1 冒烟

**文件**：追加进 `smoke_test.py`：

```python
def check_v122_phase1(SRC):
    import importlib.util, re
    spec = importlib.util.spec_from_file_location("dgtf", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.PHASES["0"].objective == "manifest"
    assert m.PHASES["1"].objective == "truth"
    assert m.PHASES["both"].objective == "collision"
    assert m.PHASES["all"].objective == "closure"
    assert m.coverage_of(m.Pool(), {}, entry="0") is None
    assert m.coverage_of(m.Pool(), {}, entry="both") is None
    assert m.coverage_of(m.Pool(), {}, entry="all") is None
    assert m._classify_unsaid(m.View(entry="0", collision="")) == "lazy"
    assert m._classify_unsaid(m.View(
        entry="0", collision="一、让两端各自把话说完\n二、各推到极端",
        probes=[{"question":"Q","covers":["T1"]}])) == "real"
    v = m.View(entry="0", collision="（此处未生）",
               probes=[{"question":"Q","covers":["T1"]}])
    assert m._classify_unsaid(v) == "lazy"
    src = open(SRC, encoding="utf-8").read()
    assert "修行层不追求收敛" in src
    assert "分层目标" in src
    return True
```

### 2.5 阶段 1 验收

**命令**：

```bash
python _v122_verify.py --phase 1 --src 元DGTF-V1.22.0-rc1.py
echo "EXIT=$?"
```

**期望**：

```
━━━ PASS N / FAIL 0 ━━━
EXIT=0
```

**真跑 3 题**：

```bash
python bench/bench_run.py
LATEST=$(ls -t bench/runs | head -1)
for d in bench/runs/$LATEST/*/; do
  echo "--- $d"
  grep -c "分层目标" "$d/stdout.log" 2>/dev/null || echo 0
done
```

**期望**：每题都 ≥ 1。

**通过判据**：

- FAIL = 0，EXIT = 0
- 3 题真跑都有产物且含"分层目标"
- 修行层产物不再被评价覆盖率
- `git diff` 代码 `del` 行数 = 0

**阶段 1 报告**：`v122_phase1_报告.md`

---

## 3. 阶段 2（3）：三态多票化 + 冻结 + 人工校准

### 3.1 目标表

| 编号 | 目标 | 量化验收 |
|---|---|---|
| G2.1 | 三票 prompt | 长度 = 3 |
| G2.2 | 多票方法 | 新增 + 旧保留 |
| G2.3 | 冻结 | signature 非空 + 篡改抛错 |
| G2.4 | coverage 用冻结 | 改判后分母不变 |
| G2.5 | 头部渲染 | 含"三态多票" + "冻结" |
| G2.6 | 校准脚本 | export / import 都有 |
| G2.7 | packed | 含 freeze + calibration_queue |
| G2.8 | 一致率 | ≥ 50% |

### 3.2 Step 清单

#### Step 2.1 三票 prompt 常量

**新增常量**（放在 `_DECIDABILITY_STATES` 附近）：

```python
_TRI_VOTE_PROMPTS = (
    "你是【严格判决官】。宁可判 undecidable，也不要草率判 decidable。"
    "只有存在**明确可指认的 0/1 候选答案**时才判 decidable。",
    "你是【宽松判决官】。只要能指认一个**可操作化路径**"
    "（哪怕需要先做一次测量），就判 decidable。",
    "你是【中立判决官】。按「可指认位置 / 空槽」的原始定义判。"
    "可指认 = 能指到具体对象；空槽 = 位置本身还没长出来。",
)
```

**验收命令**：`_v122_verify.py --phase 2` 里 grep `2.1`。

#### Step 2.2 多票判决函数

**新增方法**（放在 `_adjudicate_sub_tristate` 之后）：

```python
def _adjudicate_sub_tristate_multi(self, subs, question, n=3):
    if not subs:
        return 0, 0, []
    lines = [f"  {i}. {str(s.get('question',''))[:200]}"
             for i, s in enumerate(subs, 1)]
    user = (f"【原始问题】\n{question}\n\n"
            f"【待判的子问题】\n" + "\n".join(lines))
    votes = {}
    for vi, prompt in enumerate(_TRI_VOTE_PROMPTS[:n]):
        base = (prompt + "\n\n"
                "【★ 顺序】每条先写一句 reason，再给 decidability。\n"
                "严格 JSON：\n"
                '{"judgments":[{"id":1,"reason":"...",'
                '"decidability":"decidable|partial|undecidable"}]}\n'
                + ANTI_PRETTY)
        try:
            raw = self.llm.call(base, user, 0.0, 1200, json_mode=True,
                                stage=f"adjudicate_v{vi}")
            data = self.llm.parse_json(raw)
        except Exception as e:
            logger.warning("三票判决 %d 失败: %s", vi, e)
            data = None
        if not isinstance(data, dict):
            votes[vi] = {}
            continue
        j = {}
        for it in (data.get("judgments") or []):
            if not isinstance(it, dict):
                continue
            try:
                sid = int(it.get("id", 0))
            except (TypeError, ValueError):
                continue
            st = str(it.get("decidability", "")).lower()
            if st in _DECIDABILITY_STATES:
                j[sid] = st
        votes[vi] = j

    agree_total = 0
    valid_total = 0
    calibration_queue = []
    for i, s in enumerate(subs, 1):
        labels = [votes[vi].get(i) for vi in range(n)]
        labels = [l for l in labels if l]
        if not labels:
            continue
        valid_total += 1
        counts = {st: labels.count(st) for st in set(labels)}
        final = max(counts, key=counts.get)
        agreement = counts[final] / len(labels)
        s["votes"] = [{"voter": vi, "label": votes[vi].get(i)}
                      for vi in range(n) if votes[vi].get(i)]
        s["agreement"] = round(agreement, 2)
        s["stability"] = ("high" if agreement == 1.0
                          else "medium" if agreement >= 2/3
                          else "low")
        s["first_label"] = str(s.get("decidability", "")).lower()
        if s["stability"] == "low":
            s["decidability"] = "partial"
            s["unstable"] = True
            calibration_queue.append({"sub_id": i, "votes": s["votes"]})
        else:
            s["decidability"] = final
        if s["first_label"] != s["decidability"]:
            s.setdefault("label_disagreed", []).append(
                [s["first_label"], s["decidability"]])
        agree_total += (1 if s["stability"] == "high" else 0)

    for s in subs:
        s["_decided_answerable"] = s.get("decidability") in _DEC_ANSWERABLE

    self.vp(f"   🎯 三票判决：high {agree_total} / "
            f"valid {valid_total} / low {len(calibration_queue)}")
    return agree_total, valid_total, calibration_queue
```

**替换调用点**：

位置 1 · `_run_layer` 里：

```python
self._tri_agree, self._tri_total, self._calibration_queue = \
    self._adjudicate_sub_tristate_multi(subs, question, n=3)
```

位置 2 · `_b_pre_layer` 里同改。

**保留**：旧 `_adjudicate_sub_tristate` 方法不删，加注释 `# [v122 P2] deprecated，保留供外部脚本调用`。

**新增实例字段**：`__init__` 加：

```python
self._calibration_queue: List[dict] = []
```

`run()` 开头重置：`self._calibration_queue = []`。

#### Step 2.3 冻结类

**新增类**（放在 `_normalize_decidability` 附近）：

```python
class DecidabilityFreeze:
    """[v122 P2] 评估结束时冻结三态与分母。"""
    def __init__(self):
        self.signature: str = ""
        self.freeze_at_layer: int = 0

    @staticmethod
    def _sign(pool) -> str:
        payload = []
        for s in (pool.sub_questions or []):
            payload.append({
                "id": s.get("id"),
                "frozen": s.get("_frozen_decidability"),
                "answerable": s.get("_frozen_answerable"),
            })
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False)
            .encode("utf-8")).hexdigest()

    def freeze(self, pool, layer: int) -> None:
        for s in (pool.sub_questions or []):
            s["_frozen_decidability"] = s.get("decidability")
            s["_frozen_answerable"] = (
                s.get("decidability") in _DEC_ANSWERABLE)
            s["_frozen_at"] = datetime.now().isoformat()
        self.signature = self._sign(pool)
        self.freeze_at_layer = layer

    def verify(self, pool) -> None:
        if not self.signature:
            return
        if self._sign(pool) != self.signature:
            raise RuntimeError(
                "DecidabilityFreeze 签名被篡改（有代码改了 "
                "_frozen_decidability/_frozen_answerable）")
```

**import**：文件顶部加 `import hashlib`（若未 import）。

**实例化**：`MetaDGTF.__init__` 加：

```python
self._freeze = DecidabilityFreeze()
```

`run()` 开头重置：`self._freeze = DecidabilityFreeze()`。

**调用**：在 `_adjudicate_sub_tristate_multi` 返回值后立刻调：

```python
self._freeze.freeze(self.pools["1"], layer=1)
```

**校验**：`update_deferrals` / `_starve_escalation` 调用 `apply_decidability_change` **之前**加：

```python
# 在 MetaDGTF 的方法里：
self._freeze.verify(self.pools["1"])
```

#### Step 2.4 `coverage_parts` 改用冻结

**改动**：`coverage_parts` 里：

```python
if any("_frozen_answerable" in s for s in _all):
    subs = [s for s in _all if s.get("_frozen_answerable")]
elif any("_decided_answerable" in s for s in _all):
    subs = [s for s in _all if s.get("_decided_answerable")]
else:
    subs = [s for s in _all if s.get("decidability") in _DEC_ANSWERABLE]
```

#### Step 2.5 头部渲染

**`save_result` 里，三态一致率行之后**：

```python
_sqs = ((result.get("pools") or {}).get("1") or {}).get("sub_questions") or []
_high = sum(1 for s in _sqs if s.get("stability") == "high")
_med = sum(1 for s in _sqs if s.get("stability") == "medium")
_low = sum(1 for s in _sqs if s.get("stability") == "low")
if _sqs:
    f.write(f"**三态多票**：high {_high} / medium {_med} / low {_low}"
            f"（共 {len(_sqs)} 条）\n\n")
_fz = result.get("freeze") or {}
if _fz.get("signature"):
    f.write(f"**冻结**：signature={_fz['signature'][:12]} · "
            f"layer={_fz.get('layer','?')} · "
            f"之后改判 {_fz.get('changed_after', 0)} 条\n\n")
```

**`MetaDGTF._pack_result`** 加：

```python
"freeze": {
    "signature": self._freeze.signature,
    "layer": self._freeze.freeze_at_layer,
    "changed_after": sum(
        1 for s in (self.pools["1"].sub_questions or [])
        if s.get("_frozen_decidability")
        and s.get("decidability") != s.get("_frozen_decidability")),
},
"calibration_queue": list(self._calibration_queue or []),
```

#### Step 2.6 `bench_calibrate.py`

**文件**：`bench/bench_calibrate.py`

```python
import json, sys
from pathlib import Path

def cmd_export(run_dir, out_md):
    res = json.loads((Path(run_dir) / "result.json").read_text(encoding="utf-8"))
    q = res.get("calibration_queue") or []
    lines = [
        "# 校准批次", "",
        f"来源 run: {run_dir}", "",
        "| # | 子问题 | 三票 | 最终 | 人工 verdict | 备注 |",
        "|---|---|---|---|---|---|",
    ]
    for i, it in enumerate(q, 1):
        sid = it.get("sub_id")
        votes = " / ".join(v.get("label", "?") for v in it.get("votes", []))
        qs = ""
        for s in ((res.get("pools") or {}).get("1") or {}).get("sub_questions") or []:
            if s.get("id") == sid:
                qs = s.get("question", "")[:60]
                break
        lines.append(f"| {i} | [{sid}] {qs} | {votes} | partial | | |")
    Path(out_md).write_text("\n".join(lines), encoding="utf-8")
    print(f"exported -> {out_md}")

def cmd_import(md_path):
    rows = []
    for line in Path(md_path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 6 or cells[0] == "#":
            continue
        try:
            idx = int(cells[0])
        except ValueError:
            continue
        rows.append({"idx": idx, "verdict": cells[4]})
    print(f"imported {len(rows)} rows")

if __name__ == "__main__":
    if sys.argv[1] == "export":
        cmd_export(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "import":
        cmd_import(sys.argv[2])
```

### 3.3 阶段 2 冒烟

```python
def check_v122_phase2(SRC):
    import importlib.util
    spec = importlib.util.spec_from_file_location("dgtf", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert len(m._TRI_VOTE_PROMPTS) == 3
    pool = m.Pool()
    pool.sub_questions = [
        {"id": 1, "question": "Q1", "decidability": "decidable"},
        {"id": 2, "question": "Q2", "decidability": "partial"},
    ]
    fz = m.DecidabilityFreeze()
    fz.freeze(pool, layer=1)
    assert pool.sub_questions[0]["_frozen_answerable"] is True
    pool.sub_questions[0]["_frozen_answerable"] = False
    try:
        fz.verify(pool)
        assert False, "应抛错"
    except RuntimeError:
        pass
    pool2 = m.Pool()
    pool2.sub_questions = [
        {"id": 1, "question": "Q1", "decidability": "decidable",
         "status": "answered", "depth": 1.0},
        {"id": 2, "question": "Q2", "decidability": "decidable"},
    ]
    fz2 = m.DecidabilityFreeze()
    fz2.freeze(pool2, layer=1)
    pool2.sub_questions[0]["decidability"] = "undecidable"
    _, _, cov = m.coverage_parts(pool2, {})
    assert cov is not None
    assert hasattr(m.DGTF, "_adjudicate_sub_tristate")
    assert hasattr(m.DGTF, "_adjudicate_sub_tristate_multi")
    src = open(SRC, encoding="utf-8").read()
    assert "三态多票" in src and "**冻结**" in src
    return True
```

### 3.4 阶段 2 验收

**命令**：

```bash
python _v122_verify.py --phase 2 --src 元DGTF-V1.22.0-rc1.py
echo "EXIT=$?"
```

**期望**：`PASS N / FAIL 0` + `EXIT=0`。

**一致率核对**：

```bash
for i in 1 2 3; do
  python 元DGTF-V1.22.0-rc1.py "订单系统要保证不超卖又要不卡顿。CAP 约束下，下单链路怎么设计？" \
    --route 1 --rounds "1:4" --parallel serial --quiet
done
LATEST=$(ls -t outputs/*.md | head -1)
grep "三态多票" $LATEST
```

**通过判据**：

- high + medium ≥ 总 sub 数的 50%
- 若不足，标记为 `unstable`，**该阶段验收失败**

**阶段 2 报告**：`v122_phase2_报告.md`

---

## 4. 阶段 3（4）：decision 模式强制行动闭环

### 4.1 目标表

| 编号 | 目标 | 量化验收 |
|---|---|---|
| G3.1 | 开关 | landing_decision 存在 |
| G3.2 | 分流 | 两个 render 函数都在 |
| G3.3 | 抽取 | ≥ 1 条 action |
| G3.4 | 五字段 | 每条都有 |
| G3.5 | 硬约束 | action_incomplete + not_do_missing |
| G3.6 | rubric | 存在 |
| G3.7 | decision 题 | 100% ≥ 3 action |
| G3.8 | rubric | 平均 ≥ 2/3 |

### 4.2 Step 清单

#### Step 3.1 新增开关

**`DEFAULT_CONFIG["actions"]` 加**：

```python
"landing_decision": True,
```

#### Step 3.2 落地层分流

**`render_landing` 顶部改**：

```python
def render_landing(res):
    cfg = res.get("_config") or {}
    orientation = res.get("orientation") or "auto"
    if orientation == "boundary" or \
            not _action_on(cfg, "landing_decision"):
        return _render_landing_boundary(res)
    return _render_landing_decision(res)
```

**保留**：现有 `render_landing` 整体改名 `_render_landing_boundary`，只加一层壳。

**`_pack_result` 加**：`"_config": {"actions": self.config.get("actions") or {}}`。

#### Step 3.3 `_render_landing_decision`

**新增函数**：

```python
def _render_landing_decision(res):
    out = []
    views = res.get("views") or {}
    v1 = views.get("1") or {}
    dp = v1.get("decidable_product") or {}
    out.append("## 落地层（decision 模式）\n\n")

    out.append("### 一、决议书\n")
    ans = dp.get("answer") or "（未产出可执行结论）"
    out.append(f"- **主结论**：{ans}\n")

    out.append("\n### 二、行动清单\n")
    actions = _extract_actions(v1)
    if not actions:
        out.append("（未抽出 action，rubric 扣分）\n")
    for a in actions:
        out.append(f"- **{a.get('id','A?')}**：{a.get('verb','')} "
                   f"{a.get('object','')}\n")
        out.append(f"  - 负责人：{a.get('owner_role','（未指定）')}\n")
        out.append(f"  - 时限：{a.get('deadline_hint','（未指定）')}\n")
        out.append(f"  - 验收：{a.get('acceptance','（未指定）')}\n")
        out.append(f"  - 回退：{a.get('fallback','（未指定）')}\n")

    out.append("\n### 三、所需数据清单\n")
    out.append("\n### 四、失败模式与回退\n")
    out.append("\n### 五、不做什么\n")
    out.append("\n### 六、如果只能做一件事\n")
    if actions:
        a1 = actions[0]
        out.append(f"- {a1.get('verb','')} {a1.get('object','')}\n")
    return "".join(out)
```

#### Step 3.4 `extract_actions`

**新增函数**：

```python
_ACTION_VERB_WHITELIST = (
    "指派", "指定", "核查", "测量", "提交", "申请", "封堵",
    "清淤", "试点", "备案", "签发", "复核", "排查", "改造",
    "扩容", "委托", "报审", "谈判", "调取",
)

def _extract_actions(view) -> list:
    import re
    out = []
    dp = getattr(view, "decidable_product", None) or {}
    text = str(dp.get("answer") or "")
    for m in re.finditer(r"[。；;]([^。；;]{4,120})", text):
        s = m.group(1).strip()
        if not any(v in s for v in _ACTION_VERB_WHITELIST):
            continue
        out.append({
            "id": f"A{len(out)+1}",
            "verb": next((v for v in _ACTION_VERB_WHITELIST if v in s), ""),
            "object": s,
            "owner_role": _guess_role(s),
            "deadline_hint": _guess_deadline(s),
            "acceptance": _guess_acceptance(s),
            "fallback": _guess_fallback(s),
        })
        if len(out) >= 5:
            break
    return out

def _guess_role(s):
    for role in ("区防汛办", "排水公司", "信息科", "医务科",
                 "法务", "财务", "项目组", "上级部门"):
        if role in s:
            return role
    return "（未指定）"

def _guess_deadline(s):
    for hint in ("汛期前", "本月内", "30 天内", "本季度", "下一财年"):
        if hint in s:
            return hint
    return "（未指定）"

def _guess_acceptance(s):
    if "验收" in s:
        return s.split("验收", 1)[1][:60]
    return "（未指定）"

def _guess_fallback(s):
    if "回退" in s or "否则" in s:
        return s.split("否则", 1)[-1][:60]
    return "（未指定）"
```

#### Step 3.5 硬约束

**`_finalize_layer_common` 里加**：

```python
_orientation = getattr(self, "_orientation", "auto")
if entry == "1" and _orientation == "decision":
    _acts = _extract_actions(view)
    if len(_acts) < 3:
        view.errors.append(
            f"decision 模式行动清单不足（{len(_acts)} < 3），需补 A1~A3")
        view.quality_flags.append("action_incomplete")
    _dp = getattr(view, "decidable_product", None) or {}
    _ans = str(_dp.get("answer") or "")
    if any(k in _ans for k in ("缺主体", "无主体", "无承接者", "缺承接者")):
        if not _acts:
            view.errors.append("结论落在'缺 X'但未给行动，需补 A1~A3")
```

**`MetaDGTF._orientation`** 由 `run(orientation=...)` 传入。

#### Step 3.6 rubric

**`bench_score.py` 里**：`score_decision_rubric(res, gold)`（见阶段 1 Step 1.9）。

**`save_result` 里**：把 `_extract_actions(view)` 结果写进 `packed["views"]["1"]["_actions"]`。

### 4.3 阶段 3 冒烟

```python
def check_v122_phase3(SRC):
    import importlib.util
    spec = importlib.util.spec_from_file_location("dgtf", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    v = m.View(entry="1")
    v.decidable_product = {"answer": "先指派区防汛办核查。否则回退上级。"}
    acts = m._extract_actions(v)
    assert len(acts) >= 1
    assert hasattr(m, "_render_landing_decision")
    assert hasattr(m, "_render_landing_boundary")
    src = open(SRC, encoding="utf-8").read()
    assert "landing_decision" in src
    assert "action_incomplete" in src
    assert "not_do_missing" in src
    v2 = m.View(entry="1")
    v2.decidable_product = {"answer": ""}
    assert len(m._extract_actions(v2)) == 0
    return True
```

### 4.4 阶段 3 验收

**命令**：

```bash
python _v122_verify.py --phase 3 --src 元DGTF-V1.22.0-rc1.py
echo "EXIT=$?"
```

**decision 题 3 道真跑**：

```bash
for q in \
  "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？怎么权衡？" \
  "现金流紧张的中小制造企业，上自动化产线还是维持人工加局部优化？怎么决策？" \
  "社区医院人力有限，慢性病管理推远程监测还是加派人手上门随访？资源怎么配？"; do
  python 元DGTF-V1.22.0-rc1.py "$q" \
    --route 0,1,both,all --rounds "0:4,1:4,both:4,all:5" \
    --parallel serial --orientation decision --quiet
done
LATEST=$(ls -t outputs/*.md | head -1)
grep -A20 "### 二、行动清单" $LATEST | grep -c "^- \*\*A"
```

**通过判据**：

- decision 题 100% ≥ 3 action
- rubric 平均 ≥ 2/3
- boundary 题不受影响（走五块模板）

**阶段 3 报告**：`v122_phase3_报告.md`

---

## 5. 阶段 4（2）：外部锚点变真证据

### 5.1 目标表

| 编号 | 目标 | 量化验收 |
|---|---|---|
| G4.1 | 五档 | as_evidence 五值之一 |
| G4.2 | tier | tier=1 进表 / tier=4 不进 |
| G4.3 | 真检索 | AnchorRetriever 存在 |
| G4.4 | X# 支撑 | decidable 成立 |
| G4.5 | X# 支撑 | undecidable 驳回 |
| G4.6 | 冲突留痕 | view.errors + pool.meta |
| G4.7 | triage 降级 | ≥ 1 条 |
| G4.8 | 头部 | 含"锚点分级" + "triage 降级" |

### 5.2 Step 清单

#### Step 4.1 五档 `as_evidence`

**`DEFAULT_CONFIG["external_anchor"]` 加**：

```python
"as_evidence": "off",   # off / record / crosscheck / evidence / gate
"tier_floor": 2,
"api_key_env": "TAVILY_API_KEY",
"cache_ttl_hours": 24,
"retriever": "snapshot",
```

#### Step 4.2 tier 分级

**锚点条目允许 `tier` 字段**（1~4，缺省 3）。`_load_anchors` 里：

```python
_tier = int(a.get("tier", 3) or 3)
out.append({..., "tier": _tier})
```

#### Step 4.3 真检索

**新增类**：

```python
class AnchorRetriever:
    def __init__(self, backend, api_key, ttl_hours=24):
        self.backend = backend
        self.api_key = api_key
        self.ttl = ttl_hours * 3600

    def _cache_path(self, queries):
        key = hashlib.sha256(
            json.dumps(queries, sort_keys=True).encode()).hexdigest()
        return Path("cache/anchors") / f"{key}.json"

    def search(self, queries, max_n):
        cache = self._cache_path(queries)
        if cache.exists():
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                if time.time() - data.get("_ts", 0) < self.ttl:
                    return data.get("anchors") or []
            except Exception:
                pass
        if self.backend == "tavily":
            res = self._tavily(queries, max_n)
        elif self.backend == "snapshot":
            return []
        else:
            raise RuntimeError(f"未实现的检索后端: {self.backend}")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(
            {"_ts": time.time(), "anchors": res},
            ensure_ascii=False, indent=2), encoding="utf-8")
        return res

    def _tavily(self, queries, max_n):
        import urllib.request
        out = []
        for q in queries[:2]:
            body = json.dumps({
                "api_key": self.api_key,
                "query": q,
                "max_results": max_n,
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.tavily.com/search",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            for it in data.get("results", []):
                out.append({
                    "id": f"t{len(out)+1}",
                    "claim": it.get("content", "")[:400],
                    "source": it.get("url", ""),
                    "url": it.get("url", ""),
                    "as_of": "",
                    "kind": "tavily",
                    "tier": 3,
                })
                if len(out) >= max_n:
                    return out
        return out
```

**接入**：`MetaDGTF._anchor_round` 里 `retriever != "snapshot"` 时用 `AnchorRetriever.search`。

#### Step 4.4 引用入表

**`_citation_table` 里**：

```python
if getattr(pool, "anchor_as_evidence", False):
    for _xi, _xa in enumerate(
            (getattr(pool, "anchors", None) or [])[:12], 1):
        _t = int(_xa.get("tier", 3) or 3)
        if _t > int(cfg.get("tier_floor", 2)):
            continue
        out.append((f"X{_xi}", str(_xa.get("claim", ""))))
```

**`apply_decidability_change` 里**：

```python
_valid_x = str(r.get("resolved_to", "")).startswith("X")
if _valid_x and ent["to"] == "undecidable":
    return _reject("锚点编号只能支撑 →decidable / →partial，"
                   "不能用来支撑 →undecidable")
```

#### Step 4.5 冲突处理

**`_anchor_crosscheck` 里**：

```python
if verdict == "冲突":
    view.errors.append(f"锚点冲突：{cid} ↔ {ids}")
    pool.meta.append(f"[锚点冲突] {cid} ↔ {ids}")
    if cfg.get("as_evidence") == "gate":
        blocked.append(cid)
```

**`_pack_result` 里**：`"blocked_conclusions": blocked`。

#### Step 4.6 triage 降级

**`_anchor_crosscheck` 里**：

```python
_TRIAGE_KEYS = ("信息不足", "需外部动作", "缺数据", "无外部")
for a in (dec.get("undecidable_aspects") or []):
    if not any(k in str(a) for k in _TRIAGE_KEYS):
        continue
    hit = next((x for x in anchors
                if int(x.get("tier", 3) or 3) <= cfg["tier_floor"]
                and _similar(str(a), str(x.get("claim", "")), 0.6)),
               None)
    if hit:
        triage_downgrades.append({
            "from": "undecidable", "to": "partial",
            "aspect": str(a)[:80],
            "anchor_id": hit["id"],
        })
```

#### Step 4.7 头部渲染

**`save_result` 里**：

```python
_ea = result.get("external_anchor") or {}
if _ea:
    f.write(f"**锚点分级**：{_ea.get('as_evidence', 'off')}\n")
    f.write(f"**triage 降级**：{_ea.get('triage_downgrades', 0)} 条\n")
    f.write(f"**冲突**：{_ea.get('conflicts', 0)} 条\n\n")
```

### 5.3 阶段 4 冒烟

```python
def check_v122_phase4(SRC):
    import importlib.util
    spec = importlib.util.spec_from_file_location("dgtf", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    ea = m.DEFAULT_CONFIG.get("external_anchor") or {}
    assert ea.get("as_evidence") in (
        "off", "record", "crosscheck", "evidence", "gate")
    assert "tier_floor" in ea
    assert "api_key_env" in ea
    pool = m.Pool()
    pool.anchors = [{"id": "a1", "claim": "X", "tier": 1}]
    pool.anchor_as_evidence = True
    tbl = m._citation_table(None, pool)
    assert any(c.startswith("X") for c, _ in tbl)
    pool.anchors = [{"id": "a2", "claim": "Y", "tier": 4}]
    tbl = m._citation_table(None, pool)
    assert not any(c.startswith("X") for c, _ in tbl)
    assert hasattr(m, "AnchorRetriever")
    src = open(SRC, encoding="utf-8").read()
    assert "锚点冲突" in src
    assert "triage_downgrades" in src
    assert "锚点分级" in src
    return True
```

### 5.4 阶段 4 验收

**命令**：

```bash
python _v122_verify.py --phase 4 --src 元DGTF-V1.22.0-rc1.py
echo "EXIT=$?"
```

**真跑（带锚点）**：先写 `_test_anchors.json`（含 tier 1 的 2 条），跑：

```bash
python - <<'EOF'
import importlib.util
spec = importlib.util.spec_from_file_location("dgtf", "元DGTF-V1.22.0-rc1.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
cfg = m.DEFAULT_CONFIG.copy()
cfg["external_anchor"] = dict(cfg["external_anchor"])
cfg["external_anchor"].update({
    "enabled": True, "path": "_test_anchors.json",
    "as_evidence": "evidence", "tier_floor": 2,
})
meta = m.MetaDGTF(cfg)
res = meta.run("老城区暴雨内涝频发，排水系统重建还是局部改造加海绵措施？",
               route=["0", "1"], rounds="0:3,1:3")
m.save_result(res, "outputs")
EOF
LATEST=$(ls -t outputs/*.md | head -1)
grep -E "锚点分级|triage 降级|已获证据资格" $LATEST
```

**通过判据**：

- 至少一份产物"已获证据资格"
- 至少一条判定被 `X#` 支撑
- 至少一条 triage 降级
- 冲突留痕可见

**阶段 4 报告**：`v122_phase4_报告.md`

---

## 6. 阶段 5（6A）：机制审计

### 6.1 目标表

| 编号 | 目标 | 量化验收 |
|---|---|---|
| G5.1 | 审计脚本 | 可运行 |
| G5.2 | 审计报告 | 含所有机制名 |
| G5.3 | pending_fix | 文档存在 + 每条有 |
| G5.4 | 双实现检出 | auto_plan 被检出 |
| G5.5 | 头部渲染 | 含"机制审计" |
| G5.6 | 本版无删除 | del = 0 |

### 6.2 Step 清单

#### Step 5.1 `_audit_v122_dead_mechanisms.py`

```python
import re, json, sys
from pathlib import Path

MECHS = [
    ("escalate_starve_rounds", "连续 N 圈无进展 + 名下有账"),
    ("no_push_when_idle", "空转类判据 + 未深入方向"),
    ("_reopen_closed_debt", "分类被推翻 + 曾有 escalated"),
    ("stable_layers", "悬置连续 N 圈同批"),
    ("both_quota.max_ratio", "both 占比超阈值"),
    ("both_tighten_ratio", "同上，改判"),
    ("_all_settle_streak", "元层清算未下降"),
    ("min_rounds", "layer_no < min_r"),
    ("structure_saturation", "每 N 圈无新维度"),
    ("_budget_exhausted", "调用数超预算"),
    ("DecidabilityFreeze.verify", "签名不匹配"),
    ("triage_downgrades", "信息不足型 und + 锚点命中"),
    ("_anchor_crosscheck.conflict", "结论与锚点相反"),
]

def count_in(paths, name):
    n = 0
    for p in paths:
        text = p.read_text(encoding="utf-8", errors="replace")
        n += text.count(name)
    return n

def main():
    logs = list(Path(".").glob("verif_*.log"))
    prods = list(Path("outputs").glob("*.md"))
    rows = []
    for name, cond in MECHS:
        lh = count_in(logs, name)
        ph = count_in(prods, name)
        rows.append({
            "mechanism": name, "condition": cond,
            "log_hits": lh, "prod_hits": ph,
            "verdict": "可达" if (lh + ph) > 0 else "待审",
        })
    Path("audit_v122_dead_mechanisms.md").write_text(
        "# 机制审计 v122\n\n" +
        "| 机制 | 触发条件 | 日志命中 | 产物命中 | 判定 |\n"
        "|---|---|---|---|---|\n" +
        "\n".join(f"| {r['mechanism']} | {r['condition']} | "
                  f"{r['log_hits']} | {r['prod_hits']} | {r['verdict']} |"
                  for r in rows),
        encoding="utf-8")
    print("audit -> audit_v122_dead_mechanisms.md")

if __name__ == "__main__":
    main()
```

#### Step 5.2 双实现清单

**扫描**：`grep -n "def _auto_plan\|def auto_plan\|_rephrase_streak" 元DGTF-V1.22.0-rc1.py`

**输出**：写进 `docs/机制审计-v122.md`：

```markdown
## 双实现清单

| 机制 | 实现 A | 实现 B | 行为相同? | 处理 |
|---|---|---|---|---|
| auto_plan | 模块级 auto_plan | MetaDGTF._auto_plan | 待验证 | 阶段 6 收口或标 pending_fix |
| _rephrase_streak | _run_layer | _run_one_round_B | 待验证 | 同上 |
```

#### Step 5.3 `pending_fix` 标注

**在主文件加注释**：`# [AUDIT-122] 标 pending_fix：<理由>`

**头部渲染**：`save_result` 加：

```python
f.write(f"**机制审计**：pending_fix N 项，双实现 M 项"
        f"（详见 docs/机制审计-v122.md）\n\n")
```

### 6.3 阶段 5 冒烟

```python
def check_v122_phase5(SRC):
    from pathlib import Path
    assert Path("_audit_v122_dead_mechanisms.py").exists()
    assert Path("audit_v122_dead_mechanisms.md").exists()
    text = Path("audit_v122_dead_mechanisms.md").read_text(encoding="utf-8")
    for name in ("escalate_starve_rounds", "no_push_when_idle",
                 "_reopen_closed_debt", "stable_layers",
                 "min_rounds", "triage_downgrades"):
        assert name in text
    src = open(SRC, encoding="utf-8").read()
    assert "机制审计" in src
    assert "auto_plan" in src and "_auto_plan" in src
    return True
```

### 6.4 阶段 5 验收

**命令**：

```bash
python _audit_v122_dead_mechanisms.py
python _v122_verify.py --phase 5 --src 元DGTF-V1.22.0-rc1.py
echo "EXIT=$?"
python - <<'EOF'
import sys; sys.path.insert(0, ".")
from _v122_verify import count_del_lines
n, sample = count_del_lines("_baseline_v12177.py", "元DGTF-V1.22.0-rc1.py")
print(f"删除代码行数: {n}")
assert n == 0, f"本版不许删代码，实测删了 {n} 行"
EOF
```

**通过判据**：

- 审计报告生成
- 零触发机制全部被判定为“可达 / 狭窄 / pending_fix”
- `auto_plan` 双实现被检出
- 头部“机制审计”行出现
- 删除代码行数 = 0

**阶段 5 报告**：`v122_phase5_报告.md`

---

## 7. 阶段 6（6B）：双实现收口

### 7.1 目标表

| 编号 | 目标 | 量化验收 |
|---|---|---|
| G6.1 | 行为对照 | before/after 快照 |
| G6.2 | auto_plan 收口 | 薄壳 + 逐字相同 |
| G6.3 | _rephrase_streak 收口 | 唯一实现 |
| G6.4 | 产物文本一致 | 逐字（排时间戳） |
| G6.5 | 审计文档更新 | resolved 段有 |
| G6.6 | AST 等价 | 或逐节点差异有解释 |

### 7.2 Step 清单

#### Step 6.1 行为对照基线

```bash
python _probe_v122_phase6.py baseline --out _v122_phase6_baseline_before.json
```

#### Step 6.2 `auto_plan` 收口

**模块级 `auto_plan` 唯一实现**：

```python
def auto_plan(question, config=None, config_path=None, llm=None):
    ...
```

**`MetaDGTF._auto_plan` 退薄壳**：

```python
def _auto_plan(self, question: str) -> dict:
    """[v122 P6] 收口到模块级 auto_plan。签名保持兼容。"""
    return auto_plan(question, self.config, llm=self.llm)
```

#### Step 6.3 `_rephrase_streak` 收口

```python
def _compute_rephrase_streak(view, state) -> int:
    _mi_from_view = getattr(view, "_meta_idle_streak", 0)
    _mi_state = int((state or {}).get("meta_idle_streak", 0) or 0)
    return max(_mi_state, int(_mi_from_view or 0))
```

两处调用点（`_run_layer` / `_b_check_stop`）各改一行。

#### Step 6.4 收口后行为对照

```bash
python _probe_v122_phase6.py baseline --out _v122_phase6_baseline_after.json
diff -u _v122_phase6_baseline_before.json _v122_phase6_baseline_after.json
```

#### Step 6.5 审计文档更新

`docs/机制审计-v122.md` 的 `resolved` 段追加。

### 7.3 阶段 6 冒烟

```python
def check_v122_phase6(SRC):
    import importlib.util, ast, hashlib
    spec = importlib.util.spec_from_file_location("dgtf", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert hasattr(m, "auto_plan")
    src = open(SRC, encoding="utf-8").read()
    assert "return auto_plan(question, self.config" in src
    assert src.count("def _compute_rephrase_streak") == 1
    from pathlib import Path
    assert Path("docs/机制审计-v122.md").exists()
    return True
```

### 7.4 阶段 6 验收

**命令**：

```bash
python _v122_verify.py --phase 6 --src 元DGTF-V1.22.0.py
echo "EXIT=$?"
```

**产物逐字一致**：

```bash
python 元DGTF-V1.22.0-rc1.py "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵措施？" \
  --route 0,1 --rounds "0:3,1:3" --parallel serial --quiet --profile balanced
BEFORE=$(ls -t outputs/*.md | head -1)
cp $BEFORE _v122_phase6_before.md

python 元DGTF-V1.22.0.py "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵措施？" \
  --route 0,1 --rounds "0:3,1:3" --parallel serial --quiet --profile balanced
AFTER=$(ls -t outputs/*.md | head -1)
cp $AFTER _v122_phase6_after.md

grep -v "^\*\*时间\*\*" _v122_phase6_before.md > _b.md
grep -v "^\*\*时间\*\*" _v122_phase6_after.md > _a.md
diff -q _b.md _a.md
```

**通过判据**：

- 无 diff 输出
- 函数节点数不增加
- 审计文档 `resolved` 段有更新

**阶段 6 报告**：`v122_phase6_报告.md`

---

## 8. 附 6C：拆模块（只出报告，不落地）

### Step 8.1 依赖分析

`_probe_v122_phase7_modules.py`：全库符号依赖图 → 强连通分量 → 候选模块划分。

### Step 8.2 兼容策略

保留 `元DGTF-V1.22.0.py` 作为**薄 shim**：import 全部 + `main()`。

### Step 8.3 报告

`docs/拆模块方案-v122.md`：

- 候选模块划分（config / llm / pools / lifecycle / decidability / anchors / spiral / render / bench / meta / dgtf / main）
- 迁移步骤
- 风险与回退
- AST 等价验证方案
- 27 个探针 / 冒烟的兼容性核对

### Step 8.4 验收判据

- 报告生成
- 依赖图无循环
- 迁移方案可执行
- **不实际拆**

---

## 9. 全局收尾

### Step F.1 全量回归

```bash
python bench/bench_run.py
LATEST=$(ls -t bench/runs | head -1)
python bench/bench_report.py bench/runs/$LATEST > bench/reports/v122_full.md
```

**通过判据**：

- 20 题产物都存在
- 报告含 4 列：判定 / 一致率 / 分层 pass / rubric

### Step F.2 版本定稿

- `__version__ = "1.22.0"`
- changelog 加 `v1.22.0 相对 v1.21.77`，六段

### Step F.3 `v122_报告.md`

```
一、总览：六阶段目标、判据、结论
二、阶段 1：目标函数分层 + Bench 骨架
三、阶段 2：三态多票 + 冻结 + 人工校准
四、阶段 3：decision 行动闭环
五、阶段 4：外部锚点真证据
六、阶段 5：机制审计
七、阶段 6：双实现收口
八、附 6C：拆模块方案（未落地）
九、全量回归结果
十、遗留与下一版候选
```

### Step F.4 交付物清单核对

```bash
python - <<'EOF'
import sys
from pathlib import Path
req = [
    "元DGTF-V1.22.0.py", "smoke_test.py", "_v122_verify.py",
    "_v122_final_verify.sh",
    "_audit_v122_dead_mechanisms.py", "audit_v122_dead_mechanisms.md",
    "docs/机制审计-v122.md", "docs/拆模块方案-v122.md",
    "v122_phase1_报告.md", "v122_phase2_报告.md",
    "v122_phase3_报告.md", "v122_phase4_报告.md",
    "v122_phase5_报告.md", "v122_phase6_报告.md",
    "v122_报告.md",
    "bench/bench_run.py", "bench/bench_score.py",
    "bench/bench_diff.py", "bench/bench_report.py",
    "bench/bench_calibrate.py",
]
missing = [r for r in req if not Path(r).exists()]
print(f"缺失: {missing}")
sys.exit(1 if missing else 0)
EOF
```

**通过判据**：`缺失: []`。

---

## 10. 每阶段报告模板

```markdown
# v1.22 阶段 N 报告

## 一、目标
## 二、改前基线（探针 before，附 diff 片段）
## 三、改了什么（逐条 + 行号）
## 四、改后对照（探针 after）
## 五、冒烟结果（exit / ✗ 数 / 新断言数）
## 六、真跑样本（≥3 题：calls / tokens / 分层指标）
## 七、验收判据核对（逐项打勾）
## 八、遗留与下一阶段候选

（阶段 5/6 加）
## 九、pending_fix 清单
## 十、双实现收口清单
## 十一、AST 等价证据
```

---

## 11. 遇到不确定时的处理

| 情况 | 处理 |
|---|---|
| 不确定该不该改代码 | 先写探针量出改前行为 |
| 不确定该加还是该删 | 加。本版不删任何机制 |
| 不确定阈值取多少 | 给默认值，写进配置 |
| 不确定某机制是否已存在 | grep 全库 + 读冒烟断言 |
| 不确定是否影响旧断言 | 跑全套冒烟；红了就修，不改旧断言 |
| 不确定是否该跨阶段 | 不跨。前一阶段未通过，不许开下一阶段 |
| 不确定是否要真跑 | 要。每阶段至少 3 道题真跑 |
| 不确定是否该报“已完成” | 回到代码与日志核对；必须能指到行号或产物 |
| 不确定双实现能否收口 | 同一 mock 输入跑两版对照；逐字段一致才收 |
| 不确定是否该拆模块 | 不拆。只出报告 |

---

## 12. 执行顺序与禁令

### 执行顺序

```
阶段 1（1+5） → 验收
  ↓
阶段 2（3）   → 验收
  ↓
阶段 3（4）   → 验收
  ↓
阶段 4（2）   → 验收
  ↓
阶段 5（6A）  → 验收
  ↓
阶段 6（6B）  → 验收
  ↓
附 6C（报告） → 无验收
  ↓
全量收尾
```

### 禁令

- 不许跳过验收判据
- 不许一次改两个阶段
- 不许改已有阈值 / 常量
- 不许删旧键、旧方法（**本版一行 `del` 都不许有**）
- 不许把失败写进日志了事
- 不许在没有探针对照的情况下宣称"修好了"
- 不许在报告里写"大致完成""基本可用"——要么能指到行号或产物，要么写"未完成"
- 不许在阶段 6 顺手拆模块
- 不许在没有 AST 等价证明的情况下宣称"重构无影响"

---

## 附录 A · `_v122_verify.py` 骨架

完整代码见上一轮回答中的 `_v122_verify.py`。核心函数：

- `load_module(src)`
- `ast_sig(path)`
- `diff_stat(a, b)`
- `crlf_ok(path)`
- `count_del_lines(a, b)`
- `phase1(src)` ~ `phase6(src)`
- `global_checks(src)`
- `main()` 支持 `--phase 1~6|all` 与 `--src`

## 附录 B · `_v122_final_verify.sh`

```bash
#!/usr/bin/env bash
set -e
SRC=${1:-元DGTF-V1.22.0.py}
echo "════════════════════════════════════════"
echo "v1.22 最终验收 · SRC=$SRC"
echo "════════════════════════════════════════"
echo
echo "【1】六阶段验收"
python _v122_verify.py --phase all --src "$SRC"
echo
echo "【2】冒烟"
python smoke_test.py
echo "smoke EXIT=$?"
echo
echo "【3】CRLF"
python - <<EOF
import sys; sys.path.insert(0, ".")
from _v122_verify import crlf_ok
ok, info = crlf_ok("$SRC")
print(f"CRLF: {info}")
sys.exit(0 if ok else 1)
EOF
echo
echo "【4】无删除代码行"
python - <<EOF
import sys; sys.path.insert(0, ".")
from _v122_verify import count_del_lines
n, sample = count_del_lines("_baseline_v12177.py", "$SRC")
print(f"del={n}")
if sample: print("sample:", sample)
sys.exit(0 if n == 0 else 1)
EOF
echo
echo "【5】bench 全量"
python bench/bench_run.py
LATEST=$(ls -t bench/runs | head -1)
python bench/bench_report.py "bench/runs/$LATEST" > "bench/reports/v122_full.md"
echo "report -> bench/reports/v122_full.md"
echo
echo "════════════════════════════════════════"
echo "✅ 全部验收通过"
echo "════════════════════════════════════════"
```

---

## 交付物总清单（最终核对用）

```
代码
  ☐ 元DGTF-V1.22.0.py
  ☐ 元DGTF-V1.22.0-rc1.py ~ rcN.py（中间态）
  ☐ smoke_test.py（含 6 条 check_v122_phaseN）

验收
  ☐ _v122_verify.py
  ☐ _v122_final_verify.sh
  ☐ _probe_v122_phase1.py ~ phase6.py
  ☐ _probe_v122_phaseN_*_before.txt / _after.txt

Bench
  ☐ bench/questions/*.yaml（≥ 20）
  ☐ bench/gold/*.yaml（≥ 3）
  ☐ bench/bench_run.py / bench_score.py / bench_diff.py
  ☐ bench/bench_report.py / bench_calibrate.py
  ☐ bench/runs/<ts>/*
  ☐ bench/reports/v122_full.md

审计
  ☐ _audit_v122_dead_mechanisms.py
  ☐ audit_v122_dead_mechanisms.md
  ☐ docs/机制审计-v122.md
  ☐ docs/拆模块方案-v122.md

报告
  ☐ v122_phase1_报告.md
  ☐ v122_phase2_报告.md
  ☐ v122_phase3_报告.md
  ☐ v122_phase4_报告.md
  ☐ v122_phase5_报告.md
  ☐ v122_phase6_报告.md
  ☐ v122_报告.md
```

**任何一项缺失 = 任务未完成。**
