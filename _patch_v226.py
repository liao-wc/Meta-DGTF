# -*- coding: utf-8 -*-
"""补丁：V2.2.5 → V2.2.6（失败熔断，opt-in 默认关）。

背景（实测）：端点持续不可用时，`LLM.call` 仍按 max_retries=3 逐次重试，
每次吃满单次超时 —— 本地档三次 503 各耗 111s，一次失败白耗 ~333s。

改动：
  1) 标题/__version__ → 2.2.6；docstring 增段
  2) DEFAULT_CONFIG 增 api.circuit_breaker（默认 enabled=False）
  3) LLM.__init__ 增熔断状态（默认关 ⇒ 零行为差）
  4) LLM.call 增：熔断中快速失败 / 冷却后半开试探 / 成功复位 / 失败计数并触发
  5) packed 出口增 llm_cb_opened / llm_cb_skipped（纯增量，默认 0）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENG = ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
SRC = ENG / "Meta-DGTF-V2.2.5.py"
DST = ENG / "Meta-DGTF-V2.2.6.py"

EDITS = [
    ("标题版本",
     "Meta-DGTF-道生三阶模型 · V2.2.5",
     "Meta-DGTF-道生三阶模型 · V2.2.6"),
    ("版本号",
     '__version__ = "2.2.5"',
     '__version__ = "2.2.6"'),
    ("docstring 增段",
     "★ V2.2.5 补丁（零行为差，只补归因）：",
     "★ V2.2.6 补丁（opt-in，默认关 ⇒ 不打开时逐字行为不变）：失败熔断。\n"
     "  端点持续不可用时，原实现按 max_retries 逐次重试并**吃满每次超时**\n"
     "  （实测：本地档三次 503 各 111s ⇒ 一次失败白耗 ~333s；云 API 熔断/限流同样踩）。\n"
     "  配置 api.circuit_breaker = {enabled, fail_threshold, cooldown_sec}：\n"
     "  连续 fail_threshold 次尝试失败 ⇒ 冷却期内**不再发起 HTTP**，直接快速失败；\n"
     "  冷却结束放行一次试探，成功即复位。省下的墙钟与跳过的调用数进产物\n"
     "  （llm_cb_opened / llm_cb_skipped），不是只写在日志里。\n\n"
     "★ V2.2.5 补丁（零行为差，只补归因）："),
    ("默认配置增键",
     '        "json_repair": False,',
     '        "json_repair": False,\n'
     '        # ★ [失败熔断] 默认关（enabled=False ⇒ 逐字零行为差）。\n'
     '        #   打开后：连续 fail_threshold 次尝试失败 ⇒ 冷却 cooldown_sec 内\n'
     '        #   不再发起 HTTP（原实现会把每次重试的超时都等满）。\n'
     '        #   ★ 阈值按**尝试次数**算而不是按 call 算：一次 call 内重试 3 次\n'
     '        #     就是 3 次真实失败、3 份墙钟，按 call 算会漏掉这一层浪费。\n'
     '        "circuit_breaker": {\n'
     '            "enabled": False,\n'
     '            "fail_threshold": 3,\n'
     '            "cooldown_sec": 60,\n'
     '        },'),
    ("init 增状态",
     '        self.json_repaired = 0\n        self.json_repair_failed = 0',
     '        self.json_repaired = 0\n'
     '        self.json_repair_failed = 0\n'
     '        # ★ [失败熔断] 状态（默认 enabled=False ⇒ 下列字段全程不被读，\n'
     '        #   行为与改前逐字一致）。\n'
     '        _cb = api_cfg.get("circuit_breaker") or {}\n'
     '        if not isinstance(_cb, dict):\n'
     '            _cb = {}\n'
     '        self.cb_enabled = bool(_cb.get("enabled", False))\n'
     '        self.cb_threshold = max(1, int(_cb.get("fail_threshold", 3) or 3))\n'
     '        self.cb_cooldown = max(0.1, float(_cb.get("cooldown_sec", 60) or 60))\n'
     '        self.cb_consec_fail = 0\n'
     '        self.cb_open_until = 0.0\n'
     '        self.cb_skipped_calls = 0\n'
     '        self.cb_opened_times = 0'),
    ("call 熔断检查",
     "        _tries = max(1, int(self.max_retries or 0))\n"
     "        for attempt in range(1, _tries + 1):",
     "        _tries = max(1, int(self.max_retries or 0))\n"
     "        # ★ [失败熔断] 关闭时整块不进 ⇒ 零行为差。\n"
     "        if self.cb_enabled:\n"
     "            _cbn = time.monotonic()\n"
     "            if self.cb_open_until > _cbn:\n"
     "                _left = self.cb_open_until - _cbn\n"
     "                with self._lock:\n"
     "                    self.cb_skipped_calls += 1\n"
     "                logger.warning(\n"
     "                    \"[CB-OPEN] 跳过调用（连续 %d 次失败，冷却剩余 %.0fs）\"\n"
     "                    \" stage=%s\", self.cb_consec_fail, _left, stage)\n"
     "                raise RuntimeError(\n"
     "                    \"circuit_open: 连续 %d 次失败，冷却剩余 %.0fs\"\n"
     "                    % (self.cb_consec_fail, _left))\n"
     "            if self.cb_open_until:\n"
     "                # 冷却结束 ⇒ 半开：放行这一次试探，成功即复位\n"
     "                with self._lock:\n"
     "                    self.cb_open_until = 0.0\n"
     "                logger.info(\"[CB-HALF] 冷却结束，放行试探调用 stage=%s\",\n"
     "                            stage)\n"
     "        for attempt in range(1, _tries + 1):"),
    ("成功复位",
     "                resp = self.client.chat.completions.create(**kwargs)\n"
     "                ch = resp.choices[0]",
     "                resp = self.client.chat.completions.create(**kwargs)\n"
     "                # ★ 端点活着 ⇒ 复位连续失败并关闭熔断窗口\n"
     "                #   （只清计数不清窗口 ⇒ 会出现「连续 0 次失败却仍在熔断」，\n"
     "                #    那是一次成功重试把计数洗掉、但窗口还挂着 —— 逻辑自相矛盾）\n"
     "                if self.cb_enabled and (self.cb_consec_fail\n"
     "                                        or self.cb_open_until):\n"
     "                    with self._lock:\n"
     "                        self.cb_consec_fail = 0\n"
     "                        self.cb_open_until = 0.0\n"
     "                ch = resp.choices[0]"),
    ("失败计数与触发",
     "            except Exception as e:\n"
     "                last_err = e\n"
     "                logger.warning(\"调用失败(%d/%d): %s\", attempt, _tries, e)",
     "            except Exception as e:\n"
     "                last_err = e\n"
     "                logger.warning(\"调用失败(%d/%d): %s\", attempt, _tries, e)\n"
     "                if self.cb_enabled:\n"
     "                    _trip = False\n"
     "                    with self._lock:\n"
     "                        self.cb_consec_fail += 1\n"
     "                        if (self.cb_consec_fail >= self.cb_threshold\n"
     "                                and self.cb_open_until <= time.monotonic()):\n"
     "                            self.cb_open_until = (\n"
     "                                time.monotonic() + self.cb_cooldown)\n"
     "                            self.cb_opened_times += 1\n"
     "                            _trip = True\n"
     "                    if _trip:\n"
     "                        logger.warning(\n"
     "                            \"[CB-TRIP] 连续 %d 次失败 ⇒ 熔断 %.0fs\"\n"
     "                            \"（后续调用不再发起 HTTP）\",\n"
     "                            self.cb_consec_fail, self.cb_cooldown)\n"
     "                        # ★ 刚熔断就别再重试剩下的 attempt ——\n"
     "                        #   否则「熔断」只是多记了一行日志，本次 call\n"
     "                        #   仍会把 max_retries 次超时全吃满。\n"
     "                        break"),
    ("产物出口",
     "        _pack[\"llm_json_repair_failed\"] = int(\n"
     "            getattr(self.llm, \"json_repair_failed\", 0) or 0)",
     "        _pack[\"llm_json_repair_failed\"] = int(\n"
     "            getattr(self.llm, \"json_repair_failed\", 0) or 0)\n"
     "        # ★ [失败熔断] 省下来的东西要能出口：开了几次熔断、跳过了几次调用。\n"
     "        #   默认关时两者恒 0（与改前一致的「没有这个读数」语义）。\n"
     "        _pack[\"llm_cb_opened\"] = int(\n"
     "            getattr(self.llm, \"cb_opened_times\", 0) or 0)\n"
     "        _pack[\"llm_cb_skipped\"] = int(\n"
     "            getattr(self.llm, \"cb_skipped_calls\", 0) or 0)"),
]


def main() -> int:
    raw = SRC.read_bytes()
    crlf, lf = raw.count(b"\r\n"), raw.count(b"\n")
    assert crlf == lf, f"源不是纯 CRLF: {crlf} vs {lf}"
    text = raw.decode("utf-8").replace("\r\n", "\n")

    for i, (name, old, new) in enumerate(EDITS, 1):
        n = text.count(old)
        assert n == 1, f"[{i}] {name}: 锚点命中 {n} 次（要求 1）"
        text = text.replace(old, new, 1)
        print(f"  [{i}] OK {name}")

    DST.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    chk = DST.read_bytes()
    c2, l2 = chk.count(b"\r\n"), chk.count(b"\n")
    assert c2 == l2, f"输出不是纯 CRLF: {c2} vs {l2}"
    assert chk.count(b"\r\r\n") == 0, "出现 \\r\\r\\n"
    assert b'"2.2.6"' in chk
    print(f"\n写出 {DST.name}: {len(chk)} bytes / {c2} 行 / 纯 CRLF OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
