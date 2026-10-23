#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.8：smoke_test.py 接线。

  1) SRC → 元DGTF-V1.23.8.py
  2) 新增 `check_v1238_render_guards`（渲染层三处守卫，自带负对照 + 接线断言）
  3) 在 main() 末尾接上守卫

幂等（哨兵盯精确注册串）；smoke_test.py 必须保持纯 CRLF。
"""
import ast
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE / "smoke_test.py"
BAK = HERE / "_bak_smoke_test.pre_v1238"
END_MARK = "# <<<end v123 checks>>>"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
GUARD_RE = re.compile(r'^    if not check_[A-Za-z0-9_]+\(\):\n        return 1\n', re.M)

NEW_CHECK = '''def _v1238_sections(txt):
    """切成 (标题, 该节正文字符数)。「有标题、正文 0 字」= 空节。"""
    import re as _re
    parts = _re.split(r"(?m)^(#{3,4} .*)$", txt)
    out = []
    for _i in range(1, len(parts) - 1, 2):
        out.append((parts[_i].strip(), len(parts[_i + 1].strip())))
    return out


def check_v1238_render_guards():
    """[v1.23.8] 渲染层三处守卫：空节不留空 / 停因上头部 / 悬置渲染去重。

    ★ 负对照全部内置（没有负对照的「全绿」只说明判据没跑）：
      · 空节：无 actions 时不许出现「有标题、正文 0 字」的节，但**三/六两个
        标题必须还在** —— 防「靠删标题消灭空节」（v1.23.8 首版补丁正是这么
        错的，被探针 A1_节数 当场抓到）；有 actions 时行动清单/落地层头不许少。
      · 停因：四层全「体力耗尽」必须报「自然 0 / 被截断 4」且带警示；混合停因
        不许带警示；无停因必须返回空串（不许印 0/0 冒充读数）。
      · 去重：真跑形态（同 target、第二条带「；元层决定不消解。」后缀）必须合并
        成 3 条；**异 target 一条都不许合**；单条输入不许被吞。
      · 接线：三个新函数必须真被 save_result 调到，否则是死代码。
    """
    import inspect as _inspect
    bad = []
    m = globals().get("mod")
    if m is None:
        print("  \\u2717 [v1238] 命名空间里没有 mod")
        return False

    # ── A 空节守卫 ────────────────────────────────────────────
    _r1 = {"orientation": "decision",
           "_config": {"actions": {"landing_decision": True}},
           "views": {}, "decidability": {}}
    _t1 = m.render_landing(_r1)
    _e1 = [x for x, _n in _v1238_sections(_t1) if _n == 0]
    if _e1:
        bad.append("无 actions 时仍有空节：%s" % _e1)
    for _need in ("### 三、所需数据清单", "### 六、如果只能做一件事"):
        if _need not in _t1:
            bad.append("负对照失效：%s 标题被删（不许靠删标题消灭空节）" % _need)
    _r2 = {"orientation": "decision",
           "_config": {"actions": {"landing_decision": True}},
           "views": {"1": {"decidable_product": {
               "answer": "指派 排水公司 核查 内涝点位，汛期前完成，"
                         "否则回退人工排查。"}}},
           "decidability": {}}
    _t2 = m.render_landing(_r2)
    if "### 二、行动清单" not in _t2:
        bad.append("有 actions 时行动清单段缺失")
    if "落地层（decision 模式）" not in _t2:
        bad.append("有 actions 时落地层头缺失")
    _e2 = [x for x, _n in _v1238_sections(_t2) if _n == 0]
    if _e2:
        bad.append("有 actions 时仍有空节：%s" % _e2)

    # ── B 停因上头部 ──────────────────────────────────────────
    _cut = ("体力耗尽（1 圈走满，未触发任何停止判据，是被截断不是自然停止）")
    if not hasattr(m, "_stop_kind_summary"):
        bad.append("缺 _stop_kind_summary")
    else:
        _s4 = m._stop_kind_summary(
            {k: {"stop_reason": _cut} for k in ("0", "1", "both", "all")})
        if "自然 0" not in _s4 or "被截断（体力耗尽）4" not in _s4 \\
                or "\\u26a0" not in _s4:
            bad.append("四层全被截断的读数不对：%r" % _s4)
        _s1 = m._stop_kind_summary({
            "0": {"stop_reason": _cut},
            "1": {"stop_reason": "连续 2 轮无新 &，螺旋停止"}})
        if "自然 1" not in _s1 or "被截断（体力耗尽）1" not in _s1 \\
                or "\\u26a0" in _s1:
            bad.append("混合停因读数不对（不该带「无一层自然收敛」警示）：%r" % _s1)
        if m._stop_kind_summary({}) != "" or m._stop_kind_summary({"0": {}}) != "":
            bad.append("无停因时必须返回空串（不许印 0/0 冒充读数）")

    # ── C 悬置渲染去重 ────────────────────────────────────────
    if not hasattr(m, "_dedup_suspensions_for_render"):
        bad.append("缺 _dedup_suspensions_for_render")
    else:
        _it = [
            {"target": "用途场景未显形，精度三档无判据", "reason": "r1"},
            {"target": "用途场景未显形，精度三档无判据；元层决定不消解。",
             "reason": "r2"},
            {"target": "日期同压事件发生与被命名，分离口缺席", "reason": "r3"},
            {"target": "日期同压事件发生与被命名，分离口缺席；元层决定不消解。",
             "reason": "r4"},
            {"target": "共同纲领、政府成立、开国大典效力层级排序", "reason": "r5"},
        ]
        _k, _d = m._dedup_suspensions_for_render(_it)
        if len(_k) != 3 or _d != 2:
            bad.append("真跑形态去重结果不对：保留 %d / 合并 %d（期望 3 / 2）"
                       % (len(_k), _d))
        _k2, _d2 = m._dedup_suspensions_for_render(
            [{"target": "甲甲甲甲甲甲"}, {"target": "乙乙乙乙乙乙"}])
        if len(_k2) != 2 or _d2 != 0:
            bad.append("负对照：异 target 被误合并（保留 %d / 合并 %d）"
                       % (len(_k2), _d2))
        _k3, _d3 = m._dedup_suspensions_for_render([{"target": "丙丙丙丙丙丙"}])
        if len(_k3) != 1 or _d3 != 0:
            bad.append("负对照：单条输入被吞（保留 %d / 合并 %d）"
                       % (len(_k3), _d3))
        if hasattr(m, "_susp_key"):
            if m._susp_key("甲甲甲甲") != "甲甲甲甲":
                bad.append("_susp_key 对短 target 应退回全长")
            if m._susp_key("甲甲甲甲甲甲；尾") != "甲甲甲甲甲甲":
                bad.append("_susp_key 应取首个分句")

    # ── 接线断言（防死代码）────────────────────────────────────
    _ss = _inspect.getsource(m.save_result)
    if "_stop_kind_summary(" not in _ss:
        bad.append("_stop_kind_summary 没被 save_result 调用（死代码）")
    if "_dedup_suspensions_for_render(" not in _ss:
        bad.append("_dedup_suspensions_for_render 没被 save_result 调用（死代码）")

    if bad:
        for _m in bad:
            print("  \\u2717 [v1238] %s" % _m)
        return False
    print("  \\u2713 [v1238] 空节守卫(三/六+负对照) / 停因汇总(3 读数) / "
          "悬置去重(真跑形态 3+2、异 target 不合) / 三处接线均在")
    return True


'''


def main():
    raw = SK.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
    s = raw.decode("utf-8").replace("\r\n", "\n")

    n = len(SRC_RE.findall(s))
    assert n == 1, "SRC 行命中 %d 次" % n
    s = SRC_RE.sub('SRC = HERE / "元DGTF-V1.23.8.py"', s, count=1)
    print("SRC → 元DGTF-V1.23.8.py")

    if "def check_v1238_render_guards" in s:
        print("[skip] v1238 判据已存在")
    else:
        k = s.rindex(END_MARK)
        s = s[:k] + NEW_CHECK + s[k:]
        print("已插入 check_v1238_render_guards")

    if "if not check_v1238_render_guards():" in s:
        print("[skip] 守卫已存在")
    else:
        hits = list(GUARD_RE.finditer(s))
        n_before = len(hits)
        assert n_before >= 95, "守卫只有 %d 条（基线 95）" % n_before
        pos = hits[-1].end()
        s = s[:pos] + "    if not check_v1238_render_guards():\n        return 1\n" + s[pos:]
        n_after = len(GUARD_RE.findall(s))
        assert n_after == n_before + 1, "守卫 %d -> %d" % (n_before, n_after)
        print("守卫 %d -> %d" % (n_before, n_after))

    if not BAK.exists():
        shutil.copy2(SK, BAK)
        print("回滚点：%s" % BAK.name)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
    SK.write_bytes(out)
    c = SK.read_bytes()
    ast.parse(c.decode("utf-8").replace("\r\n", "\n"))
    print("smoke_test.py：%d 字节 / %d 行 / CRLF=%d 裸LF=%d CRCRLF=%d；ast OK"
          % (len(c), c.count(b"\n"), c.count(b"\r\n"),
             c.count(b"\n") - c.count(b"\r\n"), c.count(b"\r\r\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
