# -*- coding: utf-8 -*-
"""v1.23.36 判据：**联网全接 + 所有层注入 + 配置可控**。

## 判据分两层
  · **源码级**：接线存在、环节表完整、控制面有真实调用点；
  · **构造性**（真实入口，**零 API 花费**）：直接驱动 `LLM._web_augment`，
    验「未接线不增强 / 总闸关不增强 / 开+授权即增强 / **四层全可注入** /
    未授权被 Gate 拒且有拒因」。
    ★ 不跑 mock run —— 因为冒烟的 `fake_call` 会把 `LLM.call` 整体替换，
      `_web_augment` 就**不会被执行**（本轮栽过这个观测层错误）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "smoke_test.py"

NEW_FN = '''def check_v12336_allweb():
    """[v1.23.36] 联网全接：一处改覆盖 30 个环节 + 所有层注入 + 配置可控。

    ★ 用户口径：「**联网全接配置可控开关**」「**所有层都注入**」。
    ★ 为什么判据要分两层：源码级只能证明「接线写了」；**构造性**那一层
      直接驱动真实方法，才能证明「打开就真注入、关了就真不注入」。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")

    # ── ① 源码级：五个部件都要在 ──
    for _t, _what in (("_LLM_CTX", "线程局部上下文"),
                      ("_llm_ctx_set", "上下文写入"),
                      ("_llm_ctx_get", "上下文读取"),
                      ("_infer_stage_from_stack", "环节名推断"),
                      ("_web_augment", "增强层")):
        if _t not in src:
            bad.append("[全接] 缺 %s（%s）" % (_t, _what))
    if "self._web_augment(stage, user)" not in src:
        bad.append("[全接] `LLM.call` 里**没有**调 `_web_augment`（层没接上）")
    if "web_searcher=self._web_search" not in src:
        bad.append("[全接] `MetaDGTF.run` **没注入** `web_searcher`（依赖没接上）")
    if "_llm_ctx_set(entry=str(entry), round=int(layer_no or 0))" not in src:
        bad.append("[全接] `_before_round` 没逐圈刷新 entry/round")
    # 控制面必须有**真实调用点**（审计 A2 抓过「定义后零引用」）
    if src.count("self._control.write(") < 2:
        bad.append("[全接] `ControlSurface` 接线不足（应 ≥2 处写入）")

    # ── ② 环节表与配置键 ──
    _stages = getattr(mod, "_WEB_ALL_STAGES", None) or ()
    if len(_stages) != 30:
        bad.append("[全接] `_WEB_ALL_STAGES` 应为 30 项（实得 %d）" % len(_stages))
    _cfg_st = ((mod.DEFAULT_CONFIG.get("web_search") or {}).get("stages") or {})
    _missing = [k for k in _stages if k not in _cfg_st]
    if _missing:
        bad.append("[全接] 配置里缺环节开关：%r" % (_missing[:5],))
    if any(_cfg_st.get(k) is not False for k in _stages):
        bad.append("[全接] 新增环节开关**不是默认 false**（会改默认行为）")
    # ★ 防「插错位置」：那些环节名**不许**污染 `api.thinking.stages`
    _th = ((mod.DEFAULT_CONFIG.get("api") or {}).get("thinking") or {}).get(
        "stages") or {}
    _pollute = [k for k in _stages if k in _th]
    if len(_pollute) > 8:
        bad.append("[全接] 疑似把开关插进了 `api.thinking.stages`（会强制关思考）："
                   "%r…共 %d 个" % (_pollute[:5], len(_pollute)))

    # ── ③ 构造性：直接驱动真实方法（零 API 花费）──
    _ST = "ing"

    def _mk(enabled, stage_on, wire, entry):
        cfg = {k: (dict(v) if isinstance(v, dict) else v)
               for k, v in mod.DEFAULT_CONFIG.items()}
        ws = dict(cfg.get("web_search") or {})
        ws["enabled"] = enabled
        _s = dict(ws.get("stages") or {})
        _s[_ST] = stage_on
        ws["stages"] = _s
        cfg["web_search"] = ws
        gate, _cl = mod.build_web_search(cfg)
        calls = []

        def _searcher(stage, queries, round_no, used_as="evidence", pre_seq=0):
            ok, why = gate.allow(stage, round_no)      # ★ 真 Gate
            calls.append((str(stage), bool(ok), str(why)[:24]))
            return [{"claim": "样例外部参考", "url": "https://x.invalid",
                     "tier": 3}] if ok else []
        mod._llm_ctx_set(web_searcher=(_searcher if wire else None),
                         question="术语与判据该怎么做？", entry=entry, round=1)
        return mod.LLM(cfg)._web_augment(_ST, "原 user"), calls

    try:
        _o, _ = _mk(True, True, False, "1")
        if _o:
            bad.append("[全接] 未接线却增强了")
        _o, _c = _mk(False, True, True, "1")
        if _o:
            bad.append("[全接] 总闸关却增强了")
        elif not any("未启用" in x[2] for x in _c):
            bad.append("[全接] 总闸关时 Gate 没给出拒因（不可追溯）")
        _o, _ = _mk(True, True, True, "1")
        if not (_o and "【外部参考】" in str(_o)):
            bad.append("[全接] 开+授权却**没增强**（接线不可达）")
        for _e in ("0", "1", "both", "all"):
            _o, _ = _mk(True, True, True, _e)
            if not (_o and "【外部参考】" in str(_o)):
                bad.append("[全接] entry=%s **没有增强**"
                           "（用户口径：所有层都注入）" % _e)
        _o, _c = _mk(True, False, True, "1")
        if _o:
            bad.append("[全接] 未授权却增强了（开关不精确）")
        elif not any("未授权" in x[2] for x in _c):
            bad.append("[全接] 未授权时 Gate 没给拒因")
    except Exception as _e:
        bad.append("[全接] 构造性验证抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.36 联网全接（30 环节一键覆盖 · 上下文注入 · "
          "四层全可注 · 开关精确 · 拒因可追溯 · 控制面已接线）全过")
    return True


def check_v12334_prompt():'''

ANCHOR_CALL = '''    if not check_v12334_prompt():
        return 1'''
NEW_CALL = '''    if not check_v12334_prompt():
        return 1
    if not check_v12336_allweb():
        return 1'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "smoke_test.py 应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    n = s.count("def check_v12334_prompt():")
    assert n == 1, "插入锚点命中 %d 次" % n
    s = s.replace("def check_v12334_prompt():", NEW_FN, 1)
    n2 = s.count(ANCHOR_CALL)
    assert n2 == 1, "调用锚点命中 %d 次" % n2
    s = s.replace(ANCHOR_CALL, NEW_CALL, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 联网全接判据已加；smoke_test.py 行数 %d" % out.count(b"\n"))


main()
