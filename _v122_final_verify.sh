#!/usr/bin/env bash
# 元 DGTF v1.22.0 一键验收脚本（任务书附录 B，按本机环境与 v122 口径落地）
#
# 用法：bash _v122_final_verify.sh 元DGTF-V1.22.0.py
#
# 与附录 B 的差异（都写明在这里，不藏）：
#   1. `python` → `$PY`（本机 python 不在 PATH 上，用托管解释器绝对路径；
#      可用 PY=... 覆盖）
#   2. 【4】的删除判据改用 `_v122_verify.count_del_lines`
#      （**纯删除块**口径）+ 追加 `mechanism_removed()`（按 AST 符号判）。
#      附录 B 里那句「以 '-' 开头的行数」会把**改写**也算成删除 ——
#      而任务书本身要求改签名 / 搬正文，那样判据恒为红。
#   3. 【2】冒烟退出码单独打印（set -e 会让它在失败处直接退出，看不到后续）
set -u
SRC="${1:-元DGTF-V1.22.0.py}"
PY="${PY:-C:/Users/18432/.workbuddy/binaries/python/versions/3.13.12/python.exe}"
PROFILE="${PROFILE:-economy}"
ROUNDS="${ROUNDS:-0:2,1:2,both:2,all:3}"
RC=0

echo "════════════════════════════════════════"
echo "v1.22 最终验收 · SRC=$SRC"
echo "════════════════════════════════════════"

echo
echo "【1】六阶段验收"
"$PY" _v122_verify.py --phase all --src "$SRC"
if [ $? -ne 0 ]; then RC=1; echo "❌ 六阶段验收未通过"; fi

echo
echo "【2】冒烟"
"$PY" smoke_test.py > _smoke_v122.log 2>&1
SM=$?
echo "smoke EXIT=$SM（✗ 计数 = $(grep -c '✗' _smoke_v122.log)）"
if [ $SM -ne 0 ]; then RC=1; echo "❌ 冒烟未通过"; tail -8 _smoke_v122.log; fi

echo
echo "【3】CRLF"
"$PY" - "$SRC" <<'EOF'
import sys
from pathlib import Path
sys.path.insert(0, ".")
from _v122_verify import crlf_ok
# ★ crlf_ok 返回的是 **dict**（ok / bare_lf / crr_lf ...），不是元组。
#   第一版按 `ok, info = crlf_ok(...)` 解包 → ValueError，看起来像
#   「CRLF 不一致」。判据函数被更换返回形态时，调用点必须同步。
c = crlf_ok(sys.argv[1])
print("CRLF:", {k: c[k] for k in sorted(c)})
sys.exit(0 if c["ok"] else 1)
EOF
if [ $? -ne 0 ]; then RC=1; echo "❌ CRLF 不一致"; fi

echo
echo "【4】无删除代码行（纯删除块口径）+ 机制未被移除（AST 符号）"
"$PY" - "$SRC" <<'EOF'
import sys
from pathlib import Path
sys.path.insert(0, ".")
from _v122_verify import (count_del_lines, count_replaced_lines,
                          mechanism_removed, function_shrunk)
base, src = "_baseline_v12177.py", sys.argv[1]
nd = count_del_lines(base, src)
nr = count_replaced_lines(base, src)
gone = mechanism_removed(base, src)
sh = function_shrunk(base, src)
print(f"纯删除行 = {nd}（期望 0）；改写行 = {nr}（如实报，不计删）")
print(f"符号消失 = {len(gone)} 项 {gone[:4]}")
print(f"函数体骤减 = {len(sh)} 项 {sh}（须在报告里解释）")
sys.exit(0 if (nd == 0 and not gone) else 1)
EOF
if [ $? -ne 0 ]; then RC=1; echo "❌ 删除/机制移除检查未通过"; fi

echo
echo "【5】bench 全量（PROFILE=$PROFILE ROUNDS=$ROUNDS）"
echo "      ★ 任务书原始档是 balanced + 0:5,1:5,both:5,all:6；本机预算有限，"
echo "        这里按 PROFILE/ROUNDS 降档跑，index.json 会记下覆盖值。"
echo "        原始档已在阶段 1 的 3 题真跑（bench/runs/p1v2）上验过。"
if [ -f bench/runs/v122_full/index.json ]; then
  echo "      · 已有 bench/runs/v122_full 的结果，**复用不再跑**（避免重复花钱）"
  echo "        要强制重跑：先删掉 bench/runs/v122_full/"
else
  "$PY" bench/bench_run.py --src "$SRC" --jobs 3 \
    --profile "$PROFILE" --rounds "$ROUNDS" --tag v122_full
  BR=$?
  echo "bench_run EXIT=$BR"
  if [ $BR -ne 0 ]; then RC=1; echo "❌ bench 全量未通过"; fi
fi
LATEST="bench/runs/v122_full"
mkdir -p bench/reports
"$PY" bench/bench_report.py "$LATEST" > bench/reports/v122_full.md
echo "report -> bench/reports/v122_full.md（$(wc -l < bench/reports/v122_full.md) 行）"

echo
echo "════════════════════════════════════════"
if [ $RC -eq 0 ]; then
  echo "✅ 全部验收通过"
else
  echo "❌ 有验收项未通过"
fi
echo "════════════════════════════════════════"
exit $RC
