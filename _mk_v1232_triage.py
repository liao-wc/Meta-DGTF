# -*- coding: utf-8 -*-
"""[v1.23.2 · 判据形态修正] 把 triage 的组装逻辑抽成**纯函数**，并改判据形态。

发现：`P2.4.a`（「≥1 题 triage ≥ 1 条」）在**同配置**两次批次上给出 [1,0,0] 与
[0,…] —— 它是对**低概率随机机制**做 n=3 采样。这样的「能力存在性」判据
本质是掷硬币，不是判据。

正解（两步）：
1. **抽纯函数** `_triage_suggestions(und_aspects, anchors, cfg)`：把「哪些侧面该
   建议降级」这段从 `_anchor_crosscheck` 里抽出来（行为一字不改，只搬位置）。
2. **判据改成构造性证明**：喂已知合格的输入 ⇒ 断言必出 ≥1 条；再配 3 条负对照
   （真·自指 / 非候选 / tier 超门）；真跑采样读数降为**观察项**打印。

★ 通则：**「能力存在性」用构造性证明，「效果大小」才用采样。**
"""
import ast
from pathlib import Path

P = Path("元DGTF-V1.23.2.py")
src = P.read_bytes().decode("utf-8")
assert src.count("\r\n") == src.count("\n")
s = src.replace("\r\n", "\n")

if "_triage_suggestions" in s:
    print("已有 _triage_suggestions，跳过")
    raise SystemExit(0)

# ---------------- 1 新增纯函数（放在 _is_never_downgrade 之后）----------------
ANCH = '''def _is_never_downgrade(aspect: str) -> bool:
    """这些是 v1.21.59 定义的真正「原则判不出」：锚点无关，不许降级。"""
    s = str(aspect or "")
    return any(k in s for k in _TRIAGE_NEVER_DOWNGRADE)'''
NEW = ANCH + '''


def _triage_suggestions(und_aspects, anchors, cfg) -> List[dict]:
    """[v1.23.2] 分诊降级的**建议清单**（纯函数，无副作用、不调 LLM）。

    从 `_anchor_crosscheck` 里**原样抽出**（行为一字不改，只搬位置）。

    【为什么抽成纯函数】它是「能力存在性」的**判定核心**，而原先只能通过
      **真跑采样**间接观察 ⇒ 判据写成 n=3 的采样比较，本质是掷硬币
      （实测同配置两次批次：[1,0,0] 与 [0,…]）。抽出来之后可以
      **构造性证明**：喂已知合格的输入，断言必产 ≥1 条；再配负对照。

    【条件】该侧面 ① 非「真·自指」（`_is_never_downgrade`）、
      ② 属「缺外部材料」那类（`_is_triage_candidate`）、
      ③ 被一条 **tier ≤ floor** 的锚点命中（`answers` 或 `claim` 双路径取 OR）。
    ★ 只出**建议**，不改任何判定 —— 无证据的自动降档正是要避免的事。
    """
    out: List[dict] = []
    _floor = _tier_floor(cfg)
    for _a in (und_aspects or []):
        if _is_never_downgrade(_a):
            continue
        if not _is_triage_candidate(_a):
            continue
        _hit = next((x for x in (anchors or [])
                     if int(x.get("tier", 3) or 3) <= _floor
                     and (_hit_by_answers(str(_a), x.get("answers") or [])
                          or _hit_by_claim(str(_a),
                                           str(x.get("claim", ""))))),
                    None)
        if _hit:
            out.append({"from": "undecidable", "to": "partial",
                        "aspect": str(_a)[:80],
                        "anchor_id": _hit.get("id")})
    return out'''
assert s.count(ANCH) == 1, "锚点命中 %d 次" % s.count(ANCH)
s = s.replace(ANCH, NEW)

# ---------------- 2 _anchor_crosscheck 改为调用纯函数 ----------------
OLD = '''        _tg: List[dict] = []
        _und_aspects = ((self.decidability_result or {}).get(
            "undecidable_aspects") or [])
        for _a in _und_aspects:
            # [v1.22.1 P2] 先剔「真·自指」那类（锚点无关，不许降级），
            #   再判是否属于「缺外部材料」（结构标签 或 语义关键词）。
            if _is_never_downgrade(_a):
                continue
            if not _is_triage_candidate(_a):
                continue
            # [v1.22.1 P2b] 双路径取 OR：answers（锚点自声明能回答什么）
            #   或 claim（老路径，阈值 0.6 一字不动）。两路都在 **tier 门之内**。
            _hit = next((x for x in (self._anchors or [])
                         if int(x.get("tier", 3) or 3) <= _floor_c
                         and (_hit_by_answers(str(_a), x.get("answers") or [])
                              or _hit_by_claim(str(_a),
                                               str(x.get("claim", ""))))),
                        None)
            if _hit:
                _tg.append({"from": "undecidable", "to": "partial",
                            "aspect": str(_a)[:80],
                            "anchor_id": _hit.get("id")})'''
NEW2 = '''        # [v1.23.2] 组装逻辑抽成纯函数 `_triage_suggestions`（行为一字不改）——
        #   这样「能力存在性」可以用**构造性证明**验，不必靠真跑采样
        #   （triage 是低概率机制，n=3 的采样判据本质是掷硬币）。
        _und_aspects = ((self.decidability_result or {}).get(
            "undecidable_aspects") or [])
        _tg: List[dict] = _triage_suggestions(
            _und_aspects, self._anchors, {"tier_floor": _floor_c})'''
assert s.count(OLD) == 1, "组装块锚点命中 %d 次" % s.count(OLD)
s = s.replace(OLD, NEW2)

ast.parse(s)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
P.write_bytes(out)
print("已抽纯函数 `_triage_suggestions` 并接入 `_anchor_crosscheck`")
