#!/usr/bin/env bash
# [v1.21.60] 收束前最后一轮并行真跑：验证 koan 进不进得去 + reclassification 入口 +
# 元层自然安住（stable_layers 3）。3 个 run 并发（这也是并行 runner 的首测）。
set -u
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8

python -u _run_parallel_batch.py --max-concurrency 3 \
  "serial 6 koan1 人生的意义是什么" \
  "serial 12 reclass 复杂问题被拆成几个部分分别研究之后，剩下的那个整体到底是什么？" \
  "serial 6 koan2 自由意志是否存在"
