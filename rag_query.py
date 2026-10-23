# -*- coding: utf-8 -*-
"""查询嵌入：stdin 读文本，stdout 输出 JSON 向量。"""
import json, os, sys
import torch
from transformers import AutoTokenizer, AutoModel
MODEL = os.environ.get('DGTF_EMBED_MODEL', 'D:/元DGTF-多模并行架构/local_model/models/bge-small-zh-v1.5')
q = sys.stdin.read()
tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
m = AutoModel.from_pretrained(MODEL, torch_dtype=torch.float16, trust_remote_code=True)
m.eval()
dev = 'cuda' if torch.cuda.is_available() else 'cpu'
m.to(dev)
enc = tok([q[:2000]], padding=True, truncation=True, max_length=512, return_tensors='pt')
enc = {k: v.to(dev) for k, v in enc.items()}
with torch.no_grad():
    out = m(**enc).last_hidden_state[:, 0]
v = torch.nn.functional.normalize(out.float(), p=2, dim=1)[0].cpu().tolist()
sys.stdout.write(json.dumps({'ok': True, 'vec': [round(float(x), 5) for x in v]}))
