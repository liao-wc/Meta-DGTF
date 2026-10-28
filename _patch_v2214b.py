# -*- coding: utf-8 -*-
"""V2.2.14b 补丁：auto_dispatch 的本地端点感知降档。

实测根因链（2026-10-28，shim 请求转储 _diag_shim_dump.jsonl 定位）：
  auto 模式调度对事实型问题判定 web=true / thinking=on / effort=high
  （对云端强模型合理）⇒ 本地 0.5B 上：
    1. thinking=on ⇒ _apply_runtime 整表 stages 改 enabled
       ⇒ LLM.call 走推理模型语义「不发 temperature」⇒ shim temp=0.0
       ⇒ 确定性复读（gen=224 全是同一短语）⇒ JSON 必截断；
    2. web=true ⇒ 工具预检把检索材料（网页教案 W8/W10/W12/W13，
       最多 2500 字）插进 self 通道 ⇒ system 被污染
       ⇒ temp 0 下小模型整段照抄 system 尾部文本。
  ⇒ re_anchor 解析失败 ⇒ touched/untouched 恒空 ⇒ aspect_units
  永不登记 ⇒ 修行层目标读数「零存量（未测出）」。

修法：auto_dispatch 纯函数里加 `_is_local_llm_endpoint(cfg)` 检查
（api.base_url 指向 127.0.0.1/localhost）；命中时**仅对 auto 来源**的
web/thinking/effort 决策降档（web→False、thinking→"off"、effort→None）。
explicit / config 来源是人定的，不碰。留痕 source="local-downgrade"
+ 原因，产物 _auto_dispatch 里可见。_apply_auto_dispatch 的 _is_mine
相应认这个来源（否则降档决策没人写进配置）。
"""
import py_compile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENG = HERE / "dgtf_engine" / "dgtf_v2" / "engine" / "Meta-DGTF-V2.2.14.py"

raw = ENG.read_bytes()
n_lf, n_crlf = raw.count(b"\n"), raw.count(b"\r\n")
assert n_lf == n_crlf, f"不是纯 CRLF: LF={n_lf} CRLF={n_crlf}"
text = raw.decode("utf-8").replace("\r\n", "\n")

REPL = []

# ── 1. _is_local_llm_endpoint 帮助函数（插在 auto_dispatch 之前）─────
REPL.append((
    'def auto_dispatch(question: str, config=None, explicit=None,\n'
    '                  save_dir=None, history=None) -> dict:',
    'def _is_local_llm_endpoint(cfg) -> bool:\n'
    '    """api.base_url 指向本机 ⇒ 本地小模型链路（shim/本地服务）。\n'
    '\n'
    '    ★ 只认地址，不认模型名：模型名随部署变（local / qwen-local / …），\n'
    '      而「跑在用户自己机器上」这件事由地址唯一决定。\n'
    '    """\n'
    '    try:\n'
    '        _u = str(((cfg or {}).get("api") or {}).get("base_url") or "")\n'
    '    except Exception:  # noqa: BLE001\n'
    '        return False\n'
    '    _host = (_u.split("//", 1)[-1].split("/", 1)[0]\n'
    '             .split(":", 1)[0].strip("[]").lower())\n'
    '    return _host in ("127.0.0.1", "localhost", "::1")\n'
    '\n'
    '\n'
    'def auto_dispatch(question: str, config=None, explicit=None,\n'
    '                  save_dir=None, history=None) -> dict:',
))

# ── 2. 降档夹断（插在 return plan 之前）──────────────────
REPL.append((
    '        plan[name] = v\n'
    '        plan["_items"][name] = {"value": v, "source": src,\n'
    '                                "reason": why, "auto_value": val}\n'
    '    return plan',
    '        plan[name] = v\n'
    '        plan["_items"][name] = {"value": v, "source": src,\n'
    '                                "reason": why, "auto_value": val}\n'
    '\n'
    '    # ★ [V2.2.14 · 本地端点感知] auto 决策的 web/thinking/effort 对\n'
    '    #   本地小模型是灾难链（实测）：thinking=on ⇒ 整表 stages 改\n'
    '    #   enabled ⇒ 推理模型语义「不发 temperature」⇒ temp 0 确定性\n'
    '    #   复读；web=on ⇒ 工具预检把检索材料灌进 self 通道 ⇒ system\n'
    '    #   被污染 ⇒ 小模型整段照抄。⇒ 仅对 **auto 来源**的决策降档\n'
    '    #   （explicit / config 是人定的，不碰）；留痕让产物可见。\n'
    '    if _is_local_llm_endpoint(cfg):\n'
    '        for _n, _clamp in (("web", False), ("thinking", "off"),\n'
    '                            ("effort", None)):\n'
    '            _it = (plan.get("_items") or {}).get(_n) or {}\n'
    '            if _it.get("source") == "auto":\n'
    '                plan[_n] = _clamp\n'
    '                plan["_items"][_n] = {\n'
    '                    "value": _clamp, "source": "local-downgrade",\n'
    '                    "reason": "本地端点：auto 的 %s 决策降档"\n'
    '                              "（原 auto 判定：%s）"\n'
    '                              % (_n, _it.get("reason") or "?"),\n'
    '                    "auto_value": _it.get("auto_value"),\n'
    '                }\n'
    '    return plan',
))

# ── 3. _apply_auto_dispatch 认 local-downgrade 来源 ──────────
REPL.append((
    '    def _is_mine(name):\n'
    '        return (items.get(name) or {}).get("source") in ("auto", "explicit")',
    '    def _is_mine(name):\n'
    '        # ★ [V2.2.14] local-downgrade = auto 决策的本地端点降档\n'
    '        #   （auto_dispatch 里夹断产生），同样要写进配置才生效。\n'
    '        return (items.get(name) or {}).get("source") in (\n'
    '            "auto", "explicit", "local-downgrade")',
))

for i, (old, new) in enumerate(REPL, 1):
    n = text.count(old)
    assert n == 1, "锚点 %d 命中 %d 次（应为 1）" % (i, n)
    text = text.replace(old, new)

out = text.replace("\n", "\r\n").encode("utf-8")
ENG.write_bytes(out)
chk = ENG.read_bytes()
assert chk.count(b"\r\r\n") == 0
assert chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(ENG), doraise=True)
print("OK: V2.2.14b 本地端点降档已写入（%d bytes, CRLF=%d）"
      % (len(chk), chk.count(b"\r\n")))
