# -*- coding: utf-8 -*-
"""「联网全接」A2：由 `MetaDGTF` **注入**上下文（`web_searcher` + 题面 + 层/圈）。

## 为什么必须由 MetaDGTF 注入
`_web_search` 定义在 **`MetaDGTF`**（它是联网的唯一实现）；而 `DGTF`
（**每层每圈新建**的实例，环节 `_ing` / `_expand_pair` / … 都在它上面）
**没有** `_web_search`。⇒ 只能由持有者把回调**注入**进线程上下文。

## 注入点（两个，都在**统一实现**上）
  · `MetaDGTF.run` 开头：`web_searcher`（绑定方法）+ `question`（题面）—— 全程有效；
  · `_before_round`（圈前统一动作，两条通道共用）：`entry` + `round` —— 逐圈精确。

★ 为什么 `round` 要在 `_before_round` 每圈更新：`LLM.call` 的增强会把它当
  `round_no` 传给 Gate ⇒ 三层配额里的 `per_stage_round` 才真的是「每圈」。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

# ── A：`MetaDGTF.run` 里注入（锚在**唯一可判语句**上，不锚多行签名）──
#   ★ 教训：多行签名当锚点很脆（我第一版按记忆猜的签名与真实签名完全不同）；
#     锚「函数体里的一句唯一语句」既准又稳。
ANCHOR_RUN = '''        self._run_id = str(run_id or "")'''

INJECT_RUN = '''        self._run_id = str(run_id or "")
        # ★ [联网全接] 把**联网实现**与**题面**注入线程上下文：
        #   `_web_search` 定义在 MetaDGTF 上，而 30 个环节里的 `LLM.call`
        #   都拿不到它（`DGTF` 是每圈新建的实例）—— 靠这一个协议接起来。
        #   `LLM` 因此只依赖「上下文里有 web_searcher」这一个约定，
        #   不依赖任何具体类（依赖注入）。
        #   ★ 修行层的「不注入」红线在 `LLM._web_augment` 里按 entry 判。
        try:
            _llm_ctx_set(web_searcher=self._web_search,
                         question=str(question or ""))
        except Exception:
            pass'''

# ── B：`_before_round` 里逐圈更新 ──
ANCHOR_BR = '''        if entry == "0" and int(layer_no or 0) == 1:
            try:
                self._practice_term_calibration_prep()
            except Exception as _e_tc2:  # noqa: BLE001
                logger_web.warning("[W-TERM-CAL] 调用失败：%s", _e_tc2)'''

NEW_BR = '''        # ★ [联网全接] 逐圈刷新上下文：环节里任何一次 `LLM.call` 都能据此
        #   知道「现在在哪一层哪一圈」（Gate 的 per_stage_round 配额靠它）。
        try:
            _llm_ctx_set(entry=str(entry), round=int(layer_no or 0))
        except Exception:
            pass
        if entry == "0" and int(layer_no or 0) == 1:
            try:
                self._practice_term_calibration_prep()
            except Exception as _e_tc2:  # noqa: BLE001
                logger_web.warning("[W-TERM-CAL] 调用失败：%s", _e_tc2)'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")

    # A：run 里注入（锚在唯一语句上）
    n = s.count(ANCHOR_RUN)
    assert n == 1, "run 注入锚点命中 %d 次（应为 1）" % n
    s = s.replace(ANCHOR_RUN, INJECT_RUN, 1)

    # B：_before_round 逐圈刷新
    n2 = s.count(ANCHOR_BR)
    assert n2 == 1, "_before_round 锚点命中 %d 次（应为 1）" % n2
    s = s.replace(ANCHOR_BR, NEW_BR, 1)

    assert s.count("_llm_ctx_set(") >= 2, "注入点不足"
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 联网全接 A2 已加（context 注入）；行数 %d" % out.count(b"\n"))


main()
