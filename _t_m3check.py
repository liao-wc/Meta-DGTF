import importlib.util
import io
import contextlib
import sys

src = open('元DGTF-V1.23.26.py', encoding='utf-8').read().replace('\r\n', '\n')
old = '    if ma and mb:\n        return 1.0 if ma.group(1) == mb.group(1) else 0.0\n'
new = '    if ma and mb:\n        return 0.0\n'
print('M3 anchor count =', src.count(old))
src2 = src.replace(old, new, 1)
open('_t_m3.py', 'w', encoding='utf-8', newline='\n').write(src2)
for tag, path in [('真文件', '元DGTF-V1.23.26.py'), ('M3变异', '_t_m3.py')]:
    spec = importlib.util.spec_from_file_location('x' + tag, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules['x' + tag] = m
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(m)
    print('%s: sim3(T3,3)=%.4f sim3(T3,T4)=%.4f jaccard(T3,3)=%.4f'
          % (tag, m._sim3('T3', '3'), m._sim3('T3', 'T4'), m._jaccard('T3', '3')))
