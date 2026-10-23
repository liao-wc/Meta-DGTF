# -*- coding: utf-8 -*-
"""诊断：定位让 inspect.getsource 失效的真正的 check。
逐 check 跑，每次跑完测一次 getsource 长度，第一个掉落点即真凶。"""
import importlib.util, inspect, io, contextlib, os, re, sys
from pathlib import Path

HERE = Path('.').resolve()
os.environ.setdefault('DGTF_API_KEY', 'sk-smoke-test-key')
os.environ.setdefault('SMOKE_SAVE_DIR', 'smoke_outputs')

spec = importlib.util.spec_from_file_location('sm', str(HERE / 'smoke_test.py'))
m = importlib.util.module_from_spec(spec)
sys.modules['sm'] = m
spec.loader.exec_module(m)

txt = (HERE / 'smoke_test.py').read_bytes().decode('utf-8').replace('\r\n', '\n').split('\n')
order = []
for l in txt:
    mm = re.match(r'^    if not (check_\w+)\(\)', l)
    if mm:
        order.append(mm.group(1))

stop_at = order.index('check_v1221_p2b')
print('total checks in main():', len(order), 'stop_at idx', stop_at)

def probe():
    try:
        return len(inspect.getsource(m.mod.save_result))
    except Exception as e:
        return 'EXC:' + type(e).__name__

prev = probe()
print('baseline len=', prev)
for i, n in enumerate(order[:stop_at]):
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            getattr(m, n)()
        except Exception:
            pass
    cur = probe()
    if cur != prev:
        print('!!! DROP at idx %d  %s : %s -> %s' % (i, n, prev, cur))
        prev = cur
print('final len=', probe())
