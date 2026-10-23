# -*- coding: utf-8 -*-
"""D3 语义熵 —— 阈值解耦后的行为矩阵（含负对照）。"""
import sys
import types
import importlib.util

o = types.ModuleType('openai')


class _C:
    def __init__(self, *a, **k):
        pass


o.OpenAI = _C
o.AzureOpenAI = _C
o.APIError = type('APIError', (Exception,), {})
o.APIConnectionError = o.APIError
o.RateLimitError = o.APIError
o.AuthenticationError = o.APIError
o.OpenAIError = o.APIError
sys.modules['openai'] = o

spec = importlib.util.spec_from_file_location('dgtf_mod', '元DGTF-V1.23.28.py')
m = importlib.util.module_from_spec(spec)
sys.modules['dgtf_mod'] = m
spec.loader.exec_module(m)

print('_SEM_CLUSTER_THR =', m._SEM_CLUSTER_THR)
print('DEFAULT belief.sem_entropy_thr =',
      m.DEFAULT_CONFIG['belief'].get('sem_entropy_thr'))
print()


def show(tag, p, expect):
    p.refresh_belief_entropy(thr=p.sem_entropy_thr)
    ents = [(it['id'], it.get('occurrence_n'), it['semantic_entropy'])
            for it in p.belief_items]
    print('--- %s  [期望 %s] ---' % (tag, expect))
    for i, n, e in ents:
        print('    %s occ_n=%s ent=%s' % (i, n, e))
    return ents


# A. 单条 => None
p = m.Pool(); p.sem_entropy_thr = m._SEM_CLUSTER_THR
p.upsert_belief('只有一条主张', ground='layer1', round_no=1,
                sources=['layer1'])
show('A 单条', p, 'None')

# B. 两条近义 => 聚成一簇 => 0.0
p = m.Pool(); p.sem_entropy_thr = m._SEM_CLUSTER_THR
p.upsert_belief('落盘的最小单位是约束', ground='layer1', round_no=1,
                sources=['layer1'])
p.upsert_belief('落盘的最小单位是那条约束', ground='layer0', round_no=2,
                sources=['layer0'])
show('B 近义两条', p, '0.0')

# C. 两条异质 => 两簇 => 1.0
p = m.Pool(); p.sem_entropy_thr = m._SEM_CLUSTER_THR
p.upsert_belief('落盘的最小单位是约束', ground='layer1', round_no=1,
                sources=['layer1'])
p.upsert_belief('今天天气很好适合去钓鱼', ground='layer0', round_no=2,
                sources=['layer0'])
show('C 异质两条', p, '1.0')

# D. 逐字复现跨层 => 去重后 1 种说法 => None
p = m.Pool(); p.sem_entropy_thr = m._SEM_CLUSTER_THR
p.upsert_belief('同一条被两层独立复现', ground='layer1', round_no=1,
                sources=['layer1'])
p.upsert_belief('同一条被两层独立复现', ground='layer0', round_no=2,
                sources=['layer0'])
show('D 逐字复现', p, 'None')

# E. 三近义 => 全同簇 => 0.0
p = m.Pool(); p.sem_entropy_thr = m._SEM_CLUSTER_THR
p.upsert_belief('落盘的最小单位是约束', ground='layer1', round_no=1,
                sources=['layer1'])
p.upsert_belief('落盘的最小单位就是那条约束', ground='layer0', round_no=2,
                sources=['layer0'])
p.upsert_belief('落盘的最小单位是那个约束项', ground='both', round_no=3,
                sources=['both'])
show('E 三近义', p, '0.0')

# F. 负对照：把阈值调回 0.70（旧口径）=> 一律退化
p = m.Pool(); p.sem_entropy_thr = 0.70
p.upsert_belief('落盘的最小单位是约束', ground='layer1', round_no=1,
                sources=['layer1'])
p.upsert_belief('落盘的最小单位是那条约束', ground='layer0', round_no=2,
                sources=['layer0'])
show('F 负对照 thr=0.70', p, '全部 None（证阈值真接线）')
