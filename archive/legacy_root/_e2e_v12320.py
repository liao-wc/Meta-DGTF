# -*- coding: utf-8 -*-
"""v1.23.20 离线 E2E：跑一层一圈（LLM 打桩，零成本），验 stdout 的行为。

诉求：运行时**只留进度**，不留「全量留痕」与「ing / view 全文框」。
用 smoke_test 的 harness（它已把 LLM 打桩），因此不花一分钱。
"""

import contextlib
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402

mod = st.mod
cfg = st.build_cfg(True)                       # verbose=True（进度本就走它）
meta = mod.MetaDGTF(cfg)
q = "测试：留痕默认关，运行时只留进度"

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    meta.run(q, route=["0"], rounds={"0": 1}, parallel_mode="serial")
out = buf.getvalue()

checks = [
    ("无『圈全量留痕』", "圈全量留痕" not in out),
    ("无『收尾留痕』", "收尾留痕" not in out),
    ("无『【ing 全文】』", "【ing 全文】" not in out),
    ("无『【view 全文】』", "【view 全文】" not in out),
    ("有进度（修行 / ━━━）", ("修行" in out) or ("\u2501" in out)),
]
bad = [n for n, ok in checks if not ok]
for n, ok in checks:
    print(("  \u2713 " if ok else "  \u2717 ") + n)
print("stdout 共 %d 字符" % len(out))
if bad:
    print("FAIL:", bad)
    for kw in ("圈全量留痕", "收尾留痕", "【ing 全文】"):
        i = out.find(kw)
        if i >= 0:
            print("  出现 %r @ %d: %r" % (kw, i, out[max(0, i - 60):i + 60]))
    sys.exit(1)
print("E2E OK")
