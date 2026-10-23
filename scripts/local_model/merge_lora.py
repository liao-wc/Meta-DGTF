# -*- coding: utf-8 -*-
"""合并 LoRA adapter 到基座，导出可直接加载的完整模型。"""
import sys, torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
base = sys.argv[1] if len(sys.argv) > 1 else 'D:/Meta-DGTF-道生三阶模型/local_model/models/Qwen2.5-0.5B-Instruct'
adapter = sys.argv[2] if len(sys.argv) > 2 else 'llm_sft/adapter_qwen05b_v1'
out = sys.argv[3] if len(sys.argv) > 3 else 'D:/Meta-DGTF-道生三阶模型/local_model/models/Qwen2.5-0.5B-Instruct-merged-v1'
tok = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
m = AutoModelForCausalLM.from_pretrained(base, torch_dtype=torch.float16, trust_remote_code=True)
m = PeftModel.from_pretrained(m, adapter)
m = m.merge_and_unload()
m.save_pretrained(out, safe_serialization=True)
tok.save_pretrained(out)
print('MERGED', out)
