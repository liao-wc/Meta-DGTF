import py_compile
from pathlib import Path

E = Path("dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.16.py")
et = E.read_bytes().decode("utf-8").replace("\r\n", "\n")

def rep(name, old, new, cnt=1):
    global et
    c = et.count(old)
    assert c == cnt, "%s 锚点命中 %d 次（应为 %d）" % (name, c, cnt)
    et = et.replace(old, new)

# ── 1) LLM.record_local_call（插在 def call 之前）──────────────
rep("record-method",
    "    def call(self, system, user, temperature=0.6, max_tokens=3000,\n",
    "    def record_local_call(self, stage, calls=1, tokens=0, ms=0) -> None:\n"
    "        \"\"\"本地直连（不经 OpenAI 客户端）的调用记账 —— 成本归因不能有暗路。\n"
    "\n"
    "        ★ [V2.2.16] 本地端点自动切 local 档后，self_check / dual_judge 走\n"
    "          引擎直连 /generate，不经 self.client ⇒ LLM.call 的记账点看不到它们。\n"
    "          不补的话 llm_calls / llm_by_stage 会把这两类调用**整段漏掉**\n"
    "          （正是 V2.2.9/V2.2.10 反复修的那类盲区）。\n"
    "        \"\"\"\n"
    "        try:\n"
    "            _c = max(0, int(calls))\n"
    "            _tk = max(0, int(tokens))\n"
    "            _ms = max(0, int(ms))\n"
    "        except (TypeError, ValueError):\n"
    "            return\n"
    "        _sn = str(stage or \"unknown\")\n"
    "        with self._lock:\n"
    "            self.total_calls += _c\n"
    "            self.total_tokens += _tk\n"
    "            if cost_bucket(_sn) == \"eval\":\n"
    "                self.eval_calls += _c\n"
    "                self.eval_tokens += _tk\n"
    "            else:\n"
    "                self.ops_calls += _c\n"
    "                self.ops_tokens += _tk\n"
    "            self.stage_calls[_sn] = self.stage_calls.get(_sn, 0) + _c\n"
    "            self.stage_tokens[_sn] = self.stage_tokens.get(_sn, 0) + _tk\n"
    "            self.stage_ms[_sn] = self.stage_ms.get(_sn, 0) + _ms\n"
    "\n"
    "    def call(self, system, user, temperature=0.6, max_tokens=3000,\n")

# ── 2) self_check local 记账 ──────────────────────────────────
rep("selfcheck-record",
    "            data[\"_local_confidence\"] = conf\n"
    "            return data\n",
    "            data[\"_local_confidence\"] = conf\n"
    "            try:\n"
    "                self.llm.record_local_call(\n"
    "                    \"self_check\", calls=1,\n"
    "                    tokens=int(payload.get(\"prompt_tokens\") or 0)\n"
    "                    + int(payload.get(\"gen_tokens\") or 0),\n"
    "                    ms=int(float(payload.get(\"ms\") or 0)))\n"
    "            except Exception:  # noqa: BLE001\n"
    "                pass\n"
    "            return data\n")

# ── 3) dual_judge local：回退路径保留 token 读数 + 成功记账 ──────
rep("dj-raw-token",
    "                    raw_results.append({\"ok\": True,\n"
    "                                        \"text\": str(_d.get(\"text\") or \"\"),\n"
    "                                        \"json\": _d.get(\"json\"),\n"
    "                                        \"confidence\": _d.get(\"confidence\")})\n",
    "                    raw_results.append({\"ok\": True,\n"
    "                                        \"text\": str(_d.get(\"text\") or \"\"),\n"
    "                                        \"json\": _d.get(\"json\"),\n"
    "                                        \"confidence\": _d.get(\"confidence\"),\n"
    "                                        \"prompt_tokens\": _d.get(\"prompt_tokens\"),\n"
    "                                        \"gen_tokens\": _d.get(\"gen_tokens\"),\n"
    "                                        \"ms\": _d.get(\"ms\")})\n")

rep("dj-record",
    "            if view is not None:\n"
    "                try:\n"
    "                    view.meta.append(\n"
    "                        \"[DJ-local] 本地双判 %d/%d 条（%d 块，conf=%s）\"\n",
    "            # ★ [V2.2.16] 直连本地服务的成本归因（不经 OpenAI 客户端）\n"
    "            try:\n"
    "                _dtk = 0\n"
    "                _dms = 0\n"
    "                for _r in (raw_results or []):\n"
    "                    if not isinstance(_r, dict):\n"
    "                        continue\n"
    "                    _dtk += (int(_r.get(\"prompt_tokens\") or 0)\n"
    "                             + int(_r.get(\"gen_tokens\") or 0))\n"
    "                    _dms += int(float(_r.get(\"ms\") or 0))\n"
    "                self.llm.record_local_call(\n"
    "                    \"dual_judge\", calls=len(raw_results or []),\n"
    "                    tokens=_dtk, ms=_dms)\n"
    "            except Exception:  # noqa: BLE001\n"
    "                pass\n"
    "            if view is not None:\n"
    "                try:\n"
    "                    view.meta.append(\n"
    "                        \"[DJ-local] 本地双判 %d/%d 条（%d 块，conf=%s）\"\n")

out = et.replace("\n", "\r\n").encode("utf-8")
E.write_bytes(out)
chk = E.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(E), doraise=True)
print("OK V2.2.16: 本地直连调用记账")
