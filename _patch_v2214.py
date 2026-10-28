# -*- coding: utf-8 -*-
"""V2.2.14 补丁：re_anchor few-shot（修行层读数断粮的引擎侧修法）。

实测根因（2026-10-28，本地 0.5B 直测）：
  (a) 原 prompt 下底座不出 JSON——纯文本复述 9 token 即 EOS
      => parse_json 空 dict => touched/untouched 恒空
      => aspect_units 永不登记 => 修行层 hist=[0,0] 「未测出（零存量）」。
  (b) 加示例后 schema 通了，但确定性复读（同一短语 ×N 撞 224 上限）
      => JSON 截断。复读由本地适配层的 repetition_penalty 治理
      （shim/service/gates 侧，本轮另一批改动）。
  (c) ★ 模板行与示例**不能共存**：实测共存时弱模型照抄模板占位符
      「≤80字一句话」（2/2 次），模板行必须去掉、只留示例。

本脚本只改引擎三处：docstring 版本 + 补丁说明 + __version__ +
_re_anchor 的 system prompt（few-shot 化）。纯 CRLF 往返。
"""
import py_compile
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "dgtf_engine" / "dgtf_v2" / "engine" / "Meta-DGTF-V2.2.13.py"
DST = HERE / "dgtf_engine" / "dgtf_v2" / "engine" / "Meta-DGTF-V2.2.14.py"

raw = SRC.read_bytes()
n_lf = raw.count(b"\n")
n_crlf = raw.count(b"\r\n")
assert n_lf == n_crlf, f"源文件不是纯 CRLF: LF={n_lf} CRLF={n_crlf}"
text = raw.decode("utf-8").replace("\r\n", "\n")

REPL = []

# ── 1. docstring 版本行 ─────────────────────────────
REPL.append((
    "Meta-DGTF-道生三阶模型 · V2.2.13\n",
    "Meta-DGTF-道生三阶模型 · V2.2.14\n",
))

# ── 2. 补丁说明（插在 V2.2.13 段之前）─────────────────
REPL.append((
    "★ V2.2.13 补丁（LLM 调用显式携带 stage）：",
    "★ V2.2.14 补丁（re_anchor few-shot）：本地 0.5B 底座在锚点重述\n"
    "     prompt 下 (a) 不出 JSON（纯文本复述即 EOS）⇒ touched/untouched\n"
    "     恒空 ⇒ aspect_units 永不登记 ⇒ 修行层目标读数「零存量」；\n"
    "     (b) few-shot 后 schema 通了但确定性复读撞上限 ⇒ JSON 截断\n"
    "     （复读由本地适配层 repetition_penalty 治理，见 gates.\n"
    "     BASE_STAGE_REP_PEN）。★ 模板行与示例不能共存——实测共存时\n"
    "     弱模型照抄模板占位符「≤80字一句话」⇒ 模板行去掉，只留示例。\n"
    "\n"
    "★ V2.2.13 补丁（LLM 调用显式携带 stage）：",
))

# ── 3. __version__ ──────────────────────────────────
REPL.append((
    '__version__ = "2.2.13"',
    '__version__ = "2.2.14"',
))

# ── 4. re_anchor system prompt：few-shot 化（模板行去掉）──
OLD_PROMPT = '''        system = (
            "你是【锚点重述者】。\\n"
            "把输入重述成当下要处理的那个问题/处境。\\n"
            "不改变本质，只让它成为'此刻的问题'。\\n"
            f"{self.phase.anchor}\\n"
            "【★ 重述必须带出两半】\\n"
            "  · touched：这句话里**已经被触及、已经被指向**的方面（0-4 条）\\n"
            "    —— 重述之后你重新看见的、原本就在里面的东西\\n"
            "  · untouched：这句话里**还没被触及、还没被展开**的方面（0-4 条）\\n"
            "  ★ touched 是重述真的发生了的证据。如果 touched 空着，\\n"
            "    说明这次只是在换说法，没有真的重述。\\n"
            "严格 JSON：\\n"
            '{"anchor":"≤80字一句话","touched":["≤30字"],"untouched":["≤30字"]}\\n'
            + ANTI_PRETTY
            + self._self_block()
        )'''
NEW_PROMPT = '''        system = (
            "你是【锚点重述者】。\\n"
            "把输入重述成当下要处理的那个问题/处境。\\n"
            "不改变本质，只让它成为'此刻的问题'。\\n"
            f"{self.phase.anchor}\\n"
            "重述必须带出两半：touched（这句话里已被触及的方面，0-4 条）与"
            " untouched（还没被触及/展开的方面，0-4 条）。\\n"
            "★ touched 是重述真的发生了的证据——空着说明只是换说法。\\n"
            "只输出严格 JSON，结构照下例（anchor 是对输入的改写而不是照抄；"
            "touched/untouched 各 1-4 条，每条是不同的方面，不要重复）：\\n"
            "示例1 输入：怎样提高睡眠质量\\n"
            '输出：{"anchor":"当下要处理：如何让一觉睡得真正解乏",'
            '"touched":["睡眠时长"],"untouched":["卧室环境","睡前习惯"]}\\n'
            "示例2 输入：孩子不爱吃蔬菜怎么办\\n"
            '输出：{"anchor":"当下要处理：怎样让孩子主动愿意吃蔬菜",'
            '"touched":["孩子挑食这个现象"],'
            '"untouched":["蔬菜的做法与口味","家庭的进餐氛围"]}\\n'
            + ANTI_PRETTY
            + self._self_block()
        )'''
REPL.append((OLD_PROMPT, NEW_PROMPT))

for i, (old, new) in enumerate(REPL, 1):
    n = text.count(old)
    assert n == 1, "锚点 %d 命中 %d 次（应为 1）" % (i, n)
    text = text.replace(old, new)

out = text.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)

chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0, "出现 \r\r\n 污染"
assert chk.count(b"\n") == chk.count(b"\r\n"), "不是纯 CRLF"
py_compile.compile(str(DST), doraise=True)
print("OK: V2.2.14 写入", DST.name,
      "(%d bytes, CRLF=%d)" % (len(chk), chk.count(b"\r\n")))
