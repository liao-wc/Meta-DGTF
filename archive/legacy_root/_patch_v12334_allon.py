# -*- coding: utf-8 -*-
"""v1.23.34：`_ALL_ON_ITEMS` 补 `actions.merge_expand`（降本能力必须能被全开验到）。

## 逮到的问题（用户口径逼出来的）
用户要求：「所有最终真跑验收默认都是配置开关全开」。
真跑日志特征扫描发现 **`merge_expand` 出现 0 次** ⇒ 全开清单里**没有它**
⇒ 本次全开真跑**验不到**阴阳合并这条降本能力 —— 而它正是上一轮引入的改动。
**「有开关却永远不被全开验到」= 这类能力在验收里是隐形的。**

## 修法
① 清单加一项 `("actions.merge_expand", True, "阴阳合并成一次调用（省 token）")`；
② ★ 把**收录标准**与**故意不收录的项及原因**写成注释 —— 让「不在清单里」
   也是**显式的决定**，而不是「忘了加」（本项目最怕的就是「没登记＝静默」）。

## 判据影响
冒烟 `check_v1234`（或 v1234 全开判据）是**遍历** `_ALL_ON_ITEMS` 的
（`for _p, _v, _w in mod._ALL_ON_ITEMS`），**不硬编码项数** ⇒ 加项不破判据。
`_v122_verify.py` 的 V3 白名单已改为**动态导出** ⇒ 自动跟上。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

OLD = '''_ALL_ON_ITEMS = (
    ("auto.enabled", True, "自适应调度总开关"),
    ("playbook.mode", "on", "EML 经验记忆生效（跨跑学习闭环）"),
    ("stop.anytime_alpha", 0.05, "anytime-valid 停止判据生效（δ=0.05）"),
    ("auto.bandit.enabled", True, "预算 bandit 生效（探索必留痕）"),
    ("belief.merge_semantic", True, "语义归并生效（换说法记为复现）"),
    ("belief.sem_entropy_thr", "rel", "语义熵改用本批相对分位"),
    ("web_search.enabled", True, "联网检索"),
    ("external_anchor.as_evidence", "gate", "锚点作 gate 证据"),
    ("api.thinking.default", "enabled", "思考档默认开"),
    ("api.thinking.effort", "high", "思考强度 high"),
)'''

NEW = '''#: [一键全开] 清单 —— **真跑验收默认全开**（用户口径）。
#: ★ **收录标准**（三项全满足才收）：
#:   ① 它影响**引擎能力**（跑法 / 判据 / 成本），不是纯显示开关；
#:   ② 全开**不破坏**产物（不会把产物刷成不可读）；
#:   ③ 全开能**验到**某轮改动的效果（否则那轮改动在验收里是隐形的）。
#: ★ **故意不收**（留在清单外，各有原因）：
#:   · `output.show_ing` / `output.show_manifest` —— **显示**开关：全开会把
#:     每圈全文刷进日志（②不满足），且它们与「能力是否生效」无关；
#:   · `web_search.tier_proposal` —— **提案**开关：全开会让未确认域名进待审
#:     队列，属「待人工确认」的中间态，不是「能力应当生效」；
#:   · `playbook.learn_from_anon` —— **数据卫生**开关：无 id 的跑次不应入库
#:     （测试替生产刷票，见其定义处的说明）⇒ 全开反而是错的。
#:   ★ 想加项就加在这一段里，并写清为什么满足上面三条；**加了才算被验收覆盖**。
_ALL_ON_ITEMS = (
    ("auto.enabled", True, "自适应调度总开关"),
    ("playbook.mode", "on", "EML 经验记忆生效（跨跑学习闭环）"),
    ("stop.anytime_alpha", 0.05, "anytime-valid 停止判据生效（δ=0.05）"),
    ("auto.bandit.enabled", True, "预算 bandit 生效（探索必留痕）"),
    ("belief.merge_semantic", True, "语义归并生效（换说法记为复现）"),
    ("belief.sem_entropy_thr", "rel", "语义熵改用本批相对分位"),
    ("web_search.enabled", True, "联网检索"),
    ("external_anchor.as_evidence", "gate", "锚点作 gate 证据"),
    ("api.thinking.default", "enabled", "思考档默认开"),
    ("api.thinking.effort", "high", "思考强度 high"),
    # ★ 降本能力：阴阳合并成一次调用。上一轮加的开关，原先**不在清单里**
    #   ⇒ 全开真跑验不到它（「有开关却永远不被全开验到」= 验收里的盲区）。
    ("actions.merge_expand", True, "阴阳合并成一次调用（省 token）"),
)'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    assert s.count(OLD) == 1, "锚点命中 %d 次" % s.count(OLD)
    s = s.replace(OLD, NEW, 1)
    assert s.count("merge_expand\", True") == 1
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK `_ALL_ON_ITEMS` 已加 merge_expand（+ 收录标准注释）；行数 %d"
          % out.count(b"\n"))


main()
