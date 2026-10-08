#!/usr/bin/env bash
# [v1.21.60] 验证池评估提示词修正：重跑两道「明显可判定」的题，
# 看池判是否从 partial 回到 decidable。用与上次完全相同的模式做干净 A/B。
set -u
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
export V60_STREAM=1

echo "=== 验证批次开始 $(date '+%F %T') ==="

echo "[verifyG] 欧盟AI法案 · modeG · 4 圈（上次：池判 partial，外判 decidable）"
python -u _run_v60.py G 4 verifyG \
  "2024 年欧盟 AI 法案对高风险 AI 系统规定了哪些合规要求？"

echo "[verifyH] 地铁运营 · modeH · 4 圈（上次：池判 partial，外判 decidable）"
python -u _run_v60.py H 4 verifyH \
  "怎么衡量一条城市地铁线路的运营效率？用什么指标、数据从哪来？"

echo "=== 验证批次结束 $(date '+%F %T') ==="
