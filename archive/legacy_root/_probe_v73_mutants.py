# -*- coding: utf-8 -*-
"""[v1.21.73 变异测试] 证明 check_v73_anchor 的六组判据**有判别力**。

为什么必须做：这些判据在 v1.21.73 上必然全绿 —— 「通过」本身不构成证据。
做法（skill 7c）：把 v1.21.73 改成 6 个畸形体，每个都是「某一处机制坏掉」
的样子，让**原样的判据函数**去跑，必须判红。哪个畸形体还能全绿，就说明
那条判据是永真的死判据。

跑法：python _probe_v73_mutants.py
"""
from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"
BASE = HERE / "元DGTF-V1.21.73.py"
TD = Path(tempfile.mkdtemp(prefix="v73mut_"))

_raw = BASE.read_bytes().decode("utf-8")
assert _raw.count("\r\n") == _raw.count("\n")
BASE_TXT = _raw.replace("\r\n", "\n")

MUTANTS = {
    "M1 删 run() 里的 _load_anchors 调用": [
        ("        self._load_anchors()\n", "")],
    "M2 _pack_result 不挂 external_anchor 键": [
        ("        if _ar is not None:\n            _pack[\"external_anchor\"] = _ar\n",
         "        if False:\n            _pack[\"external_anchor\"] = _ar\n")],
    "M3 锚点编号不校验（模型编的也算）": [
        ("            ids = [x for x in ids if x in valid]\n", "")],
    "M4 关闭时也拼锚点段（破坏加性）": [
        ("        _anchor_sys = \"\"\n", "        _anchor_sys = \"\\n【外部事实锚点】残留\"\n")],
    "M5 加载失败不留痕（静默降级）": [
        ("            self._anchor_err = (\"锚点文件读取失败：\" + type(exc).__name__\n"
         "                                + \": \" + str(exc)[:200])\n",
         "            self._anchor_err = \"\"\n")],
    "M6 对照写回池（不是只读）": [
        ("        self.vp(\"\\n⚓ 外部锚点对照：结论 \"",
         "        self.pools[\"1\"].sub_questions.append({\"question\": \"污染条目\", \"status\": \"answered\"})\n"
         "        self.vp(\"\\n⚓ 外部锚点对照：结论 \"")],
}


def build(txt: str, name: str) -> Path:
    p = TD / f"mut_{name}.py"
    p.write_bytes(txt.replace("\n", "\r\n").encode("utf-8"))
    return p


def run_check(target: Path) -> bool:
    """让**原样**的 check_v73_anchor 去跑目标引擎，返回判据结果。"""
    src = SMOKE.read_text(encoding="utf-8")
    pat = re.compile(r'SRC = HERE / "元DGTF-V1\.21\.\d+\.py"')
    assert len(pat.findall(src)) == 1
    src = pat.sub('SRC = Path(r"%s")' % str(target).replace("\\", "\\\\"), src)
    mod = types.ModuleType("mut_" + target.stem)
    mod.__file__ = str(SMOKE)
    sys.modules[mod.__name__] = mod
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(src, str(SMOKE), "exec"), mod.__dict__)
            return bool(mod.check_v73_anchor())
    except Exception as exc:
        print(f"    判据自身抛异常（也算判红）：{type(exc).__name__}: {exc}")
        return False
    finally:
        out = buf.getvalue()
        for line in out.splitlines():
            if "v73 锚点" in line or "✗" in line:
                print("    " + line.strip()[:150])


def main() -> int:
    print("=" * 60)
    print("[0] 原样 v1.21.73 —— 期望 True（全绿）")
    print("=" * 60)
    ok0 = run_check(BASE)
    print(f"    原样结果：{ok0}\n")
    if not ok0:
        print("❌ 原样都判红，先修判据再谈变异")
        return 1

    bad = []
    for i, (name, reps) in enumerate(MUTANTS.items(), 1):
        txt = BASE_TXT
        for old, new in reps:
            n = txt.count(old)
            if n != 1:
                print(f"❌ [{name}] 变异锚点命中 {n} 次（应为 1），跳过")
                bad.append(name)
                txt = None
                break
            txt = txt.replace(old, new, 1)
        if txt is None:
            continue
        p = build(txt, str(i))
        print("=" * 60)
        print(f"[{i}] {name} —— 期望 False（判据必须抓到）")
        print("=" * 60)
        got = run_check(p)
        print(f"    结果：{got}\n")
        if got:
            bad.append(f"{name}：畸形体仍全绿 ⇒ 这条判据没有判别力")
            print(f"    ❌ {name} 变异体未被抓到")
    if bad:
        print("\n❌ 有判据是永真的：")
        for b in bad:
            print("   - " + b)
        return 1
    print("\n✅ 6 个变异体全部被抓到 —— 六组判据都有判别力")
    return 0


if __name__ == "__main__":
    sys.exit(main())
