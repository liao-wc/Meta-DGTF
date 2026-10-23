#!/usr/bin/env bash
Q="老城区暴雨内涝频发，排水系统重建还是局部改造加海绵措施？"
set -x
python 元DGTF-V1.22.0-rc1.py "$Q" --route 0,1 --rounds "0:3,1:3" \
  --parallel serial --quiet --profile balanced > _p6_before_stdout.log 2>&1
B=$(ls -t outputs/*.md | head -1)
cp "$B" _v122_phase6_before.md
python 元DGTF-V1.22.0.py "$Q" --route 0,1 --rounds "0:3,1:3" \
  --parallel serial --quiet --profile balanced > _p6_after_stdout.log 2>&1
A=$(ls -t outputs/*.md | head -1)
cp "$A" _v122_phase6_after.md
echo "before=$B"
echo "after=$A"
grep -v "^\*\*时间\*\*" _v122_phase6_before.md > _b.md
grep -v "^\*\*时间\*\*" _v122_phase6_after.md > _a.md
if diff -q _b.md _a.md; then echo "PHASE6_PRODUCT_IDENTICAL"; else echo "PHASE6_PRODUCT_DIFF"; fi
