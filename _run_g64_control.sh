#!/usr/bin/env bash
Q="老城区暴雨内涝频发，排水系统重建还是局部改造加海绵措施？"
python 元DGTF-V1.22.0.py "$Q" --route 0,1 --rounds "0:3,1:3" \
  --parallel serial --quiet --profile balanced > _ctrl1.log 2>&1
cp "$(ls -t outputs/2026100*.md | head -1)" _v122_ctrl1.md
python 元DGTF-V1.22.0.py "$Q" --route 0,1 --rounds "0:3,1:3" \
  --parallel serial --quiet --profile balanced > _ctrl2.log 2>&1
cp "$(ls -t outputs/2026100*.md | head -1)" _v122_ctrl2.md
echo CONTROL_DONE
