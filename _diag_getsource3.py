# -*- coding: utf-8 -*-
"""诊断 3：p2b 到底是"自身"污染，还是"其在 main() 中的位置"污染。
测三种：(a) 全新 import 只跑 p2b；(b) 跑 p2b 前后各测 getsource；
(c) 跑全部 114 个 check 到 p2b 之后（含 p2b）测。"""
import importlib.util, inspect, io, contextlib, os, re, sys
from pathlib import Path

HERE = Path('.').resolve()
os.environ.setdefault('DGTF_API_KEY', 'sk-smoke-test-key')
os.environ.setdefault('SMOKE_SAVE_DIR', 'smoke_outputs')

spec = importlib.util.spec_from_file_location('sm', str(HERE / 'smoke_test.py'))
m = importlib.util.module_from_spec(spec)
sys.modules['sm'] = m
spec.loader.exec_module(m)


def probe(tag):
    try:
        L = len(inspect.getsource(m.mod.save_result))
    except Exception as e:
        L = 'EXC:' + type(e).__name__
    print('%-34s getsource len= %s' % (tag, L))
    return L


probe('fresh import')

# (a) 只跑 p2b
with contextlib.redirect_stdout(io.StringIO()):
    r = m.check_v1221_p2b()
probe('after p2b only')
print('   p2b returned', r)

# 关键：p2b 里的 finally unlink 之后，检查 mod 的 __file__ 与 sys.path
print('   mod.__file__ =', getattr(m.mod, '__file__', None))
print('   cwd =', os.getcwd())
print('   linecache cachesave_result?',
      any('元DGTF' in str(k) for k in __import__('linecache').cache))
