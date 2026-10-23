# APP V1.5.13 发布说明

## 主题

引擎 v1.30.2 答案/过程门与质量重放接入。

## 改动

- 质量 API 补 answer_quality/process_ready/evidence_gaps/tri/depth。
- 离线质量重放脚本 scripts/replay_quality.py。
- 版本/静态资源 1.5.13。

## 验证

- fast_gate 12/0；selftest 371/0；依赖审计 78/0。
- 质量重放：127 packed，public ready_but_process_false=0，layer1 citations>0 46 份。
