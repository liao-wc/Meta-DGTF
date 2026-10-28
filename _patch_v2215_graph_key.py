# -*- coding: utf-8 -*-
"""[V2.2.15] graph 复用 key 单一定义（gates）+ service 接线 + 读数字段。"""
import py_compile
from pathlib import Path

ROOT = Path(".")

# ── 1) gates.py：graph_cache_key 唯一定义 ──────────────────────
g = ROOT / "dgtf_local_llm" / "gates.py"
gt = g.read_bytes().decode("utf-8")
assert b"\r\n" not in g.read_bytes(), "gates.py 预期纯 LF"
OLD = 'LORA_STAGES = ("self_check", "self_check_min", "dual_judge", "route")\n'
NEW = ('LORA_STAGES = ("self_check", "self_check_min", "dual_judge", "route")\n'
       '\n'
       '#: ★ [V2.2.15] CUDA graph 复用 key 的**唯一定义处**（service.py 引用它）。\n'
       '#:   为什么按 key 复用：graph 捕获时会把「当时激活的适配器算子」固化进图\n'
       '#:   （LoRA 的两条 matmul 在 Python 侧选权重），所以 LoRA stage 必须各自\n'
       '#:   一张；而 base stage 的算子图完全相同 ⇒ 共用一张。实测 graph 数\n'
       '#:   ~18 → 5、StaticCache 显存 −70%（fp32 底座下每张 3072 cache ≈75MB）。\n'
       'def graph_cache_key(stage, lora_stages=LORA_STAGES) -> str:\n'
       '    """该 stage 复用哪张 CUDA graph：LoRA stage ⇒ 专属图；其余 ⇒ 共用 base 图。"""\n'
       '    s = str(stage or "")\n'
       '    if s and s in tuple(lora_stages or ()):\n'
       '        return "adapter::" + s\n'
       '    return "base"\n')
assert gt.count(OLD) == 1
gt = gt.replace(OLD, NEW)
g.write_bytes(gt.encode("utf-8"))
py_compile.compile(str(g), doraise=True)

# ── 2) service.py：引用单一定义 + 读数字段 ────────────────────
p = ROOT / "dgtf_local_llm" / "service.py"
text = p.read_bytes().decode("utf-8-sig")
assert p.read_bytes()[:3] == b"\xef\xbb\xbf", "service.py 预期 BOM"

def rep(name, old, new):
    global text
    c = text.count(old)
    assert c == 1, "%s 锚点命中 %d 次" % (name, c)
    text = text.replace(old, new)

rep("import",
    "    sanitize_stage, LORA_STAGES)\n",
    "    sanitize_stage, LORA_STAGES, graph_cache_key)\n")

rep("stats-init",
    '                  "graph_generations": 0,\n'
    '                  "graph_sampled_generations": 0,\n'
    '                  "graph_rep_pen_generations": 0,\n'
    '                  "batch_graph_generations": 0,',
    '                  "graph_generations": 0,\n'
    '                  "graph_sampled_generations": 0,\n'
    '                  "graph_rep_pen_generations": 0,\n'
    '                  "batch_graph_generations": 0,\n'
    '                  "graph_capture_keys": [],')

rep("graph-key-method",
    '    def _graph_key(self, stage: str) -> str:\n'
    '        """graph 复用 key：LoRA stage 各一张（适配器权重被捕获进图）；其余共用一张。"""\n'
    '        if self.adapter_names and stage in self.adapter_names:\n'
    '            return "adapter::" + str(stage)\n'
    '        return "base"\n',
    '    def _graph_key(self, stage: str) -> str:\n'
    '        """graph 复用 key（**唯一定义在 gates.graph_cache_key**，此处只传当前适配器表）。"""\n'
    '        return graph_cache_key(stage, tuple(self.adapter_names or ()))\n')

rep("capture-record",
    '        self._graph_ctx[_gkey] = ctx\n'
    '        return ctx\n',
    '        self._graph_ctx[_gkey] = ctx\n'
    '        try:\n'
    '            with self._stats_lock:\n'
    '                _keylist = self.stats.get("graph_capture_keys")\n'
    '                if not isinstance(_keylist, list):\n'
    '                    _keylist = []\n'
    '                if _gkey not in _keylist:\n'
    '                    _keylist.append(_gkey)\n'
    '                self.stats["graph_capture_keys"] = _keylist\n'
    '        except Exception:  # noqa: BLE001\n'
    '            pass\n'
    '        return ctx\n')

rep("gen-return",
    '        return {"text": text, "confidence": conf,\n'
    '                "gen_tokens": int(n), "prompt_tokens": L,\n'
    '                "graph": True, "sampled": bool(temp > 0),\n'
    '                "temp": round(temp, 3)}\n',
    '        return {"text": text, "confidence": conf,\n'
    '                "gen_tokens": int(n), "prompt_tokens": L,\n'
    '                "graph": True, "sampled": bool(temp > 0),\n'
    '                "graph_key": self._graph_key(stage),\n'
    '                "temp": round(temp, 3)}\n')

rep("res-fields",
    '               "graph": bool(out.get("graph")),\n'
    '               "sampled": bool(out.get("sampled")),\n',
    '               "graph": bool(out.get("graph")),\n'
    '               "sampled": bool(out.get("sampled")),\n'
    '               "graph_key": out.get("graph_key"),\n')

p.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
py_compile.compile(str(p), doraise=True)
print("OK gates.graph_cache_key + service wiring")
