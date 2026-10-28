# -*- coding: utf-8 -*-
"""[V2.2.15] 本地服务三处结构性优化（实测支撑）：

1) 底座改用 fp32：1660 Ti(TU116) 无 tensor core，fp16 的 Linear 会命中
   cutlass wmma_tensorop 仿真核（实测 0.5ms/次 vs fp32 gemv 0.05ms）。
   实测单 token graph replay：fp16 59ms → fp32 28ms（2.1x）；模型 1.9GB 可容。
2) base stage 显式禁用适配器：PeftModel 会沿用上一次 set_adapter 的适配器
   ⇒ 底座输出被别的 LoRA 污染（实测 re_anchor 多出 anchorText 幻觉键）。
3) graph 复用：LoRA stage 各自一张（适配器权重被捕获进图）；其余 stage
   共用一张 base 图 ⇒ graph 数从 ~18 降到 5，StaticCache 显存 ~75MB/图。
"""
import py_compile
from pathlib import Path

P = Path("dgtf_local_llm/service.py")
text = P.read_bytes().decode("utf-8-sig")

def rep(name, old, new, count=1):
    global text
    c = text.count(old)
    assert c == count, "%s 锚点命中 %d 次（应为 %d）" % (name, c, count)
    text = text.replace(old, new)

# ── 1) 加载 fp32 底座 ─────────────────────────────────────────
rep("load-dtype",
'''            base = AutoModelForCausalLM.from_pretrained(
                self.model_path, dtype=torch.float16, trust_remote_code=True,
                local_files_only=True, attn_implementation="sdpa")''',
'''            # ★ [V2.2.15] fp16 → fp32：本机 1660 Ti(TU116) 无 tensor core，
            #   fp16 的 Linear 命中 cutlass wmma_tensorop 仿真核（实测
            #   0.5ms/次），fp32 走 gemv（0.05ms/次）。实测单 token graph
            #   replay 59ms→28ms（2.1x）；底座 1.9GB，6GB 卡可容。
            base = AutoModelForCausalLM.from_pretrained(
                self.model_path, dtype=torch.float32, trust_remote_code=True,
                local_files_only=True, attn_implementation="sdpa")''')

# ── 2) 新增 _adapter_ctx / _graph_key 帮助函数（放在 _set_fp32 之后）──
rep("helpers",
'''    def _set_fp32(self, on: bool) -> None:
        for m, orig, fast in self.patches:
            m.forward = fast if on else orig
''',
'''    def _set_fp32(self, on: bool) -> None:
        for m, orig, fast in self.patches:
            m.forward = fast if on else orig

    def _adapter_ctx(self, stage: str):
        """该 stage 的适配器上下文：LoRA stage 切过去，base stage **明确禁用**。

        ★ [V2.2.15] 此前 base stage 从不 set_adapter，PeftModel 会沿用上一次
          激活的适配器 ⇒ 底座输出被别的 LoRA 污染（实测 re_anchor 在
          self_check 适配器激活时多吐 "anchorText" 之类幻觉键）。base stage
          必须显式 disable_adapter 才是真底座。
        """
        import contextlib as _cl
        if self.adapter_names and stage in self.adapter_names:
            self.model.set_adapter(self.adapter_names[stage])
            return _cl.nullcontext()
        if hasattr(self.model, "disable_adapter"):
            return self.model.disable_adapter()
        return _cl.nullcontext()

    def _graph_key(self, stage: str) -> str:
        """graph 复用 key：LoRA stage 各一张（适配器权重被捕获进图）；其余共用一张。"""
        if self.adapter_names and stage in self.adapter_names:
            return "adapter::" + str(stage)
        return "base"
''')

# ── 3) _graph_capture：按 key 复用 + 进入适配器上下文 ──────────
rep("capture-key",
'''        import torch as _t
        ctx = self._graph_ctx.get(stage)
        if ctx is not None:
            return ctx''',
'''        import torch as _t
        _gkey = self._graph_key(stage)
        ctx = self._graph_ctx.get(_gkey)
        if ctx is not None:
            return ctx''')

rep("capture-adapter",
'''        out_logits = _t.zeros((1, vocab), dtype=_t.float32, device="cuda")
        if self.adapter_names and stage in self.adapter_names:
            self.model.set_adapter(self.adapter_names[stage])
''',
'''        out_logits = _t.zeros((1, vocab), dtype=_t.float32, device="cuda")
''')

rep("capture-with",
'''        with _t.inference_mode():
            mask[0, :1] = 1
            for _ in range(3):
                step()
            g = _t.cuda.CUDAGraph()
            with _t.cuda.graph(g):
                step()''',
'''        # ★ 在目标适配器上下文里捕获：LoRA stage 捕获该适配器的算子图；
        #   base stage 在 disable_adapter 下捕获，replay 永远是底座。
        with _t.inference_mode(), self._adapter_ctx(stage):
            mask[0, :1] = 1
            for _ in range(3):
                step()
            g = _t.cuda.CUDAGraph()
            with _t.cuda.graph(g):
                step()''')

rep("capture-store",
'''        self._graph_ctx[stage] = ctx
        return ctx''',
'''        self._graph_ctx[_gkey] = ctx
        return ctx''')

# ── 4) generate_graph：prefill 走同一适配器上下文 ──────────────
rep("gen-adapter",
'''        out_logits, g = ctx["out_logits"], ctx["graph"]
        if self.adapter_names and stage in self.adapter_names:
            self.model.set_adapter(self.adapter_names[stage])
        temp = float(temperature or 0.0)''',
'''        out_logits, g = ctx["out_logits"], ctx["graph"]
        temp = float(temperature or 0.0)''')

rep("gen-prefill",
'''                self._set_fp32(True)
                cache.reset()
                mask.zero_()
                o = self.model(input_ids=ids,
                               attention_mask=_t.ones(
                                   (1, L), dtype=_t.long, device="cuda"),
                               past_key_values=cache,
                               cache_position=_t.arange(L, device="cuda"),
                               use_cache=True)''',
'''                self._set_fp32(True)
                cache.reset()
                mask.zero_()
                with self._adapter_ctx(stage):
                    o = self.model(input_ids=ids,
                                   attention_mask=_t.ones(
                                       (1, L), dtype=_t.long, device="cuda"),
                                   past_key_values=cache,
                                   cache_position=_t.arange(L, device="cuda"),
                                   use_cache=True)''')

# ── 5) 慢路径 generate：所有 self.model 调用包适配器上下文 ─────
rep("gen-slow-sig",
'''        ids = input_ids.to("cuda")
        L = ids.shape[1]
        attn = torch.ones((1, L), dtype=torch.long, device="cuda")
        if use_adapter and self.adapter_names and stage in self.adapter_names:
            self.model.set_adapter(self.adapter_names[stage])
        self._set_fp32(True)
        outs = self.model(input_ids=ids, attention_mask=attn,
                          use_cache=True)''',
'''        ids = input_ids.to("cuda")
        L = ids.shape[1]
        attn = torch.ones((1, L), dtype=torch.long, device="cuda")
        import contextlib as _cl
        _actx = self._adapter_ctx(stage) if use_adapter else _cl.nullcontext()
        self._set_fp32(True)
        with _actx:
            outs = self.model(input_ids=ids, attention_mask=attn,
                              use_cache=True)''')

rep("gen-slow-step",
'''                o = self.model(input_ids=nxt, attention_mask=attn,
                               past_key_values=past, use_cache=True)''',
'''                with _actx:
                    o = self.model(input_ids=nxt, attention_mask=attn,
                                   past_key_values=past, use_cache=True)''')

P.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
py_compile.compile(str(P), doraise=True)
print("OK fp32+adapter-ctx+graph-reuse patch applied")
