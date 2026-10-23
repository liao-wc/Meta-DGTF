#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dgtf_app 侧变异体验证（v1.23.33 起）——给新增的两条 app 判据背书。

## 为什么要有
本项目的红线：**审计必须自带变异体**（没变异体的「全绿」只说明没跑）。
引擎侧有 `_mut_v12332.py`；**app 侧一直没有** ⇒ 新增的 app 判据没人背书。

## 用法（需先起服务，mock 零花费）
```
cd dgtf_app
CODEBUDDY_SAFE_DELETE_ENABLED=0 python server.py --port 8765 &
python ../_mut_app_v12333.py
```
★ 变异体**必须跑完不许 kill**（`finally` 只在正常退出执行，被 kill 会把源码
  留在变异态）。本脚本用 try/finally 恢复，并在结尾**逐项核对源码已还原**。

## 覆盖的判据（M-A1 / M-A2）
  A1 mock 的量化格式与真引擎对齐（两向对账 · 防漂移）
  A2 参数标签统一成「键（中文说明）」
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE / "dgtf_app"
SELFTEST = APP / "selftest.py"
PY = sys.executable

#: (编号, 说明, 目标文件, 旧串, 新串)
MUTS = [
    ("A1", "mock 的【各环节量化】段被改名（真引擎与 mock 漂移）",
     APP / "mock_engine.py", "【各环节量化】", "【XX】"),
    ("A2", "`merge_expand` 的中文标签被清掉（标签退化成裸键）",
     APP / "params.py",
     '"actions.merge_expand": "阴阳合并成一次调用（省 token）",',
     '"actions.merge_expand": "",'),
]


def run_selftest() -> tuple[int, str]:
    p = subprocess.run([PY, str(SELFTEST)], cwd=str(APP),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    only = set(sys.argv[1:]) or {m[0] for m in MUTS}
    rc, out = run_selftest()
    if "FAIL 0" not in out:
        print("X 干净基线不绿：")
        for ln in out.splitlines():
            if "✗" in ln or "失败项" in ln:
                print("   " + ln)
        return 2
    print("OK 干净基线判绿")

    n_red = 0
    for tag, why, path, old, new in MUTS:
        if tag not in only:
            continue
        raw = path.read_bytes()
        s = raw.decode("utf-8")
        if s.count(old) < 1:
            print("X %s 锚点命中 0（变异体失效）" % tag)
            continue
        try:
            path.write_bytes(s.replace(old, new).encode("utf-8"))
            _, out2 = run_selftest()
            red = "FAIL 0" not in out2
            if red:
                n_red += 1
                print("OK M-%s %s 红(判别力OK)" % (tag, why))
            else:
                print("X M-%s %s **未判红**（判据没牙）" % (tag, why))
        finally:
            path.write_bytes(raw)          # ★ 必须还原（含异常路径）
    # ── 还原核对（逐项，不靠记忆）──
    bad = []
    for tag, _, path, old, new in MUTS:
        if tag not in only:
            continue
        s = path.read_text(encoding="utf-8")
        if old not in s or new in s:
            bad.append(tag)
    if bad:
        print("X 源码未正确还原：%r —— 必须手工核查！" % (bad,))
        return 3
    print("\n=== app 变异体汇总：%d 判红 / %d 总数（源码已逐项核对还原）==="
          % (n_red, len(only)))
    return 0 if n_red == len(only) else 1


if __name__ == "__main__":
    sys.exit(main())
