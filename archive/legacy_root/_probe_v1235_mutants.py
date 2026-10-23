# -*- coding: utf-8 -*-
"""v1.23.5 变异体：证明 check_v1235_pending_fix 真有判别力。

「现版全绿」不构成判别力证据（结构不变式在现版必然通过）。每个畸形体
独立 module，让**原样的判据函数**去跑，**必须判红**。

M1 归一化重新内联一份  → 判据 1a/1b/1c 应红（唯一实现被破坏）
M2 布尔兼容去掉留痕    → 判据 3 应红（可观测化被破坏）
M3 两段式低置信改提前 return → 判据 1e 应红（刻意保留的差异被抹平）
M4 登记常量改回 3      → 判据 2 应红（两向对账被破坏）

用法：python _probe_v1235_mutants.py
"""
import re
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"
BASE = HERE / "元DGTF-V1.23.5.py"

MUTANTS = {}

# ---- M1：把 rounds 归一化重新内联一份进单调用分支 ----
MUTANTS["M1 归一化内联回两份"] = (
    "        rnd = _normalize_plan_rounds(data, hard)\n",
    "        rnd = {}\n"
    "        _rr = data.get('rounds') or {}\n"
    "        _ff = min(_MIN_LAYER_ROUNDS, hard)\n"
    "        if isinstance(_rr, dict):\n"
    "            for k in ('0', '1', 'both', 'all'):\n"
    "                try:\n"
    "                    iv = int(_rr.get(k))\n"
    "                except (TypeError, ValueError):\n"
    "                    continue\n"
    "                if 1 <= iv <= hard:\n"
    "                    rnd[k] = max(iv, _ff)\n"
    "        if rnd and len(rnd) < 4:\n"
    "            _vals = sorted(rnd.values())\n"
    "            _fill = _vals[len(_vals) // 2]\n"
    "            for k in ('0', '1', 'both', 'all'):\n"
    "                rnd.setdefault(k, _fill)\n"
    "        for k in list(rnd):\n"
    "            rnd[k] = min(max(rnd[k], _layer_floor(k, hard, _ff)),\n"
    "                         _layer_ceil(k, hard, _ff))\n")

# ---- M2：布尔兼容去掉留痕 ----
MUTANTS["M2 布尔兼容去留痕"] = (
    "        logger.warning(\n"
    "            \"external_anchor.as_evidence 用了 v1.21.75 的布尔写法 %r\"\n"
    "            \" → %s（请迁到五档字符串 off/record/crosscheck/evidence/gate）\",\n"
    "            raw, \"evidence\" if raw else \"off\")\n",
    "        pass\n")

# ---- M3：两段式的低置信改成提前 return 并改写 reason ----
MUTANTS["M3 抹平低置信差异"] = (
    "    conf = _plan_conf(data)\n"
    "    if mode != \"serial\" and conf < _PARALLEL_CONF_MIN:\n"
    "        mode = \"serial\"\n",
    "    conf = _plan_conf(data)\n"
    "    if mode != \"serial\" and conf < _PARALLEL_CONF_MIN:\n"
    "        return {\"route\": route, \"mode\": \"serial\", \"rounds\": rnd,\n"
    "                \"max_calls\": 0,\n"
    "                \"reason\": \"低置信(%.2f)，退回 serial\" % conf,\n"
    "                \"confidence\": conf}\n")

# ---- M4：登记常量改回 3 ----
MUTANTS["M4 登记常量改回 3"] = ("_AUDIT122_PENDING_FIX = 2",
                                "_AUDIT122_PENDING_FIX = 3")


def build_harness(target: Path):
    """读 smoke_test.py 源码、只替换 SRC 那一行，exec 成独立 module。"""
    src = SMOKE.read_text(encoding="utf-8")
    pat = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
    n = len(pat.findall(src))
    assert n == 1, "SRC 行命中 %d 次" % n
    src = pat.sub('SRC = Path(r"%s")' % str(target).replace("\\", "\\\\"), src)
    m = types.ModuleType("mut_%s" % target.stem)
    m.__file__ = str(SMOKE)
    sys.modules[m.__name__] = m
    exec(compile(src, str(SMOKE), "exec"), m.__dict__)
    return m


def main():
    smoke_src = SMOKE.read_text(encoding="utf-8")
    ok_all = True
    print("=" * 66)
    print("v1.23.5 变异体：check_v1235_pending_fix 必须对每个畸形体判红")
    print("=" * 66)

    # 正对照：干净版必须绿
    hm = build_harness(BASE)
    r = hm.check_v1235_pending_fix()
    print("\n[正对照] 干净 v1.23.5 -> %s（应为 True）" % r)
    if not r:
        ok_all = False

    tmpdir = Path(tempfile.mkdtemp(prefix="_v1235_mut_"))
    for name, (old, new) in MUTANTS.items():
        txt = BASE.read_bytes().decode("utf-8").replace("\r\n", "\n")
        n = txt.count(old)
        if n != 1:
            print("\n[%s] ★ 锚点命中 %d 次（应为 1）—— 变异体没打成" % (name, n))
            ok_all = False
            continue
        mp = tmpdir / ("mut_%s.py" % abs(hash(name)))
        mp.write_bytes(txt.replace(old, new).replace("\n", "\r\n")
                       .encode("utf-8"))
        try:
            hm2 = build_harness(mp)
            r2 = hm2.check_v1235_pending_fix()
        except Exception as e:
            r2 = "EXC:%s" % type(e).__name__
        red = (r2 is False)
        print("\n[%s] 判据返回 %r -> %s" % (name, r2,
                                            "判红 ✓" if red else "★ 没判红"))
        if not red:
            ok_all = False

    print()
    print("=" * 66)
    print("结论：%s" % ("全部变异体都被判红 —— 判据有判别力"
                        if ok_all else "★ 有变异体没被判红 —— 判据缺牙"))
    print("=" * 66)
    try:
        import shutil
        shutil.rmtree(tmpdir)
    except OSError:
        pass
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
