# -*- coding: utf-8 -*-
"""[V2.2.15] 本地服务：CUDA graph 解码支持 temp>0 采样 + 重复惩罚（graph 外采样）。

改的是 dgtf_local_llm/service.py：
  1. _graph_capture：graph 只做「一步前向 + logits→静态 fp32 buffer」；
  2. generate_graph：采样（argmax / softmax+multinomial）、rep_pen 全在 graph 外；
  3. _handle：graph 快路径不再限 temp==0；TimeoutError 直接抛（不再回慢路径重来）；
  4. 统计：graph_sampled_generations / graph_rep_pen_generations；
  5. 回包留痕：graph / sampled / temp。
"""
import py_compile
from pathlib import Path

P = Path("dgtf_local_llm/service.py")
raw = P.read_bytes()
assert raw[:3] == b"\xef\xbb\xbf", "预期 UTF-8 BOM"
assert b"\r\n" not in raw, "预期纯 LF"
text = raw.decode("utf-8-sig")

NEW_CAPTURE = '''    def _graph_capture(self, stage: str) -> dict:
        """为指定 stage 捕获一个 decode 步的 CUDA graph（惰性，每 stage 一次）。

        ★ [V2.2.15] graph 只捕获「一步前向 + logits 落静态 buffer」，采样
          （贪心 / 温度 / 重复惩罚）全部搬到 graph 外面：
            · 旧版把 argmax + log_softmax 捕获进 graph ⇒ 只有 temp==0 能走
              graph；而引擎绝大多数调用 temp 0.2~0.9 ⇒ 全落慢路径
              （实测单次 20~37s，是本地链墙钟的大头）；
            · 新版 temp>0 也走 graph，log_softmax 也从 graph 里挪走
              （confidence 才需要，放外面按需算）。
        """
        import torch as _t
        ctx = self._graph_ctx.get(stage)
        if ctx is not None:
            return ctx
        cache = StaticCache(self.model.config, max_cache_len=self._GRAPH_TOTAL)
        in_tok = _t.zeros((1, 1), dtype=_t.long, device="cuda")
        mask = _t.zeros((1, self._GRAPH_TOTAL), dtype=_t.long, device="cuda")
        pos = _t.zeros((1,), dtype=_t.long, device="cuda")
        cp = _t.zeros((1,), dtype=_t.long, device="cuda")
        vocab = int(getattr(self.model.config, "vocab_size", 0) or 0)
        if vocab <= 0:
            raise RuntimeError("model.config.vocab_size 不可用，graph 无法捕获")
        out_logits = _t.zeros((1, vocab), dtype=_t.float32, device="cuda")
        if self.adapter_names and stage in self.adapter_names:
            self.model.set_adapter(self.adapter_names[stage])

        def step():
            o = self.model(input_ids=in_tok, attention_mask=mask,
                           position_ids=pos, past_key_values=cache,
                           cache_position=cp, use_cache=True)
            # 只做「拷到静态 buffer」：cast fp16→fp32 与采样都在 graph 外。
            out_logits.copy_(o.logits[:, -1, :])

        with _t.inference_mode():
            mask[0, :1] = 1
            for _ in range(3):
                step()
            g = _t.cuda.CUDAGraph()
            with _t.cuda.graph(g):
                step()
            try:
                cache.reset()
            except Exception:  # noqa: BLE001
                for lay in cache.layers:
                    if getattr(lay, "keys", None) is not None:
                        lay.keys.zero_(); lay.values.zero_()
        ctx = {"cache": cache, "in_tok": in_tok, "mask": mask, "pos": pos,
               "cp": cp, "out_logits": out_logits, "graph": g,
               "stage": stage}
        self._graph_ctx[stage] = ctx
        return ctx
'''

NEW_GEN = '''    def generate_graph(self, stage: str, input_ids, max_new_tokens: int,
                       deadline: float, temperature: float = 0.0,
                       rep_pen: float = 0.0) -> dict:
        """单序列（B=1）CUDA graph 解码；返回与 generate 同构 dict。

        ★ [V2.2.15] temp>0 与重复惩罚都走 graph 快路径（采样在 graph 外）：
          · temp==0 ⇒ argmax（与旧版逐 token 一致）；
          · temp>0  ⇒ softmax(scores/temp) + multinomial（语义同慢路径）；
          · rep_pen>1 ⇒ HF 口径（正分除、负分乘；只罚已生成 token）；
          · confidence 仍按「所选 token 的 logprob 均值取 exp」，口径不变。
        返回 dict 增加 graph / sampled / temp 三个留痕字段。
        """
        import torch as _t
        ids = input_ids.to("cuda")
        L = int(ids.shape[1])
        total = self._GRAPH_TOTAL
        if L + max_new_tokens + 2 > total:
            raise RuntimeError("prompt+max_new 超出 graph cache")
        ctx = self._graph_capture(stage)
        cache = ctx["cache"]
        in_tok, mask, pos, cp = ctx["in_tok"], ctx["mask"], ctx["pos"], ctx["cp"]
        out_logits, g = ctx["out_logits"], ctx["graph"]
        if self.adapter_names and stage in self.adapter_names:
            self.model.set_adapter(self.adapter_names[stage])
        temp = float(temperature or 0.0)
        _pen_on = bool(rep_pen and rep_pen > 1.0)
        _vocab = int(out_logits.shape[-1])
        eos = self.tok.eos_token_id
        try:
            with _t.inference_mode():
                cache.reset()
                mask.zero_()
                o = self.model(input_ids=ids,
                               attention_mask=_t.ones(
                                   (1, L), dtype=_t.long, device="cuda"),
                               past_key_values=cache,
                               cache_position=_t.arange(L, device="cuda"),
                               use_cache=True)
                cur_logits = o.logits[:, -1, :].float()
                mask[0, :L] = 1
                # 采样状态全放 GPU：逐 token 只同步一次（取 token id 判 EOS）。
                pen_vec = _t.ones(_vocab, dtype=_t.float32, device="cuda")
                gen = _t.empty((max_new_tokens,), dtype=_t.long, device="cuda")
                lps = _t.empty((max_new_tokens,), dtype=_t.float32,
                               device="cuda")
                n = 0
                while n < max_new_tokens:
                    if time.time() > deadline:
                        raise TimeoutError("graph 生成超时")
                    scores = cur_logits[0]
                    if _pen_on and n > 0:
                        scores = _t.where(scores > 0, scores / pen_vec,
                                          scores * pen_vec)
                    if temp > 0:
                        nxt = _t.multinomial(
                            _t.softmax(scores / temp, dim=-1), 1)
                    else:
                        nxt = scores.argmax(-1).reshape(1)
                    cur = int(nxt[0])
                    gen[n] = cur
                    lps[n] = _t.log_softmax(scores, dim=-1)[cur]
                    n += 1
                    if eos is not None and cur == eos:
                        break
                    if n >= max_new_tokens:
                        break
                    if _pen_on:
                        # O(1)：已生成 token 的分数下一步按同一 rep_pen 罚
                        pen_vec[cur] = float(rep_pen)
                    in_tok.fill_(cur)
                    pos.fill_(L + n - 1)
                    cp.fill_(L + n - 1)
                    if L + n - 1 < total:
                        mask[0, L + n - 1] = 1
                    g.replay()
                    cur_logits = out_logits
        except TimeoutError:
            self._set_fp32(True)
            raise
        text = self.tok.decode(gen[:n].tolist(), skip_special_tokens=True)
        conf = (round(float(_t.exp(lps[:n].mean())), 4) if n > 0 else None)
        self._set_fp32(True)
        try:
            with self._stats_lock:
                self.stats["graph_generations"] = int(
                    self.stats.get("graph_generations", 0)) + 1
                if temp > 0:
                    self.stats["graph_sampled_generations"] = int(
                        self.stats.get("graph_sampled_generations", 0)) + 1
                if _pen_on:
                    self.stats["graph_rep_pen_generations"] = int(
                        self.stats.get("graph_rep_pen_generations", 0)) + 1
        except Exception:  # noqa: BLE001
            pass
        return {"text": text, "confidence": conf,
                "gen_tokens": int(n), "prompt_tokens": L,
                "graph": True, "sampled": bool(temp > 0),
                "temp": round(temp, 3)}
'''

OLD_HANDLE = '''        deadline = time.time() + timeout
        out = None
        if temp == 0 and int(ids.shape[0]) == 1:
            try:
                out = self.generate_graph(stage, ids, max_new, deadline)
            except Exception as _ge:  # noqa: BLE001
                print("[graph] fallback:", type(_ge).__name__, _ge, flush=True)
                out = None
        if out is None:
            out = self.generate(stage, ids, max_new, temp, deadline,
                                rep_pen=rep_pen)
'''
NEW_HANDLE = '''        deadline = time.time() + timeout
        out = None
        # ★ [V2.2.15] graph 快路径不再限 temp==0：采样在 graph 外做，
        #   temp>0 与 rep_pen 都支持（这是本地链墙钟的大头）。
        if int(ids.shape[0]) == 1:
            try:
                out = self.generate_graph(stage, ids, max_new, deadline,
                                          temperature=temp, rep_pen=rep_pen)
            except TimeoutError:
                # graph 内超时=真超时：再走一遍慢路径只会白付一次 prefill。
                raise
            except Exception as _ge:  # noqa: BLE001
                print("[graph] fallback:", type(_ge).__name__, _ge, flush=True)
                out = None
        if out is None:
            out = self.generate(stage, ids, max_new, temp, deadline,
                                rep_pen=rep_pen)
'''

OLD_STATS = '''                  "graph_generations": 0,
                  "batch_graph_generations": 0,'''
NEW_STATS = '''                  "graph_generations": 0,
                  "graph_sampled_generations": 0,
                  "graph_rep_pen_generations": 0,
                  "batch_graph_generations": 0,'''

OLD_RES = '''               "ms": round((time.time() - t0) * 1000, 1),
               "rep_pen": round(rep_pen, 3),'''
NEW_RES = '''               "ms": round((time.time() - t0) * 1000, 1),
               "rep_pen": round(rep_pen, 3),
               "graph": bool(out.get("graph")),
               "sampled": bool(out.get("sampled")),'''

def cut(a, b):
    i = text.index(a)
    j = text.index(b, i)
    return i, j

i, j = cut("    def _graph_capture(self, stage: str) -> dict:",
           "    def generate_graph(")
text = text[:i] + NEW_CAPTURE + "\n" + text[j:]
i, j = cut("    def generate_graph(self, stage: str, input_ids",
           "    def _handle(self, req: dict) -> dict:")
text = text[:i] + NEW_GEN + "\n" + text[j:]

for name, old, new in (("handle", OLD_HANDLE, NEW_HANDLE),
                       ("stats", OLD_STATS, NEW_STATS),
                       ("res", OLD_RES, NEW_RES)):
    c = text.count(old)
    assert c == 1, "%s 锚点命中 %d 次（应为 1）" % (name, c)
    text = text.replace(old, new)

assert "out_logits" in text and "graph_sampled_generations" in text
P.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
py_compile.compile(str(P), doraise=True)
b = P.read_bytes()
assert b[:3] == b"\xef\xbb\xbf", "BOM 丢失"
assert b.count(b"\r\n") == 0, "行尾被改成 CRLF"
print("OK service.py:", len(b), "bytes, LF", b.count(b"\n"), "CRLF", b.count(b"\r\n"))
