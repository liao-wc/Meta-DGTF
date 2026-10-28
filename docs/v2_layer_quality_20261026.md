# V2 outcome 层局部质量修复记录

时间：2026-10-26

## 缺陷

原 V2 schedule_outcome 把整跑 quality 复制给同一 run 的每个模板：

    quality = q_overall

导致同一 run 内 0:r2 / 1:r2 / both:r2 / all:r2 quality 完全相同；
配对 A/B 120 对差异全 0，模板胜者不可识别，自动策略只能冻结。

## 修复

1. dgtf_v2/bridge.py 新增 _layer_quality()：
   - 以整跑 quality 为锚；
   - 用该层 decidable/undecidable 产物、covered/uncovered、untouched、quality_flags 做 ±0.2 偏移；
   - 输出 quality_source=layer_signals_v1、quality_overall、层结构读数；
2. memory.py / unified_memory.py 的 outcome 支持安全 extra 字段；
3. 新增 scripts/recompute_v2_layer_quality.py 重算历史 891 条 outcome；
4. /api/schedule/v2/auto-apply 增加校准闸：
   - 可识别性通过后，仍要求 layer_signals_v1 经过整跑校准；
   - 当前 _V2_LAYER_QUALITY_VALIDATED=False，自动写入继续冻结；
5. 帕累托推荐只使用 n>=5 的模板。

## 效果

迁移后配对：

    n_pairs=120
    nonzero_pairs=117
    nonzero_ratio=0.975
    identifiable=true
    winner=1:r2

自动写入：

    ok=false
    error=层局部质量 layer_signals_v1 尚未通过整跑校准；
          自动写入保持冻结

## 注意

- layer_signals_v1 是确定性结构启发式，不是整跑质量；
- 必须用独立真跑 A/B 校准后才可打开自动写入；
- 历史 quality_overall 保留，可追溯；
- 备份：
  - dgtf_memory/v2_events.jsonl.bak_requal_*
  - dgtf_memory/schedule_policy.json.bak_*
