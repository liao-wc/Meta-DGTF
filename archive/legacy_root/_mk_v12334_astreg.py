# -*- coding: utf-8 -*-
"""修 `_v122_ast_registry.json` 里 `_render_layer_glance` 的 reason（反引号被
shell 命令替换吃掉了）。★ 教训：写脚本一律用 Write 工具 —— 在 `python -c "..."`
里放反引号，shell 会先做命令替换，把内容悄悄改掉且**不报错**。
"""
import json
from pathlib import Path

P = Path(__file__).resolve().parent / "_v122_ast_registry.json"
d = json.loads(P.read_text(encoding="utf-8"))
d["registry"]["_render_layer_glance"] = {
    "phase": "提示词/可读性",
    "reason": "本层速览渲染辅助：在 DGTF._render 的正文最前面给一行全局"
              "（跑了 N 圈 / 候选 / & / 线头 / 悬置），只增一行、不改既有结构",
}
P.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("OK reason 已修：", d["registry"]["_render_layer_glance"]["reason"])
