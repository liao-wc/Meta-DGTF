# -*- coding: utf-8 -*-
"""v1.23.28 smoke_test 升级：D3 判据随实现更新（R2/R3 之后）。

## 为什么必须改这条判据（不是放宽阈值）

`check_v12328_real_entry` 里原有一条：

    _it0 = (_p.belief_items or [{}])[0]
    if _it0.get("semantic_entropy") is None:
        bad.append("[R-D3] 真实入口后 semantic_entropy 仍为 None ...")

它的隐含前提是「两条**不同**主张 ⇒ 熵有值」—— 那是 **R1/r2 版**（把
全池文本混在一起算）的语义。**R3 重新设计后语义变了**：熵度量的是
「**同一条主张**的历次说法有多发散」⇒ 两条**无关**主张各只有自己一种
说法 ⇒ 正确读数就是 `None`（诚实缺省），不是缺陷。

⇒ 这条判据**不是**「真回归」，是**判据过时**。按项目通则「判据随实现
   更新，不是放宽阈值」：把它改成能**分辨**「接线了」与「没接线」的形态：

  · 正例：同一主张的**两种近义说法**（换说法 ⇒ 两条目）⇒ 必须聚成
    一簇 ⇒ `semantic_entropy == 0.0`（**不是 None**）。这**构造性地**
    证明：D3 有值、聚类真的发生、阈值真的可达成。
  · 负对照 1：单条主张 ⇒ 必须 `None`（不许印 0.0 冒充「很稳」）。
  · 负对照 2：把池的 `sem_entropy_thr` 拨回 0.70（旧错值）⇒ 同一组
    近义说法**必须**退化成 `None`（证阈值**真接线**，不是摆设）。
  · 出口：`occurrence_n` 与 `semantic_clusters` 必须落盘。

★ 判别力由 `_mut_v12328.py` 的 D3 变异体背书（打在本判据读的那个东西上）。
★ 铁律：锚点断言命中 == 1；read_bytes/write_bytes；纯 CRLF。
"""
SRC = "smoke_test.py"


def _load(path=SRC):
    b = open(path, "rb").read()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n") - crlf
    assert crlf > 0, "smoke_test.py 必须是 CRLF"
    assert lf == 0, "smoke_test.py 混入裸 LF %d 处" % lf
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


OLD_D3 = '''    # ── D3 真实入口：语义熵落盘有值 ────────────────────────
    _it0 = (_p.belief_items or [{}])[0]
    if _it0.get("semantic_entropy") is None:
        bad.append("[R-D3] 真实入口后 semantic_entropy 仍为 None"
                   "（D3 未接线；两条不同主张时不该是 None）")
'''

NEW_D3 = '''    # ── D3 真实入口：语义熵**真的量出「同一主张的说法发散度」** ───
    # ★ 语义（R3 重新设计）：熵度量的是「**同一条主张**的历次说法有多
    #   发散」。两条**无关**主张各只有自己一种说法 ⇒ 正确读数就是
    #   `None`（诚实缺省），**不是**「未接线」。所以本判据改用
    #   「同一主张的两种近义说法」构造：换说法 ⇒ 两条目 ⇒ 必须聚成
    #   一簇 ⇒ 熵 **0.0**（不是 None）。这构造性地证明三件事同时成立：
    #     ① D3 真的算出值；② 聚类真的发生；③ 阈值真的可达成。
    _pd = mod.Pool()
    _pd.sem_entropy_thr = float(getattr(mod, "_SEM_CLUSTER_THR", 0.30))
    _pd.upsert_belief("落盘的最小单位是约束", ground="layer1", round_no=1,
                      sources=["layer1"])
    _pd.upsert_belief("落盘的最小单位是那条约束", ground="layer0",
                      round_no=2, sources=["layer0"])
    _pd.refresh_belief_entropy(thr=_pd.sem_entropy_thr)
    _ed = [(it.get("id"), it.get("occurrence_n"),
            it.get("semantic_entropy")) for it in _pd.belief_items]
    _ok_pairs = [e for e in _ed if e[1] and e[1] >= 2]
    if not _ok_pairs:
        bad.append("[R-D3] 同一主张的两种近义说法未聚成一簇"
                   "（occurrence_n 全 < 2；读数=%r）—— D3 未接线或阈值"
                   "不可达成" % (_ed,))
    elif not all(e[2] is not None and e[2] <= 0.05 for e in _ok_pairs):
        bad.append("[R-D3] 同一主张近义说法应近 0 熵（实为 %r）"
                   "—— 聚类未发生或口径错" % (_ed,))
    # 负对照 1：单条主张 ⇒ 必须 None（不许印 0.0 冒充「很稳」）
    _pd2 = mod.Pool()
    _pd2.upsert_belief("只出现一次的主张", ground="layer1", round_no=1,
                       sources=["layer1"])
    _pd2.refresh_belief_entropy(thr=_pd2.sem_entropy_thr)
    if _pd2.belief_items and _pd2.belief_items[0].get(
            "semantic_entropy") is not None:
        bad.append("[R-D3-neg1] 单条主张应返回 None（实为 %r）—— "
                   "印 0.0 是自欺"
                   % (_pd2.belief_items[0].get("semantic_entropy"),))
    # 负对照 2：阈值拨回旧错值 0.70 ⇒ 同一组近义说法必须退化成 None
    #   （证 `sem_entropy_thr` **真接线**，不是只在 DEFAULT_CONFIG 里挂着）
    _pd3 = mod.Pool()
    _pd3.sem_entropy_thr = 0.70
    _pd3.upsert_belief("落盘的最小单位是约束", ground="layer1", round_no=1,
                       sources=["layer1"])
    _pd3.upsert_belief("落盘的最小单位是那条约束", ground="layer0",
                      round_no=2, sources=["layer0"])
    _pd3.refresh_belief_entropy(thr=_pd3.sem_entropy_thr)
    _ed3 = [it.get("occurrence_n") for it in _pd3.belief_items]
    if any(n and n >= 2 for n in _ed3):
        bad.append("[R-D3-neg2] thr=0.70 时近义说法竟仍聚成一簇"
                   "（occurrence_n=%r）—— 阈值未接线或聚类不受 thr 影响"
                   % (_ed3,))
    # 出口：occurrence_n 与 semantic_clusters 必须落盘
    if _ok_pairs and not all("semantic_clusters" in it
                             for it in _pd.belief_items):
        bad.append("[R-D3-out] 信念条目缺 semantic_clusters 出口")
    # 池级出口：belief_items 里的 occurrence_n 必须能经 to_dict 读到
    _dd = _pd.to_dict()
    _bi_out = _dd.get("belief_items") or []
    if _bi_out and not all("semantic_entropy" in x for x in _bi_out):
        bad.append("[R-D3-out] 池级 belief_items 出口缺 semantic_entropy")
'''


def main():
    txt, crlf0, lf0 = _load()
    print("[in] CRLF=%d LF=%d" % (crlf0, lf0))

    txt = patch(txt, "D3-judge", OLD_D3, NEW_D3)

    # 收尾汇总行补一句（说明判据已升级）
    txt = patch(
        txt, "tail",
        '''    print("  \\u2713 [v12328] 真实入口产出（跨层 stable / attack revoked / "
          "清偿 resolved / 同层负对照 0）· 池级出口 · D3 落盘 · "
          "A3 出口 · gain_source（6 变异体背书）")
''',
        '''    print("  \\u2713 [v12328] 真实入口产出（跨层 stable / attack revoked / "
          "清偿 resolved / 同层负对照 0）· 池级出口 · D3 语料自供+阈值"
          "解耦（近义聚簇 / 单条 None / thr 负对照）· "
          "A3 出口 · gain_source（变异体背书）")
''',
    )

    _save(txt)
    _, crlf1, lf1 = _load()
    print("[out] CRLF=%d LF=%d  \\r\\r\\n=%d"
          % (crlf1, lf1, open(SRC, "rb").read().count(b"\r\r\n")))
    print("[OK] smoke D3 judge upgraded")


if __name__ == "__main__":
    main()
