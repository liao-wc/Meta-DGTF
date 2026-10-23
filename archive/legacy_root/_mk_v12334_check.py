# -*- coding: utf-8 -*-
"""v1.23.34 判据：提示词优化（有据 / 智者语气 / 输出结构）。

## 判据设计要点（★ 本版是「改措辞」的一版 ⇒ 判据必须**两向**）
  ① **新规范真的接上了**：三个共通常量存在 + 接线到六处视角 / ing；
  ② **老红线一条都没被削弱**（这是「不改变原有语义和行为」的**可执行化**）：
     输出格式契约 / `ANTI_PRETTY` / 「不煽情、不客服」/ `===ING-STRUCT===` /
     mock 分流依赖的「阴视角 · 阳视角 · 结构化尾块」字样。
  ★ 只有 ① 的判据挡不住「为了加新规范而删掉老约束」——所以 ② 与 ① 同等重要。

## 为什么单独一个函数
  判据读的是**源码文本**（提示词就在源码里）⇒ 零成本、可逐条对账。
  「本层速览」的**真实入口**断言（跑一次 `_render`）放在 ㉟ 段**共用**同一个
  mock run ⇒ 不重复起引擎（本项目对冒烟时长敏感）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "smoke_test.py"

NEW_FN = '''def check_v12334_prompt():
    """[v1.23.34] 提示词优化：有据 / 智者语气 / 输出结构（**改措辞不改机制**）。

    两向判据（见本函数上头补丁脚本的说明）：
      ① 新规范接上了；② 老红线一条没少。
    ★ 「本层速览」的真实入口断言不在这里 —— 它与 ㉟ 共用同一个 mock run
      （在 `check_v12333_autotune` 里断言），避免重复起引擎。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")

    # ── ① 三个共通常量：各 1 定义 ──
    for _c in ("VOICE", "EVIDENCE", "EXPLORE_FORMAT"):
        if ("%s = " % _c) not in src and ('%s = (' % _c) not in src:
            bad.append("[提示词] 共通常量 `%s` 未定义" % _c)

    # ── ①b 接线到六处视角 + ing ──
    _n_v = src.count("+ VOICE")
    _n_e = src.count("+ EVIDENCE")
    if _n_v < 7:
        bad.append("[提示词] `VOICE` 只接上 %d 处（六处视角 + ing = 7）" % _n_v)
    if _n_e < 7:
        bad.append("[提示词] `EVIDENCE` 只接上 %d 处（六处视角 + ing = 7）" % _n_e)
    if src.count("+ EXPLORE_FORMAT") < 6:
        bad.append("[提示词] `EXPLORE_FORMAT` 未在六处视角接上（实得 %d）"
                   % src.count("+ EXPLORE_FORMAT"))

    # ── ② 输出格式契约**不变**（红线：不改行为）──
    _i = src.find("EXPLORE_FORMAT = (")
    if _i < 0:
        bad.append("[提示词] 找不到 `EXPLORE_FORMAT` 定义体")
    else:
        _ef = src[_i:_i + 800]
        for _need in ("- [kind] 描述", "concept/event/person/object",
                      "startpoint/question/thread/other", "（无）"):
            if _need not in _ef:
                bad.append("[提示词] `EXPLORE_FORMAT` 丢了格式契约片段：%r" % _need)

    # ── ③ 反廉价感**未被削弱** ──
    if src.count("+ ANTI_PRETTY") < 6:
        bad.append("[提示词] `ANTI_PRETTY` 接线变少（不许削弱反漂亮约束）")
    if "不煽情，不客服" not in src:
        bad.append("[提示词] 「不煽情、不客服」被删（不许削弱）")

    # ── ④ 证据引用：**内容级**允许、**管道级**禁止 ──
    _j = src.find("EVIDENCE = ")
    if _j < 0:
        bad.append("[提示词] 找不到 `EVIDENCE` 定义体")
    else:
        _ev = src[_j:_j + 1600]
        if "落到内容" not in _ev:
            bad.append("[提示词] `EVIDENCE` 没写「引用要落到内容」")
        _missing = [t for t in ("资料里说", "检索显示", "上下文提到")
                    if t not in _ev]
        if _missing:
            bad.append("[提示词] `EVIDENCE` 的管道级**禁止清单**不全（缺 %r）"
                       % (_missing,))
        if "本来就知道" not in _ev:
            bad.append("[提示词] `EVIDENCE` 没写「把资料当成本来就知道的事」")

    # ── ⑤ mock 分流依赖的字样必须保留 ──
    for _t in ("阴视角", "阳视角", "结构化尾块"):
        if src.count(_t) < 2:
            bad.append("[提示词] 「%s」字样变少（冒烟 mock 靠它分流）" % _t)

    # ── ⑥ ing 输出结构 + 机器契约 ──
    if "六步各起一行" not in src:
        bad.append("[提示词] ing 未要求「六步各起一行」（输出结构没优化）")
    if "===ING-STRUCT===" not in src or "ing_structured" not in src:
        bad.append("[提示词] ing 结构化尾块契约被动了（机器解析依赖它）")

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.34 提示词优化（VOICE/EVIDENCE/EXPLORE_FORMAT 三常量接线 · "
          "格式契约未动 · 反漂亮未削弱 · 内容级引用/管道级禁止 · "
          "ing 输出结构 · mock 分流字样保留）全过")
    return True


def check_v12333_autotune():'''

ANCHOR_CALL = '''    if not check_v12333_autotune():
        return 1'''
NEW_CALL = '''    if not check_v12333_autotune():
        return 1
    if not check_v12334_prompt():
        return 1'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "smoke_test.py 应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    n = s.count("def check_v12333_autotune():")
    assert n == 1, "插入锚点命中 %d 次（应为 1）" % n
    s = s.replace("def check_v12333_autotune():", NEW_FN, 1)
    n2 = s.count(ANCHOR_CALL)
    assert n2 == 1, "调用锚点命中 %d 次（应为 1）" % n2
    s = s.replace(ANCHOR_CALL, NEW_CALL, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 判据 check_v12334_prompt 已加；smoke_test.py 行数 %d"
          % out.count(b"\n"))


main()
