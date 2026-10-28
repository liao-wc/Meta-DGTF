# -*- coding: utf-8 -*-
"""[V2.2.17] 生成 V2.2.17：本地 prompt 瘦身（行去重 + 噪声块截断 + 尾部保护）。

离线原型（真实 584 条引擎 prompt）：总 token 106.6 万 → 58.3 万（-45.3%），
schema 行零丢失。瘦身只对【本地端点】生效（llm.base_url 指本机）⇒ 云端零行为差。
"""
import py_compile
from pathlib import Path

ENG = Path("dgtf_engine/dgtf_v2/engine")
SRC = ENG / "Meta-DGTF-V2.2.16.py"
DST = ENG / "Meta-DGTF-V2.2.17.py"
raw = SRC.read_bytes()
assert raw[:3] != b"\xef\xbb\xbf"
assert raw.count(b"\n") == raw.count(b"\r\n")
text = raw.decode("utf-8").replace("\r\n", "\n")

REPL = []
# 1) 标题 / 版本
REPL.append(("Meta-DGTF-道生三阶模型 · V2.2.16\n",
             "Meta-DGTF-道生三阶模型 · V2.2.17\n"))
REPL.append(('__version__ = "2.2.16"', '__version__ = "2.2.17"'))
# 2) 补丁说明
REPL.append((
    "★ V2.2.16 补丁（JSON 期望显式声明：本地约束解码通道）：",
    "★ V2.2.17 补丁（本地 prompt 瘦身：行去重 + 噪声块截断 + 尾部保护）：\n"
    "     真实 584 条引擎 prompt 统计：行级完全去重可省 **45.3% token**（106.6 万→\n"
    "     58.3 万），且 schema/指令行零丢失 —— prompt 里「参考记忆特征」被重复\n"
    "     2~3 次、「Agent知识回声」/「0层侧面清单」重复多份，0.5B 既读不完也读不\n"
    "     准（p50 2042 token，50% 被 2048 右截断）。\n"
    "     本版在 LLM.call 里对【本地端点】做纯函数瘦身：行级完全去重 + 已知噪声块\n"
    "     只留第一份并截到 CAP + 尾部 TAIL 字符原样保护；云端点一字不动（零行为\n"
    "     差），可用 --local-prompt-diet off 关。packed 新增 llm_prompt_diet 读数。\n"
    "     判据：tests_local_prompt_diet.py（纯函数 + 门控 + 变异体）。\n"
    "\n"
    "★ V2.2.16 补丁（JSON 期望显式声明：本地约束解码通道）："))
# 3) 纯函数（插在 class LLM 之前）
ANCHOR_LLM = "class LLM:\n"
FUNCS = '''# ── [V2.2.17] 本地 prompt 瘦身（纯函数，零外部依赖，可单测）─────────
#: 已知噪声块头（这些块在 prompt 里会被重复追加：参考记忆哈希 / Agent 知识回声 /
#: 0 层侧面清单 / 上一位是谁）。规则：只留第一份，且截到 _LPD_CAP 字符。
_LPD_NOISE_HEADS = ("参考记忆特征", "【Agent知识回声】",
                    "【0层侧面清单】", "【你上一次是谁】")
_LPD_CAP = 240
_LPD_TAIL = 320
_LPD_HEAD_RE = re.compile(r"^\\s*(【[^】]{1,30}】)")


def _lpd_blocks(text: str) -> list:
    """按行首【…】标记把文本粗分块（无标记的长段并入上一块）。"""
    out, cur = [], []
    for ln in text.split("\\n"):
        if _LPD_HEAD_RE.match(ln) and cur:
            out.append("\\n".join(cur))
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        out.append("\\n".join(cur))
    return out


def diet_local_prompt(text: str, cap: int = _LPD_CAP,
                      tail: int = _LPD_TAIL) -> tuple:
    """本地端点专用 prompt 瘦身；返回 (new_text, stats)。

    规则（保守，宁少瘦不多删）：
      R1 行级**完全去重**：strip 后相同的非空行只留第一次出现（顺序不变）；
      R2 噪声块：以上述噪声头开头的块只留第一份，超过 cap 字符截断；
      R3 尾部保护：最后 tail 字符原样保留（JSON schema / 最终指令通常在这里），
         不参与 R1/R2 —— 0.5B 场景下尾部指令比重复记忆重要得多。
    空文本 / 瘦身后为空 / 变长 ⇒ 原样返回（绝不把 prompt 弄坏）。
    """
    if not text:
        return text, {"lines_removed": 0, "blocks_truncated": 0,
                      "chars_before": 0, "chars_after": 0}
    n_tail = max(0, int(tail or 0))
    n_cap = max(0, int(cap or 0))
    if n_tail and len(text) > n_tail:
        head, keep = text[:-n_tail], text[-n_tail:]
    else:
        head, keep = "", text
    seen = set()
    kept = []
    removed = 0
    for ln in head.split("\\n"):
        k = ln.strip()
        if k and k in seen:
            removed += 1
            continue
        if k:
            seen.add(k)
        kept.append(ln)
    head2 = "\\n".join(kept)
    out, seen_noise, trunc = [], set(), 0
    for b in _lpd_blocks(head2):
        s = b.lstrip()
        nk = next((h for h in _LPD_NOISE_HEADS if s.startswith(h)), None)
        if nk is not None:
            if nk in seen_noise:
                trunc += 1
                continue
            seen_noise.add(nk)
            if len(b) > n_cap:
                out.append(b[:n_cap])
                trunc += 1
                continue
        out.append(b)
    new = ("\\n".join(out) + keep) if head else text
    if not new.strip() or len(new) > len(text):
        return text, {"lines_removed": 0, "blocks_truncated": 0,
                      "chars_before": len(text), "chars_after": len(text)}
    return new, {"lines_removed": removed, "blocks_truncated": trunc,
                 "chars_before": len(text), "chars_after": len(new)}


'''
REPL.append((ANCHOR_LLM, FUNCS + ANCHOR_LLM))

# 4) LLM.__init__ 字段（插在 stage_ms 之后）
REPL.append((
    "        self.stage_ms: Dict[str, int] = {}\n",
    "        self.stage_ms: Dict[str, int] = {}\n"
    "        # ★ [V2.2.17] 本地 prompt 瘦身：默认开，但**只对本地端点**生效\n"
    "        #   （云端一字不动 ⇒ 零行为差）；--local-prompt-diet off 可关。\n"
    "        _lpd = api_cfg.get(\"local_prompt_diet\")\n"
    "        self.lpd_enabled = True if _lpd is None else bool(_lpd)\n"
    "        self.lpd_cap = int(_LPD_CAP)\n"
    "        self.lpd_tail = int(_LPD_TAIL)\n"
    "        self._local_endpoint = _is_local_llm_endpoint(config)\n"
    "        self.prompt_diet_stats = {\"applied\": 0, \"chars_before\": 0,\n"
    "                                  \"chars_after\": 0, \"lines_removed\": 0,\n"
    "                                  \"blocks_truncated\": 0}\n"))

# 5) LLM.call：在 kwargs 构建前应用
REPL.append((
    "        kwargs: Dict[str, Any] = {\n"
    "            \"model\": model,\n",
    "        # ★ [V2.2.17] 本地端点 prompt 瘦身（纯函数；失败不阻断调用）。\n"
    "        try:\n"
    "            system, user = self._maybe_diet_prompts(system, user)\n"
    "        except Exception:  # noqa: BLE001\n"
    "            pass\n"
    "        kwargs: Dict[str, Any] = {\n"
    "            \"model\": model,\n"))

# 6) _maybe_diet_prompts 方法（插在 record_local_call 之前）
REPL.append((
    "    def record_local_call(self, stage, calls=1, tokens=0, ms=0) -> None:\n",
    "    def _maybe_diet_prompts(self, system, user):\n"
    "        \"\"\"本地端点 + 开关开 ⇒ 对 system/user 分别瘦身并记账；否则原样返回。\n"
    "\n"
    "        ★ 为什么在 LLM.call 里做（唯一咽喉）：prompt 由几十个调用点拼出来，\n"
    "          逐点改必然漂移；在出货前统一过一遍纯函数，规则只有一份。\n"
    "        ★ 云端（非本机 base_url）直接返回原值 —— 云端 prompt 一字不动。\n"
    "        \"\"\"\n"
    "        if not (getattr(self, \"_local_endpoint\", False)\n"
    "                and getattr(self, \"lpd_enabled\", False)):\n"
    "            return system, user\n"
    "        ns, s1 = diet_local_prompt(system, self.lpd_cap, self.lpd_tail)\n"
    "        nu, s2 = diet_local_prompt(user, self.lpd_cap, self.lpd_tail)\n"
    "        before = s1[\"chars_before\"] + s2[\"chars_before\"]\n"
    "        after = s1[\"chars_after\"] + s2[\"chars_after\"]\n"
    "        if before <= 0 or after <= 0 or after >= before:\n"
    "            return system, user\n"
    "        try:\n"
    "            with self._lock:\n"
    "                st = self.prompt_diet_stats\n"
    "                st[\"applied\"] = int(st.get(\"applied\", 0)) + 1\n"
    "                st[\"chars_before\"] = int(st.get(\"chars_before\", 0)) + before\n"
    "                st[\"chars_after\"] = int(st.get(\"chars_after\", 0)) + after\n"
    "                st[\"lines_removed\"] = (int(st.get(\"lines_removed\", 0))\n"
    "                                        + s1[\"lines_removed\"] + s2[\"lines_removed\"])\n"
    "                st[\"blocks_truncated\"] = (int(st.get(\"blocks_truncated\", 0))\n"
    "                                           + s1[\"blocks_truncated\"]\n"
    "                                           + s2[\"blocks_truncated\"])\n"
    "        except Exception:  # noqa: BLE001\n"
    "            pass\n"
    "        return ns, nu\n"
    "\n"
    "    def record_local_call(self, stage, calls=1, tokens=0, ms=0) -> None:\n"))

# 7) packed 读数出口
REPL.append((
    "        _pack[\"llm_json_repaired\"] = int(\n",
    "        _pack[\"llm_prompt_diet\"] = dict(\n"
    "            getattr(self.llm, \"prompt_diet_stats\", {}) or {})\n"
    "        _pack[\"llm_json_repaired\"] = int(\n"))

# 8) DEFAULT_CONFIG：api.local_prompt_diet（bool，J2 可读性）
REPL.append((
    "        \"local_llm\": {\n"
    "            \"url\": \"http://127.0.0.1:8772/generate\",\n"
    "            # ★ [Round 2] 30→45s、600→160 tokens：0.5B 本地模型 ~6 tok/s，\n"
    "            #   600 tokens 要 100s，必然超时；min schema 160 tokens 足够。\n"
    "            \"timeout\": 45.0,\n"
    "            \"max_new_tokens\": 160,\n"
    "            \"enabled\": True,\n"
    "            \"min_confidence\": 0.6,\n"
    "        },\n",
    "        \"local_llm\": {\n"
    "            \"url\": \"http://127.0.0.1:8772/generate\",\n"
    "            # ★ [Round 2] 30→45s、600→160 tokens：0.5B 本地模型 ~6 tok/s，\n"
    "            #   600 tokens 要 100s，必然超时；min schema 160 tokens 足够。\n"
    "            \"timeout\": 45.0,\n"
    "            \"max_new_tokens\": 160,\n"
    "            \"enabled\": True,\n"
    "            \"min_confidence\": 0.6,\n"
    "        },\n"
    "        # ★ [V2.2.17] 本地端点 prompt 瘦身（行去重 + 噪声块截断 + 尾部保护）。\n"
    "        #   只对本地端点生效；云端点一字不动。--local-prompt-diet off 可关。\n"
    "        \"local_prompt_diet\": True,\n"))

# 9) CLI 参数
REPL.append((
    "    parser.add_argument(\"--local-llm-url\", default=None,\n",
    "    parser.add_argument(\"--local-prompt-diet\", default=None,\n"
    "                        choices=[\"on\", \"off\"],\n"
    "                        help=\"本地端点 prompt 瘦身（行去重+噪声块截断+尾部保护）：\"\n"
    "                             \"on/off（默认 on；只对本地端点生效，云端一字不动）\")\n"
    "    parser.add_argument(\"--local-llm-url\", default=None,\n"))

# 10) CLI 应用（在 prompt_stable_first apply 之后）
REPL.append((
    "    if getattr(args, \"prompt_stable_first\", False):\n"
    "        cfg.setdefault(\"output\", {})[\"prompt_stable_first\"] = True\n",
    "    if getattr(args, \"prompt_stable_first\", False):\n"
    "        cfg.setdefault(\"output\", {})[\"prompt_stable_first\"] = True\n"
    "    if getattr(args, \"local_prompt_diet\", None):\n"
    "        _lpd_on = str(args.local_prompt_diet).lower() != \"off\"\n"
    "        cfg.setdefault(\"api\", {})[\"local_prompt_diet\"] = _lpd_on\n"
    "        print(\"   ✓ 本地 prompt 瘦身：%s（只对本地端点生效）\"\n"
    "              % (\"开\" if _lpd_on else \"关\"))\n"))

for i, (old, new) in enumerate(REPL, 1):
    n = text.count(old)
    assert n == 1, "锚点 %d 命中 %d 次（应为 1）" % (i, n)
    text = text.replace(old, new)

out = text.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)
chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0
assert chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(DST), doraise=True)
print("OK:", DST.name, len(chk), "bytes")
