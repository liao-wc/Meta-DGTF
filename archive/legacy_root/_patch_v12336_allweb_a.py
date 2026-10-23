# -*- coding: utf-8 -*-
"""「联网全接」A：在 `LLM.call` 加统一增强层（一处改 ⇒ 30 个环节全部可联网）。

## 为什么是这里
用户口径：「**联网全接配置可控开关**」——每个层每圈每个环节都能按需联网，
且**由配置开关控制**。

30 个环节各改一遍 prompt 既慢又散（且**必然漏**）；而它们**都经过**
`LLM.call` ⇒ 在那一处加一层，**一处改、全部生效**，且每环节一个配置键。

## 设计（三个干净的点）
  ① **依赖注入**：`LLM` 是**模块级类**，拿不到 `DGTF`/`MetaDGTF` 的
     `_web_search` ⇒ 由调用方通过 **thread-local context** 注入
     `web_searcher` 回调。`LLM` 不需要知道联网实现在哪。
  ② **stage 推断**：没显式传 `stage=` 的调用点（多数）⇒ 从**调用栈**
     推断出环节函数名作 stage。⇒ 30 个环节**各自一个开关**，无需逐处改签名。
  ③ **红线**：**修行层（entry == "0"）不注入** —— 它的输入必须只有形状。
     修行层的联网由 `practice_term_calibration` 承担（只留痕、不注入）。

## 零行为差
`web_search.enabled=false`（出厂）⇒ `_web_augment` 立刻返回 None ⇒
`call()` 里 `user` 一字不变。★ 所有新增分支都在「开关打开」之后。

## 可控
所有增强都过 **Gate**（`web_search.stages.<环节名>` 授权 + 三层配额 +
连续失败降级）⇒ 就是用户要的「**配置可控开关**」。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

# ── A：模块级 context（放在 `class LLM:` 之前）──
ANCHOR_CTX = '''class LLM:
    def __init__(self, config: dict):'''
NEW_CTX = '''#: [联网全接] 当前调用的**线程局部上下文**。
#: ★ 为什么需要：`LLM` 是**模块级类**，拿不到 `DGTF` / `MetaDGTF` 的实例状态
#:   （题面 / 当前层 / 圈号 / 联网实现）；而 30 个环节都经 `LLM.call`
#:   ⇒ 用它把上下文递进去，`LLM` 只依赖这一个协议、不依赖任何具体类。
#: ★ 为什么 thread-local：并行模式下多个层**同进程多线程**跑，
#:   共享一个全局变量会串台（本项目在 `SERVED_SEEN` 上踩过跨线程的口径问题）。
_LLM_CTX = threading.local()


def _llm_ctx_set(**kw) -> None:
    """设置当前线程的调用上下文（`web_searcher` / `question` / `entry` / `round`）。"""
    for _k, _v in (kw or {}).items():
        setattr(_LLM_CTX, _k, _v)


def _llm_ctx_get(key: str, default=None):
    return getattr(_LLM_CTX, key, default)


def _infer_stage_from_stack() -> str:
    """从调用栈推断当前环节名（= `LLM.call` 最近的**非 LLM 内部**调用方的函数名）。

    ★ 为什么要推断：30 个环节里只有 11 处显式传了 `stage=` ——
      要「**每个环节一个开关**」就得知道是谁在调。逐处改签名会碰 30 个点
      （且新环节会漏），而调用栈**天然带着答案**。
    ★ 开销：`sys._getframe` 是常数级；相对一次 LLM 调用的耗时**可忽略**。
    ★ 拿不到就返回 `""`（调用方据此**不增强** —— 宁可少查，不许猜错环节）。
    """
    try:
        f = sys._getframe(1)
        while f is not None:
            _n = f.f_code.co_name
            # 跳过 LLM 自身与 `_call_long` 这类包装
            if _n not in ("call", "_call_long", "_web_augment", "<module>") \\
                    and not _n.startswith("_llm_"):
                return _n
            f = f.f_back
    except Exception:
        pass
    return ""


class LLM:
    def __init__(self, config: dict):'''

# ── B：`_web_augment` 方法（放在 `call` 之前）──
ANCHOR_M = '''    def call(self, system, user, temperature=0.6, max_tokens=3000,
             json_mode=False, model=None, thinking=None, stage=None):'''
NEW_M = '''    def _web_augment(self, stage: str, user: str) -> Optional[str]:
        """[联网全接] 给**任何环节**按需挂「外部参考」。返回增强后的 user 或 None。

        ★ 默认关：`web_search.enabled=false` ⇒ **立刻返回 None**（零行为差）。
        ★ 红线：**修行层（entry == "0"）不注入** —— 它的输入必须只有形状；
          修行层的联网走 `practice_term_calibration`（只留痕、不注入）。
        ★ 全部经 Gate：授权（`stages.<环节名>`）/ 三层配额 / 失败降级 ⇒ **可控**。
        ★ 查不到 / 没授权 / 没注入器 ⇒ 返回 None（**不许**返回空壳提示词）。
        """
        _searcher = _llm_ctx_get("web_searcher")
        if not callable(_searcher):
            return None                       # 没接线（如独立调用 LLM）⇒ 不增强
        if str(_llm_ctx_get("entry", "")) == "0":
            return None                       # ★ 红线：修行层不注入
        _st = str(stage or _infer_stage_from_stack() or "")
        if not _st:
            return None
        _q = str(_llm_ctx_get("question", "") or "").strip()
        if not _q:
            return None
        _rn = int(_llm_ctx_get("round", 0) or 0)
        _qs = ["%s %s" % (_q[:100], _st.replace("_", " ")[:60])]
        try:
            _res = _searcher(_st, _qs, _rn, "evidence")
        except Exception:
            return None
        if not _res:
            return None                       # 空结果 = 「外部确实没有」⇒ 不注入
        _lines = []
        for _it in _res[:3]:
            _c = str((_it or {}).get("claim", "") or "").strip()
            if _c:
                _lines.append("- " + _c[:300])
        if not _lines:
            return None
        return ("【外部参考】（用于本环节的判断；**当成你本来就知道的事**说，"
                "不要交代来源；与已知冲突时如实标出）\\n"
                + "\\n".join(_lines) + "\\n\\n" + str(user))

    def call(self, system, user, temperature=0.6, max_tokens=3000,
             json_mode=False, model=None, thinking=None, stage=None):'''

# ── C：`call()` 里接线（在 messages 构造**之前**）──
ANCHOR_C = '''        is_thinking = str(th or "").lower() == "enabled"
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],'''
NEW_C = '''        is_thinking = str(th or "").lower() == "enabled"
        # ★ [联网全接] 统一增强层：默认关 ⇒ 返回 None ⇒ `user` 一字不变。
        #   位置：在 messages 组装**之前**（增强的就是送出去的 user）。
        try:
            _aug = self._web_augment(stage, user)
            if _aug:
                user = _aug
        except Exception:
            pass
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new, tag in ((ANCHOR_CTX, NEW_CTX, "A context"),
                          (ANCHOR_M, NEW_M, "B _web_augment"),
                          (ANCHOR_C, NEW_C, "C call 接线")):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（应为 1）" % (tag, n)
        s = s.replace(old, new, 1)
    for _t in ("_LLM_CTX", "_llm_ctx_set", "_llm_ctx_get",
               "_infer_stage_from_stack", "_web_augment"):
        assert _t in s, "缺 %s" % _t
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 联网全接 A 已加；行数 %d" % out.count(b"\n"))


main()
