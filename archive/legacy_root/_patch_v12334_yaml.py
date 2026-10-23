# -*- coding: utf-8 -*-
"""v1.23.34：同步 `dgtf_config.yaml`（头部版本 + 升级段）。

★ 为什么必须：审计判据 **C3「yaml 头部版本 == `__version__`」** ——
  建新版后不同步 yaml 头部，整套冒烟会在审计那一步**直接中断**（EXIT=1）。
★ 本次**不新增任何配置键**（纯提示词与输出结构）⇒ 只改头部 + 加升级段，
  `DEFAULT_CONFIG` 与出厂键值一律不动（零行为差）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "dgtf_config.yaml"

OLD_HEAD = "# 元 DGTF · v1.23.33 配置文件"
NEW_HEAD = "# 元 DGTF · v1.23.34 配置文件"

ANCHOR_SEG = "# 【v1.23.32 → v1.23.33】机制级吸收"
NEW_SEG = '''# 【v1.23.33 → v1.23.34】提示词优化：有据 + 智者语气 + 输出结构
#   ★ 本次**不新增任何配置键**（纯提示词与输出结构）⇒ 出厂默认行为不变。
#   ① **共通表达规范**（新增两个模块级常量）：
#      · `VOICE` —— 说话的方式（讲人话 / 有分寸 / 短而准；和蔼不是讨好）。
#      · `EVIDENCE` —— 有据：只允许**内容级**引用（是哪一条、哪个判断），
#        禁止**管道级**暴露（"资料里说" "检索显示" "上下文提到"）。
#        依据「第四面墙」问题：模型受 RLHF 影响会主动交代来源，把系统管道
#        讲给读者听，须**显式禁止**（光有正面要求不够）。
#   ② **六处视角提示词的格式契约抽成 `EXPLORE_FORMAT`**：原先六份**逐字重复**
#      ⇒ 抽成一处，以后一处改、六处全生效。**数值契约不变**（8 条上限 / 20-80 字）。
#   ③ **`ing`（对撞）**：六步改成「各起一行、先结论后依据」；接上 `VOICE` +
#      `EVIDENCE`；明确「篇幅按需」。★ `===ING-STRUCT===` 结构化尾块**未动**
#      （那是机器解析契约，`view.ing_structured` 依赖它）。
#   ④ **保留**原有的「不煽情、不客服」与 `ANTI_PRETTY`（反廉价感）——
#      本次是**追加**规范，不是替换。输出格式契约 `- [kind] 描述` 也未动。
#   ★ 本轮**未改动**任何判定条件 / 通道 / 四态 / 停止判据（红线：改措辞不改机制）。

# 【v1.23.32 → v1.23.33】机制级吸收'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "yaml 应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new in ((OLD_HEAD, NEW_HEAD), (ANCHOR_SEG, NEW_SEG)):
        assert s.count(old) == 1, "锚点命中 %d 次：%r" % (s.count(old), old[:30])
        s = s.replace(old, new, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK yaml 已同步；行数 %d" % out.count(b"\n"))


main()
