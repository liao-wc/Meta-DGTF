#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""迁移后的项目路径/运行依赖检查。"""
from pathlib import Path
import sys, json
ROOT = Path(r'D:\Meta-DGTF-道生三阶模型')
checks = {
  'root': ROOT,
  'app_server': ROOT/'dgtf_app'/'server.py',
  'engine': ROOT/'dgtf_engine'/'dgtf_v2'/'engine'/'Meta-DGTF-V2.2.0.py',
  'dgtf_v2': ROOT/'dgtf_engine'/'dgtf_v2',
  'models': ROOT/'local_model'/'models',
  'bge': ROOT/'local_model'/'models'/'bge-small-zh-v1.5',
  'qwen05': ROOT/'local_model'/'models'/'Qwen2.5-0.5B-Instruct',
  'qwen15': ROOT/'local_model'/'models'/'Qwen2.5-1.5B-Instruct',
  'deepseek15': ROOT/'local_model'/'models'/'DeepSeek-R1-Distill-Qwen-1.5B',
  'env_python': ROOT/'local_model'/'envs'/'dgtf_llm_env'/'Scripts'/'python.exe',
  'token': ROOT/'dgtf_memory'/'.access_token',
  'config': ROOT/'dgtf_config.yaml',
}
ok=True
for k,p in checks.items():
    good=p.exists(); ok=ok and good
    print(('PASS' if good else 'FAIL'), k, p)
print('RESULT', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
