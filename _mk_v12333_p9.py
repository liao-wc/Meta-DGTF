#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.33 补丁 P9：**一键全开**（`all_on`）。

用户口径：「设置一个全开键」「默认每次真跑全开，除非针对性验收」。

设计（不动既有纪律）：
  · 引擎侧 `DEFAULT_CONFIG["all_on"] = False` —— **保守默认**，
    所有判据/冒烟走的是它 ⇒ **基线零影响**。
  · 出厂 `dgtf_config.yaml` 写 `all_on: true` —— 本机真跑**默认全开**。
  · 生效点选在 `load_config` 的**最外层**（与既有 `_apply_runtime` 同层）——
    那是四个 return 出口的唯一汇合处，插在中间会「某些路径不生效」。
  · **必须留痕**：把每一项 `旧值 → 新值` 打成一行（与 `_apply_runtime` 的 notes 同格式）。
"""
from pathlib import Path
import ast

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

HOOK = '''#: [一键全开] 生效清单：`(配置路径, 全开值, 为什么)`。
#: ★ 只列**可切换的能力开关**；不含 route/rounds 这类运行参数（那是跑次的事）。
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
)


def _apply_all_on(cfg: dict):
    """[一键全开] `all_on: true` ⇒ 把 `_ALL_ON_ITEMS` 全部置开，并返回留痕。

    ★ 与 `_apply_runtime` 同层（`load_config` 最外层）—— 那是四个 return 出口的
      唯一汇合处；插在函数体中间会「某些路径不生效」，且没有判据看得见。
    ★ `all_on` 为假 ⇒ **恒等变换**（返回原 cfg、零 notes）⇒ 判据基线零影响。
    ★ 显式优先级：`all_on` 语义就是「全开」，因此它**覆盖**这些键的出厂值；
      要针对某一项做对照实验就**关掉 all_on**（而不是指望单项覆盖赢）。
    """
    if not (cfg or {}).get("all_on"):
        return cfg, []
    notes = []
    for path, val, why in _ALL_ON_ITEMS:
        d = cfg
        ks = str(path).split(".")
        for k in ks[:-1]:
            if not isinstance(d.get(k), dict):
                d[k] = {}
            d = d[k]
        old = d.get(ks[-1], "<缺>")
        if old != val:
            d[ks[-1]] = val
            notes.append("[all_on] %s：%r → %r（%s）" % (path, old, val, why))
    return cfg, notes


'''

NEW_LOAD = '''    cfg, notes = _apply_runtime(_load_config_raw(path))
    cfg, _ao_notes = _apply_all_on(cfg)
    notes = list(notes) + list(_ao_notes)
    for n in notes:
        print("   · " + n)
    return cfg'''


def main():
    b = SRC.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n") and b.count(b"\r\r\n") == 0
    s = b.decode("utf-8").replace("\r\n", "\n")

    # ① 插入 _ALL_ON_ITEMS + _apply_all_on（放在 load_config 之前）
    anchor = "def load_config(path: str) -> dict:"
    assert s.count(anchor) == 1
    s = s.replace(anchor, HOOK + anchor, 1)

    # ② load_config 里接上（替换其函数体最后三行）
    old_body = '''    cfg, notes = _apply_runtime(_load_config_raw(path))
    for n in notes:
        print("   · " + n)
    return cfg'''
    assert s.count(old_body) == 1, s.count(old_body)
    s = s.replace(old_body, NEW_LOAD, 1)

    # ③ DEFAULT_CONFIG 加 all_on（保守默认 false）
    old_cfg = '''    "playbook": {'''
    new_cfg = '''    # ★ [一键全开] 出厂**引擎侧默认 false**（保守）：所有判据/冒烟走它 ⇒
    #   基线零影响。出厂 `dgtf_config.yaml` 写 `true` ⇒ **本机真跑默认全开**。
    #   生效清单见 `_ALL_ON_ITEMS`（EML on / anytime 停止 / bandit / 语义归并 /
    #   相对阈值 / 联网 / 锚点 gate / 思考 high + effort high）。
    "all_on": False,

    "playbook": {'''
    assert s.count(old_cfg) == 1
    s = s.replace(old_cfg, new_cfg, 1)

    ast.parse(s)
    SRC.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
    s2 = SRC.read_bytes().decode("utf-8")
    assert "def _apply_all_on(cfg: dict):" in s2
    assert "_ALL_ON_ITEMS" in s2 and '"all_on": False' in s2
    assert s2.count("\r\r\n") == 0
    print("OK P9：一键全开（all_on）已接入 load_config 最外层 + DEFAULT_CONFIG 保守默认")

    # ④ 出厂 yaml 默认全开
    p = HERE / "dgtf_config.yaml"
    yb = p.read_bytes()
    is_crlf = yb.count(b"\r\n") == yb.count(b"\n") and yb.count(b"\r\n") > 0
    y = yb.decode("utf-8").replace("\r\n", "\n")
    if "\nall_on:" not in y:
        y = y.replace("# ============================================================\n"
                      "# 统一自适应调度器（v1.23.13）",
                      """# ★★ 【一键全开】all_on: true ⇒ 本机真跑**默认全开**（用户口径：
#     「默认每次真跑全开，除非针对性验收」）。它会在 `load_config` 最外层
#     把下列开关一起置开并**逐项留痕**（打印 `[all_on] 键：旧 → 新（为什么）`）：
#       auto.enabled / playbook.mode=on / stop.anytime_alpha=0.05 /
#       auto.bandit.enabled / belief.merge_semantic / belief.sem_entropy_thr=rel /
#       web_search.enabled / external_anchor.as_evidence=gate /
#       api.thinking.default=enabled / api.thinking.effort=high
#     ★ 要做**针对性验收**（单项对照）就把 all_on 关掉（false），
#       否则单项设置会被它覆盖 —— 这是「全开」的语义，不是 bug。
#     ★ 引擎侧 `DEFAULT_CONFIG["all_on"]` 仍是 false（保守默认）：
#       判据/冒烟走引擎默认 ⇒ 基线不受影响。
all_on: true

# ============================================================
# 统一自适应调度器（v1.23.13）""", 1)
    p.write_bytes((y.replace("\n", "\r\n") if is_crlf else y).encode("utf-8"))
    print("OK P9：出厂 yaml 已写 all_on: true")


if __name__ == "__main__":
    main()
