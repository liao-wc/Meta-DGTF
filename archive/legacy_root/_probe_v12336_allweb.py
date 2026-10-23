#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：**联网全接 + 所有层注入 + 配置可控** —— 四件事一起验。

## 为什么改成「直接驱动 `_web_augment`」
第一版跑了一次 mock run 去观测 —— 但冒烟的 `fake_call` **已经把
`LLM.call` 整体替换**了 ⇒ `_web_augment` **根本不会被执行** ⇒ 观测恒为空
（表现为「接线不可达」的假象）。
★ 教训：**要在「被测逻辑真正执行的那一层」观测** —— 整体替换外层包装
  等于把被测对象一起换掉了（本轮第二次栽在这个形态上）。

## 验四件事
 ① 未接线（没有 `web_searcher`）⇒ 不增强；
 ② 总闸关 ⇒ 不增强（零行为差）；
 ③ 总闸开 + **该环节**授权 ⇒ 增强，且注入了「外部参考」段；
 ④ **所有层都注入**（用户口径）：entry 0/1/both/all 四个值下**都能**增强；
 ⑤ Gate 真判：未授权的环节 ⇒ Gate 拒 ⇒ 不增强（配置可控的本体）。
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = "ing"


def main():
    spec = importlib.util.spec_from_file_location("smoke_aw2", HERE / "smoke_test.py")
    st = importlib.util.module_from_spec(spec)
    sys.modules["smoke_aw2"] = st
    spec.loader.exec_module(st)
    mod = st.mod

    bad = []

    def _mk(enabled: bool, stage_on: bool, wire: bool, entry: str):
        cfg = {k: (dict(v) if isinstance(v, dict) else v)
               for k, v in mod.DEFAULT_CONFIG.items()}
        ws = dict(cfg.get("web_search") or {})
        ws["enabled"] = enabled
        _stg = dict(ws.get("stages") or {})
        _stg[STAGE] = stage_on
        ws["stages"] = _stg
        cfg["web_search"] = ws
        gate, _client = mod.build_web_search(cfg)
        calls = []

        def _searcher(stage, queries, round_no, used_as="evidence", pre_seq=0):
            ok, why = gate.allow(stage, round_no)      # ★ 真 Gate
            calls.append((str(stage), bool(ok), str(why)[:24]))
            return [{"claim": "外部参考样例：术语 X 通常指……",
                     "url": "https://example.invalid/x", "tier": 3}] if ok else []
        if wire:
            mod._llm_ctx_set(web_searcher=_searcher, question="术语与判据该怎么做？",
                             entry=entry, round=1)
        else:
            mod._llm_ctx_set(web_searcher=None, question="术语与判据该怎么做？",
                             entry=entry, round=1)
        llm = mod.LLM(cfg)
        out = llm._web_augment(STAGE, "原 user")
        return out, calls

    # ① 未接线
    o1, c1 = _mk(True, True, False, "1")
    print("【未接线】augment = %r" % (bool(o1),))
    if o1:
        bad.append("没接线却增强了")

    # ② 总闸关
    o2, c2 = _mk(False, True, True, "1")
    print("【总闸关】augment = %r；Gate 调用 %r" % (bool(o2), c2))
    if o2:
        bad.append("总闸关却增强了")

    # ③ 开 + 授权 ⇒ 增强
    o3, c3 = _mk(True, True, True, "1")
    _has = bool(o3) and ("【外部参考】" in str(o3))
    print("【开+授权】augment = %r；含「外部参考」= %r；Gate %r"
          % (bool(o3), _has, c3))
    if not _has:
        bad.append("开+授权却**没增强**（接线不可达）")

    # ④ **所有层都注入**（entry 0/1/both/all）
    print("【所有层都注入】逐层验：")
    for _e in ("0", "1", "both", "all"):
        _o, _c = _mk(True, True, True, _e)
        _ok = bool(_o) and ("【外部参考】" in str(_o))
        print("   entry=%-5s 增强=%r" % (_e, _ok))
        if not _ok:
            bad.append("entry=%s **没有增强**（用户口径：所有层都注入）" % _e)

    # ⑤ 未授权 ⇒ Gate 拒 ⇒ 不增强
    o5, c5 = _mk(True, False, True, "1")
    print("【开但未授权】augment = %r；Gate %r（应含「未授权」）" % (bool(o5), c5))
    if o5:
        bad.append("未授权却增强了（配置不精确）")
    if not any("未授权" in x[2] for x in c5):
        bad.append("Gate 没给出「未授权」的拒因（不可追溯）：%r" % (c5,))

    if not bad:
        print("\n[OK] 未接线不增强 / 总闸关不增强 / 开+授权即增强 / "
              "**四层全可注入** / 未授权被 Gate 拒（可控 + 可追溯）")
    else:
        print("\n[FAIL] " + "；".join(bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
