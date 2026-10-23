# -*- coding: utf-8 -*-
import tempfile
from pathlib import Path
from dgtf_v2.agent_repair import stage_patch,apply_patch
def main():
 d=Path(tempfile.mkdtemp());r=stage_patch("t1","diff --git a/x b/x\n",["元DGTF-V1.30.0.py"],str(d/"p"));print(("PASS" if r["path_ok"] else "FAIL"),"path_ok")
 r2=stage_patch("t2","",["/etc/passwd"],str(d/"p"));print(("PASS" if not r2["path_ok"] else "FAIL"),"bad_path")
 a=apply_patch(str(d/"p"/"t1.patch"),"");print(("PASS" if a["status"]=="refused" else "FAIL"),"approve_required")
if __name__=="__main__":main()
