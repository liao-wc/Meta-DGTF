# -*- coding: utf-8 -*-
"""抓取 mock 产物基线：用于验证 P3-1 重构（抽 _finalize_layer_common）无损。

调法：python _snap_baseline.py <前置标签>
产出：_baseline/<tag>_<mode>.md（serial / B / C 三种通道各一份）
"""
import os
import sys
import io
import contextlib

import smoke_test as st

TAG = sys.argv[1] if len(sys.argv) > 1 else "before"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_baseline")
os.makedirs(OUT, exist_ok=True)

Q = "测试问题：AI 在数字 IC 设计里到底能做什么，哪些已经量产？"
ROUNDS = {"0": 3, "1": 3, "both": 3, "all": 3}


def snap(mode):
    st.CALLS["n"] = 0
    cfg = st.build_cfg(False)
    cfg["cost_profile"] = "quality"   # 基线用 quality，避免成本档干扰
    meta = st.mod.MetaDGTF(cfg)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        res = meta.run(Q, route=["0", "1", "both", "all"],
                       rounds=ROUNDS, parallel_mode=mode)
    # 用与 save_result 相同的渲染函数，但不落 outputs/
    txt = st.mod.render_markdown(res) if hasattr(st.mod, "render_markdown") \
        else None
    if txt is None:
        # 退路：直接调 save_result 再读回来
        p = st.mod.save_result(res, os.path.join(OUT, "_tmp"))
        txt = p.read_text(encoding="utf-8")
        try:
            p.unlink()
        except OSError:
            pass
    dst = os.path.join(OUT, f"{TAG}_{mode}.md")
    with open(dst, "w", encoding="utf-8", newline="") as f:
        f.write(txt)
    print(f"  {mode:6} calls={res['llm_calls']:3}  字节={len(txt.encode('utf-8')):6}  -> {dst}")


def main():
    print(f"抓基线 tag={TAG}")
    for m in ("serial", "B", "C"):
        snap(m)
    print("完成")


if __name__ == "__main__":
    sys.exit(main() or 0)
