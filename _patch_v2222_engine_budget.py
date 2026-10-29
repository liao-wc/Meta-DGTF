# -*- coding: utf-8 -*-
"""[V2.2.22] 引擎：预算配置 CLI 暴露（--max-minutes / --max-tokens），打通动态最优配置输入。"""
import py_compile
from pathlib import Path

ENG = Path("dgtf_engine/dgtf_v2/engine")
SRC = ENG / "Meta-DGTF-V2.2.21.py"
DST = ENG / "Meta-DGTF-V2.2.22.py"
raw = SRC.read_bytes()
assert raw[:3] != b"\xef\xbb\xbf" and raw.count(b"\n") == raw.count(b"\r\n")
t = raw.decode("utf-8").replace("\r\n", "\n")


def rep(a, b):
    global t
    c = t.count(a)
    assert c == 1, "锚点命中 %d 次: %r" % (c, a[:60])
    t = t.replace(a, b)


rep("Meta-DGTF-道生三阶模型 · V2.2.21\n", "Meta-DGTF-道生三阶模型 · V2.2.22\n")
rep('__version__ = "2.2.21"', '__version__ = "2.2.22"')
rep("★ V2.2.21 补丁（道生模式与标准模式融合 · 引擎侧零行为差）：",
"""★ V2.2.22 补丁（动态最优配置全流程可达）：
      · 新增 --max-minutes / --max-tokens：把 run() 早已支持的墙钟/令牌预算
        从 CLI/App 真正接通（此前 main 从不传 ⇒ 运行期墙钟降档路径不可达）；
      · 预算到达时 dynamic_adjust 在层/波边界自动降档 fast（质量下限允许时），
        与显式圈数锁定语义一致（rounds_locked 场景不改圈）；
      · 默认不给 => 0 => 与 V2.2.21 行为逐字相同。

★ V2.2.21 补丁（道生模式与标准模式融合 · 引擎侧零行为差）：""")

# 1) CLI：预算参数（放在 --local-llm-url 之后、--quiet 之前）
rep('''    parser.add_argument("--local-llm-url", default=None,
                        help="local 档本地模型端点（默认 output.local_llm.url）")
''',
'''    parser.add_argument("--local-llm-url", default=None,
                        help="local 档本地模型端点（默认 output.local_llm.url）")
    # ★ [V2.2.22] 预算配置全流程可达：run() 早已支持，此前 main 不传 ⇒ 死路径。
    parser.add_argument("--max-minutes", type=float, default=0.0,
                        help="墙钟预算（分钟）；到点优雅停/层间动态降档 fast，0=不限")
    parser.add_argument("--max-tokens", type=int, default=0,
                        help="令牌预算（0=不限；层间动态降档 fast，质量下限允许时）")
''')

# 2) run 调用：把预算传进去
rep('''    result = meta.run(question, route=route, keep=keep,
                      rounds=args.rounds or _dispatch.get("rounds") or 0,
                      channels=channels, parallel_mode=_pm,
                      orientation=args.orientation, auto_plan=_dispatch,
                      run_id=_run_id)''',
'''    result = meta.run(question, route=route, keep=keep,
                      rounds=args.rounds or _dispatch.get("rounds") or 0,
                      channels=channels, parallel_mode=_pm,
                      orientation=args.orientation, auto_plan=_dispatch,
                      run_id=_run_id,
                      # ★ [V2.2.22] 预算接通：墙钟/令牌两种预算都能驱动运行期动态降档
                      max_minutes=float(getattr(args, "max_minutes", 0) or 0),
                      max_tokens=float(getattr(args, "max_tokens", 0) or 0))''')

out = t.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)
chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(DST), doraise=True)
print("OK", DST.name, len(chk))

# 3) App engine_runner：透传两个预算参数（能力门控）
P = Path("dgtf_app/engine_runner.py")
s = P.read_text(encoding="utf-8")
old = '''    # ★ [V2.2.19] 输入驱动自动模式（引擎 V2.2.19+ 才有；能力门控见 _GATED_FLAGS）
    "mode": "--mode",
}'''
new = '''    # ★ [V2.2.19] 输入驱动自动模式（引擎 V2.2.19+ 才有；能力门控见 _GATED_FLAGS）
    "mode": "--mode",
    # ★ [V2.2.22] 预算配置全流程：墙钟/令牌预算从 App 任务 opts 直达引擎 run()
    "max_minutes": "--max-minutes",
    "max_tokens": "--max-tokens",
}'''
assert s.count(old) == 1
s = s.replace(old, new)
old2 = '''    # ★ [V2.2.19] 自动模式选择（旧引擎无此 flag => 门控自动不透传）
    "auto_mode": "--mode",
}'''
new2 = '''    # ★ [V2.2.19] 自动模式选择（旧引擎无此 flag => 门控自动不透传）
    "auto_mode": "--mode",
    # ★ [V2.2.22] 预算 CLI（旧引擎无此 flag => 门控自动不透传）
    "budget_cli": "--max-minutes",
}'''
assert s.count(old2) == 1
s = s.replace(old2, new2)
old3 = '''_GATED_FLAGS = {"--history-fusion", "--self-check-mode", "--dual-judge-mode",
                "--mode"}'''
new3 = '''_GATED_FLAGS = {"--history-fusion", "--self-check-mode", "--dual-judge-mode",
                "--mode", "--max-minutes", "--max-tokens"}'''
assert s.count(old3) == 1
s = s.replace(old3, new3)
P.write_text(s, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK engine_runner budget flags")
