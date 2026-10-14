# -*- coding: utf-8 -*-
"""v1.23.34 第一期：提示词优化 —— 共通表达规范 + 抽出六处重复的格式契约。

## 用户诉求（原文）
「在阴阳视角、展开、ing、对撞、view 等阶段，可以引用自己的产物证据或结论、
外部联网检索到的、导入的资料证据进行论述；全文内容有深度 + 让人类看得懂的
语言输出；语气像一个全知全能的智者，和蔼可亲；字数根据实际需要控制；
有理有据；**保证不改变原有语义和行为**的前提下优化现有提示词使其更精准。」

## 前沿依据（检索所得，逐条对应落地）
① ★ **第四面墙问题**（The Fourth Wall Problem, josephwp.com）：
   LLM 天然区分不了「用户给的」「系统注入的」「自己知道的」——由于 RLHF 奖励
   来源标注，它会**主动交代来源**，把系统管道暴露给读者（「从你的 recall
   snippet 看…」）。解法三件套：认识论框架 + 第四面墙规则 + **显式禁止短语**。
   ⇒ 这正是本项目「引用证据」必须走的形态：**内容级引用**（是哪一条、哪个判断）
     允许；**管道级暴露**（"资料里说" "检索显示" "上下文提到"）**禁止**。
   ⇒ 落地 `EVIDENCE` 常量。
② **换语气不改数据**（shshell.com, RAG Prompt 设计）：
   「You can change the Tone without changing the data. The Context stays the
   same; only the Template changes.」⇒ 语气优化**不触碰语义与判定条件**。
③ **人设影响准确性**（trendflash.net, 2025）：指派角色（如「谨慎细致的
   事实核查者」）能引导模型走向更保守准确的输出风格 ⇒ 智者人设服务
   「有理有据」，不是装饰。
④ **证据要求要具体**（byaiteam.com）：提示词应「Specify tasks, audiences,
   constraints, and **evidence requirements**」⇒ 把「有据」写成可执行的清单。
⑤ XML 标签帮助模型分离指令与数据（shshell.com）⇒ 沿用本项目既有的
   `【】` 分段风格，不引入新记号（避免与现有解析冲突）。

## 本轮改什么 / 不改什么
**改**：① 抽出六处**完全相同**的格式契约（消除六份内联重复 ⇒ 以后一处改全生效）；
        ② 新增 `VOICE`（智者语气）与 `EVIDENCE`（内容级引用）两个常量并接进
           六处视角 + `ing`；③ 字数由「硬区间」改述为「按需」（**数值契约不变**）。
**不改**：① 输出格式契约 `- [kind] 描述`（下游解析依赖）；② 任何判定条件、
           通道、四态、停止判据；③ **「阴视角」「阳视角」「结构化尾块」字样**
           （★ 冒烟 mock 依赖它们分流，见 `smoke_test.py` 的 `fake_call`）。

## 纪律
主文件纯 CRLF；锚点命中数**显式断言**；写完自检 CR-CR-LF 为 0。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

# ── A0：新常量（插在 ANTI_PRETTY 之后、_BOILERPLATE 之前）──
ANCHOR_A0 = '''_BOILERPLATE = ('''
NEW_A0 = '''#: [v1.23.34] 说话的方式（**共通**：六处视角 + ing + 探针都用它）。
#: ★ 依据 ②「换语气不改数据」：它只规定**怎么说**，不增加任何判定条件。
#: ★ 依据 ③「人设影响准确性」：把"见过很多、愿意讲明白"作为姿态，服务于
#:   下面的「有据」，不是装饰。
VOICE = """
【怎么说话】
- 你是一个见识够多、也愿意把话讲明白的人。把复杂的说清楚，不是把清楚的说复杂。
  和蔼不是讨好，温厚不是含糊 —— 该硬的地方照样硬。
- 讲人话：用具体的名词和动作。不用行话，不用自造词，不用听着高级但没内容的词。
- 有分寸：确定就确定，不确定就直说不确定，**并说清是哪一点不确定**。
  拿分寸感代替含糊词 —— 不许用"大概/某种意义上/一定程度上"掩盖没想清。
- 一句一个意思。短而准，好过长而飘。
"""

#: [v1.23.34] 有据（**共通**）。★ 依据 ①「第四面墙」：只允许**内容级**引用，
#: 禁止**管道级**暴露 —— 读者关心"这件事是什么"，不关心"你是从哪拿到的"。
#: ★ 依据 ④：把"有据"写成可执行清单（可引的三类来源 + 一个禁止清单）。
EVIDENCE = """
【有据：每一句论断都要落到出得上】
- 可引的据有三类：
  ① 本层自己的产物：这一圈的候选、池里的 & / 线头 / 悬置、上一圈的结论；
  ② 上游层已经说过的话（已在下面给出）；
  ③ 附带的资料：锚点文本、导入的资料、联网结果。
- 引用要**落到内容**：说清"是哪一条、哪个判断"，不要笼统说"根据资料"。
  例：说「边界不可声明这件事，& 里已经记下」而不是「资料里提到边界问题」。
- ★ 不要说"资料里说""检索显示""上下文提到""根据提供的信息"这类话 ——
  那是把自己的管道讲给读者听。把资料当成**你本来就知道的事**讲出来。
- 没有据就不要编：宁可标"（此处无据）"或用 '&' 标记撞不动，也不许拿话填。
"""

#: [v1.23.34] 六处视角**完全相同**的格式契约（抽成一处 ⇒ 以后改一次全生效）。
#: ★ 数值契约（8 条上限 / 20-80 字）**保持不变**，只把"按需"讲清楚。
EXPLORE_FORMAT = (
    "能写几条写几条（8 是上限，不是要交的作业量）。"
    "展开几条就写几条；一条都展开不出来就只输出一行：'（无）'\\n"
    "每行格式：- [kind] 描述（20-80字；说清一条算一条，"
    "不必凑到 80，也不必压到 20）\\n"
    "kind: concept/event/person/object/startpoint/question/thread/other\\n"
    "不要解释，不要标题。\\n"
)

_BOILERPLATE = ('''

# ── A1：六处视角的公共尾巴 → 抽成常量 + 接上 VOICE/EVIDENCE ──
#   ★ 这段在六处**逐字相同**（含 12 空格缩进）⇒ 用 replace 全量替换。
#   ★ 断言命中数 == 6：少一处说明有人已经改过，多一处说明我数错了 —— 都必须停。
ANCHOR_A1 = '''            "能写几条写几条（8 是上限，不是要交的作业量）。"
            "展开几条就写几条；一条都展开不出来就只输出一行：'（无）'\\n"
            "每行格式：- [kind] 描述（20-80字）\\n"
            "kind: concept/event/person/object/startpoint/question/thread/other\\n"
            "不要解释，不要标题。\\n"
            + ANTI_PRETTY'''
NEW_A1 = '''            + EXPLORE_FORMAT
            + VOICE
            + EVIDENCE
            + ANTI_PRETTY'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")

    n0 = s.count(ANCHOR_A0)
    assert n0 == 1, "A0 锚点命中 %d 次（应为 1）" % n0
    s = s.replace(ANCHOR_A0, NEW_A0, 1)

    n1 = s.count(ANCHOR_A1)
    assert n1 == 6, ("A1 锚点命中 %d 次（应为 **6** ——六处视角）"
                     "⇒ 停手核查，不许蒙着改" % n1)
    s = s.replace(ANCHOR_A1, NEW_A1)

    for _tok in ("阴视角", "阳视角"):
        assert s.count(_tok) >= 6, "「%s」字样变少（mock 分流依赖它）" % _tok
    assert "===ING-STRUCT===" in s, "ing 结构化尾块不见了"
    assert s.count("EXPLORE_FORMAT") == 7, \
        "EXPLORE_FORMAT 应为 1 定义 + 6 使用，实得 %d" % s.count("EXPLORE_FORMAT")

    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    assert out.count(b"\n") == out.count(b"\r\n")
    P.write_bytes(out)
    print("OK 第一期已应用；行数 %d" % out.count(b"\n"))


main()
