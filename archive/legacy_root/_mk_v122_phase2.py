#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段2] 打补丁：三态多票化 + 可判定性冻结 + 校准队列留痕。"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

VOTE_BLOCK = r'''

# ============================================================
# [v122 阶段2 G2.1] 三态多票判决的三套判据
# ============================================================
# 【为什么多票】单票判出来的标签**同时**是：覆盖率的分母、路由与提前停的
#   依据、终局「可判定 / 不可判定」的分区线。而实测同题四跑 ANSWERABLE 在
#   1~5 之间跳（见 `_adjudicate_sub_tristate` 的 docstring）。一次抽样的
#   标签撑不起这么多下游 —— 这里用**同一批子问题、三套不同侧重的判据**
#   各判一次，按多数票定标签。
#   ★ 三票之间**互不可见**（各自独立一次调用），不是一次调用里要三个答案：
#     后者只会得到三份高度相关的复制品，投票就没有信息量。
_TRI_VOTE_HEAD = (
    "你是【可判定性判决官】。本次是**三票独立判决**中的一票。\n"
    "\n"
    "给你若干条子问题，逐条判它：能不能被**判定**。\n"
    "\n"
    "【三态定义】\n"
    "- decidable：存在可指认的 0/1 候选答案——某个动作、条款、数值、\n"
    "  时间戳能被指认出「是或不是」。答得出也没关系，关键是**存在一个\n"
    "  能被占据的位置**。\n"
    "- undecidable：角色槽本身就是空的——定义尚未生成、角色未被指派、\n"
    "  缺共同参照系。不是「还没找到答案」，是「承载答案的位置还没长出来」。\n"
    "- partial：一部分能被指认，另一部分落在空槽里。\n"
    "\n"
    "【★ 顺序】每条先写一句 reason（为什么落在这一格），再给\n"
    "decidability。理由没写出来就判，等于猜。\n"
    "\n"
    "【本票的侧重】\n"
)

_TRI_VOTE_SLANT = (
    "偏严：只有你真的能指出那个「能被占据的位置」时才判 decidable；\n"
    "「理论上可以问」不算。判不出来就如实写 undecidable。",
    "偏保守：拿不准一律 partial。宁可承认不确定，也不要替它挑一格；\n"
    "但定义清楚、位置明显存在的，仍然要判 decidable，不要一律和稀泥。",
    "换角度：先问「承载这条答案的角色槽今天存在吗」——存在且被指派就\n"
    "decidable，槽没长出来就 undecidable，只有一半就 partial。",
)

_TRI_VOTE_JSON = (
    "\n"
    "严格 JSON：\n"
    '{"judgments":[{"id":1,"reason":"...",'
    '"decidability":"decidable|partial|undecidable"}]}'
)

_TRI_VOTE_PROMPTS = tuple(
    _TRI_VOTE_HEAD + s + _TRI_VOTE_JSON for s in _TRI_VOTE_SLANT
)


class DecidabilityFreeze:
    """[v122 阶段2 G2.3] 可判定性冻结条。

    【它解决什么】覆盖率的分母必须是**判完那一刻**的名单，而不是"此刻
    `decidability` 落在 ANSWERABLE 里的条数"。后者会被同一批内部机制一路
    改写（饿够圈数迁移、清算时迁移），于是两次跑的百分比不可比 —— 差的
    不是质量，是那一圈有没有触发迁移。

    【做法】`freeze()` 把每条子问题「判完那一刻是否可答」写成
    `_frozen_answerable` 布尔值，并对 `(id, decidability, 是否可答)` 序列
    取 sha256 当签名。签名覆盖**判定本身**，不只是分母 —— 否则
    `decidable → partial` 这种"分母没变、判定变了"的改动会**测不出来**
    （实测踩过：只签布尔时，篡改 decidable→partial 后 `verify()` 不报错）。
    理由文本不进签名：理由措辞每轮都会变，算进去会让签名每轮都不同。

    【`verify()` 为什么抛错而不是返回 False】调用点若忘了检查返回值，
    一个 False 会被静默吞掉；抛 RuntimeError 逼调用方在"冻结条已被推翻"
    这件事上显式表态（这正是 `sub["decidability"]` 被改判时的形态）。
    """

    def __init__(self) -> None:
        self.signature = ""
        self.layer = None
        self.n = 0
        self.items: List[List[object]] = []
        self.frozen_at = ""

    def _canon(self, pool) -> List[List[object]]:
        out: List[List[object]] = []
        for s in (getattr(pool, "sub_questions", None) or []):
            _lab = str(s.get("decidability", "") or "")
            out.append([str(s.get("id", "")), _lab,
                        bool(_lab in _DEC_ANSWERABLE)])
        return out

    @staticmethod
    def _digest(layer, items) -> str:
        payload = json.dumps({"layer": layer, "n": len(items),
                              "items": items},
                             ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def freeze(self, pool, layer: int = 1) -> str:
        self.layer = int(layer)
        self.items = self._canon(pool)
        self.n = len(self.items)
        for s in (getattr(pool, "sub_questions", None) or []):
            _ans = bool(s.get("decidability") in _DEC_ANSWERABLE)
            s["_frozen_answerable"] = _ans
            # 与 v1.21.62 起用的 `_decided_answerable` 同步写：
            #   coverage_parts 读的是那个键，两处必须同值，否则分母会
            #   在"新旧两个冻结口径"之间飘 —— 那是更难查的一种不可比。
            s["_decided_answerable"] = _ans
        self.frozen_at = datetime.now().isoformat()
        self.signature = self._digest(self.layer, self.items)
        return self.signature

    def verify(self, pool) -> bool:
        cur = self._canon(pool)
        if self._digest(self.layer, cur) != self.signature:
            raise RuntimeError(
                "可判定性冻结条被推翻：当前判定与冻结签名不符"
                f"（冻结 {self.n} 条 / 现在 {len(cur)} 条，"
                f"layer={self.layer}）")
        return True

    def to_dict(self) -> dict:
        return {"signature": self.signature, "layer": self.layer,
                "n": self.n, "frozen_at": self.frozen_at,
                "items": self.items}

'''

DISPATCH_BLOCK = r'''        # [v122 阶段2 G2.2] 三态多票化：开关打开时走多票；关闭时下面这段
        #   单票实现**原样保留**（v1.21.77 的行为逐字不变，是退路）。
        if _action_on(self.config, "tri_multi_vote"):
            return self._adjudicate_sub_tristate_multi(subs, question)
'''

MULTI_METHOD = r'''    # ---------- [v122 阶段2 G2.1/G2.2] 三态多票判决 ----------
    def _adjudicate_sub_tristate_multi(self, subs: List[dict],
                                       question: str) -> Tuple[int, int]:
        """三态**多票**判决（3 票，各自独立一次调用）。

        返回 `(与拆解原标签一致的条数, 有效条数)` —— 与单票实现**同签名**，
        所以两个调用点和产物的 `tri_state` 字段都不用改。多票自己的置信
        分布另存 `self._tri_consensus = (high, medium, low)`，
        逐条明细存 `self._tri_multi_items`（进 packed 的校准队列）。

        ★ 三票全失败 → 返回 (0, 0)，保留拆解原标签（与单票失败同语义）。
          这里**绝不能**回头调 `_adjudicate_sub_tristate` —— 那个方法在
          多票开启时会派发回本方法，会无限递归。
        ★ 无多数票（三票全不同）→ 落 partial，记 low，进校准队列。
          落 partial 而不是 undecidable：`_DEC_ANSWERABLE` 含 partial，
          落 undecidable 会把分母砍掉一截（这正是 v1.21.62 修过的那个形态）。
        """
        if not subs:
            return 0, 0
        lines = [f"  {i}. {str(s.get('question', ''))[:200]}"
                 for i, s in enumerate(subs, 1)]
        user = (f"【原始问题】\n{question}\n\n"
                f"【待判的子问题】\n" + "\n".join(lines))
        votes: Dict[int, List[str]] = {}
        ok_votes = 0
        for sysp in _TRI_VOTE_PROMPTS:
            try:
                raw = self.llm.call(sysp, user, 0.0, 1200, json_mode=True,
                                    stage="adjudicate_sub_tristate_multi")
                data = self.llm.parse_json(raw)
            except Exception as e:
                logger.warning("三态多票：一票失败（跳过）: %s", e)
                continue
            if not isinstance(data, dict):
                continue
            ok_votes += 1
            for it in (data.get("judgments") or []):
                if not isinstance(it, dict):
                    continue
                try:
                    sid = int(it.get("id", 0))
                except (ValueError, TypeError):
                    continue
                st = str(it.get("decidability", "")).lower().strip()
                if st not in _DECIDABILITY_STATES:
                    continue
                votes.setdefault(sid, []).append(st)
        if ok_votes == 0:
            logger.warning("三态多票：三票全失败 → 保留拆解原标签")
            return 0, 0
        high = med = low = 0
        agree = 0
        n = 0
        items: List[dict] = []
        for i, s in enumerate(subs, 1):
            vs = votes.get(i) or []
            if not vs:
                continue
            n += 1
            cnt: Dict[str, int] = {}
            for v in vs:
                cnt[v] = cnt.get(v, 0) + 1
            top = max(cnt.values())
            winners = [k for k, c in cnt.items() if c == top]
            old = str(s.get("decidability", "")).lower()
            s["first_label"] = old
            s["_tri_votes"] = list(vs)
            if len(winners) == 1 and top >= 2:
                final = winners[0]
                if top == len(vs):
                    high += 1
                    level = "high"
                else:
                    med += 1
                    level = "medium"
                s["decidability"] = final
                if final == old:
                    agree += 1
            else:
                low += 1
                level = "low"
                s["decidability"] = "partial"
                s["label_disagreed"] = [old] + list(vs)
            s["_tri_final"] = s["decidability"]
            s["_tri_level"] = level
            items.append({"sub_id": s.get("id", i),
                          "question": str(s.get("question", ""))[:160],
                          "votes": list(vs),
                          "final": s["decidability"],
                          "first_label": old, "level": level})
        for s in subs:
            s["_decided_answerable"] = s.get("decidability") in _DEC_ANSWERABLE
        self._tri_consensus = (high, med, low)
        self._tri_multi_items = items
        _tot = max(1, n)
        self.vp(f"   🗳 三态多票（3 票）：一致 {high} / 多数 {med} / "
                f"分裂 {low}（共识 {(high + med) / _tot:.0%}；"
                f"与拆解原标签一致 {agree}/{n}）")
        return agree, n

'''

PACK_BLOCK = r'''        # [v122 阶段2 G2.7] 可判定性冻结条 + 人工校准队列 + 多票共识。
        #   冻结条写在研究层池上：判定早已跑完，这里是**判完那一刻**的
        #   名单快照，后面任何一种迁移都改不动它。
        _pack["tri_consensus"] = list(getattr(self, "_tri_consensus",
                                              None) or [])
        try:
            _p1 = self.pools.get("1")
            if _p1 is not None:
                _fz = DecidabilityFreeze()
                _fz.freeze(_p1, layer=1)
                _pack["freeze"] = _fz.to_dict()
                _pack["calibration_queue"] = list(
                    getattr(self, "_tri_multi_items", None) or [])
            else:
                _pack["freeze"] = {"signature": "", "reason": "研究层未跑"}
                _pack["calibration_queue"] = []
        except Exception as _e:
            logger.warning("冻结/校准队列写入失败: %s", _e)
            _pack["freeze"] = {"signature": "", "error": str(_e)}
            _pack["calibration_queue"] = []

'''

HEADER_BLOCK = r'''            # [v122 阶段2 G2.5/G2.6] 三态多票 + **冻结**
            _fz = result.get("freeze") or {}
            _cons = result.get("tri_consensus") or []
            _sig = str(_fz.get("signature") or "")
            _cqn = len(result.get("calibration_queue") or [])
            if _cons or _sig:
                if len(_cons) == 3:
                    _cs = f"一致 {_cons[0]} / 多数 {_cons[1]} / 分裂 {_cons[2]}"
                else:
                    _cs = "（无多票记录）"
                f.write(f"**三态多票**（3 票）：{_cs}　"
                        f"**冻结**：sha256={_sig[:16]}…"
                        f"（{len(_sig)} 位）　校准队列 {_cqn} 条\n\n")

'''

REPS = [
    ("import json\nimport logging\n", "import hashlib\nimport json\nimport logging\n", 1),
    ('_DEC_ANSWERABLE = ("decidable", "partial")\n',
     '_DEC_ANSWERABLE = ("decidable", "partial")\n' + VOTE_BLOCK, 1),
    # 派发：插在单票实现开头
    ('        if not subs:\n'
     '            return 0, 0\n'
     '        lines = [f"  {i}. {str(s.get(\'question\', \'\'))[:200]}"\n'
     '                 for i, s in enumerate(subs, 1)]\n',
     DISPATCH_BLOCK +
     '        if not subs:\n'
     '            return 0, 0\n'
     '        lines = [f"  {i}. {str(s.get(\'question\', \'\'))[:200]}"\n'
     '                 for i, s in enumerate(subs, 1)]\n', 1),
    # 多票方法插在单票方法定义之前
    ('    # ---------- [v1.21.62] 三态独立判决 ----------\n'
     '    def _adjudicate_sub_tristate(self, subs: List[dict],\n',
     MULTI_METHOD +
     '    # ---------- [v1.21.62] 三态独立判决 ----------\n'
     '    def _adjudicate_sub_tristate(self, subs: List[dict],\n', 1),
    # packed：冻结 + 校准队列
    ('        _ar = self._anchor_report_for_pack(results)\n',
     PACK_BLOCK + '        _ar = self._anchor_report_for_pack(results)\n', 1),
    # 头部：三态多票 + 冻结
    ('                f.write(f"  - 可信度分级：{_level}\\n\\n")\n',
     '                f.write(f"  - 可信度分级：{_level}\\n\\n")\n'
     + HEADER_BLOCK, 1),
    # 配置开关
    ('        # v1.21.52 [P1-6] 输入健全性自检：P=PN 这一步就该被说出来\n'
     '        "input_sanity": True,\n',
     '        # v1.21.52 [P1-6] 输入健全性自检：P=PN 这一步就该被说出来\n'
     '        "input_sanity": True,\n'
     '        # [v122 阶段2 G2.1] 三态多票化（3 票）。关掉 = 退回 v1.21.77\n'
     '        #   的单票判决（少 2 次调用/次判决）。\n'
     '        "tri_multi_vote": True,\n', 1),
]


def main():
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    for old, new, cnt in REPS:
        n = s.count(old)
        if n != cnt:
            print(f"✗ 断言失败：出现 {n} 次（期望 {cnt}）：{old[:70]!r}")
            return 1
        s = s.replace(old, new, cnt)
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n")
    assert out.count("\r") == out.count("\r\n")
    TARGET.write_bytes(out.encode("utf-8"))
    print("✓ 阶段2 补丁完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
