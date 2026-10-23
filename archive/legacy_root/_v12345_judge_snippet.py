def check_v12345_output_rep():
    """[v1.23.45 · P-4] **输出内**逐字复读率读数（补集合式 n-gram 信号的结构盲区）。

    ★ 依据：Reflective Budget Governor 实测「集合式 trigram 对输出内逐字复读结构盲」。
    ★ 判据：① 高度复读文本 ⇒ 比值高（近 1）；② 全新鲜文本 ⇒ 比值 0；
      ③ 太短 / 空 ⇒ **None**（不表态）；④ 读数**有出口**（两个标签表 + `_quant_note` 接线）。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for tok in ("def output_repetition(text: str",
                "_OUTREP_N = 3",
                '_quant_note(view, "output_repetition"',
                '("output_repetition", "内复读")',
                '"output_repetition": "输出内复读率"'):
        if tok not in src:
            bad.append("[P4] 源码缺：%s" % tok)

    R = mod.output_repetition
    # ① 高度复读 ⇒ 高
    _rep = "甲" * 60
    _rv = R(_rep)
    if _rv is None or _rv < 0.8:
        bad.append("[P4] 全同文本复读率应接近 1：%r" % (_rv,))
    # 段间重复（灾难性退化的形态：同一段重复多遍）
    _dup = ("这是一段会重复的话，用来模拟输出内的逐字复读。" * 8)
    _dv = R(_dup)
    if _dv is None or _dv < 0.6:
        bad.append("[P4] 段间重复竟没测出来：%r" % (_dv,))
    # ② 全新鲜 ⇒ 0
    _fresh = "".join("甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥"
                     "[%d]" % i for i in range(6))
    _fv = R(_fresh)
    if _fv is None or _fv > 0.05:
        bad.append("[P4] 全新鲜文本复读率应≈0：%r" % (_fv,))
    # ③ 太短/空 ⇒ None
    if R("") is not None:
        bad.append("[P4] 空文本竟给值（应 None）")
    if R("短") is not None:
        bad.append("[P4] 过短文本竟给值（应 None）")

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.45 P4 输出内复读率（全同≈1 · 段间重复>0.6 · 全新鲜≈0 · 短/空=None · "
          "两标签表+接线在源码）全过")
    return True
