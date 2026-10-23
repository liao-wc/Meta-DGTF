# -*- coding: utf-8 -*-
"""[v1.21.73 补丁] 接外部锚点（external_anchor）。

从 v1.21.72 复制出 v1.21.73，按项目铁律走 CRLF 往返：
  读字节 → 断言纯 CRLF → 转 LF → 替换（每处断言锚点出现 1 次）→ 转回 CRLF
  → 断言换行数不变 → 写字节。

改动清单见脚本 `REPLACES` 顺序；改完打印 docstring 里各版本段的起始行号，
确认「最新在最前」。
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.72.py"
DST = HERE / "元DGTF-V1.21.73.py"

s = ""


def rd(p: Path) -> str:
    raw = p.read_bytes().decode("utf-8")
    assert raw.count("\r\n") == raw.count("\n"), "源文件不是纯 CRLF"
    assert raw.count("\r") == raw.count("\r\n"), "源文件有孤立 CR"
    return raw


def rep(old: str, new: str, tag: str) -> None:
    global s
    n = s.count(old)
    assert n == 1, f"[{tag}] 锚点出现 {n} 次（应为 1）"
    s = s.replace(old, new, 1)
    print(f"  [{tag}] ok")


# ================================================================ 读
raw = rd(SRC)
s = raw.replace("\r\n", "\n")
print(f"读入 {SRC.name}：{len(s)} 字符（LF 计）")

# ================================================================ 1) 版本号
rep("元 DGTF · v1.21.72", "元 DGTF · v1.21.73", "版本号·docstring标题")
rep('__version__ = "1.21.72"', '__version__ = "1.21.73"', "版本号·__version__")

# ================================================================ 2) changelog
CHANGELOG = r"""  v1.21.73 是本轮「接外部锚点」版。v1.21.63 起产物头部那句
  「外部锚点：无」是**写死的承认**，不是开关 —— 探针
  `_probe_v73_anchor.py` [1][3][4] 实测：全文 `external_anchor` /
  `web_search` / `external_facts` 引用数**均为 0**，`_assess_decidability`
  只收题面（system 788 字符、无「锚点」二字）。也就是说所谓「外判」一直
  是模型的第二意见，没有外部事实源。本版把它做成**真能接的通道**。

  ────────────────────────────────────────────────────────────
  外部锚点（external_anchor）
  ────────────────────────────────────────────────────────────

  **根因**：螺旋跑 N 层到底是「逼近真理」还是「绕圈」，没有外部参照无从
  判断。v1.21.63 的选择是让产物自己承认没有 —— 承认不等于可测。

  **做法（三处）**
  1. 配置 `external_anchor.{enabled, path, max_items, crosscheck}`，
     默认 **enabled=False**。★ 关闭时 packed 键集合、assess 的 prompt、
     产物文案与 v1.21.72 **逐字相同**（加性；冒烟 `check_v73_anchor`
     有专门的反证）。
  2. `_load_anchors()`：读快照 JSON，逐条校验（缺 claim 的丢弃），截断到
     `max_items`。失败**一律留痕**写进 `external_anchor.error`，不静默
     降级成「没接入」——那正是本项目反复踩的坑。
  3. 两处消费：
     · `DGTF._assess_decidability(question, anchors)`：锚点作为**可引用的
       外部事实**附在 prompt 后，要求把用到的编号填 `anchor_refs`；
       anchors 为空时 `system` **一字不改**（拼接空串）。
     · `_anchor_crosscheck()`：收尾**只读**对照 —— 本次结论条目 vs 锚点，
       逐条标 印证 / 冲突 / 无对应，计数进产物。

  **★ 红线不动**：锚点**不进池、不参与对撞与清算、不改任何 view**。
  它是校验标尺，不是题面输入（「输入是形状不是数据」这条不变）。
  因此它的价值是**测出结论与外部事实差多少**，不是让结论更正确。

  **为什么是读文件，不是引擎自己联网**：引擎没有联网能力（v9.1 的
  `web_search` 在 v1.21 重写后 0 处引用，v1.21.61 已核过）。与其假装
  联网，不如把外部事实**显式落盘**再读 —— 每条锚点带来源、URL 与检索
  时刻，可复现、可核对、可事后逐条复查。

  **验证**：冒烟 `check_v73_anchor`（关时逐字同构 + 开时挂键 + 失败留痕 +
  三条负对照）+ 探针 before/after + 真跑 OFF/ON 对照（见 v73_报告.md）。

  v1.21.72 是本轮文档与可观测性版"""

rep("  v1.21.72 是本轮文档与可观测性版", CHANGELOG, "changelog 插段")

# ================================================================ 3) DEFAULT_CONFIG
CFG_OLD = r"""        "min_rounds": {
            "0": 0,
            "1": 0,
            "both": 0,
            "all": 0,
        },
    },
}"""
CFG_NEW = r"""        "min_rounds": {
            "0": 0,
            "1": 0,
            "both": 0,
            "all": 0,
        },
    },

    # ============================================================
    # [v1.21.73] 外部锚点（把「没有外部事实校验」从承认变成可测）
    # ============================================================
    "external_anchor": {
        # 【用途】是否接入外部事实锚点（题外独立检索到的事实快照）。
        # 【默认】false —— 关闭时行为与 v1.21.72 逐字相同（加性改动）。
        "enabled": False,
        # 【用途】锚点快照 JSON 的路径（相对当前工作目录，或绝对路径）。
        #   格式：{"question":..., "retrieved_at":..., "retriever":...,
        #          "anchors":[{"id","claim","source","url","as_of","kind"}]}
        "path": "",
        # 【用途】最多用几条锚点（防 prompt 膨胀）。
        "max_items": 12,
        # 【用途】收尾要不要做「结论 vs 锚点」只读对照（一次额外调用）。
        "crosscheck": True,
    },
}"""
rep(CFG_OLD, CFG_NEW, "DEFAULT_CONFIG 加 external_anchor")

# ================================================================ 4) __init__ 新字段
INIT_OLD = r"""        self._tri_agree: int = 0
        self._tri_total: int = 0"""
INIT_NEW = r"""        self._tri_agree: int = 0
        self._tri_total: int = 0
        # [v1.21.73] 外部锚点：`_anchors` 是载入的锚点条目，`_anchor_err`
        #   是加载/对照的失败原因（必须留痕，不静默降级），`_anchor_report`
        #   是收尾对照报告（打包时挂到 packed 上，None = 本次不挂）。
        self._anchors: List[dict] = []
        self._anchor_err: str = ""
        self._anchor_source: Dict[str, str] = {}
        self._anchor_report: Optional[dict] = None"""
rep(INIT_OLD, INIT_NEW, "__init__ 加锚点字段")

# ================================================================ 5) run() 开头加载
RUN_OLD = r"""        self._ext_assess_cache = {}
        # [v1.21.62 P2-7] 判据从"能不能判"改成"想要什么"
        route = self._route_by_decidability(question, route, orientation)"""
RUN_NEW = r"""        self._ext_assess_cache = {}
        # [v1.21.73] 外部锚点：同样必须在 `_route_by_decidability` **之前**
        #   加载 —— 它会打外部评估（`_cached_ext_assess` → `_assess_decidability`），
        #   晚加载的话那一发就用不上锚点，对照实验的 ON 臂会退化成 OFF 臂。
        self._anchor_report = None
        self._anchor_source = {}
        self._load_anchors()
        # [v1.21.62 P2-7] 判据从"能不能判"改成"想要什么"
        route = self._route_by_decidability(question, route, orientation)"""
rep(RUN_OLD, RUN_NEW, "run() 开头加载锚点")

# ================================================================ 6) _assess_decidability 签名
rep("    def _assess_decidability(self, question: str) -> dict:",
    "    def _assess_decidability(self, question: str,\n"
    "                             anchors: Optional[List[dict]] = None) -> dict:",
    "assess 签名加 anchors")

# ================================================================ 7) assess 调用处拼锚点
CALL_OLD = r"""        try:
            raw = self.llm.call(system, f"【问题】\n{question}",
                                0.2, 1100, json_mode=True,
                                stage="assess_decidability")"""
CALL_NEW = r"""        # [v1.21.73] 外部锚点：有锚点时附在 prompt 后面当**可引用的外部
        #   事实**。★ 加性 —— `system` 本身一字不改，只在后面拼一段；
        #   anchors 为空时拼的是空串，发给模型的与 v1.21.72 逐字相同。
        _anchor_sys = ""
        _anchor_user = ""
        if anchors:
            _a_lines = []
            for _a in anchors:
                _ln = "- [" + str(_a.get("id")) + "] " + str(_a.get("claim"))
                if _a.get("source"):
                    _ln = _ln + "（来源：" + str(_a.get("source")) + "）"
                _a_lines.append(_ln)
            _anchor_sys = (
                "\n\n【外部事实锚点】\n"
                "下面会附上本次运行前由外部检索得到的真实事实条目。它们是**校验参照**：\n"
                "- 只在某条事实能支撑或反驳某个方面时引用它，不要凭空扩写；\n"
                "- 用到的条目把编号填进 anchor_refs；一条都没用到就给空列表；\n"
                "- 锚点没覆盖到的方面照常按你自己的知识判，不要因为没锚点就判"
                "不可判定，也不要因为有锚点就判可判定。\n")
            _anchor_user = ("\n\n【外部事实锚点（" + str(len(anchors)) + " 条）】\n"
                            + "\n".join(_a_lines))
        try:
            raw = self.llm.call(system + _anchor_sys,
                                f"【问题】\n{question}" + _anchor_user,
                                0.2, 1100, json_mode=True,
                                stage="assess_decidability")"""
rep(CALL_OLD, CALL_NEW, "assess 调用处拼锚点")

# ================================================================ 8) assess 返回加 anchor_refs
RET_OLD = r"""        original_status = status
        status = _normalize_decidability(status, dec_aspects, und_aspects,
                                        where="外部评估")

        return {"decidability": status,
                "reason": str(data.get("reason", ""))[:200],
                "features": _list("features"),
                "decidable_aspects": dec_aspects,
                "undecidable_aspects": und_aspects,
                "_original_status": original_status}"""
RET_NEW = r"""        original_status = status
        status = _normalize_decidability(status, dec_aspects, und_aspects,
                                        where="外部评估")

        # [v1.21.73] 外部锚点：模型说它用到了哪几条。★ 只认本次真给出的
        #   编号（防模型编一个 id 出来也算数）；没给锚点时 schema 里没有
        #   这个字段，结果自然是空列表，与 v1.21.72 同构。
        _refs: List[str] = []
        if isinstance(data.get("anchor_refs"), list):
            _valid = set(str(_a.get("id")) for _a in (anchors or []))
            _refs = [str(x)[:40] for x in data["anchor_refs"][:8]
                     if str(x) in _valid]

        return {"decidability": status,
                "reason": str(data.get("reason", ""))[:200],
                "features": _list("features"),
                "decidable_aspects": dec_aspects,
                "undecidable_aspects": und_aspects,
                "_original_status": original_status,
                "anchor_refs": _refs,
                "_anchors_given": len(anchors or [])}"""
rep(RET_OLD, RET_NEW, "assess 返回加 anchor_refs")

# ================================================================ 9) _cached_ext_assess 传锚点
rep("        res = d._assess_decidability(question)",
    "        res = d._assess_decidability(question,\n"
    "                                     anchors=getattr(self, \"_anchors\", None))",
    "cached_ext_assess 传锚点")

# ================================================================ 10) 插入新方法
NEW_METHODS = r'''    # ============================================================
    # [v1.21.73] 外部锚点：加载 / 只读对照
    # ============================================================

    def _load_anchors(self) -> List[dict]:
        """[v1.21.73] 读外部锚点快照（一次 run 只在开头调一次）。

        ★ 为什么是「读文件」而不是「引擎自己联网」：引擎没有联网能力
          （v9.1 的 web_search / external_facts 在 v1.21 重写后是 0 处
          引用，v1.21.61 已核过）。与其假装联网，不如把外部事实**显式
          落盘**再读 —— 每条锚点带来源、URL 与检索时刻，可复现、可核对、
          可事后逐条复查。
        ★ 失败一律留痕：读不到 / 结构不对 / 空列表都写 `self._anchor_err`，
          日志与产物都会印出来。★ 不静默降级成「没接入」—— 那正是本
          项目反复踩的坑（看着像没接，其实是接了但失败了）。
        """
        cfg = self.config.get("external_anchor") or {}
        self._anchors = []
        self._anchor_err = ""
        if not cfg.get("enabled"):
            return self._anchors
        path = str(cfg.get("path") or "").strip()
        max_items = int(cfg.get("max_items", 12) or 12)
        if not path:
            self._anchor_err = "enabled=True 但没有给 path"
            logger.warning("外部锚点加载失败：%s", self._anchor_err)
            return self._anchors
        try:
            p = Path(path)
            if not p.is_absolute():
                p = Path.cwd() / p
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            self._anchor_err = ("锚点文件读取失败：" + type(exc).__name__
                                + ": " + str(exc)[:200])
            logger.warning("外部锚点加载失败：%s", self._anchor_err)
            return self._anchors
        if not isinstance(data, dict):
            self._anchor_err = "锚点文件顶层不是对象"
            logger.warning("外部锚点加载失败：%s", self._anchor_err)
            return self._anchors
        raw = data.get("anchors")
        if not isinstance(raw, list) or not raw:
            self._anchor_err = "锚点文件里 anchors 不是非空列表"
            logger.warning("外部锚点加载失败：%s", self._anchor_err)
            return self._anchors
        self._anchor_source = {
            "file": p.name,
            "retrieved_at": str(data.get("retrieved_at") or "")[:40],
            "retriever": str(data.get("retriever") or "")[:80],
        }
        out: List[dict] = []
        for i, a in enumerate(raw[:max_items], 1):
            if not isinstance(a, dict):
                continue
            claim = str(a.get("claim") or "").strip()
            if not claim:
                continue
            out.append({"id": str(a.get("id") or ("a" + str(i))),
                        "claim": claim[:400],
                        "source": str(a.get("source") or "")[:200],
                        "url": str(a.get("url") or "")[:300],
                        "as_of": str(a.get("as_of") or "")[:40],
                        "kind": str(a.get("kind") or "")[:40]})
        self._anchors = out
        if not out:
            self._anchor_err = ("锚点文件里 " + str(len(raw))
                                + " 条全部缺 claim")
            logger.warning("外部锚点加载失败：%s", self._anchor_err)
        else:
            self.vp("\n⚓ 外部锚点：载入 " + str(len(out)) + " 条（"
                    + p.name + "）")
        return out

    def _anchor_claims(self, results) -> List[str]:
        """[v1.21.73] 收集本次要拿去对照的**结论条目**（只读，不改任何池）。

        取两处：各层 view 的 `decidable_product.answer`（成品答案）与研究
        池里状态为 answered 的子问题。都空就返回空列表 —— 产物里会写
        「本次没有可对照的结论条目」，而不是假装对照过。
        """
        out: List[str] = []
        for k in ("1", "both", "all", "0"):
            v = (results or {}).get(k)
            if v is None:
                continue
            dp = getattr(v, "decidable_product", None) or {}
            ans = str(dp.get("answer") or "").strip()
            if ans:
                out.append(ans[:300])
        rp = (self.pools or {}).get("1")
        subs = getattr(rp, "sub_questions", None) or []
        for sq in subs:
            if isinstance(sq, dict) and sq.get("status") == "answered":
                q = str(sq.get("question") or "").strip()
                if q:
                    out.append(q[:300])
        seen = set()
        uniq = []
        for c in out:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        return uniq[:12]

    def _anchor_crosscheck(self, results) -> dict:
        """[v1.21.73] 收尾只读对照：本次结论条目 vs 外部锚点。

        ★ 只读：不写回任何 view / pool / settlement，不改判定。它回答的是
          「本次跑出来的结论，与外部事实对得上吗」—— 这是 v1.21.63 那句
          承认回答不了的问题。
        ★ 一次 LLM 调用，只在「开启 + 有锚点 + 有可对照条目」时发生。
        """
        base = {
            "enabled": True,
            "anchors": len(self._anchors or []),
            "source_file": (self._anchor_source or {}).get("file", ""),
            "retrieved_at": (self._anchor_source or {}).get("retrieved_at", ""),
            "retriever": (self._anchor_source or {}).get("retriever", ""),
            "claims": 0,
            "items": [],
            "summary": {"claims": 0, "supported": 0, "conflicted": 0,
                        "unmatched": 0, "anchor_used": 0},
            "error": self._anchor_err or "",
        }
        if not self._anchors:
            if not base["error"]:
                base["error"] = "没有可用锚点（未开启或加载失败）"
            return base
        claims = self._anchor_claims(results)
        base["claims"] = len(claims)
        if not claims:
            base["error"] = ("本次没有可对照的结论条目（成品答案与已答"
                             "子问题都为空）")
            self.vp("\n⚓ 外部锚点：本次无结论条目可对照（不假装对照过）")
            return base
        if not (self.config.get("external_anchor") or {}).get("crosscheck", True):
            base["error"] = "crosscheck 已关闭，只载入锚点不做对照"
            return base
        a_lines = []
        for a in self._anchors:
            ln = "- [" + str(a.get("id")) + "] " + str(a.get("claim"))
            if a.get("source"):
                ln = ln + "（来源：" + str(a.get("source")) + "）"
            a_lines.append(ln)
        c_lines = []
        for i, c in enumerate(claims, 1):
            c_lines.append("- [c" + str(i) + "] " + c)
        system = """你是【外部事实对照者】。

你会拿到两组材料：一组是本次运行产出的结论条目，一组是运行前由外部检索得到的真实事实（外部锚点）。你的任务是把两组对起来，逐条给判定。

判定只有三种，不许给第四种：
- 印证：锚点里有条目支持它（把编号填进 anchor_ids）
- 冲突：锚点里有条目与它相反、或使它不成立（把编号填进 anchor_ids）
- 无对应：锚点里没有能支持也没有能反驳它的条目（anchor_ids 给空列表）

【判据】
- 只在锚点条目**直接**支持或反驳时才判印证 / 冲突；沾不上边就判无对应。不要因为"大致相关"就判印证 —— 那会把对照变成奉承。
- note 写一两句理由，说明用的是哪条锚点的什么内容。判无对应也要写（写"锚点未涉及 X"之类）。
- 一条结论最多引 3 条锚点，编号必须来自下面给出的锚点列表，不许自造。

严格 JSON：
{
  "items": [
    {"claim_id": "c1", "verdict": "印证|冲突|无对应", "anchor_ids": ["a1"], "note": "40字内"}
  ]
}
"""
        user = ("【本次结论条目（" + str(len(claims)) + " 条）】\n"
                + "\n".join(c_lines)
                + "\n\n【外部锚点（" + str(len(self._anchors)) + " 条）】\n"
                + "\n".join(a_lines)
                + "\n\n逐条给判定，严格 JSON。")
        try:
            raw = self.llm.call(system, user, 0.2, 1800, json_mode=True,
                                stage="anchor_crosscheck")
        except Exception as exc:
            base["error"] = ("对照调用失败：" + type(exc).__name__ + ": "
                             + str(exc)[:200])
            logger.warning("外部锚点对照失败：%s", base["error"])
            return base
        data = self.llm.parse_json(raw)
        if not isinstance(data, dict):
            base["error"] = "对照返回的不是对象"
            return base
        raw_items = data.get("items")
        if not isinstance(raw_items, list):
            base["error"] = "对照返回缺 items 列表"
            return base
        cmap = {}
        for i, c in enumerate(claims, 1):
            cmap["c" + str(i)] = c
        used = set()
        sup = 0
        con = 0
        unm = 0
        items: List[dict] = []
        valid = set(str(a.get("id")) for a in self._anchors)
        for it in raw_items[:24]:
            if not isinstance(it, dict):
                continue
            cid = str(it.get("claim_id") or "").strip()
            if cid not in cmap:
                continue
            verdict = str(it.get("verdict") or "").strip()
            if verdict not in ("印证", "冲突", "无对应"):
                verdict = "无对应"
            ids = [str(x)[:20] for x in (it.get("anchor_ids") or [])[:3]
                   if isinstance(x, str)]
            ids = [x for x in ids if x in valid]
            used.update(ids)
            if verdict == "印证":
                sup += 1
            elif verdict == "冲突":
                con += 1
            else:
                unm += 1
            items.append({"claim_id": cid, "claim": cmap[cid][:200],
                          "verdict": verdict, "anchor_ids": ids,
                          "note": str(it.get("note") or "")[:160]})
        covered = set(i["claim_id"] for i in items)
        for cid, c in cmap.items():
            if cid not in covered:
                unm += 1
                items.append({"claim_id": cid, "claim": c[:200],
                              "verdict": "无对应", "anchor_ids": [],
                              "note": "对照未覆盖该条目（判据缺失，不是无冲突）"})
        base["items"] = items
        base["summary"] = {"claims": len(claims), "supported": sup,
                           "conflicted": con, "unmatched": unm,
                           "anchor_used": len(used)}
        self.vp("\n⚓ 外部锚点对照：结论 " + str(len(claims)) + " 条 —— 印证 "
                + str(sup) + " / 冲突 " + str(con) + " / 无对应 " + str(unm)
                + "（用到锚点 " + str(len(used)) + "/" + str(len(self._anchors))
                + "）")
        return base

    def _anchor_report_for_pack(self, results):
        """[v1.21.73] 打包时决定要不要挂 `external_anchor` 键。

        ★ 只在配置开启时返回 dict（哪怕失败也返回 —— 失败是必须留痕的
          状态）；关闭时返回 None，packed 与 v1.21.72 逐字同构。
        """
        if not (self.config.get("external_anchor") or {}).get("enabled"):
            return None
        if self._anchor_report is not None:
            return self._anchor_report
        self._anchor_report = self._anchor_crosscheck(results)
        return self._anchor_report

    def _cached_ext_assess(self, question: str) -> dict:'''
rep("    def _cached_ext_assess(self, question: str) -> dict:",
    NEW_METHODS, "插入锚点三方法（含 _cached_ext_assess 头）")

# ================================================================ 11) _pack_result 改名
rep("        self._refresh_settlement(results)\n        return {",
    "        self._refresh_settlement(results)\n        _pack = {",
    "_pack_result 返回改变量")

# ================================================================ 12) _pack_result 挂键
PACK_OLD = r'''            "layer_contribution": self._layer_contribution(results),
        }'''
PACK_NEW = r'''            "layer_contribution": self._layer_contribution(results),
        }
        # [v1.21.73] 外部锚点：只在**开启**时挂键（失败也要挂，失败是状态）。
        #   关闭时不挂 —— packed 的键集合与 v1.21.72 逐字相同，旧断言、
        #   旧产物、跨版本对表都不受影响。
        _ar = self._anchor_report_for_pack(results)
        if _ar is not None:
            _pack["external_anchor"] = _ar
        return _pack'''
rep(PACK_OLD, PACK_NEW, "_pack_result 挂 external_anchor")

# ================================================================ 13) save_result 头部渲染
SAVE_OLD = r'''            f.write("**外部锚点**：无（本产物不含外部事实校验；"
                    "所有结论的可信度取决于池内材料的一致性——"
                    "这是设计边界，不是缺陷）\n\n")'''
SAVE_NEW = r'''            _ea = result.get("external_anchor")
            if _ea:
                _sm = _ea.get("summary") or {}
                f.write(f"**外部锚点**：已接入 {_ea.get('anchors', 0)} 条"
                        f"（{_ea.get('source_file', '?')}"
                        f"，检索于 {_ea.get('retrieved_at', '?')}）\n\n")
                if _ea.get("error"):
                    f.write(f"**锚点异常**：{_ea['error']}\n\n")
                else:
                    f.write(f"**锚点对照**：结论 {_sm.get('claims', 0)} 条 —— "
                            f"印证 {_sm.get('supported', 0)} / "
                            f"冲突 {_sm.get('conflicted', 0)} / "
                            f"无对应 {_sm.get('unmatched', 0)}"
                            f"（用到锚点 {_sm.get('anchor_used', 0)}/"
                            f"{_ea.get('anchors', 0)}）\n\n")
            else:
                f.write("**外部锚点**：无（本产物不含外部事实校验；"
                        "所有结论的可信度取决于池内材料的一致性——"
                        "这是设计边界，不是缺陷）\n\n")'''
rep(SAVE_OLD, SAVE_NEW, "save_result 头部渲染锚点")

# ================================================================ 14) 产物正文加对照段
BODY_OLD = r'''        chans = result.get("channels") or []
        f.write(f"**回来通道**: "
                f"{'、'.join(chans) if chans else '全关（历史不参与本次）'}\n\n")'''
BODY_NEW = r'''        chans = result.get("channels") or []
        f.write(f"**回来通道**: "
                f"{'、'.join(chans) if chans else '全关（历史不参与本次）'}\n\n")
        # [v1.21.73] 外部锚点逐条对照的**正文出口**。头部只给计数，逐条
        #   在这里 —— 否则又是一个「有字段没渲染点」的键（v1.21.67 已为
        #   input_sanity / layer_contribution 补过一次全量附录，这里的
        #   教训一样：新字段必须有正文出口，不能只躺在 packed 里）。
        _ea2 = result.get("external_anchor")
        if _ea2 and not _ea2.get("error"):
            f.write("### 外部锚点 · 逐条对照\n\n")
            f.write(f"来源 `{_ea2.get('source_file', '?')}`"
                    f"（{_ea2.get('retriever', '?')}"
                    f"，检索于 {_ea2.get('retrieved_at', '?')}）\n\n")
            for _it in (_ea2.get("items") or []):
                _mark = {"印证": "✅", "冲突": "❌",
                         "无对应": "➖"}.get(_it.get("verdict"), "➖")
                f.write(f"- {_mark} {_it.get('verdict')}｜"
                        f"{_it.get('claim', '')[:160]}")
                if _it.get("anchor_ids"):
                    f.write(f"　← 锚点 {'、'.join(_it['anchor_ids'])}")
                if _it.get("note"):
                    f.write(f"　（{_it['note'][:120]}）")
                f.write("\n")
            f.write("\n")'''
rep(BODY_OLD, BODY_NEW, "产物正文加锚点对照段")

# ================================================================ 15) render_manifestation
GAP_OLD = r'''    _gaps.append("**外部锚点**：本次没有接入任何外部事实校验"
                 "（DGTF 的设计目标是显形过程，不是逼近真理——"
                 "结论的可信度取决于池内材料的一致性）")'''
GAP_NEW = r'''    _ea = res.get("external_anchor")
    if _ea:
        _n = _ea.get("summary") or {}
        _g = (f"**外部锚点**：已接入 {_ea.get('anchors', 0)} 条外部事实；"
              f"对照结论 {_n.get('claims', 0)} 条 —— 印证 "
              f"{_n.get('supported', 0)} / 冲突 {_n.get('conflicted', 0)} / "
              f"无对应 {_n.get('unmatched', 0)}")
        if _ea.get("error"):
            _g = _g + f"；⚠️ {_ea['error']}"
        _gaps.append(_g)
    else:
        _gaps.append("**外部锚点**：本次没有接入任何外部事实校验"
                     "（DGTF 的设计目标是显形过程，不是逼近真理——"
                     "结论的可信度取决于池内材料的一致性）")'''
rep(GAP_OLD, GAP_NEW, "render_manifestation 渲染锚点")

# ================================================================ 写回
out = s.replace("\n", "\r\n")
assert out.count("\n") == out.count("\r\n"), "写回后不是纯 CRLF"
assert out.count("\r") == out.count("\r\n"), "写回后有孤立 CR"
DST.write_bytes(out.encode("utf-8"))
print(f"\n写出 {DST.name}：{len(out)} 字符")

# ================================================================ 自检：版本段顺序
seq = [(m.start(), m.group(1))
       for m in re.finditer(r"^  v1\.21\.(\d\d) ", s, re.M)]
print("docstring 版本段（行号从 1 起，最新应在最前）：")
for pos, v in seq[:6]:
    print(f"   v1.21.{v}  行 {s[:pos].count(chr(10)) + 1}")
assert "__version__ = \"1.21.73\"" in s, "版本号没改成 73"
assert "v1.21.73 是本轮" in s
print("\nOK：v1.21.73 已生成")
