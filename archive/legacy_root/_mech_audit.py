# -*- coding: utf-8 -*-
"""
机制审计：把所有真跑日志扫一遍，把「覆盖面」变成可量化的数字。

用法：python -u _mech_audit.py [日志glob，默认 v60_*.log]

看两件事：
  1. 覆盖面 —— 哪些模式/题型跑过、哪些没有
  2. 机制触发 —— 哪些机制真跑里动过、哪些写了但从没触发（0 次）
"""
import re
import sys
import glob
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATTERN = sys.argv[1] if len(sys.argv) > 1 else "v60_*.log"

# 机制 → 日志里对应的措辞（多个关键词取并集）
MECHANISMS = [
    # ★ 只认 koan 真正进入的那行。「koan」本身会匹配到 tag 名（koan1/
    #   koan2/m61koan），那是假计数。
    ("koan 进入", ["进入 koan 整体不可判定分解"]),
    ("reclass 成立", ["可判定性转移成立", "转移成立"]),
    ("reclass 驳回", ["可判定性转移驳回", "转移驳回"]),
    ("复债(重新挂账)", ["重新挂账"]),
    # ★ 只认「迁向不可判定」。早先用「升级」当关键词，命中一堆无关
    #   文本（256 次），那是假计数 —— 审计自己不能制造噪声。
    ("escalation", ["迁向不可判定"]),
    ("预算用尽", ["预算用尽"]),
    ("延迟债务挂账", ["⏳ 债务", "延迟债务"]),
    ("悬置 active", ["主动悬置"]),
    ("撤回悬置", ["撤回的悬置"]),
    ("探针回归", ["探针回归"]),
    ("未深入推迟", ["未深入方向"]),
]

# 判据字段（能自动查的那两条）
CRITERIA = [
    ("分叉", r"分叉=(\S+)"),
    ("无追溯", r"无追溯=(\d+)"),
]


def scan(path: Path) -> dict:
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"file": path.name, "error": str(e)}

    d = {"file": path.name, "error": ""}

    # 文件名：v60_<tag>_r<rounds>_<mode>.log（宽松：末段当模式）
    m = re.match(r"v60_(.+)\.log$", path.name)
    d["tag"] = "?"
    d["r_tag"] = "?"
    d["mode"] = "?"
    if m:
        parts = m.group(1).split("_")
        d["mode"] = parts[-1] if parts else "?"
        if len(parts) >= 3:
            d["r_tag"] = parts[-2]
            d["tag"] = "_".join(parts[:-2])
        else:
            d["tag"] = m.group(1)

    # 判据
    for name, pat in CRITERIA:
        mm = re.search(pat, txt)
        d[name] = mm.group(1) if mm else "-"

    # 判定值：日志里写的是「池判：✓ 以可判定为主」这类标签，映射回来
    _LABEL2STATE = {"以可判定为主": "decidable",
                    "双通道并行": "partial",
                    "以不可判定为主": "undecidable"}
    mm = re.search(r"池判：\s*[^ ]*\s*([^ \n]+)", txt)
    d["判定"] = "-"
    if mm:
        _lab = mm.group(1)
        for k, v in _LABEL2STATE.items():
            if k in _lab:
                d["判定"] = v
                break

    # 机制计数
    for name, keys in MECHANISMS:
        d[name] = sum(txt.count(k) for k in keys)

    # 停止理由里有没有"体力耗尽"（被截断而非自然停止）
    d["体力耗尽"] = txt.count("体力耗尽")
    d["缺层"] = len(re.findall(r"❌ 缺层", txt))
    return d


def main():
    files = sorted(HERE.glob(PATTERN))
    if not files:
        print(f"没有匹配 {PATTERN} 的日志")
        return
    rows = [scan(f) for f in files]

    print(f"=== 机制审计：{len(rows)} 份日志 ===\n")

    # ---- 1. 逐 run ----
    hdr = f"{'tag':<12}{'mode':<7}{'r':<6}{'判定':<12}{'分叉':<10}{'无追溯':<7}{'体力耗尽':<9}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        if r.get("error"):
            print(f"{r['file']}: 读不了（{r['error']}）")
            continue
        print(f"{r['tag']:<12}{r['mode']:<7}{r['r_tag']:<6}"
              f"{r['判定']:<12}{r['分叉'][:9]:<10}{r['无追溯']:<7}"
              f"{r['体力耗尽']:<9}")

    # ---- 2. 机制触发汇总 ----
    print("\n=== 机制触发次数（跨全部 run 求和）===")
    for name, _ in MECHANISMS:
        total = sum(r.get(name, 0) for r in rows)
        n_runs = sum(1 for r in rows if r.get(name, 0) > 0)
        flag = "  ← ★ 从未触发" if total == 0 else ""
        print(f"  {name:<18} 共 {total:>4} 次（{n_runs}/{len(rows)} 个 run）{flag}")

    # ---- 3. 覆盖面 ----
    print("\n=== 覆盖面 ===")
    modes = {}
    for r in rows:
        modes[r["mode"]] = modes.get(r["mode"], 0) + 1
    all_modes = ["serial", "A", "B", "C", "D", "E", "F", "G", "H", "auto"]
    print("  模式：" + "  ".join(
        f"{m}={modes.get(m, 0)}" for m in all_modes if modes.get(m, 0)))
    missing_modes = [m for m in all_modes if m != "auto" and not modes.get(m)]
    if missing_modes:
        print(f"  ★ 没跑过的模式：{', '.join(missing_modes)}")
    else:
        print("  ✓ 全部 9 种模式都跑过")

    # ---- 4. 判据健康度 ----
    print("\n=== 判据健康度 ===")
    div = [r for r in rows if str(r.get("分叉", "")).startswith("True")]
    unt = [r for r in rows if str(r.get("无追溯", "")).isdigit()
           and int(r["无追溯"]) > 0]
    trunc = [r for r in rows if r.get("体力耗尽", 0) > 0]
    print(f"  判定分叉：{len(div)}/{len(rows)} 个 run")
    print(f"  有不可判定无追溯：{len(unt)}/{len(rows)} 个 run")
    print(f"  体力耗尽被截断：{len(trunc)}/{len(rows)} 个 run"
          + ("（" + ", ".join(r["tag"] for r in trunc) + "）" if trunc else ""))


if __name__ == "__main__":
    main()
