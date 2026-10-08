#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段4] 外部锚点变真证据（任务书 Step 4.1~4.7）。

- 4.1 `external_anchor` 加五档 `as_evidence` + tier_floor / api_key_env /
      cache_ttl_hours / retriever
- 4.2 `_load_anchors` 给每条锚点补 `tier`（缺省 3）
- 4.3 `AnchorRetriever`（snapshot 零调用 / tavily 真检索 + 24h 缓存）
- 4.4 `_citation_table` 的 X# 入表加 tier ≤ tier_floor 门
      （spec 里 X# 只能支撑 →decidable/→partial，已有硬约束在
       apply_decidability_change，本版不动它）
- 4.5 冲突留痕：view.errors + pool.meta；gate 档进 blocked_conclusions
- 4.6 triage 降级：「信息不足」型 und + 锚点命中 → partial
- 4.7 头部渲染「锚点分级 / triage 降级 / 冲突」

★ 兼容：v1.21.75 的 `as_evidence` 是**布尔**。`_anchor_tier()` 把
  True→evidence / False→off，老 yaml 与老快照不受影响。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

# ---------------------------------------------------------------- 4.1 配置
A_CFG = ('        # 【用途】收尾要不要做「结论 vs 锚点」只读对照（一次额外调用）。\n'
         '        "crosscheck": True,\n')
B_CFG = ('        # 【用途】收尾要不要做「结论 vs 锚点」只读对照（一次额外调用）。\n'
         '        "crosscheck": True,\n'
         '        # [v122 P4 G4.1] 锚点分五档。旧布尔写法仍兼容：\n'
         '        #   True → "evidence"，False → "off"（见 _anchor_tier）。\n'
         '        #   off      不给模型看\n'
         '        #   record   只记录，不进引用表\n'
         '        #   crosscheck 只做收尾对照（v1.21.75 的默认行为）\n'
         '        #   evidence 进引用表 X#，可支撑 →decidable / →partial\n'
         '        #   gate     evidence + 冲突即阻断该结论\n'
         '        "as_evidence": "off",\n'
         '        # [v122 P4 G4.2] 引用表只收 tier ≤ 此值的锚点（1 最硬）。\n'
         '        "tier_floor": 2,\n'
         '        # [v122 P4 G4.3] 真检索要用的环境变量名（不落盘 key）。\n'
         '        "api_key_env": "TAVILY_API_KEY",\n'
         '        "cache_ttl_hours": 24,\n'
         '        # snapshot | tavily\n'
         '        "retriever": "snapshot",\n')

# ------------------------------------------------- 4.2 tier / 4.3 检索器
CONSTS = '''
# ============================================================
# [v122 阶段4 G4.1~G4.3] 外部锚点：五档 / tier 门 / 真检索
# ============================================================
_ANCHOR_TIERS = ("off", "record", "crosscheck", "evidence", "gate")

# triage 降级只认这四类理由：它们都指向「缺外部材料」，而不是「问题本身
# 不可判定」。别的理由（例如"概念本身未定义"）不该被一次检索推翻。
_TRIAGE_KEYS = ("信息不足", "需外部动作", "缺数据", "无外部")


def _anchor_tier(cfg) -> str:
    """把 `external_anchor.as_evidence` 归一到五档之一。

    ★ 兼容 v1.21.75 的布尔：True → "evidence"，False → "off"。
      非法值按 "off" 处理（调用点会把它渲染出来，不静默升级权限）。
    """
    raw = (cfg or {}).get("as_evidence", "off")
    if isinstance(raw, bool):
        return "evidence" if raw else "off"
    s = str(raw or "off").strip().lower()
    return s if s in _ANCHOR_TIERS else "off"


def _tier_floor(cfg) -> int:
    try:
        return int((cfg or {}).get("tier_floor", 2) or 2)
    except (TypeError, ValueError):
        return 2


class AnchorRetriever:
    """[v122 阶段4 G4.3] 锚点检索适配层。

    `snapshot` 是**零调用**路径（读快照）。`tavily` 走真 HTTP，结果按
    queries 的 sha256 落 `cache/anchors/`，TTL 内不再打网络 —— 检索是
    最贵的一环，「先量后改」在钱上同样成立。
    """

    def __init__(self, backend: str, api_key: str, ttl_hours: int = 24):
        self.backend = str(backend or "snapshot").strip().lower()
        self.api_key = api_key or ""
        self.ttl = float(ttl_hours or 24) * 3600.0

    def _cache_path(self, queries):
        key = hashlib.sha256(
            json.dumps(list(queries), sort_keys=True,
                       ensure_ascii=False).encode("utf-8")).hexdigest()
        return Path("cache/anchors") / (key[:24] + ".json")

    def search(self, queries, max_n: int = 12) -> List[dict]:
        if self.backend == "snapshot":
            return []
        if self.backend != "tavily":
            raise RuntimeError(
                "未实现的检索后端: " + repr(self.backend) + "（不静默降级）")
        cache = self._cache_path(queries)
        try:
            if cache.is_file():
                d0 = json.loads(cache.read_text(encoding="utf-8"))
                if time.time() - float(d0.get("_ts") or 0) < self.ttl:
                    return list(d0.get("anchors") or [])
        except Exception:
            pass                      # 缓存坏了不是错误，重查一遍即可
        res = self._tavily(list(queries or []), int(max_n or 12))
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"_ts": time.time(),
                                         "anchors": res},
                                        ensure_ascii=False, indent=2),
                             encoding="utf-8")
        except Exception as exc:      # 缓存写失败不影响本次结果
            logger.warning("锚点缓存写入失败：%s", exc)
        return res

    def _tavily(self, queries, max_n: int) -> List[dict]:
        import urllib.request
        out: List[dict] = []
        for q in queries[:2]:
            body = json.dumps({"api_key": self.api_key, "query": q,
                               "max_results": max_n}).encode("utf-8")
            req = urllib.request.Request(
                "https://api.tavily.com/search", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            for it in (data.get("results") or []):
                out.append({"id": "t" + str(len(out) + 1),
                            "claim": str(it.get("content", ""))[:400],
                            "source": str(it.get("url", "")),
                            "url": str(it.get("url", "")),
                            "as_of": "", "kind": "tavily", "tier": 3})
                if len(out) >= max_n:
                    return out
        return out

'''

# ------------------------------------------------------- 4.4 X# 入表加 tier 门
A_CITE = '''    if getattr(pool, "anchor_as_evidence", False):
        for _xi, _xa in enumerate(
                (getattr(pool, "anchors", None) or [])[:12], 1):
            out.append((f"X{_xi}", str(_xa.get("claim", ""))))
'''
B_CITE = '''    if getattr(pool, "anchor_as_evidence", False):
        # [v122 P4 G4.4] 只收 tier ≤ tier_floor 的锚点。tier 小的更硬；
        #   让一条 tier=4 的二手转述去支撑 →decidable，比"没证据"更危险。
        _floor_c = _tier_floor(getattr(pool, "_anchor_cfg", None) or {})
        _xi = 0
        for _xa in (getattr(pool, "anchors", None) or []):
            _t = int(_xa.get("tier", 3) or 3)
            if _t > _floor_c:
                continue
            _xi += 1
            out.append((f"X{_xi}", str(_xa.get("claim", ""))))
            if _xi >= 12:
                break
'''

# ------------------------------------------------------- 4.3 检索器接入
A_RETR = '''        cfg = self.config.get("external_anchor") or {}
        mode = str(cfg.get("retriever") or "snapshot").strip().lower()
        if mode != "snapshot":
            raise RuntimeError(
                f"external_anchor.retriever={mode!r} 尚未实现"
                f"（当前只有 'snapshot'）；不静默降级")
        return list(self._anchors or [])
'''
B_RETR = '''        cfg = self.config.get("external_anchor") or {}
        mode = str(cfg.get("retriever") or "snapshot").strip().lower()
        if mode == "snapshot":
            # 「零调用读快照」是 v1.21.75 的既有语义，逐字保留。
            return list(self._anchors or [])
        # [v122 P4 G4.3] 真检索后端。key 只从环境变量读，不写配置文件。
        import os as _os
        _env = str(cfg.get("api_key_env") or "TAVILY_API_KEY")
        _r = AnchorRetriever(mode, _os.environ.get(_env, ""),
                             int(cfg.get("cache_ttl_hours", 24) or 24))
        got = _r.search(queries or [], int(cfg.get("max_items", 12) or 12))
        if got:
            # 检索到的锚点并入本 run 的锚点池；tier 缺省 3（二手转述）。
            for _a in got:
                _a.setdefault("tier", 3)
            self._anchors = list(self._anchors or []) + got
        return got
'''

# ------------------------------------------------------- 4.5 入池时的档位
A_AE = '        pool.anchor_as_evidence = bool(cfg.get("as_evidence", False))\n'
B_AE = ('        # [v122 P4 G4.1] 五档归一；同时把 cfg 快照挂到池上，\n'
        '        #   让 _citation_table 能拿到 tier_floor（纯函数读不到 self）。\n'
        '        pool._anchor_cfg = dict(cfg)\n'
        '        _ae_tier = _anchor_tier(cfg)\n'
        '        pool.anchor_as_evidence = _ae_tier in ("evidence", "gate")\n')

# ------------------------------------------------------- 4.2 tier 字段
A_TIER = ('            out.append({"id": str(a.get("id") or ("a" + str(i))),\n'
          '                        "claim": claim[:400],\n')
B_TIER = ('            # [v122 P4 G4.2] tier 1~4，缺省 3（＝二手转述）。\n'
          '            try:\n'
          '                _t = int(a.get("tier", 3) or 3)\n'
          '            except (TypeError, ValueError):\n'
          '                _t = 3\n'
          '            out.append({"id": str(a.get("id") or ("a" + str(i))),\n'
          '                        "tier": max(1, min(4, _t)),\n'
          '                        "claim": claim[:400],\n')

# ------------------------------------------------ 4.5/4.6/4.7 crosscheck 增项
A_CB = '            "as_evidence": bool((self.config.get("external_anchor")\n                                  or {}).get("as_evidence", False)),\n'
B_CB = ('            # [v122 P4 G4.1] 这里是**档位字符串**，不再压成布尔 ——\n'
        '            #   压成布尔之后产物里看不出是 record 还是 evidence。\n'
        '            "as_evidence": _anchor_tier(\n'
        '                self.config.get("external_anchor") or {}),\n')

A_CT = '''        base["items"] = items
        base["summary"] = {"claims": len(claims), "supported": sup,
                           "conflicted": con, "unmatched": unm,
                           "anchor_used": len(used)}
'''
B_CT = '''        # [v122 P4 G4.5] 冲突必须留痕：只躺在 packed 里等于没发生。
        #   · view.errors —— 让研究层自己知道结论被外部事实顶了；
        #   · pool.meta   —— 按本项目的规矩，池级也要记一笔；
        #   · gate 档     —— 冲突直接进 blocked_conclusions。
        _tier_c = _anchor_tier(self.config.get("external_anchor") or {})
        _floor_c = _tier_floor(self.config.get("external_anchor") or {})
        _pv1 = results.get("1") if isinstance(results, dict) else None
        _blocked: List[str] = []
        for _it in items:
            if _it.get("verdict") != "冲突":
                continue
            _ids = "、".join(_it.get("anchor_ids") or []) or "?"
            if _pv1 is not None:
                try:
                    _pv1.errors.append("锚点冲突：" + str(_it.get("claim_id"))
                                       + " ↔ " + _ids)
                except Exception:
                    pass
            try:
                self.pools["1"].meta.append(
                    "[锚点冲突] " + str(_it.get("claim_id")) + " ↔ " + _ids)
            except Exception:
                pass
            if _tier_c == "gate":
                _blocked.append(str(_it.get("claim_id")))
        # [v122 P4 G4.6] triage 降级：只在理由属于「缺外部材料」那四类、
        #   且被 tier ≤ floor 的锚点命中时才降一档。
        #   ★ 降档**不改池里已有的判定**（那只在 apply_decidability_change
        #     这条唯一入口里做，且要证据）；这里只出「建议降级清单」，
        #     供人核对 —— 无证据的自动降档正是本版要避免的事。
        _tg: List[dict] = []
        _und_aspects = ((self.decidability_result or {}).get(
            "undecidable_aspects") or [])
        for _a in _und_aspects:
            if not any(k in str(_a) for k in _TRIAGE_KEYS):
                continue
            _hit = next((x for x in (self._anchors or [])
                         if int(x.get("tier", 3) or 3) <= _floor_c
                         and _similar(str(_a), str(x.get("claim", "")), 0.6)),
                        None)
            if _hit:
                _tg.append({"from": "undecidable", "to": "partial",
                            "aspect": str(_a)[:80],
                            "anchor_id": _hit.get("id")})
        base["tier_floor"] = _floor_c
        base["triage_downgrades"] = len(_tg)
        base["triage_items"] = _tg
        base["blocked_conclusions"] = _blocked
        base["items"] = items
        base["summary"] = {"claims": len(claims), "supported": sup,
                           "conflicted": con, "unmatched": unm,
                           "anchor_used": len(used)}
'''

# ------------------------------------------------------- 4.7 头部渲染
A_HDR = ('                    f.write(f"**锚点对照**：结论 {_sm.get(\'claims\', 0)} 条 —— "\n'
         '                            f"印证 {_sm.get(\'supported\', 0)} / "\n'
         '                            f"冲突 {_sm.get(\'conflicted\', 0)} / "\n'
         '                            f"无对应 {_sm.get(\'unmatched\', 0)}"\n'
         '                            f"（用到锚点 {_sm.get(\'anchor_used\', 0)}/"\n'
         '                            f"{_ea.get(\'anchors\', 0)}）\\n\\n")\n')
B_HDR = ('''                    f.write(f"**锚点对照**：结论 {_sm.get('claims', 0)} 条 —— "
                            f"印证 {_sm.get('supported', 0)} / "
                            f"冲突 {_sm.get('conflicted', 0)} / "
                            f"无对应 {_sm.get('unmatched', 0)}"
                            f"（用到锚点 {_sm.get('anchor_used', 0)}/"
                            f"{_ea.get('anchors', 0)}）\\n\\n")
                    # [v122 P4 G4.7] 三行：档位 / triage 降级 / 冲突。
                    #   ★ 无条件写（哪怕是 off）——「没这个档」和「这个档
                    #     没发生」必须能分开读（本项目的老坑）。
                    f.write(f"**锚点分级**：{_ea.get('as_evidence', 'off')}"
                            f"（tier_floor {_ea.get('tier_floor', '?')}）\\n\\n")
                    f.write(f"**triage 降级**："
                            f"{_ea.get('triage_downgrades', 0)} 条\\n\\n")
                    f.write(f"**冲突**：{_sm.get('conflicted', 0)} 条"
                            f"（gate 阻断 {len(_ea.get('blocked_conclusions') or [])} 条）\\n\\n")
''')

REPS = [
    ("cfg", A_CFG, B_CFG, 1),
    ("cite", A_CITE, B_CITE, 1),
    ("retriever", A_RETR, B_RETR, 1),
    ("as_evidence_pool", A_AE, B_AE, 1),
    ("tier_field", A_TIER, B_TIER, 1),
    ("crosscheck_meta", A_CB, B_CB, 1),
    ("crosscheck_tail", A_CT, B_CT, 1),
    ("header", A_HDR, B_HDR, 1),
]


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")

    for name, old, new, want in REPS:
        got = s.count(old)
        assert got == want, f"[{name}] 锚点 {got} 次，期望 {want}"
        s = s.replace(old, new, want)
        print(f"  ✓ {name}")

    anchor = "def _citation_table(view, pool) -> List[tuple]:\n"
    assert s.count(anchor) == 1, "citation_table 锚点不唯一"
    s = s.replace(anchor, CONSTS.lstrip("\n") + "\n" + anchor, 1)
    print("  ✓ 常量 + AnchorRetriever")

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))
    print(f"✓ 阶段4 补丁完成；行数 {len(out.splitlines())}；ast.parse OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
