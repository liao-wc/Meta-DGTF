# -*- coding: utf-8 -*-
"""构建本地 BGE 语义索引（无外部服务）。"""
import json, os, re, sys, time
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModel

ROOT = Path(__file__).resolve().parent
MODEL = os.environ.get('DGTF_EMBED_MODEL', 'D:/元DGTF-多模并行架构/local_model/models/bge-small-zh-v1.5')
OUT = ROOT / 'dgtf_memory' / 'rag_index.json'
MAX_ITEMS = int(os.environ.get('DGTF_RAG_MAX_ITEMS', '1200'))

def para_split(text):
    parts = re.split(r'\n\s*\n', str(text or ''))
    return [p.strip() for p in parts if len(p.strip()) >= 40]

items = []
seen = set()
def add(kind, source, text):
    t = str(text or '').strip()
    if len(t) < 40:
        return
    sig = source + '|' + t[:100]
    if sig in seen:
        return
    seen.add(sig)
    items.append({'kind': kind, 'source': source, 'text': t[:1200]})

for rel in ['README.md', 'dgtf_app/README.md', 'docs/app_engine_mapping.md',
            'docs/full_loop.md', 'docs/llm_lora_finetune.md',
            'docs/real_run_20261021.md', 'docs/rag_v2.md',
            'v130_升级报告.md', 'docs/不做什么-v1221.md']:
    p = ROOT / rel
    if not p.exists():
        continue
    for x in para_split(p.read_text(encoding='utf-8', errors='replace')):
        add('doc', rel, x)

kn = ROOT / 'dgtf_memory' / 'agent_knowledge.jsonl'
if kn.exists():
    for ln in kn.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            d = json.loads(ln)
        except Exception:
            continue
        title = str(d.get('title') or '')
        body = str(d.get('claim') or d.get('summary') or d.get('content') or '')
        add('knowledge', title[:200] or 'knowledge', title + '\n' + body[:1000])

fa = ROOT / 'dgtf_app' / 'anchors' / 'external_anchor.json'
if fa.exists():
    try:
        data = json.loads(fa.read_text(encoding='utf-8', errors='replace'))
        for it in data.get('anchors') or []:
            if str(it.get('kind') or '') != 'local':
                continue
            add('imported', str(it.get('source') or 'local'), str(it.get('content') or ''))
    except Exception:
        pass

items = items[:MAX_ITEMS]
print('ITEMS', len(items), flush=True)
tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
model = AutoModel.from_pretrained(MODEL, torch_dtype=torch.float16, trust_remote_code=True)
model.eval()
dev = 'cuda' if torch.cuda.is_available() else 'cpu'
model.to(dev)
vecs = []
t0 = time.time()
bs = 16
for i in range(0, len(items), bs):
    batch = [x['text'] for x in items[i:i+bs]]
    enc = tok(batch, padding=True, truncation=True, max_length=512, return_tensors='pt')
    enc = {k: v.to(dev) for k, v in enc.items()}
    with torch.no_grad():
        out = model(**enc)
    v = out.last_hidden_state[:, 0]
    v = torch.nn.functional.normalize(v.float(), p=2, dim=1).cpu().tolist()
    vecs.extend(v)
    if (i // bs) % 10 == 0:
        print('BATCH', i, '/', len(items), flush=True)
out = {'model': MODEL, 'dim': len(vecs[0]) if vecs else 0,
       'built_at': time.time(), 'items': []}
for it, v in zip(items, vecs):
    it = dict(it)
    it['vec'] = [round(float(x), 5) for x in v]
    out['items'].append(it)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
print('WROTE', OUT, OUT.stat().st_size, 'sec', round(time.time() - t0, 1), flush=True)
