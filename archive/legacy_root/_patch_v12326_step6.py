#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 打补丁 Step6：smoke_test.py 的 SRC 指新版 + 新增 check_v12326_*。

★ smoke_test.py 是纯 LF（不是 CRLF），直接 Edit 即可，但为稳妥仍走脚本。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"

b = SMOKE.read_bytes()
txt = b.decode("utf-8")
_is_crlf = b.count(b"\r\n") > 0
if _is_crlf:
    txt = txt.replace("\r\n", "\n")
print(f"smoke_test.py 换行：{'CRLF' if _is_crlf else 'LF'}  "
      f"(CRLF={b.count(b'chr13chr10')}, LF={b.count(b'chr10')})"
      .replace("chr13chr10", "\\r\\n").replace("chr10", "\\n"))

# ---------- 1) SRC 指新版 ----------
OLD = 'SRC = HERE / "元DGTF-V1.23.25.py"'
NEW = 'SRC = HERE / "元DGTF-V1.23.26.py"'
assert txt.count(OLD) == 1, f"SRC 命中 {txt.count(OLD)} 次"
txt = txt.replace(OLD, NEW, 1)
assert 'SRC = HERE / "元DGTF-V1.23.26.py"' in txt

# ---------- 2) 新增 check_v12326_sim3 ----------
NEW_CHECK = '''

def check_v12326_sim3():
    """[v1.23.26] ① sim3 三级尺子（对称 Jaccard + BM25）修 `_overlap_coef`
       短句高估 ② 池内去重阈值可配（默认 = 旧字面量，行为零变化）
       ③ covers 数字编号分支加语义校验（编号对但语义错必须报红）。

    ★ 每条判据都带**负对照**；判别力另由 `_mut_v12326.py` 的变异体证明
      （没有变异体的「全绿」只说明判据没跑）。
    ★ 判别力夹具（改前 v1.23.25 实测值 / 改后 v1.23.26 实测值）：
      · `_overlap_coef("模型 部署","模型 训练")` = 0.500（虚高）
        `_sim3(同对)` = 0.333（并集分母，不虚高）
      · covers 乱指 T1：改前**不报红**，改后**报红**
      —— 两版结论相反，否则这条夹具等于没测。
    """
    import inspect as _ins
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    cfg = build_cfg(False)

    # ================= A. sim3 修正短句高估 =================
    _a, _b = "模型 部署", "模型 训练"
    _oc = mod._overlap_coef(_a, _b)
    _s3 = mod._sim3(_a, _b)
    if abs(_oc - 0.5) > 1e-9:
        bad.append(f"[A] _overlap_coef 基线漂了：{_oc}（期望 0.5）")
    # ★ 旧尺子虚高：3 词短语共享 1 词 = 1/2
    if _oc < 0.5 - 1e-9:
        bad.append(f"[A] 旧尺子不再虚高（{_oc}）⇒ 这条判据失去意义，"
                   f"请重新设计夹具")
    # ★ 新尺子必须显著低于旧尺子（Jaccard 分母是并集）
    if not (_s3 < _oc - 0.1):
        bad.append(f"[A] _sim3({_s3}) 未显著低于 _overlap_coef({_oc})，"
                   f"短句高估没修好")
    # 对称性：sim3 必须是对称的
    _pairs = [(_a, _b), ("人工智能 模型 部署 管线", "人工智能 模型 部署"),
              ("量子纠缠实验需要极低温", "量子纠缠实验需要低温环境")]
    for _x, _y in _pairs:
        if abs(mod._sim3(_x, _y) - mod._sim3(_y, _x)) > 1e-9:
            bad.append(f"[A] _sim3 不对称：{_x} / {_y}")

    # ================= B. BM25 通道真的在起作用 =================
    _corpus = mod._bm25_corpus(
        ["量子纠缠实验需要极低温环境", "超导材料在低温下表现特殊",
         "人工智能模型部署管线优化", "模型蒸馏可以压缩参数量"])
    if _corpus[3] < 4:
        bad.append(f"[B] 语料只有 {_corpus[3]} 篇，BM25 通道不会启用")
    _no_c = mod._sim3("量子纠缠实验", "超导材料在低温下表现特殊")
    _wi_c = mod._sim3("量子纠缠实验", "超导材料在低温下表现特殊", _corpus)
    # 负对照：不相干对不该因 BM25 而升高
    if _wi_c >= _no_c + 0.2:
        bad.append(f"[B] 不相干对因 BM25 被抬高（{_no_c} -> {_wi_c}）")
    # 正对照：相关对在语料下应 >= 无语料
    _rel_a, _rel_b = "超导材料在低温下表现特殊", "低温下超导材料的特殊表现"
    if mod._sim3(_rel_a, _rel_b, _corpus) < mod._sim3(_rel_a, _rel_b) - 1e-9:
        bad.append("[B] 相关对在 BM25 语料下反而降分")
    # 语料不足时自动降级（N < _BM25_MIN_CORPUS）
    _tiny = mod._bm25_corpus(["只有一个句子"])
    if mod._bm25_best("测试", _tiny) != 0.0:
        bad.append("[B] 语料不足时 BM25 未降级（应返回 0.0）")

    # ================= C. 池内去重阈值可配 =================
    if not hasattr(mod, "_DEDUP_SIM") or not hasattr(mod, "_DEDUP_SUSP_SIM"):
        bad.append("[C] 缺池内去重常量")
    else:
        if mod._DEDUP_SIM != 0.9:
            bad.append(f"[C] _DEDUP_SIM 默认不是 0.9（{mod._DEDUP_SIM}）"
                       f"⇒ 与旧版行为不再一致")
        if mod._DEDUP_SUSP_SIM != 0.85:
            bad.append(f"[C] _DEDUP_SUSP_SIM 默认不是 0.85"
                       f"（{mod._DEDUP_SUSP_SIM}）")
    _sim_cfg = (mod.DEFAULT_CONFIG.get("sim") or {})
    if _sim_cfg.get("dedup") != 0.9 or _sim_cfg.get("dedup_susp") != 0.85:
        bad.append(f"[C] DEFAULT_CONFIG[sim] 不对：{_sim_cfg}")
    # merge 签名必须收 thr / susp_thr
    _sig = _ins.signature(mod.Pool.merge)
    for _k in ("thr", "susp_thr"):
        if _k not in _sig.parameters:
            bad.append(f"[C] Pool.merge 缺参数 {_k}")
    # ★ 行为判据：阈值真的能改行为（同一对文本，thr 不同结论不同）
    _A = "量子纠缠实验需要极低温环境与高精度探测器的配合才能完成验证"
    _B = "量子纠缠实验需要低温环境与高精度探测器的配合才能完成验证工作"
    _p1 = mod.Pool()
    _p1.merge([{"desc": _A}, {"desc": _B}], [], [], thr=0.9)
    _p2 = mod.Pool()
    _p2.merge([{"desc": _A}, {"desc": _B}], [], [], thr=0.99)
    if not (len(_p1.amps) < len(_p2.amps)):
        bad.append(f"[C] thr 改了但结论没变（0.9->{len(_p1.amps)} 条，"
                   f"0.99->{len(_p2.amps)} 条）⇒ 阈值没接上")
    # 默认值 = 旧行为（不传参时与传 0.9 等价）
    _p3 = mod.Pool()
    _p3.merge([{"desc": _A}, {"desc": _B}], [], [])
    if len(_p3.amps) != len(_p1.amps):
        bad.append("[C] 不传参的行为与传 0.9 不一致 ⇒ 默认值没对齐")

    # ================= D. covers 数字分支语义校验 =================
    # ★ 源码层：数字分支里必须出现语义比较（旧版这里是裸 has_touch = True）
    _i = src.find('if (self.entry == "1" and view.untouched and view.probes):')
    _j = src.find("if not has_touch:", _i)
    _body = src[_i:_j] if _i > 0 and _j > _i else ""
    if not _body:
        bad.append("[D] 找不到 covers 判据体")
    else:
        _num = _body.split("if m:", 1)[1].split("else:", 1)[0] if "if m:" in _body else ""
        if not any(_t in _num for _t in ("_similar", "_overlap_coef", "_sim3")):
            bad.append("[D] covers 数字分支里没有语义比较（回退了）")
    # ★ 行为判据（驱动真实方法）：covers 乱指 T1 必须报红
    _CLS = None
    for _c in ("DGTF", "MetaDGTF"):
        if hasattr(mod, _c) and hasattr(getattr(mod, _c), "_quality_check"):
            _CLS = getattr(mod, _c)
            break
    if _CLS is None:
        bad.append("[D] 找不到 DGTF._quality_check")
    else:
        _obj = _CLS.__new__(_CLS)
        _obj.entry = "1"
        _obj.config = dict(mod.DEFAULT_CONFIG)
        _obj.vp = lambda *a, **k: None
        _UT = ["材料在极低温下的超导相变临界温度测量方法",
               "实验装置的电磁屏蔽对测量信噪比的影响",
               "样品制备过程中杂质浓度对结果的可重复性"]

        def _mk(probes):
            _v = mod.View.__new__(mod.View)
            for _n, _d in [("candidates", []), ("amps", []), ("threads", []),
                           ("probes", []), ("errors", []), ("self_check", {}),
                           ("collision", ""), ("engagements", []),
                           ("deferrals", []), ("reconfirmations", []),
                           ("resolutions", []), ("escalations", []),
                           ("reclassifications", []), ("meta", []),
                           ("refinements", []), ("probe_skipped", False)]:
                try:
                    setattr(_v, _n, _d)
                except Exception:
                    pass
            _v.untouched = [{"desc": _t} for _t in _UT]
            _v.probes = probes
            return _v

        def _flags(probes):
            try:
                return _obj._quality_check(_mk(probes), mod.Pool(), 1,
                                           write_diag=False)
            except Exception as _e:
                return ["__驱动失败__:" + type(_e).__name__]

        # 负对照：编号对、语义错 ⇒ 必须报红
        _f1 = _flags([{"question": "披萨需要烤制多长时间才能外脆内软",
                       "covers": ["T1"], "expected_gain": 0.6, "link": "x"}])
        if "probe_no_target_covered" not in _f1:
            bad.append(f"[D] covers 乱指 T1 仍未报红（flags={_f1}）"
                       f"⇒ 语义校验没接上")
        # 正对照：编号对、语义对 ⇒ 不许报红
        _f2 = _flags([{"question": "超导相变临界温度在极低温下如何测量",
                       "covers": ["T1"], "expected_gain": 0.6, "link": "x"}])
        if "probe_no_target_covered" in _f2:
            bad.append(f"[D] covers 正确指向却报红（flags={_f2}）"
                       f"⇒ 校验过严")
        # 负对照：越界编号 ⇒ 报红（旧行为，不能丢）
        _f3 = _flags([{"question": "披萨需要烤制多长时间才能外脆内软",
                       "covers": ["T5"], "expected_gain": 0.6, "link": "x"}])
        if "probe_no_target_covered" not in _f3:
            bad.append(f"[D] 越界编号不再报红（flags={_f3}）")

    if bad:
        for _b2 in bad:
            print(f"  ✗ [v12326] {_b2}")
        return False
    print("  \\u2713 [v12326] sim3 三级尺子（对称 + BM25 可降级）/ "
          "池内阈值可配（默认零变化）/ covers 数字分支语义校验"
          "（负对照：乱指 T1 必报红）")
    return True
'''

# 插到 check_v12324_indep_therapy 定义之前（保持「新的在前」的惯例）
ANCHOR = "def check_v12324_indep_therapy():"
assert txt.count(ANCHOR) == 1
txt = txt.replace(ANCHOR, NEW_CHECK.strip("\\n") + "\\n\\n\\n" + ANCHOR, 1)

# ---------- 3) 注册 ----------
OLD_REG = """    if not check_v12325_struct_coverage():
        return 1
"""
NEW_REG = """    if not check_v12325_struct_coverage():
        return 1
    if not check_v12326_sim3():
        return 1
"""
assert txt.count(OLD_REG) == 1
txt = txt.replace(OLD_REG, NEW_REG, 1)

# ---------- 断言 ----------
assert "def check_v12326_sim3():" in txt
assert "if not check_v12326_sim3():" in txt
assert 'SRC = HERE / "元DGTF-V1.23.26.py"' in txt

out = txt.encode("utf-8")
if _is_crlf:
    out = txt.replace("\n", "\r\n").encode("utf-8")
SMOKE.write_bytes(out)

# 自检
b2 = SMOKE.read_bytes()
assert b2.count(b"\r\r\n") == 0, "smoke_test.py 出现 \\r\\r\\n"
print("OK Step6: smoke SRC -> v1.23.26；新增 check_v12326_sim3 并注册")
print("lines =", b2.count(b"\n"), "bytes =", len(b2))
