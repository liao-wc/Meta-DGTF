# -*- coding: utf-8 -*-
from pathlib import Path
src = Path("dgtf_config.yaml").read_text(encoding="utf-8")
old = '  save_dir: "outputs"'
assert src.count(old) == 1
out = Path("outputs/_e2e_local/cloud_dyn_validate"); out.mkdir(parents=True, exist_ok=True)
Path("outputs/_e2e_local/cloud_dyn_validate_config.yaml").write_text(
    src.replace(old, '  save_dir: "outputs/_e2e_local/cloud_dyn_validate"'), encoding="utf-8")
print("temp config OK")
