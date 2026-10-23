import sys, types, importlib.util
o = types.ModuleType('openai')
class _C:
    def __init__(self, *a, **k): pass
o.OpenAI = _C; o.AzureOpenAI = _C
o.APIError = type('APIError', (Exception,), {}); o.APIConnectionError = o.APIError
o.RateLimitError = o.APIError; o.AuthenticationError = o.APIError; o.OpenAIError = o.APIError
sys.modules['openai'] = o
spec = importlib.util.spec_from_file_location('dgtf_mod', '元DGTF-V1.23.28.py')
m = importlib.util.module_from_spec(spec); sys.modules['dgtf_mod'] = m
spec.loader.exec_module(m)

def show(tag, p):
    p.refresh_belief_entropy()
    print('---', tag, '---')
    for it in p.belief_items:
        print('   ', it['id'], 'occ_n=', it.get('occurrence_n'),
              'ent=', it['semantic_entropy'], 'cl=', it['semantic_clusters'])

# A. 单条 —— 必须 None（诚实缺省）
p = m.Pool()
p.upsert_belief('只有一条主张', ground='layer1', round_no=1, sources=['layer1'])
show('A 单条 => None', p)

# B. 两条近义 —— 应聚成一簇 => 0.0
p = m.Pool()
p.upsert_belief('落盘的最小单位是约束', ground='layer1', round_no=1, sources=['layer1'])
p.upsert_belief('落盘的最小单位是那条约束', ground='layer0', round_no=2, sources=['layer0'])
show('B 近义两条 => 0.0', p)

# C. 两条异质 —— 应两簇 => 1.0
p = m.Pool()
p.upsert_belief('落盘的最小单位是约束', ground='layer1', round_no=1, sources=['layer1'])
p.upsert_belief('今天天气很好适合去钓鱼', ground='layer0', round_no=2, sources=['layer0'])
show('C 异质两条 => 1.0', p)

# D. 逐字复现跨层 —— occurrences 累加 => None（去重后 1 种说法）
p = m.Pool()
p.upsert_belief('同一条被两层独立复现', ground='layer1', round_no=1, sources=['layer1'])
p.upsert_belief('同一条被两层独立复现', ground='layer0', round_no=2, sources=['layer0'])
show('D 逐字复现 => None', p)

# E. 三说法：两种近义 + 一种异质 => 1/3 分裂
p = m.Pool()
p.upsert_belief('落盘的最小单位是约束', ground='layer1', round_no=1, sources=['layer1'])
p.upsert_belief('落盘的最小单位就是那条约束', ground='layer0', round_no=2, sources=['layer0'])
p.upsert_belief('落盘的最小单位是那个约束项', ground='both', round_no=3, sources=['both'])
show('E 三近义 => 0.0', p)
