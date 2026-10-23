# -*- coding: utf-8 -*-
"""补 **联网按需协议** 的判据 `check_v12336_webneed`（v1.23.37 的前置依赖）。

## 为什么需要它
`_mk_v12337_deferred.py` 把 `check_v12337_roundtick` 插在
**`def check_v12336_webneed():` 的前面**（那是它的锚点），并断言该锚点命中 1 次。
而 `smoke_test.py` 里**并没有** `check_v12336_webneed` ⇒ 锚点命中 0 ⇒ 断言失败。
⇒ 本脚本先把它补上（编号留 v12336：它判的是 V1.23.36 引入/37 落地的**按需协议**，
   用 36 编号可与既有 4 条 v12336 判据并列，deferred 的锚点也正好接得上）。

## 判据设计（两层，遵循本项目的「源码级 ≠ 可达」铁律）
① **源码级**：`_WEB_NEED_MARK` / `parse_web_need` / `_web_need_report` 三件齐；
   `LLM.call` 里**有**调用点（否则「定义了没人用」）。
② **构造性**（零 API 花费）：
   - `parse_web_need` 纯函数：JSON 形态 / 逐行形态 / 无声明 / 畸形 / 截量 五种；
     ★ 逐行分支必须**收单字查询**（探针抓到的真缺口：曾用 `len(_l) > 2` 滤掉「丙」）。
   - `LLM._web_need_report`：真驱动 —— 喂一段带声明的产出，看
     `web_searcher` 是否**真被调用** + 返回条数对不对 + 无声明时**零调用**（负对照）。

## 门与幂等
不带门（这是**补判据**，不涉及权限）；重复执行会因「已存在」而跳过。
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"

#: 判据函数体。★ 注意收尾：它以 `def check_v12334_prompt():` 收束 ——
#:   即插在 `check_v12334_prompt` **之前**，不破坏原文件那一行的存在性。
SM_FN = '''def check_v12336_webneed():
    """[v1.23.36→37] 联网**按需协议**：环节自己声明「我需要外部事实」。

    ★ 与「统一增强层」(`_web_augment`) 的分工：
      增强层 = 引擎在调用**前**猜需不需要；按需 = 环节在产出**后**自己说。
    ★ 两层判据（本项目铁律：源码级只能证明「接线写了」）：
      ① 三件齐 + `LLM.call` 里有调用点；
      ② 构造性驱动 —— 真跑 `_web_need_report`，看消费方**真被调用**。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")

    # ── ① 源码级 ──
    if "_WEB_NEED_MARK" not in src:
        bad.append("[按需] 缺声明标记 `_WEB_NEED_MARK`")
    if "def parse_web_need(" not in src:
        bad.append("[按需] 缺解析器 `parse_web_need`")
    if "def _web_need_report(" not in src:
        bad.append("[按需] 缺消费方 `_web_need_report`")
    if "self._web_need_report(stage, content)" not in src:
        bad.append("[按需] `LLM.call` 里**没有**调用点（定义了没人用）")
    #   ★ 防「同一语义两处定义」：解析器应当只有一处实现
    if len(re.findall(r"^def parse_web_need\\(", src, re.M)) != 1:
        bad.append("[按需] `parse_web_need` 定义了不止一次（两处定义必分叉）")

    # ── ② 构造性：纯函数 ──
    _fn = getattr(mod, "parse_web_need", None)
    if not callable(_fn):
        bad.append("[按需] 模块里取不到 `parse_web_need`（不可达）")
    else:
        _M = getattr(mod, "_WEB_NEED_MARK", "===WEB-NEED===")
        _q = chr(34)                      # ★ 用 chr(34) 规避转义地狱（本项目纪律）
        # ① JSON 形态
        _a = _fn("前言\\n%s\\n{%squeries%s: [%s甲%s, %s乙%s]}\\n后语"
                 % (_M, _q, _q, _q, _q, _q, _q))
        if _a != ["甲", "乙"]:
            bad.append("[按需] JSON 形态解析错：%r" % (_a,))
        # ② 逐行形态（不标准格式）
        _b = _fn("前言\\n%s\\n甲\\n乙\\n丙\\n" % _M)
        #   ★ 单字「丙」**必须保留**（曾用长度阈值把它滤掉 ⇒ 真缺口）
        if "甲" not in _b or "丙" not in _b:
            bad.append("[按需] 逐行形态丢了查询（含单字）：%r" % (_b,))
        # ③ 无声明 ⇒ []
        if _fn("没有任何声明的产出") != []:
            bad.append("[按需] 无声明竟解析出东西（会凭空检索）")
        # ④ 畸形 ⇒ 不抛错、当没声明
        try:
            _fn("%s\\n{坏 JSON" % _M)
            _fn(None)
            _fn(12345)
        except Exception as _e:
            bad.append("[按需] 畸形输入抛错（不该影响主流程）：%r" % (_e,))
        # ⑤ 截量：limit 生效
        _many = "%s\\n" % _M + "\\n".join("q%d" % i for i in range(20))
        if len(_fn(_many, limit=3)) > 3:
            bad.append("[按需] `limit` 没生效（一个环节能吃光配额）")

    # ── ③ 构造性：真消费方（`_web_need_report`）──
    try:
        cfg = build_cfg(False)
        llm = mod.LLM(cfg)
        _calls = []
        _q = chr(34)

        def _searcher(stage, queries, round_no, used_as="evidence", pre_seq=0):
            _calls.append((str(stage), list(queries), str(used_as)))
            return [{"claim": "样例外部参考", "url": "https://x.invalid",
                     "tier": 3}]

        _M = getattr(mod, "_WEB_NEED_MARK", "===WEB-NEED===")
        # 有声明 ⇒ 消费方真被调用 + 返回条数
        mod._llm_ctx_set(web_searcher=_searcher, round=2)
        _body = ("产出正文\\n" + _M + "\\n") + ("{%squeries%s: [%sX%s]}"
                                            % (_q, _q, _q, _q))
        _n = llm._web_need_report("ing", _body)
        if not _calls:
            bad.append("[按需] 有声明却**没调**消费者（接线不可达）")
        elif _n < 1:
            bad.append("[按需] 有声明、消费者也调了，却没算进条数：%r" % (_n,))
        # 负对照：无声明 ⇒ 零调用
        _calls.clear()
        _n0 = llm._web_need_report("ing", "一段没有声明的普通产出")
        if _calls or _n0 != 0:
            bad.append("[按需] 无声明却动了（应零成本零调用）：%r/%r"
                       % (_calls, _n0))
        # 负对照：没注入 web_searcher ⇒ 不该炸、返回 0
        mod._llm_ctx_set(web_searcher=None, round=2)
        _n1 = llm._web_need_report(
            "ing", ("产出\\n" + _M + "\\n") + ("{%squeries%s: [%sY%s]}"
                                            % (_q, _q, _q, _q)))
        if _n1 != 0:
            bad.append("[按需] 无注入器却返回非 0：%r" % (_n1,))
    except Exception as _e:
        bad.append("[按需] 构造性验证抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.36 联网按需协议（三件齐 · 调用点真接 · JSON/逐行/畸形容错 · "
          "单字不丢 · 截量生效 · 声明真驱动消费者 · 无声明零调用）全过")
    return True


def check_v12334_prompt():'''


def main():
    s = SM.read_text(encoding="utf-8")
    if "def check_v12336_webneed(" in s:
        print("check_v12336_webneed 已存在（跳过）")
    else:
        _anchor = "def check_v12334_prompt():"
        assert s.count(_anchor) == 1, "插入锚点 %d 次" % s.count(_anchor)
        s = s.replace(_anchor, SM_FN, 1)
        print("OK check_v12336_webneed 函数体已插入")

    # 调用：加在 `check_v12336_eml()` 之后（保持 v12336 系列聚在一起）
    _call_anchor = ("    if not check_v12336_eml():\n"
                    "        return 1\n")
    if "if not check_v12336_webneed():" in s:
        print("调用已存在（跳过）")
    else:
        assert s.count(_call_anchor) == 1, "调用锚点 %d 次" % s.count(_call_anchor)
        s = s.replace(_call_anchor,
                      _call_anchor + "    if not check_v12336_webneed():\n"
                      "        return 1\n", 1)
        print("OK 调用已加")
    SM.write_text(s, encoding="utf-8")


main()
