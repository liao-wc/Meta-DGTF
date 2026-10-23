# -*- coding: utf-8 -*-
import os, sys, importlib.util
os.environ.setdefault("DGTF_API_KEY", "sk-probe")
spec = importlib.util.spec_from_file_location("smk", "smoke_test.py")
smk = importlib.util.module_from_spec(spec)
sys.modules["smk"] = smk
spec.loader.exec_module(smk)
print("RESULT =", smk.check_v12327_five_mechanisms())
