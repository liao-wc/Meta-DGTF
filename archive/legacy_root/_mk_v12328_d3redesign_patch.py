# -*- coding: utf-8 -*-
"""v1.23.28 D3 语义熵 —— **重新设计**（F1-R2）。

## 为什么推倒重来（三轮实测的完整证据链）

第 1 轮（v1.23.28 出厂）：`_txt = [本条目text] + 全池structural_amps`
  ⇒ 真跑实测 6/6 恒 `h_norm = 1.0`。任何条目都摊上一批**其他主张**的
  文本，簇必然全异 ⇒ 恒为上界。**读数无信息量。**

第 2 轮（F1a~F1c：改为按条目自身 occurrences）：
  直测发现 `upsert_belief` **按精确文本认领** ⇒ 换说法 = 新条目；
  逐字重复才累加 occurrences，而逐字重复去重后 n=1。
  ⇒ **无论怎么走，都得到 `None`。** 读数仍无信息量（换了个方向）。

第 3 轮（F1d：语料自供）：
  确认 `_sim3` 无语料只走字面层，两版 sim3 实测 0.6667 < 0.70 阈值。
  语料自供**没能救回**读数，因为问题不在尺子，在**分组口径**。

## 重新设计：熵度量的是「同一主张的历次说法有多发散」

判定「同一条主张」用 `_sim3` 聚类（这才是「语义」熵该用的分组），
而不是精确文本。对每条信念条目：
  1. 收集**候选出现集** = 该条目自身 occurrences 的文本
                          + 池内其他条目的 text（它们是「同主张的
                            不同说法」，只是没被精确文本认领成同一条）
  2. 用 `_sim3 ≥ thr` 单链聚类（`semantic_entropy_of` 内部已做）
  3. 只保留**包住本条目 text 的那个簇**作为「本主张的出现集」
  4. 对该出现集算语义熵：
     · 出现数 < 2          ⇒ `None`（诚实缺省：只有一条说法，无发散可言）
     · 出现数 ≥ 2 且全同簇 ⇒ `0.0`（说法收敛 —— **这是「稳」的读法**）
     · 出现数 ≥ 2 且分裂   ⇒ `> 0`（说法发散）

★ 与 D2 的关系：D2 用「精确文本 + 跨来源/跨圈」判迁移（保守、可负对照）；
  D3 是**观测**，用语义聚类看发散度。两者**不互相替代**（不同尺子）。
★ 语料：仍自供（本池文本），因为 `_sim3` 的 L2/B
  
  BM25 层需要它；
  但**阈值判定**在无语料时会退到字面层 —— 故语料自供是**必要条件**。
"""
SRC = "元DGTF-V1.23.28.py"


def _load(path=SRC):
    b = open(path, "rb").read()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n") - crlf
    assert crlf > 0, "主文件必须是 CRLF"
    assert lf == 0, "主文件混入裸 LF %d 处" % lf
    assert b.count(b"\r\r\n") == 0, "已存在 \\r\\r\\n"
    return b.decode("utf-8").replace("\r\n", "\n"), crlf, lf


def _save(txt, path=SRC):
    out = txt.replace("\r\n", "\n").replace("\n", "\r\n")
    data = out.encode("utf-8")
    assert data.count(b"\r\r\n") == 0, "写出前 \\r\\r\\n 非 0"
    open(path, "wb").write(data)


def patch(txt, name, old, new, count=1):
    n = txt.count(old)
    assert n == count, "[%s] 锚点命中 %d 次（期望 %d）" % (name, n, count)
    return txt.replace(old, new)


OLD_BODY_DOC = '''        ★ 出现文本从哪来（**修正后**）：该条目**自身**的 `occurrences`
          —— 每次 `upsert_belief` 记下的 (来源标签, 该次文本)。
          **不是**「本条目 text + 全池 structural_amps」：那样任何条目都会
          摊上一批**其他主张**的文本，簇必然全异 ⇒ `h_norm` 恒 = 1.0，
          读数**零信息量**（真跑核对抓到的退化，v1.23.28 修复）。
        ★ 去重口径：按 (源, 文本) —— 同一层同一句重说、或同一 (源,文本)
          重复登记，都不算「两次独立出现」。
        ★ `n < 2 ⇒ None`（诚实缺省）：只出现一次的条目**没有**发散度可言，
          返回 0.0 会被下游读成「很稳」—— 那是自欺。
        ★ `thr=None` ⇒ 用模块默认（0.70）；外部传配置值时逐位一致。
        ★ 只对 `status == "active"` 的条目算发散度？**不。**
          全部条目都算 —— 「稳不稳」是观测，不是只对某类条目生效的规则；
          只在**迁移**时用 active 的身份去读它（见 D2）。
        """'''

NEW_BODY_DOC = '''        ★ 出现文本从哪来（**重新设计**）：本条目自身的 `occurrences`
          **＋池内其他条目的 text**。为什么必须含后者：`upsert_belief` 按
          **精确文本**认领（D2 要保守、可负对照），所以「同一主张换个说法」
          会落成**另一条**；若不看它们，读数恒为 `None`（三轮实测证实）。
          **不是**「全池 structural_amps」：那会把**无关主张**也算进来，
          集内必然全异 ⇒ `h_norm` 恒 = 1.0（出厂版真跑实测 6/6，零信息量）。
        ★ 分组口径：`_sim3 ≥ thr` 单链聚类，**只取包住本条目 text 的那个簇**
          —— 那才是「本主张」的出现集。簇内出现数 < 2 ⇒ `None`（诚实缺省：
          只有一条说法，无发散可言）；≥2 且全同簇 ⇒ `0.0`（说法收敛）；
          ≥2 且分裂 ⇒ `> 0`（说法发散）。
        ★ 去重口径：按文本 —— 同一句重复登记不算「两种说法」。
        ★ `thr=None` ⇒ 用模块默认（0.70）；外部传配置值时逐位一致。
        ★ 只对 `status == "active"` 的条目算发散度？**不。**
          全部条目都算 —— 「稳不稳」是观测，不是只对某类条目生效的规则；
          只在**迁移**时用 active 的身份去读它（见 D2）。
        """'''

OLD_IMPL = '''        _out = {}
        for _it in self.belief_items:
            _txt = []
            _seen = set()
            _occs = list(_it.get("occurrences") or [])
            if not _occs:
                # 兼容：手工构造 / 老产物条目没有 occurrences ⇒ 退到
                # 「本条自己的 text」一条（n=1 ⇒ 熵 None，诚实缺省）。
                _occs = [["unknown", str(_it.get("text", "")).strip()]]
            for _oc in _occs:
                if isinstance(_oc, (list, tuple)):
                    _s = str(_oc[1]).strip() if len(_oc) > 1 else ""
                else:
                    _s = str(_oc).strip()
                if _s and _s not in _seen:
                    _seen.add(_s)
                    _txt.append(_s)
            _hn, _h, _cl = semantic_entropy_of(_txt, corpus=_corpus,
                                               thr=thr)
            _it["semantic_entropy"] = _hn
            _it["semantic_clusters"] = _cl
            _out[_it.get("id", "")] = _hn
        return _out
'''

NEW_IMPL = '''        _out = {}
        # 池内其他条目的 text 集合（「同主张的不同说法」候选来源）。
        _pool_texts = []
        for _jx in self.belief_items:
            _s0 = str(_jx.get("text", "")).strip()
            if _s0:
                _pool_texts.append(_s0)
        for _it in self.belief_items:
            _own = str(_it.get("text", "")).strip()
            _txt = []
            _seen = set()
            if _own:
                _txt.append(_own)
                _seen.add(_own)
            # 本条目自身的历次出现（逐字重复才累加，是「独立复现」的凭据）
            _occs = list(_it.get("occurrences") or [])
            for _oc in _occs:
                if isinstance(_oc, (list, tuple)):
                    _s = str(_oc[1]).strip() if len(_oc) > 1 else ""
                else:
                    _s = str(_oc).strip()
                if _s and _s not in _seen:
                    _seen.add(_s)
                    _txt.append(_s)
            # ★ 池内其他条目：先全收，后面按簇筛（只留包住本条的簇）。
            for _s0 in _pool_texts:
                if _s0 and _s0 not in _seen:
                    _seen.add(_s0)
                    _txt.append(_s0)
            if not _txt:
                _it["semantic_entropy"] = None
                _it["semantic_clusters"] = []
                _it["occurrence_n"] = 0
                _out[_it.get("id", "")] = None
                continue
            _hn_all, _h_all, _cl_all = semantic_entropy_of(
                _txt, corpus=_corpus, thr=thr)
            # 只留**包住本条目 text** 的那个簇（= 本主张的出现集）。
            _anchor_idx = _txt.index(_own) if _own in _txt else 0
            _keep = None
            for _c in (_cl_all or []):
                if _anchor_idx in _c:
                    _keep = list(_c)
                    break
            if _keep is None:
                _keep = [_anchor_idx]
            _sub = [_txt[_i] for _i in _keep]
            _hn, _h, _cl = semantic_entropy_of(_sub, corpus=_corpus, thr=thr)
            _it["semantic_entropy"] = _hn
            _it["semantic_clusters"] = _cl
            _it["occurrence_n"] = len(_sub)
            _out[_it.get("id", "")] = _hn
        return _out
'''


def main():
    txt, crlf0, lf0 = _load()
    print("[in] CRLF=%d LF=%d" % (crlf0, lf0))

    txt = patch(txt, "R2-doc", OLD_BODY_DOC, NEW_BODY_DOC)
    txt = patch(txt, "R2-impl", OLD_IMPL, NEW_IMPL)

    _save(txt)
    _, crlf1, lf1 = _load()
    print("[out] CRLF=%d LF=%d  \\r\\r\\n=%d"
          % (crlf1, lf1, open(SRC, "rb").read().count(b"\r\r\n")))
    print("[OK] F1-R2 applied")


if __name__ == "__main__":
    main()
