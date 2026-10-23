# -*- coding: utf-8 -*-
"""Step9 自检：CRLF / 语法 / 无版次批注 / E6 行为。"""
import importlib.util, sys, io, contextlib, re
from pathlib import Path

HERE = Path('.').resolve()
SRC = HERE / '元DGTF-V1.23.27.py'

raw = SRC.read_bytes()
txt = raw.decode('utf-8')
print('CRLF == LF :', txt.count('\r\n') == txt.count('\n'))
print('\\r\\r\\n == 0:', txt.count('\r\r\n') == 0)
print('bytes       :', len(raw))
print('lines       :', txt.count('\n') + 1)

# 版次批注（抠 docstring 后的正文注释）
t = txt.replace('\r\n', '\n')
import ast
tree = ast.parse(t)
doc_ranges = []
for node in ast.walk(tree):
    if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                         ast.ClassDef)):
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            doc_ranges.append((node.body[0].lineno,
                               node.body[0].end_lineno))
lines = t.split('\n')
indoc = set()
for a, b in doc_ranges:
    for i in range(a, b + 1):
        indoc.add(i)
TAG = re.compile(r'\[v\d[^\]]*\]|(?<![A-Za-z0-9_\-])v\d+(?:\.\d+)*(?![A-Za-z0-9_\-])')
bad = []
for i, l in enumerate(lines, 1):
    if i in indoc:
        continue
    s = l.strip()
    if s.startswith('#') and TAG.search(s):
        bad.append(i)
print('版次批注行数:', len(bad), bad[:8])
# docstring 前导版次标记
pre = []
for node in ast.walk(tree):
    if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                         ast.ClassDef)):
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            v = node.body[0].value.value.lstrip()
            if TAG.match(v):
                pre.append(node.body[0].lineno)
print('docstring 前导版次标记:', len(pre), pre[:5])

# ── 行为自检 ──────────────────────────────────────────────
import os
os.environ.setdefault('DGTF_API_KEY', 'sk-selfcheck')
spec = importlib.util.spec_from_file_location('dgtf27', str(SRC))
m = importlib.util.module_from_spec(spec)
sys.modules['dgtf27'] = m
spec.loader.exec_module(m)

print()
print('== e6_stop_verdict 纯函数 ==')
for seen, mg, mn, fl, exp in [
    (0, 0.0, 0.3, 0.02, (False, 'no_candidate')),
    (3, 0.01, 0.3, 0.02, (True, 'max_gain_below_floor')),
    (3, 0.02, 0.3, 0.02, (False, 'gain_ok')),   # 边界：== 不算停
    (2, 0.5, 0.3, 0.02, (False, 'gain_ok')),
    (1, None, 0.3, 0.02, (True, 'max_gain_below_floor')),
]:
    got = m.e6_stop_verdict(seen, mg, mn, fl)
    ok = 'OK ' if got == exp else 'BAD'
    print('  %s verdict(seen=%s,mg=%s)=%s' % (ok, seen, mg, got))

print()
print('== Pool.note_probe_stop + to_dict ==')
p = m.Pool()
r1 = p.note_probe_stop('research', 3, 0.005, 0.3, 0.02)
r2 = p.note_probe_stop('duel', 0, 0.0, 0.3, 0.02)
print('  rec1:', r1)
print('  rec2:', r2)
print('  history len:', len(p.probe_stop_history))
d = p.to_dict()
print('  to_dict has probe_stop_history:', 'probe_stop_history' in d)
print('  to_dict hist len:', len(d.get('probe_stop_history', [])))

print()
print('== 空 Pool 出口（不该凭空出现键）==')
p2 = m.Pool()
print('  empty to_dict has key:',
      'probe_stop_history' in p2.to_dict())

print()
print('== 配置键默认 ==')
print('  _GAIN_STOP_FLOOR =', m._GAIN_STOP_FLOOR)
