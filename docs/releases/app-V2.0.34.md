# App V2.0.34（2026-10-26）

## 主题
Round 125–126：本地 judge 吞吐治理、App 缓存显式绕过、引擎 probe 覆盖兜底、验收扩至 13 项。

## 改动
- dgtf_local_llm/service.py：dual_judge 忙/排队时立即 **503 BUSY**（快失败），
  /metrics 新增 dual_judge_fastfail；引擎毫秒级回退 llm（不再等 120s）。
- dgtf_app/server.py：opts.no_cache / opts.force_rerun 别名 ⇒ 跳过产物缓存与运行中任务去重；
  _find_cached_pack / _find_running_duplicate 内部自守卫。
- scripts/app_fast_e2e.py：支持 DGTF_E2E_NO_CACHE=1 并回显 cache_hit。
- 引擎 Meta-DGTF-V2.2.3.py：probe 覆盖判据新增 _probe_covers_target（严尺子 + 词面近义
  AND 兜底：sim3≥0.25 且 overlap≥0.30；离线审计 92 flagged 中翻正 9.8%，样例语义相关）。
- 一键验收新增 pp_cache_bypass / judge_fastfail / probe_cover_wide：**13/13（有服务）**。

## 验证
- fast_gate 12/12；V2 51/51（835 checks）；
- inal_acceptance.py --with-service **13/13 PASS**；
- judge 并发实测：一个 200（~1.96s）、另一个 **503 BUSY（17.7ms）**；
- 版本检查 pp_version_check.py 全绿（本版本）。
