import py_compile
from pathlib import Path

# ── 1) service：JSON 约束的 env 开关（A/B 可隔离；默认开）──────────
P = Path("dgtf_local_llm/service.py")
text = P.read_bytes().decode("utf-8-sig")
def rep(old, new, cnt=1):
    global text
    c = text.count(old)
    assert c == cnt, "锚点命中 %d 次（应为 %d）" % (c, cnt)
    text = text.replace(old, new)

rep('        json_mode = bool(req.get("json_mode"))\n',
    '        # ★ [V2.2.16] 约束解码总开关：默认开；DGTF_JSON_CONSTRAIN=0 可关\n'
    '        #   （A/B 隔离用；关掉时行为退回 V2.2.15）。\n'
    '        json_mode = (bool(req.get("json_mode"))\n'
    '                     and _JSON_CONSTRAIN_ON)\n')
# 模块级常量：放到 import 区域之后第一个稳定锚点（STAGES = LORA_STAGES 之后）
rep('STAGES = LORA_STAGES\n',
    'STAGES = LORA_STAGES\n'
    '#: ★ [V2.2.16] JSON 约束解码总开关（默认开；A/B 可 DGTF_JSON_CONSTRAIN=0 关闭）。\n'
    '_JSON_CONSTRAIN_ON = (os.environ.get("DGTF_JSON_CONSTRAIN", "1")\n'
    '                      .strip().lower() not in ("0", "off", "false", "no"))\n')
P.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
py_compile.compile(str(P), doraise=True)
print("OK service: DGTF_JSON_CONSTRAIN 开关")

# ── 2) 引擎 V2.2.16：本地端点自动切 self_check/dual_judge local ──────
E = Path("dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.16.py")
et = E.read_bytes().decode("utf-8").replace("\r\n", "\n")
def erep(old, new):
    global et
    c = et.count(old)
    assert c == 1, "引擎锚点命中 %d 次" % c
    et = et.replace(old, new)

# 找 CLI 覆盖之后的注入点：先看现有代码形状
import re
idx = et.find('''    if getattr(args, "self_check_mode", None):''')
assert idx > 0, "未找到 self_check_mode CLI 覆盖块"
line_end = et.find("\n", et.find("print(f\"   ✓ 双判档位", idx))
print("anchor context:", repr(et[idx:idx+240]))
