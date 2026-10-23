#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.10：smoke_test.py 接线。
  1) SRC → 元DGTF-V1.23.10.py
  2) `check_v67_full_appendix` 整函数替换：取源支持「内联 / 旁挂」两路，
     判据意图一字未改；并修一个真 bug（旁挂文件读在 with 块外 ⇒ 目录已删）
  3) 新增 `check_v12310_render_ops`（四项一次验收，自带负对照 + 接线断言）
  4) 在 main() 末尾接上守卫
幂等；smoke_test.py 必须保持纯 CRLF。
"""
import ast
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE / "smoke_test.py"
BAK = HERE / "_bak_smoke_test.pre_v12310"
END_MARK = "# <<<end v123 checks>>>"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
GUARD_RE = re.compile(r'^    if not check_[A-Za-z0-9_]+\(\):\n        return 1\n', re.M)

NEW_V67 = '''def check_v67_full_appendix():
    """[v1.21.67；v1.23.10 改取源] 产物 md 的「全量字段」附录：必须**机械全量**。

    ★ v1.23.10：全量 JSON 默认**外置**到旁挂 `<产物名>.packed.json`
      （`--appendix inline` 回旧行为）。判据意图**一字未改** —— 仍是
      「不得因为没写渲染点就丢信息」；改的是**取源**：内联的 ```json 块
      与旁挂文件两路都要能取到同一份 packed。
    ★ 断言特意塞一个**正文绝无渲染点**的深层内部量（`_probe_only_internal`），
      用它区分「机械全量」和「又挑了一批字段渲染」。
    ★ 顺带修一个真 bug：旁挂文件必须在 `with TemporaryDirectory()` **块内**
      读完 —— 出了块目录就没了，症状是「文件不存在」而不是「内容不对」。
    """
    import tempfile
    import re
    import json
    fake = {
        "question": "测试题", "route": ["1"], "keep": {"1": "all"},
        "rounds": {"1": 1},
        "dispatch": {"_parallel_mode": "serial", "order": ["1"],
                     "requested": ["1"], "skipped": []},
        "views": {"1": {}},
        "pools": {"1": {"amps": [], "threads": [], "probes": [],
                        "suspensions": [], "meta": [],
                        "sub_questions": [{"id": "s1",
                                           "_starve_rounds": 0,
                                           "_starve_max_seen": 0}],
                        "deferrals": []}},
        "llm_calls": 1, "llm_tokens": 1,
        "decidability": {"decidability": "decidable"},
        "channels": ["content"], "cost_profile": "balanced",
        "orientation": "auto", "tri_state": [0, 0],
        "_probe_only_internal": {"deep": {"x": 7}},
    }
    _side_raw = None
    try:
        with tempfile.TemporaryDirectory() as td:
            md = mod.save_result(fake, save_dir=td)
            content = md.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
            _sm = re.search(r"```text\\n(\\S+\\.packed\\.json)\\n```", content)
            if _sm:
                _sp = md.parent / _sm.group(1)
                if _sp.is_file():
                    _side_raw = _sp.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  ✗ [v67] 渲染失败: {type(e).__name__}: {e}")
        return False
    checks = [
        ("## 附录 · 全量字段（packed 原文）" in content, "缺附录标题"),
        ("```json" in content or ".packed.json" in content,
         "缺 JSON（内联与旁挂都没有）"),
        ("叶子路径" in content and "JSON " in content, "缺完整性统计行"),
    ]
    bad = [m for c, m in checks if not c]
    if bad:
        for m in bad:
            print(f"  ✗ [v67] {m}")
        return False
    if "```json" in content:
        _mm = re.search(r"```json\\n(.*?)\\n```", content, re.S)
        _raw = _mm.group(1) if _mm else None
    else:
        _raw = _side_raw
    if _raw is None:
        print("  ✗ [v67] 正文既无内联 json 块，也读不到旁挂文件")
        return False
    try:
        packed = json.loads(_raw)
    except Exception as e:
        print(f"  ✗ [v67] 全量 JSON 不可解析: {type(e).__name__}: {e}")
        return False
    if set(packed) != set(fake):
        print(f"  ✗ [v67] 附录顶层键不全，缺 {sorted(set(fake) - set(packed))}")
        return False
    # ★ 只活在 packed 里、正文绝无渲染点的内部量，也必须出现
    if ((packed.get("_probe_only_internal") or {}).get("deep") or {}).get("x") != 7:
        print("  ✗ [v67] 正文无渲染点的内部量没进附录（机械全量失效）")
        return False
    print("  ✓ [v67] 全量附录：顶层键齐全、无渲染点的内部量也在、JSON 可解析")
    return True
'''

NEW_CHECK = '''def check_v12310_render_ops():
    """[v1.23.10] 渲染层四项一次验收：形态声明 / 附录外置 / 成本自动档 / 未校验留痕。

    ★ 负对照全部内置（没有负对照的「全绿」只说明判据没跑）：
      · 形态声明：boundary 与 decision 两套模板各出一次、各自写明模板名；
        不传 question 时不许崩。
      · 附录**两向对账**：`file` 模式正文不得有 json 块且旁挂文件必须可解析、
        顶层键 == 输入、无渲染点的内部量仍在；`inline` 模式正文必须有 json 块
        且不得留旁挂文件。
      · 成本档：事实题 → economy、决策题 → balanced；argparse 必须收 auto。
      · 未校验留痕：事实题产物须写明「未接入外部校验」与 `--web on`；
        **决策题不许出现这句**。接线：save_result 里真调了 `_appendix_to_file`。
    """
    import json as _json
    import tempfile as _tf
    import inspect as _ins
    bad = []

    def _fake(q, mode):
        return {
            "question": q, "route": ["1"], "keep": {"1": "all"},
            "rounds": {"1": 1},
            "dispatch": {"_parallel_mode": "serial", "order": ["1"],
                         "requested": ["1"], "skipped": []},
            "views": {"1": {}},
            "pools": {"1": {"amps": [], "threads": [], "probes": [],
                            "suspensions": [], "meta": [],
                            "sub_questions": [], "deferrals": []}},
            "llm_calls": 1, "llm_tokens": 1,
            "decidability": {"decidability": "decidable"},
            "channels": ["content"], "cost_profile": "balanced",
            "orientation": "auto", "tri_state": [0, 0],
            "_probe_only_internal": {"deep": {"x": 7}},
            "_config": {"actions": {"landing_decision": True,
                                    "appendix_mode": mode}},
        }

    _FACT = "新中国的成立时间是什么时候"
    _DEC = "这份方案怎么落地"

    # ── R1 形态声明（两套模板各出一次）────────────────────────
    _b = mod.render_landing({"orientation": "boundary",
                             "_config": {"actions": {}}, "views": {},
                             "decidability": {}, "question": _FACT})
    _d = mod.render_landing({"orientation": "decision",
                             "_config": {"actions": {"landing_decision": True}},
                             "views": {}, "decidability": {}, "question": _DEC})
    _bh = "\\n".join(_b.split("\\n")[:4])
    _dh = "\\n".join(_d.split("\\n")[:4])
    if "**形态声明**" not in _bh or "boundary" not in _bh:
        bad.append("boundary 模板缺形态声明（或没写明模板名）")
    if "**形态声明**" not in _dh or "decision" not in _dh:
        bad.append("decision 模板缺形态声明（或没写明模板名）")
    if not _b.startswith("## "):
        bad.append("形态声明把落地层标题挤出了首行（md 结构被破坏）")
    try:
        mod.render_landing({"orientation": "auto", "_config": {"actions": {}},
                            "views": {}, "decidability": {}})
    except Exception as e:
        bad.append("缺 question 键时 render_landing 崩了：%r" % e)

    # ── R8 附录两向对账（旁挂内容必须在 with 块内读完）────────
    _mode = {}
    for _m in ("file", "inline"):
        with _tf.TemporaryDirectory() as td:
            p = mod.save_result(_fake(_FACT, _m), save_dir=td)
            _c = p.read_text(encoding="utf-8")
            _raws = [q.read_text(encoding="utf-8")
                     for q in sorted(p.parent.glob("*.packed.json"))]
            _mode[_m] = (_c, _raws)
    _cf, _sf = _mode["file"]
    _ci, _si = _mode["inline"]
    if "```json" in _cf:
        bad.append("file 模式正文里仍有内联 json 块")
    if len(_sf) != 1:
        bad.append("file 模式没有产出唯一的旁挂文件（得 %d 个）" % len(_sf))
    else:
        try:
            _pk = _json.loads(_sf[0])
            if set(_pk) != set(_fake(_FACT, "file")):
                bad.append("旁挂文件顶层键不全")
            if (((_pk.get("_probe_only_internal") or {}).get("deep")
                    or {}).get("x")) != 7:
                bad.append("旁挂文件丢了「正文无渲染点」的内部量（红线破了）")
        except Exception as e:
            bad.append("旁挂文件不可解析：%r" % e)
    if "```json" not in _ci:
        bad.append("inline 模式正文里没有内联 json 块（旧行为没保住）")
    if _si:
        bad.append("inline 模式不该产出旁挂文件")

    # ── R9 成本档自动路由 ────────────────────────────────────
    if not hasattr(mod, "_auto_profile"):
        bad.append("缺 _auto_profile")
    else:
        if mod._auto_profile(_FACT) != "economy":
            bad.append("事实题应自动选 economy（实得 %r）" % mod._auto_profile(_FACT))
        if mod._auto_profile(_DEC) != "balanced":
            bad.append("决策题应自动选 balanced（实得 %r）" % mod._auto_profile(_DEC))
    if '"auto", "quality", "balanced", "economy"' not in SRC.read_text(
            encoding="utf-8"):
        bad.append("--profile 的 choices 里没有 auto")

    # ── R10 未校验留痕（只对事实题）──────────────────────────
    if "未接入外部校验" not in _cf or "--web on" not in _cf:
        bad.append("事实题产物没有「未接入外部校验 + --web on」留痕")
    with _tf.TemporaryDirectory() as td:
        _cd = mod.save_result(_fake(_DEC, "file"), save_dir=td).read_text(
            encoding="utf-8")
    if "未接入外部校验" in _cd:
        bad.append("决策题不该出现「未接入外部校验」留痕")

    # ── 接线 ────────────────────────────────────────────────
    if "_appendix_to_file(" not in _ins.getsource(mod.save_result):
        bad.append("_appendix_to_file 没被 save_result 调用（死代码）")

    if bad:
        for _m in bad:
            print("  \\u2717 [v12310] %s" % _m)
        return False
    print("  \\u2713 [v12310] 形态声明(boundary+decision) / 附录两向对账(外置+内联) / "
          "成本档规则(事实 economy·决策 balanced) / 未校验留痕(仅事实题) / 接线在")
    return True


'''


def main():
    raw = SK.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
    s = raw.decode("utf-8").replace("\r\n", "\n")

    n = len(SRC_RE.findall(s))
    assert n == 1, "SRC 行命中 %d 次" % n
    s = SRC_RE.sub('SRC = HERE / "元DGTF-V1.23.10.py"', s, count=1)
    print("SRC → 元DGTF-V1.23.10.py")

    if "两路都要能取到同一份 packed" in s:
        print("[skip] v67 已改")
    else:
        i = s.index("def check_v67_full_appendix():")
        j = s.index("    return True", i)
        j = s.index("\n", j)
        s = s[:i] + NEW_V67 + s[j + 1:]
        print("已整函数替换 check_v67_full_appendix（内联 / 旁挂两路）")

    if "def check_v12310_render_ops" in s:
        print("[skip] v12310 判据已存在")
    else:
        k = s.rindex(END_MARK)
        s = s[:k] + NEW_CHECK + s[k:]
        print("已插入 check_v12310_render_ops")

    if "if not check_v12310_render_ops():" in s:
        print("[skip] 守卫已存在")
    else:
        hits = list(GUARD_RE.finditer(s))
        n_before = len(hits)
        assert n_before >= 97, "守卫只有 %d 条（基线 97）" % n_before
        pos = hits[-1].end()
        s = s[:pos] + "    if not check_v12310_render_ops():\n        return 1\n" + s[pos:]
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
    print("smoke_test.py：%d 字节 / %d 行；ast OK" % (len(c), c.count(b"\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
