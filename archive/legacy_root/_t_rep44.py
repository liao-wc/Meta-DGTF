import importlib.util
import io
import contextlib
import sys

spec = importlib.util.spec_from_file_location('m', '元DGTF-V1.23.26.py')
m = importlib.util.module_from_spec(spec)
sys.modules['m'] = m
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(m)

corpus = m._bm25_corpus(['量子纠缠实验需要极低温环境', '超导材料在低温下表现特殊',
                         '人工智能模型部署管线优化', '模型蒸馏可以压缩参数量',
                         '神经网络优化方法研究'])
cases = [('模型 部署', '模型 训练'),
         ('神经网络 优化', '神经网络 训练'),
         ('低温超导材料制备工艺', '超导材料低温制备工艺研究')]
for a, b in cases:
    print('%-16s / %-16s  ov=%.3f  sim3_no=%.3f  sim3_c=%.3f'
          % (a, b, m._overlap_coef(a, b, m._KW_TOP_N),
             m._sim3(a, b), m._sim3(a, b, corpus)))
print('T3/T3=%.3f T3/T4=%.3f T3/3=%.3f'
      % (m._sim3('T3', 'T3'), m._sim3('T3', 'T4'), m._sim3('T3', '3')))
