# -*- coding: utf-8 -*-
"""[v1.21.73 前置探针] 「外部锚点」通道的改前 / 改后基线。

为什么单写一支：v1.21 重写后 `web_search` / `external_facts` 是 0 处引用，
产物里那句「外部锚点：无」是**写死的承认**，不是开关。要接真锚点，先得把
「现在到底有没有通道」量出来，而不是照着外部清单改。

用法（改前改后同一支，跑两次对表）：
    python _probe_v73_anchor.py 元DGTF-V1.21.72.py before
    python _probe_v73_anchor.py 元DGTF-V1.21.73.py after

量什么：
  [1] 源码形态：抠掉 docstring 后数锚点相关形态的引用次数
      （★ 不抠会在 changelog 里数到"文档里的代码"，是本项目踩过的坑）
  [2] 配置：DEFAULT_CONFIG / load_config 后有没有 external_anchor 段
  [3] 签名：_assess_decidability 能不能收 anchors
  [4] prompt：mock 跑一次，抓 assess_decidability 这一 stage 实际发出去的
      system 长度与关键串（生产入口，不手造）
  [5] 产物：packed 顶层键集合、decidability 字段集合、md 里「外部锚点」
      出现次数与上下文
"""
from __future__ import annotations

import importlib.util
import inspect
import io
import json
import os
import re
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("DGTF_API_KEY", "sk-probe-key")

TARGET = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else \
    HERE / "元DGTF-V1.21.72.py"
TAG = sys.argv[2] if len(sys.argv) > 2 else "before"
OUT = HERE / f"_probe_v73_anchor_{TAG}.txt"

LINES: list[str] = []


def w(s=""):
    LINES.append(s)
    print(s)


def hr(t):
    w()
    w("─" * 60)
    w(t)
    w("─" * 60)


# ---------------------------------------------------------------- 加载
def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


mod = load(TARGET, "dgtf73probe")

hr(f"[0] 目标：{TARGET.name}   tag={TAG}")
w(f"    __version__ = {getattr(mod, '__version__', '?')}")

# ---------------------------------------------------------------- [1] 源码形态
hr("[1] 源码形态（抠掉 docstring 后数）")
raw = TARGET.read_bytes().decode("utf-8")
assert raw.count("\r\n") == raw.count("\n"), "主文件不是纯 CRLF"
doc = mod.__doc__ or ""
norm = raw.replace("\r\n", "\n")
assert doc.replace("\r\n", "\n") in norm, "docstring 归一化后仍不在源码里"
code = norm.replace(doc.replace("\r\n", "\n"), "", 1)
w(f"    全文 {len(norm)} 字符 → 抠掉 docstring 后 {len(code)} 字符"
  f"（必须变短，自证抠法有效）")
FORMS = ["external_anchor", "_load_anchors", "_anchor_crosscheck",
         "anchor_refs", "anchors=", "def _anchor"]
for f in FORMS:
    w(f"    {f:<22} 全文={norm.count(f):<4} 抠文档后={code.count(f)}")

# ---------------------------------------------------------------- [2] 配置
hr("[2] 配置键")
cfg_default = getattr(mod, "DEFAULT_CONFIG", {}) or {}
w(f"    DEFAULT_CONFIG 顶层键({len(cfg_default)}): "
  f"{sorted(cfg_default.keys())}")
w(f"    DEFAULT_CONFIG 有 external_anchor: "
  f"{'external_anchor' in cfg_default}")
yaml_path = HERE / "dgtf_config.yaml"
if yaml_path.exists():
    ytxt = yaml_path.read_text(encoding="utf-8")
    w(f"    dgtf_config.yaml 里 external_anchor 出现次数: "
      f"{ytxt.count('external_anchor')}")

# ---------------------------------------------------------------- [3] 签名
hr("[3] 函数签名")
for cls_name, fname in (("DGTF", "_assess_decidability"),
                        ("MetaDGTF", "_load_anchors"),
                        ("MetaDGTF", "_anchor_crosscheck")):
    cls = getattr(mod, cls_name, None)
    fn = getattr(cls, fname, None) if cls else None
    if fn is None:
        w(f"    {cls_name}.{fname:<24} 不存在")
        continue
    sig = inspect.signature(fn)
    w(f"    {cls_name}.{fname:<24} {sig}")

# ---------------------------------------------------------------- [4][5] 生产跑
hr("[4][5] 生产跑（smoke harness 打桩，route 0,1 × 1 圈）")
SMOKE = HERE / "smoke_test.py"
_src = SMOKE.read_text(encoding="utf-8")
_pat = re.compile(r'SRC = HERE / "元DGTF-V1\.21\.\d+\.py"')
hits = _pat.findall(_src)
assert len(hits) == 1, f"SRC 行不是 1 处：{hits}"
_src = _pat.sub('SRC = Path(r"%s")' % str(TARGET).replace("\\", "\\\\"), _src)
_hm = types.ModuleType("harness73")
_hm.__file__ = str(SMOKE)
sys.modules["harness73"] = _hm
buf = io.StringIO()
_stdout = sys.stdout
try:
    sys.stdout = buf
    exec(compile(_src, str(SMOKE), "exec"), _hm.__dict__)
finally:
    sys.stdout = _stdout
hm = _hm
w(f"    harness 加载完毕，mod 来自 {hm.mod.__name__}")

SEEN: list[dict] = []
_orig_call = hm.mod.LLM.call


def spy_call(self, system, user, *a, **kw):
    SEEN.append({"stage": kw.get("stage"),
                 "sys_len": len(system or ""),
                 "sys_has_anchor": "锚点" in (system or ""),
                 "sys_head": (system or "")[:40].replace("\n", " ")})
    return _orig_call(self, system, user, *a, **kw)


hm.mod.LLM.call = spy_call

tmpdir = tempfile.mkdtemp(prefix="v73probe_")
cfg = hm.build_cfg(True)
cfg["output"]["save_dir"] = tmpdir
QUESTION = "现金流紧张的中小制造企业，上自动化产线还是维持人工加局部优化？怎么决策？"
meta = hm.mod.MetaDGTF(cfg)
try:
    packed = meta.run(QUESTION, route=["0", "1"], rounds={"0": 1, "1": 1},
                      parallel_mode="serial")
except Exception as exc:  # 探针不吞错，但要能看清
    import traceback
    w("    run 异常：\n" + traceback.format_exc())
    packed = None

if packed is not None:
    w(f"    llm_calls={packed['llm_calls']} tokens={packed['llm_tokens']}")
    w(f"    packed 顶层键({len(packed)}): {sorted(packed.keys())}")
    w(f"    有 external_anchor 键: {'external_anchor' in packed}")
    dec = packed.get("decidability") or {}
    w(f"    decidability 字段({len(dec)}): {sorted(dec.keys())}")
    w(f"    decidability 值: {json.dumps({k: v for k, v in dec.items() if not str(k).startswith('_')}, ensure_ascii=False)[:300]}")
    w(f"    _source={dec.get('_source')} _divergent={dec.get('_divergent')}")

    # assess 这一 stage 的实际 prompt
    assess = [s for s in SEEN if s["stage"] == "assess_decidability"]
    w(f"    stage=assess_decidability 调用次数: {len(assess)}")
    for i, s in enumerate(assess[:4], 1):
        w(f"      #{i} sys_len={s['sys_len']} 含「锚点」={s['sys_has_anchor']}"
          f" head={s['sys_head'][:30]}")

    # 产物 md
    try:
        md_path = hm.mod.save_result(packed, tmpdir)
        mdtxt = Path(md_path).read_text(encoding="utf-8")
        w(f"    产物 {Path(md_path).name}  {len(mdtxt)} 字符")
        w(f"    md 里「外部锚点」出现次数: {mdtxt.count('外部锚点')}")
        for m in re.finditer(r".{0,60}外部锚点.{0,80}", mdtxt):
            w(f"      · …{m.group(0)}…")
        w(f"    md 里「anchor」出现次数: {mdtxt.count('anchor')}")
    except Exception:
        import traceback
        w("    save_result 异常：\n" + traceback.format_exc())

OUT.write_text("\n".join(LINES) + "\n", encoding="utf-8")
print(f"\n已写入 {OUT.name}")
