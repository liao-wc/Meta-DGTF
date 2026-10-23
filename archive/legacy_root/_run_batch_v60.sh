#!/usr/bin/env bash
# [v1.21.60] 真跑验收批次（顺序执行，避免并发抢额度/触发限流）
set -u
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8

echo "=== 批次开始 $(date '+%F %T') ==="

# ---- ② 分类分布：用 v59 的原题 + 原配置（不传 rounds → 走配置的 hard_max 12）
#      目的：与 v59 直接对比（v59 那时是 undecidable → koan → 全层交白卷）
echo "[②] 分类分布 · serial · 默认预算 · v59 原题"
python -u _run_v60.py serial 12 cls59 \
  "复杂问题被拆成几个部分分别研究之后，剩下的那个「整体」到底是什么？"

# ---- ③ C / E / G / H 各跑一次（真跑里从未出现过这四种）
#      用 4 圈把成本压住：验的是"能否端到端跑通 + 产物完整 + 分类合理"
echo "[③-C] 流水线并行 · 4 圈 · 可判定偏强的题"
python -u _run_v60.py C 4 modeC \
  "AI 能否独立完成数字 IC 设计流程？哪些环节已经量产、哪些还不行？"

echo "[③-E] 双起并行+撞元串行 · 4 圈 · v59 那道抽象题"
python -u _run_v60.py E 4 modeE \
  "复杂问题被拆成几个部分分别研究之后，剩下的那个「整体」到底是什么？"

echo "[③-G] 修行先行+撞毕收元 · 4 圈 · 明显可判定的题"
python -u _run_v60.py G 4 modeG \
  "2024 年欧盟 AI 法案对高风险 AI 系统规定了哪些合规要求？"

echo "[③-H] 逐层接力+撞元并行 · 4 圈 · 操作化题"
python -u _run_v60.py H 4 modeH \
  "怎么衡量一条城市地铁线路的运营效率？用什么指标、数据从哪来？"

echo "=== 批次结束 $(date '+%F %T') ==="
