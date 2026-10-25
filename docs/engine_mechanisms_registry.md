# 引擎机制登记表（V2.2.3 机制层）

> 适用引擎：`dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.3.py`（`__version__ = "2.2.3"`）
> 配套确定性核：`dgtf_engine/dgtf_v2/fine_check.py`（纯函数、零 IO、零 LLM）
> 原则：**默认零行为差 + 显式 opt-in**。所有新键在默认值下都不改变任何调用、
> prompt、输出或落盘内容；回退 = 把对应键改回默认。
> 写作用域：本文件只登记引擎侧契约；`dgtf_app/` 的实际透传由 App 负责人改。

---

## 1. 配置键总表

| 键 | 类型 | 默认值 | 生效位置 | 行为契约 | 关闭/回退 |
|---|---|---|---|---|---|
| `output.self_check_mode` | str | `"llm"` | `DGTF._self_check`（按层，每圈） | 自省档位：`llm`=原样一次 LLM 调用（**默认，与 V2.2.2 逐字一致**）；`auto_narr`=决策字段仍走 LLM 但 prompt 收窄、计数/复述/叙述由确定性核本地化；`local`=本地模型出语义字段+确定性核校验，失败升级云 LLM；`auto`=**实验档**，仅当运行时 provenance 判「无可疑/无复述/无静默」才跳过 LLM（回放态不承诺指标）；`off`=不自省 | 改回 `"llm"` |
| `output.dual_judge_mode` | str | `"llm"` | `DGTF._dual_judge`（对偶判断） | `llm`=原样逐轮 LLM 判位置（**默认**）；`cache`=判定缓存（key=层+归一化锚点+归一化候选文本+kind/source/attribute；落盘 `dgtf_memory/dual_judge_cache.json`，带 provenance）；`auto`=缓存+历史结构先验，二者**全覆盖**才免调用，否则整批走 LLM。`diversity_hint` 非空（结构复采样）**强制走 LLM** | 改回 `"llm"`；删除缓存文件 |
| `output.thinking_stage_overrides` | dict | `{}` | `LLM.call` 的 thinking 解析 | 环节级 thinking 覆盖，如 `{"self_check": "disabled"}`。优先级：**调用点显式 `thinking=` > 本覆盖 > `api.thinking.stages` > `thinking.default`**。默认空 = 逐字零行为差 | 改回 `{}` |
| `output.local_llm` | dict | 见下 | `DGTF._self_check_local`（仅 `local` 档） | 本地自省模型端点（早期草案位置；与 `api.local_llm` 合并读取，`api` 优先） | 改回 `self_check_mode="llm"` |
| `api.local_llm` | dict | `{"url":"http://127.0.0.1:8772/generate","timeout":30.0,"enabled":true,"min_confidence":0.6}` | 同上 | 本地模型端点（Lead/local-smith 约定位置，优先于 `output.local_llm`）。`enabled=false` 只影响 `local` 档行为，不影响默认档 | 改回 `self_check_mode="llm"` |
| `output.dual_judge_prior` | dict | `{"min_support":20,"min_confidence":0.75}` | `DGTF._dj_prior_get`（仅 `auto` 档） | 结构先验硬门控：分组历史样本 `<min_support` 或组内多数类占比 `<min_confidence` ⇒ **不用先验，升 LLM**。先验表由离线回放生成（`engine/dual_judge_prior.json`） | 文件缺失 ⇒ `auto` 退化为 `cache`；改回 `"llm"` |

### DEFAULT_CONFIG 片段（带注释，见引擎 `DEFAULT_CONFIG["output"]`）
```python
"self_check_mode": "llm",
"dual_judge_mode": "llm",
"thinking_stage_overrides": {},
"local_llm": {"url": "http://127.0.0.1:8772/generate", "timeout": 30.0,
              "fallback": "llm", "min_confidence": 0.6},
"dual_judge_prior": {"min_support": 20, "min_confidence": 0.75},
```

---

## 2. CLI 参数（`python dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.3.py ...`）

| CLI | 覆盖的配置键 | 取值 | 备注 |
|---|---|---|---|
| `--self-check-mode MODE` | `output.self_check_mode` | `llm` / `auto_narr` / `auto` / `local` / `off` | 不给 = 用 yaml/DEFAULT（零行为差） |
| `--dual-judge-mode MODE` | `output.dual_judge_mode` | `llm` / `cache` / `auto` | 不给 = 零行为差 |
| `--stage-thinking "a=disabled,b=enabled"` | `output.thinking_stage_overrides` | `环节=disabled/enabled` | 在 `_apply_runtime`（`--thinking on/off` 会重写 stages 表）**之后**应用，保证「关得掉」 |
| `--local-llm-url URL` | `output.local_llm.url`（合并进 `local_llm_cfg`） | URL | 仅 local 档读取 |

> ★ `--stage-thinking` 的优先级语义：显式 `thinking=` 参数（调用点）仍最高；
> 覆盖表只盖 `api.thinking.stages`。`_thinking_stage()` 对「只在覆盖表里出现」
> 的环节也返回 stage 名（否则新环节永远选不中）。

---

## 3. App 透传方式（登记，未改 App）

App 参数面板若需暴露本机制层，**只需把下列键原样写进传给引擎的 cfg dict**
（与 yaml 同构，无需新代码路径）：

| App 控件建议 | 写入路径 | 说明 |
|---|---|---|
| 自省档位下拉 | `cfg["output"]["self_check_mode"]` | 5 值枚举；默认不写 = llm |
| 双判档位下拉 | `cfg["output"]["dual_judge_mode"]` | 3 值枚举；默认不写 = llm |
| 环节思考覆盖（高级） | `cfg["output"]["thinking_stage_overrides"]` | dict[str,str]，值只认 `enabled/disabled` |
| 本地自省端点 | `cfg["api"]["local_llm"]["url"]`（或 `output.local_llm.url`） | local 档用；超时/置信度同理 |
| 双判先验门控 | `cfg["output"]["dual_judge_prior"]` | 可选 |

App 也可以在启动子进程时改用 CLI 参数（与上面一一对应）；两者等价。
**当前状态**：`dgtf_app/` 不在本任务写作用域，App 侧尚未透传；需要 App 负责人
（app-mode）加 5 个键或 4 个 CLI 开关。引擎侧已保证：键缺失/取值非法 ⇒
回落 `llm` 并 `logger.warning` 留痕，不阻断、不静默改行为。

---

## 4. local 模式协议（与 local-smith 对齐）

**请求**：`POST {api.local_llm.url}`，`Content-Type: application/json`
```json
{
  "stage": "self_check",
  "messages": [{"role": "system", "content": "…"}, {"role": "user", "content": "…"}],
  "text": "<system+user 拼串，兼容 text-only 服务>",
  "max_new_tokens": 600,
  "temperature": 0.3,
  "timeout": 30.0
}
```
**响应**：`HTTP 200`
```json
{"ok": true, "text": "{\"suspicious_candidates\":[1,3],\"suspicious_amps\":[],\"ing_rephrased\":false,\"unsaid_is_escape\":false,\"notes\":\"…\"}", "confidence": 0.82}
```
`text` 必须能解析出上述 JSON（允许外包一层说明文字，引擎会抠第一个 `{...}`）。

**失败即回退（硬约束）**：超时 / 非 200 / `ok=false` / `confidence < min_confidence`
/ `text` 解析不出 JSON / 连接失败 ⇒
1. `self.local_llm_errors += 1`（错误计数，可进产物）；
2. `self._local_llm_last_error` 记录类型+原因；
3. `view.meta.append("[SC-local] 本地模型失败（累计 N 次：…）⇒ 回退 llm")`；
4. 走**收窄 LLM**（`_self_check_decide_narrow`）；收窄也失败 ⇒ 整段回退
   `_self_check_llm`（原 V2.2.2 全量自省）。
确定性核与本地判定**不一致**（`fine_check.consistency_check` 报
`missing_suspicious / too_many_suspicious / rephrase_disagree`）⇒ 同样升级 LLM，
并写 `[SC-local] … 不一致 ⇒ 升级 LLM` 留痕。**绝不静默放行本地结果**。

---

## 5. 行为契约（红线）

1. **零行为差**：默认 `self_check_mode="llm"` + `dual_judge_mode="llm"` +
   `thinking_stage_overrides={}` + 不提供 local 端点时，调用次数、prompt 文本、
   返回字段、质量旗、carry 约束与 V2.2.2 **逐字一致**。
   证据：`tests_fine_check.py`（默认档 self_check `system+user` 字节级比对 PASS；
   返回字段集一致；质量旗不变）。
2. **自省是另一个视角（红线 8）**：所有档位都只写 `view.self_check`（独立字段
   + md 独立【自省】段），**不并入 content / manifest / collision**。`auto_narr`
   仍由 LLM 做语义判断，确定性核只做计数/复述/叙述。
3. **失败不静默**：确定性核导入失败 ⇒ 自动退回 `llm` 档；local/收窄调用失败
   ⇒ 回退并 `view.meta` 留痕；缓存/先验文件损坏 ⇒ 按空处理 + `logger.warning`。
4. **决策字段最小接管原则**：V2.2.3 起确定性核**不接管** `unsaid_overused` 旗、
   `ing_rephrased`、`suspicious_candidates` 的语义判断（离线回放显示召回不足，
   见 `docs/engine_fine_check_evidence.md`）；`auto_narr`/`local` 档里这些字段
   仍由 LLM/本地模型给出。
5. **不改 prompt 静态前缀**：V2.2.3 未重排任何既有 prompt 段落（零行为差要求）。
   prompt 前缀缓存优化见 §7，留待下一轮显式 opt-in。

---

## 6. 落盘与 provenance

| 文件 | 由谁写 | 内容 | 可删 |
|---|---|---|---|
| `dgtf_memory/dual_judge_cache.json` | `cache`/`auto` 档 | `{"schema":"dgtf.dual_judge_cache.v1","engine":"2.2.3","entries":{sha1:{position,why_position,provenance{entry,anchor,kind,source,first_seen,last_seen,hits,engine}}},...}` | 可删（删=缓存失效，行为不变） |
| `dgtf_engine/dgtf_v2/engine/dual_judge_prior.json` | `scripts/eval_self_check_replay.py --write-prior` | `{"schema":"dgtf.dual_judge_prior.v1","groups":{"entry|source|kind|attribute":{n,counts:{pos:n}}}}` | 可删（删=auto 退化为 cache） |
| `view.self_check`（packed/md） | 全部档位 | 11 个原字段；`auto*`/`local` 档额外 `_mode` / `_llm_used` / `_kernel` / `_audit` / `_local_errors` | 不适用 |

---

## 7. 风险与后续优化

### 风险
| 风险 | 影响 | 缓解 |
|---|---|---|
| `auto` 档在真实运行里跳过判定，但确定性核召回不足（回放实测 suspicious 召回 0.36） | 可能漏报可疑候选 | **标记实验档、不进默认**；跳过时只接管「无任何触发理由」的圈；`auto_narr`/`local` 不受影响 |
| `local` 模型质量/延迟不稳 | 语义字段质量下降或慢 | 低置信/失败/不一致三重门控 + 回退云端；默认不动 |
| `cache` 对普通问题零收益（跨跑重复仅 0.64%） | 仅重跑/续跑/修复场景有效 | 定位为「零风险附加项」，不作为主交付；`auto` 实验档才用先验 |
| `thinking_stage_overrides` 被误配成 `enabled` | 成本上升 | 显式 opt-in；registry 登记；`_thinking_stage` 只认 `enabled/disabled`，非法值忽略 |
| 双判先验替代 LLM | 位置判断错误 | 硬门控 `min_support=20 / min_confidence=0.75`，覆盖率仅 23%（离线口径），默认关 |

### 后续优化（本轮只登记，不改）
1. **prompt 前缀缓存（高 ROI，Lead 已实测）**：同 `system` + 不同 `user` 第二次命中
   1024/1269 tokens，TTL>8min；把**静态段全部前移到 system 开头、变化内容挪到
   user 末尾**可让跑次 cache hit>0。本轮不动（会破坏零行为差）。
2. `dual_judge` 的 stage 级 thinking 预算：`--stage-thinking "dual_judge=disabled"`
   已可用；真跑 A/B 待 Lead 调度。
3. `self_check_decide` 独立 stage 键（思考预算只作用于判定档）——待 App/CLI 约定。
4. 确定性核阈值（`susp_tail_*` / `sim_*`）可在更多真跑标签上再标定。

---

## 8. 快速验证命令（零 API）

```powershell
$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"
$env:PYTHONPATH="$PWD;$PWD/dgtf_engine"
python fast_gate.py                                        # 快速门禁
python scripts/run_v2_tests.py                             # V2 全量（含 tests_fine_check）
python scripts/eval_self_check_replay.py                   # 离线回放（零 API）
python dgtf_engine/dgtf_v2/tests_fine_check.py             # 机制层判据（48 checks）
```
