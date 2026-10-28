# -*- coding: utf-8 -*-
"""[V2.2.15] graph 解码走 fp16：捕获前关闭 fp32 patch，prefill 仍用 fp32。

根因假设（待实测确认）：_set_fp32 是状态式 monkeypatch。服务加载后一直是
True；generate_graph 捕获时没关 ⇒ graph 里捕获的是「每 step 把 0.5B 权重
w.float() 再算」的 fp32 版本 ⇒ 单 token 要搬 ~1GB 权重，实测 ~85ms/token。
graph 捕获前关掉 patch（fp16 权重）应显著变快；prefill 仍保留 fp32（该卡
fp32 GEMM 更快，见模块 docstring line 43）。
"""
import py_compile
from pathlib import Path

P = Path("dgtf_local_llm/service.py")
raw = P.read_bytes()
text = raw.decode("utf-8-sig")

# 1) _graph_capture：捕获前关 fp32 patch（fp16 graph）
OLD1 = '''        import torch as _t
        ctx = self._graph_ctx.get(stage)
        if ctx is not None:
            return ctx
        cache = StaticCache(self.model.config, max_cache_len=self._GRAPH_TOTAL)'''
NEW1 = '''        import torch as _t
        ctx = self._graph_ctx.get(stage)
        if ctx is not None:
            return ctx
        # ★ [V2.2.15] 捕获前必须关掉 fp32 patch：patch 会把每个 Linear 的
        #   权重每 step 转一次 fp32（0.5B 权重 ≈1GB 搬运/token，实测
        #   ~85ms/token）。graph 捕获的是算子图，捕获时的 patch 状态会被
        #   固化进 replay ⇒ 必须在 fp16 状态下捕获。
        self._set_fp32(False)
        cache = StaticCache(self.model.config, max_cache_len=self._GRAPH_TOTAL)'''

# 2) generate_graph：prefill 用 fp32、decode 用 fp16；异常路径恢复 True
OLD2 = '''        try:
            with _t.inference_mode():
                cache.reset()
                mask.zero_()
                o = self.model(input_ids=ids,'''
NEW2 = '''        try:
            with _t.inference_mode():
                # prefill 走 fp32 patch（该卡 fp32 GEMM 更快）；decode 走
                # fp16（graph 捕获的就是 fp16 算子图）。
                self._set_fp32(True)
                cache.reset()
                mask.zero_()
                o = self.model(input_ids=ids,'''

OLD3 = '''                cur_logits = o.logits[:, -1, :].float()
                mask[0, :L] = 1'''
NEW3 = '''                cur_logits = o.logits[:, -1, :].float()
                self._set_fp32(False)
                mask[0, :L] = 1'''

OLD4 = '''        except TimeoutError:
            self._set_fp32(True)
            raise
        text = self.tok.decode(gen[:n].tolist(), skip_special_tokens=True)'''
NEW4 = '''        except TimeoutError:
            self._set_fp32(True)
            raise
        except Exception:
            self._set_fp32(True)
            raise
        text = self.tok.decode(gen[:n].tolist(), skip_special_tokens=True)'''

for name, old, new in (("cap", OLD1, NEW1), ("prefill", OLD2, NEW2),
                       ("decode", OLD3, NEW3), ("except", OLD4, NEW4)):
    c = text.count(old)
    assert c == 1, "%s 锚点命中 %d 次" % (name, c)
    text = text.replace(old, new)

P.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
py_compile.compile(str(P), doraise=True)
print("OK fp16 graph patch applied")
