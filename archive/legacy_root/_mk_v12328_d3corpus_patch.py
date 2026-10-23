# -*- coding: utf-8 -*-
"""v1.23.28 真跑核对的第 4 项修复：D3 语料自供（F1d）。

背景（真跑 + 直测共同证实）：
  F1a~F1c 把 D3 的「出现文本」口径改对了（按条目自身 occurrences），
  但**读数依然无信息量** —— 因为 `_sim3` 在 `corpus=None` 时降级到
  纯字面层（Jaccard），「同一主张换个说法」几乎必落在 0.70 之下：
      直测：'落盘的最小单位是约束' vs '落盘的最小单位是那条约束'
            → h_norm = 1.0（判成「完全不发散」的反面：两个单元素簇）
  而唯一的调用点 `absorb()` 里**没有语料可用** ⇒ 语义层永远走不到。

修法：`refresh_belief_entropy` 在 `corpus is None` 时**自供语料** —— 用本池
  已累积的未决语料（`structural_amps` + `aligned_amps` + 各条目的
  occurrences 文本）编 BM25。理由：
    · 这是**同一池内自己的文本**，与 `_sent_is_rephrase` 的「上游句」同一
      思路（同一次调用里同一把尺子）；
    · 篇数 < 4 时 `_bm25_corpus`/`_sim3` 自动降级，**不会**比现在更差
      （同一批调用共享同一降级路径，簇间仍可比）；
    · 外部显式传 corpus 时**逐位覆盖**，行为不变（可负对照）。

★ 铁律同上：read_bytes → 断言 CRLF==LF → 转 LF → 替换 → 转回 CRLF → write_bytes。
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


def main():
    txt, crlf0, lf0 = _load()
    print("[in] CRLF=%d LF=%d" % (crlf0, lf0))

    txt = patch(
        txt, "F1d-corpus-self",
        '''        _out = {}
        for _it in self.belief_items:
            _txt = []
            _seen = set()
            _occs = list(_it.get("occurrences") or [])
''',
        '''        # [D3 修正·语料自供] `corpus=None` 时用**本池自己的文本**编语料：
        #   `_sim3` 无语料只走字面层（Jaccard）⇒ 「同一主张换个说法」
        #   几乎必落在阈值之下 ⇒ 语义熵退化成「换个说法就算发散」，
        #   读数无信息量（真跑 + 直测共同证实）。池自己的未决语料是
        #   最贴近的尺子，且篇数 < 4 时 BM25 自动降级 ⇒ 不会更差。
        #   ★ 外部显式传 corpus 时逐位覆盖（可负对照）。
        _corpus = corpus
        if _corpus is None:
            _bag = []
            for _sa in (self.undecidable_channel.get("structural_amps")
                        or []):
                _s0 = str(_sa).strip()
                if _s0:
                    _bag.append(_s0)
            for _aa in (self.undecidable_channel.get("aligned_amps")
                        or []):
                _s0 = str(_aa).strip()
                if _s0:
                    _bag.append(_s0)
            for _it0 in self.belief_items:
                _s0 = str(_it0.get("text", "")).strip()
                if _s0:
                    _bag.append(_s0)
                for _oc0 in (_it0.get("occurrences") or []):
                    if isinstance(_oc0, (list, tuple)) and len(_oc0) > 1:
                        _s0 = str(_oc0[1]).strip()
                        if _s0:
                            _bag.append(_s0)
            if _bag:
                _corpus = _bm25_corpus(_bag)
        _out = {}
        for _it in self.belief_items:
            _txt = []
            _seen = set()
            _occs = list(_it.get("occurrences") or [])
''',
    )

    txt = patch(
        txt, "F1d-use-corpus",
        '''            _hn, _h, _cl = semantic_entropy_of(_txt, corpus=corpus, thr=thr)
            _it["semantic_entropy"] = _hn
            _it["semantic_clusters"] = _cl
            _out[_it.get("id", "")] = _hn
        return _out
''',
        '''            _hn, _h, _cl = semantic_entropy_of(_txt, corpus=_corpus,
                                               thr=thr)
            _it["semantic_entropy"] = _hn
            _it["semantic_clusters"] = _cl
            _out[_it.get("id", "")] = _hn
        return _out
''',
    )

    _save(txt)
    txt2, crlf1, lf1 = _load()
    print("[out] CRLF=%d LF=%d  \\r\\r\\n=%d"
          % (crlf1, lf1, open(SRC, "rb").read().count(b"\r\r\n")))
    print("[OK] F1d applied")


if __name__ == "__main__":
    main()
