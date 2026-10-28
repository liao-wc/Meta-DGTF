# -*- coding: utf-8 -*-
"""[V2.2.16] 服务端 JSON 约束解码（首 token 约束 + 闭合即停）。

动机（真实转储实测）：引擎 json_mode=True 的调用（dual_judge/he_amps/probe_*/
phase_probe/self_check/decompose_* …）在本地 0.5B 上 **0% 以 { 开头**、全部撞
max_new（224）⇒ 解析不出结构、每 run 几十次 json_repair、墙钟被拖长。
改法：引擎显式声明 json_mode（extra_body）→ shim 透传 → 服务在解码层：
  1) 第 1 个 token 只在「解码后以 { 开头」的 token 集合里采样（mask 其余 logits）；
  2) 一旦 json_done(text)（第一个 JSON 对象闭合）立即停止，不再喷到上限。
纯函数在 gates.py（零 torch，可离线测）；这里只做张量侧接线与读数字段。
"""
import py_compile
from pathlib import Path

P = Path("dgtf_local_llm/service.py")
assert P.read_bytes()[:3] == b"\xef\xbb\xbf"
text = P.read_bytes().decode("utf-8-sig")

def rep(name, old, new):
    global text
    c = text.count(old)
    assert c == 1, "%s 锚点命中 %d 次（应为 1）" % (name, c)
    text = text.replace(old, new)

rep("import",
    "    sanitize_stage, LORA_STAGES, graph_cache_key)\n",
    "    sanitize_stage, LORA_STAGES, graph_cache_key,\n"
    "    json_done, json_first_token_ids)\n")

rep("mask-helper",
    "        return graph_cache_key(stage, tuple(self.adapter_names or ()))\n",
    "        return graph_cache_key(stage, tuple(self.adapter_names or ()))\n"
    "\n"
    "    def _json_lead_mask(self):\n"
    "        \"\"\"json_mode 首 token 约束的 vocab bool mask（惰性构建，失败返回 None）。\n"
    "\n"
    "        ★ 只允许「解码后以 { 开头」的 token；集合来自 tokenizer 词表扫描，\n"
    "          不同 tokenizer 的 ' {' / '\\n{' 变体都能覆盖（纯函数判）。\n"
    "          构建失败/集合为空 ⇒ None ⇒ **不加约束**（宁可退化为原行为，\n"
    "          也不能让约束把生成卡死）。\n"
    "        \"\"\"\n"
    "        cached = getattr(self, \"_json_lead_mask_cache\", \"__unset__\")\n"
    "        if cached != \"__unset__\":\n"
    "            return cached\n"
    "        mask = None\n"
    "        try:\n"
    "            import torch as _t\n"
    "            vocab = dict(self.tok.get_vocab() or {})\n"
    "            ids = json_first_token_ids((i, s) for s, i in vocab.items())\n"
    "            n = int(getattr(self.model.config, \"vocab_size\", 0) or 0)\n"
    "            if ids and n > 0:\n"
    "                mask = _t.zeros((n,), dtype=_t.bool, device=\"cuda\")\n"
    "                for i in ids:\n"
    "                    if 0 <= int(i) < n:\n"
    "                        mask[int(i)] = True\n"
    "                if int(mask.sum().item()) <= 0:\n"
    "                    mask = None\n"
    "            if mask is not None and int(mask.sum().item()) > 0:\n"
    "                print(\"[json] 首 token 约束集合 %d 个 token\"\n"
    "                      % int(mask.sum().item()), flush=True)\n"
    "        except Exception as _e:  # noqa: BLE001\n"
    "            print(\"[json] 首 token 约束不可用（退化为不约束）：\", _e, flush=True)\n"
    "            mask = None\n"
    "        self._json_lead_mask_cache = mask\n"
    "        return mask\n")

rep("gg-signature",
    "    def generate_graph(self, stage: str, input_ids, max_new_tokens: int,\n"
    "                       deadline: float, temperature: float = 0.0,\n"
    "                       rep_pen: float = 0.0) -> dict:\n",
    "    def generate_graph(self, stage: str, input_ids, max_new_tokens: int,\n"
    "                       deadline: float, temperature: float = 0.0,\n"
    "                       rep_pen: float = 0.0,\n"
    "                       json_mode: bool = False) -> dict:\n")

rep("gg-doc",
    "          · confidence 仍按「所选 token 的 logprob 均值取 exp」，口径不变。\n",
    "          · confidence 仍按「所选 token 的 logprob 均值取 exp」，口径不变。\n"
    "          · [V2.2.16] json_mode：首 token 只允许 { 开头；JSON 一闭合即停。\n")

rep("gg-constraint",
    "        temp = float(temperature or 0.0)\n"
    "        _pen_on = bool(rep_pen and rep_pen > 1.0)\n",
    "        temp = float(temperature or 0.0)\n"
    "        _pen_on = bool(rep_pen and rep_pen > 1.0)\n"
    "        _lead_mask = self._json_lead_mask() if json_mode else None\n")

rep("gg-apply-mask",
    "                    scores = cur_logits[0]\n"
    "                    if _pen_on and n > 0:\n",
    "                    scores = cur_logits[0]\n"
    "                    if _lead_mask is not None and n == 0:\n"
    "                        scores = scores.masked_fill(~_lead_mask,\n"
    "                                                    float(\"-inf\"))\n"
    "                    if _pen_on and n > 0:\n")

rep("gg-early-stop",
    "                    if eos is not None and cur == eos:\n"
    "                        break\n"
    "                    if n >= max_new_tokens:\n"
    "                        break\n",
    "                    if eos is not None and cur == eos:\n"
    "                        break\n"
    "                    if json_mode:\n"
    "                        try:\n"
    "                            _jt = self.tok.decode(gen[:n].tolist(),\n"
    "                                                 skip_special_tokens=True)\n"
    "                        except Exception:  # noqa: BLE001\n"
    "                            _jt = \"\"\n"
    "                        if json_done(_jt):\n"
    "                            break\n"
    "                    if n >= max_new_tokens:\n"
    "                        break\n")

rep("gg-return",
    "                \"graph\": True, \"sampled\": bool(temp > 0),\n"
    "                \"graph_key\": self._graph_key(stage),\n"
    "                \"temp\": round(temp, 3)}\n",
    "                \"graph\": True, \"sampled\": bool(temp > 0),\n"
    "                \"graph_key\": self._graph_key(stage),\n"
    "                \"json_mode\": bool(json_mode),\n"
    "                \"temp\": round(temp, 3)}\n")

rep("gen-signature",
    "                 do_warmup: bool = False, use_adapter: bool = True,\n"
    "                 rep_pen: float = 0.0) -> dict:\n",
    "                 do_warmup: bool = False, use_adapter: bool = True,\n"
    "                 rep_pen: float = 0.0, json_mode: bool = False) -> dict:\n")

rep("gen-mask",
    "        _pen_on = bool(rep_pen and rep_pen > 1.0)\n"
    "        try:\n"
    "            for step in range(max_new_tokens):\n",
    "        _pen_on = bool(rep_pen and rep_pen > 1.0)\n"
    "        _lead_mask = self._json_lead_mask() if json_mode else None\n"
    "        try:\n"
    "            for step in range(max_new_tokens):\n")

rep("gen-mask2",
    "                if _pen_on and generated:\n",
    "                if _lead_mask is not None and not generated:\n"
    "                    logits = logits.masked_fill(~_lead_mask.unsqueeze(0),\n"
    "                                                float(\"-inf\"))\n"
    "                if _pen_on and generated:\n")

rep("gen-stop",
    "                if eos is not None and int(nxt[0, 0]) == eos:\n"
    "                    break\n"
    "                if step + 1 >= max_new_tokens:\n"
    "                    break\n",
    "                if eos is not None and int(nxt[0, 0]) == eos:\n"
    "                    break\n"
    "                if json_mode:\n"
    "                    try:\n"
    "                        _jt = self.tok.decode(generated,\n"
    "                                             skip_special_tokens=True)\n"
    "                    except Exception:  # noqa: BLE001\n"
    "                        _jt = \"\"\n"
    "                    if json_done(_jt):\n"
    "                        break\n"
    "                if step + 1 >= max_new_tokens:\n"
    "                    break\n")

rep("handle-parse",
    "        rep_pen = max(0.0, min(2.0, rep_pen))\n",
    "        rep_pen = max(0.0, min(2.0, rep_pen))\n"
    "        json_mode = bool(req.get(\"json_mode\"))\n")

rep("handle-cachekey",
    "                    \"temperature\", \"repetition_penalty\", \"text\", \"messages\")},\n",
    "                    \"temperature\", \"repetition_penalty\", \"json_mode\",\n"
    "                    \"text\", \"messages\")},\n")

rep("handle-graph",
    "                out = self.generate_graph(stage, ids, max_new, deadline,\n"
    "                                          temperature=temp, rep_pen=rep_pen)\n",
    "                out = self.generate_graph(stage, ids, max_new, deadline,\n"
    "                                          temperature=temp, rep_pen=rep_pen,\n"
    "                                          json_mode=json_mode)\n")

rep("handle-slow",
    "            out = self.generate(stage, ids, max_new, temp, deadline,\n"
    "                                rep_pen=rep_pen)\n",
    "            out = self.generate(stage, ids, max_new, temp, deadline,\n"
    "                                rep_pen=rep_pen, json_mode=json_mode)\n")

rep("handle-res",
    "               \"graph_key\": out.get(\"graph_key\"),\n",
    "               \"graph_key\": out.get(\"graph_key\"),\n"
    "               \"json_mode\": bool(json_mode),\n")

P.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
py_compile.compile(str(P), doraise=True)
print("OK service.py: json_mode 约束解码接线完成")
