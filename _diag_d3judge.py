# -*- coding: utf-8 -*-
"""验证强化后的 D3 判据：正确实现必须过；M9 变异（全池混合）必须判红。

★ 为什么单独做这一步：M9 第一次跑「未判红」⇒ 判据无判别力。
  按项目通则「判据落在行为上、审计必须自带变异体」，这里**先证**
  判据能分辨错实现，再回去跑全套变异体。
"""
import sys
import types
import importlib.util
import tempfile
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.28.py"

_o = types.ModuleType('openai')


class _C:
    def __init__(self, *a, **k):
        pass


_o.OpenAI = _C
_o.AzureOpenAI = _C
_o.APIError = type('APIError', (Exception,), {})
_o.APIConnectionError = _o.APIError
_o.RateLimitError = _o.APIError
_o.AuthenticationError = _o.APIError
_o.OpenAIError = _o.APIError
sys.modules.setdefault('openai', _o)


def load(text):
    tmp = Path(tempfile.mkdtemp(prefix="_d3chk_")) / "m.py"
    tmp.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    os.environ.setdefault("DGTF_API_KEY", "sk-x")
    spec = importlib.util.spec_from_file_location("d3m_%d" % os.getpid(),
                                                  str(tmp))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def judge(m):
    """模拟 smoke 的强化判据：返回 (bad_list)。"""
    bad = []
    p = m.Pool()
    p.sem_entropy_thr = float(getattr(m, "_SEM_CLUSTER_THR", 0.30))
    p.upsert_belief("落盘的最小单位是约束", ground="layer1", round_no=1,
                    sources=["layer1"])
    p.upsert_belief("落盘的最小单位是那条约束", ground="layer0",
                    round_no=2, sources=["layer0"])
    p.upsert_belief("城市轨道交通客流预测模型误差主要来自换乘",
                    ground="both", round_no=3, sources=["both"])
    p.refresh_belief_entropy(thr=p.sem_entropy_thr)
    ed = [(it.get("id"), it.get("occurrence_n"),
           it.get("semantic_entropy")) for it in p.belief_items]
    pair = ed[:2]
    solo = ed[2] if len(ed) > 2 else None
    if not all(e[1] and e[1] >= 2 for e in pair):
        bad.append("近义未聚簇 ed=%r" % (ed,))
    elif not all(e[2] is not None and e[2] <= 0.05 for e in pair):
        bad.append("近义熵非 0 ed=%r" % (ed,))
    elif solo is not None and solo[1] and solo[1] >= 2:
        bad.append("无关主张被混入 solo=%r" % (solo,))
    return bad, ed


raw = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")

print("=== 正确实现（应 PASS）===")
m = load(raw)
bad, ed = judge(m)
print("  读数:", ed)
print("  判据:", "PASS" if not bad else "FAIL %r" % bad)

print()
print("=== M9 变异（全池混合，应判红）===")
mut = raw.replace(
    '''            _hn_all, _h_all, _cl_all = semantic_entropy_of(
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
''',
    '''            _hn_all, _h_all, _cl_all = semantic_entropy_of(
                _txt, corpus=_corpus, thr=thr)
            _sub = list(_txt)  # 变异：全池混合
''', 1)
assert mut != raw, "M9 锚点未命中"
m2 = load(mut)
bad2, ed2 = judge(m2)
print("  读数:", ed2)
print("  判据:", "PASS（无判别力 ✗）" if not bad2 else "FAIL（判红 ✓）%r" % bad2)
