# -*- coding: utf-8 -*-
"""v1.23.18 变异体：每条判据都要有能把它判红的畸形实现。"""
import re
import sys
import types
from pathlib import Path

HERE = Path(".").resolve()
SMOKE = HERE / "smoke_test.py"
BASE = HERE / "元DGTF-V1.23.18.py"
TMP = HERE / "_audit_tmp"
TMP.mkdir(exist_ok=True)

MUTS = {
    "M1_默认开回退": (
        '        #   既不记 error，也不当成「接失败」。\n        "enabled": True,',
        '        #   既不记 error，也不当成「接失败」。\n        "enabled": False,',
        "check_v12318_anchor_default_on",
    ),
    "M2_干净态记error": (
        '''        if not path:
            # ★ 通道开着但没挂文件 —— **不是错误**：记 error 会让每一次默认
            #   运行都写「⚠️ 接入失败」，把「没挂文件」读成「接失败了」。
            self._anchor_unconfigured = True
            logger.info("外部锚点：已开启但未配置 path（未挂锚点文件）")
            return self._anchors''',
        '''        if not path:
            self._anchor_err = "enabled=True 但没有给 path"
            return self._anchors''',
        "check_v12318_anchor_default_on",
    ),
    "M3_渲染缺未挂态": (
        '''    if isinstance(_ea, dict) and _ea.get("unconfigured"):
        # ★ 四态之「开（未挂文件）」：既不是「关」，也不是「接失败」。
        out.append("**外部锚点 · 文本**（锚点文件 `external_anchor`）："
                   "**开（未挂锚点文件）** —— 把 `external_anchor.path` 指向"
                   "锚点快照 JSON 即自动接入；本次结论只取决于池内材料")
    elif isinstance(_ea, dict):''',
        '''    if False:
        pass
    elif isinstance(_ea, dict):''',
        "check_v12318_anchor_default_on",
    ),
    "M4_明细仍写零行": (
        '''            elif isinstance(_ea, dict) and _ea.get("unconfigured"):
                # ★ 原先这里会写「结论 0 条 / 印证 0 …」**五行零** —— 读者会
                #   以为「对照做过、结果全是 0」。改成一行说明「未做对照」。
                f.write("**锚点对照**：未做 —— 通道开着但**没有挂锚点文件**"
                        "（设 `external_anchor.path` 即接入）\\n\\n")
            elif isinstance(_ea, dict):''',
        '''            elif isinstance(_ea, dict):''',
        "check_v12318_anchor_default_on",
    ),
}

_src = BASE.read_text(encoding="utf-8")
results = []
for tag, (old, new, judge) in MUTS.items():
    n = _src.count(old)
    if n != 1:
        results.append((tag, "锚点命中 %d 次（变异体失效）" % n))
        continue
    mp = TMP / ("mut18_%s.py" % tag.split("_")[0])
    mp.write_bytes(_src.replace(old, new, 1).encode("utf-8"))
    txt = SMOKE.read_text(encoding="utf-8")
    pat = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.18\.py"')
    assert len(pat.findall(txt)) == 1
    txt = pat.sub(lambda _m: 'SRC = Path(r"%s")' % str(mp), txt, count=1)
    m = types.ModuleType("mut18_" + tag)
    m.__file__ = str(SMOKE)
    sys.modules[m.__name__] = m
    exec(compile(txt, str(SMOKE), "exec"), m.__dict__)
    try:
        ok = getattr(m, judge)()
    except Exception as exc:  # noqa: BLE001
        ok = "异常 %s: %s" % (type(exc).__name__, exc)
    results.append((tag, "判红" if ok is False else "★ 没判红（%r）" % ok))

_txt = SMOKE.read_text(encoding="utf-8")
_c = types.ModuleType("ctl18")
_c.__file__ = str(SMOKE)
sys.modules["ctl18"] = _c
exec(compile(_txt, str(SMOKE), "exec"), _c.__dict__)
_ctl = all(getattr(_c, _j)() for _j in {v[2] for v in MUTS.values()})

print("=" * 60)
_bad = 0
for tag, r in results:
    print("[%s] %s" % (r, tag))
    if r != "判红":
        _bad += 1
print("control（原版）:", "判绿" if _ctl else "★ 判红（判据本身有问题）")
print("MUTANTS: %d/%d 判红" % (len(results) - _bad, len(results)))
sys.exit(1 if (_bad or not _ctl) else 0)
