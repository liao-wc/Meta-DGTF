# -*- coding: utf-8 -*-
"""诊断 4：main() 顺序跑到 p2b **之后若干** check，看何时/是否掉。
并测「p2b + 其后的 check」组合。"""
import importlib.util, inspect, io, contextlib, os, re, sys, linecache
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

j = order.index('check_v1221_p2b')
print('p2b idx', j, 'of', len(order))
print('next 6 after p2b:', order[j+1:j+7])

def probe():
    try:
        return len(inspect.getsource(m.mod.save_result))
    except Exception as e:
        return 'EXC:' + type(e).__name__

prev = probe()
print('baseline', prev)
# 跑到 p2b+8
for i, n in enumerate(order[:j+8]):
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            getattr(m, n)()
        except Exception:
            pass
    cur = probe()
    if cur != prev:
        print('!!! DROP at idx %d %s : %s -> %s' % (i, n, prev, cur))
        prev = cur
print('final', probe())
