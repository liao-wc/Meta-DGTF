#!/usr/bin/env bash
# [v1.22.1 P1.4] 任务书指定的 3 题真跑（四层 0:4,1:4,both:4,all:5；serial；decision 取向）。
# 三题**并发**（同一组参数，只有调度不同）以压缩墙钟；各自写进 outputs/p1_runN/。
cd "$(dirname "$0")"
SRC="${1:-元DGTF-V1.22.1-rc1.py}"
Q1="老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？怎么权衡？"
Q2="现金流紧张的中小制造企业，上自动化产线还是维持人工加局部优化？怎么决策？"
Q3="社区医院人力有限，慢性病管理推远程监测还是加派人手上门随访？资源怎么配？"
for i in 1 2 3; do
  mkdir -p "outputs/p1_run${i}"
  printf 'output:/n  save_dir: outputs/p1_run%s\n  verbose: false\n' "$i" > "_p1_cfg${i}.yaml"
done
eval "Q=\$Q$?" 2>/dev/null
( python "$SRC" "$Q1" -c _p1_cfg1.yaml --route 0,1,both,all --rounds "0:4,1:4,both:4,all:5" \
    --parallel serial --orientation decision --quiet > _p1_run1.log 2>&1 ) &
( python "$SRC" "$Q2" -c _p1_cfg2.yaml --route 0,1,both,all --rounds "0:4,1:4,both:4,all:5" \
    --parallel serial --orientation decision --quiet > _p1_run2.log 2>&1 ) &
( python "$SRC" "$Q3" -c _p1_cfg3.yaml --route 0,1,both,all --rounds "0:4,1:4,both:4,all:5" \
    --parallel serial --orientation decision --quiet > _p1_run3.log 2>&1 ) &
wait
for i in 1 2 3; do
  n=$(ls outputs/p1_run${i}/*.md 2>/dev/null | wc -l)
  echo "run${i}: 产物 ${n} 个"
done
echo P1_RUNS_DONE
