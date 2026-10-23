# -*- coding: utf-8 -*-
"""Step9c：把探针响应的**根级 `no_probe_reason`** 接进 view（补接线缺口）。

问题（「有接线 ≠ 这跑走得到」）：
  `_quality_check` 的 E5 双向判据读 `getattr(view, "no_probe_reason", "")`，
  但**没有任何一处把响应的 `no_probe_reason` 写进 view** ⇒ 真跑里
  `honest_empty` 永远不可能触发，空探针**一律**被判 `lazy_empty`。
  提示词里许诺的「空探针配得上理由就是合格答案，不扣分」**兑现不了**。

修法：在四处探针解析点，`data = parse_json(...)` 之后立刻把根级
  `no_probe_reason` 抄到 `view.no_probe_reason`。
  ★ 只做「有则记录」：模型没写就不写，`getattr` 默认空串，行为不变。
  ★ 累积策略：**后来的非空理由覆盖先前的空** —— 重试路径里第一次空、
    第二次给了理由，应该被认；反之不覆盖已有非空（保守）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.27.py"

CAPTURE = (
    '        # [E5] 接住**响应的根级** no_probe_reason（空探针的正当理由）。\n'
    '        _npr = str(data.get("no_probe_reason", "") or "").strip()\n'
    '        if _npr:\n'
    '            view.no_probe_reason = _npr\n'
)


def sub(text, anchor, new, tag, count=1):
    n = text.count(anchor)
    assert n == count, (
        f"[{tag}] 锚点命中 {n} 次（期望 {count}）\n锚点={anchor[:160]!r}")
    return text.replace(anchor, new, count)


def main():
    raw = SRC.read_bytes()
    txt = raw.decode("utf-8")
    assert txt.count("\r\n") == txt.count("\n"), "主文件不是纯 CRLF"
    assert "\r\r\n" not in txt, "主文件含 \\r\\r\\n"
    t = txt.replace("\r\n", "\n")

    # research：其后紧跟 E6 collect 注释
    t = sub(
        t,
        '        data = self.llm.parse_json(raw) or {}\n'
        '\n'
        '        out: List[dict] = []\n'
        '        _e6_seen = 0        # [E6] 候选探针数（含被剪掉的）\n'
        '        _e6_max_gain = 0.0  # [E6] 候选里最大的 G\n'
        '        for p in (data.get("probes") or []):\n'
        '            if not isinstance(p, dict):\n'
        '                continue\n'
        '            q = str(p.get("question", "")).strip()[:200]\n'
        '            link = str(p.get("link", "")).strip()[:120]\n'
        '            try:\n'
        '                gain = float(p.get("expected_gain", 0.0))\n'
        '            except (TypeError, ValueError):\n'
        '                gain = 0.0\n'
        '            gain = max(0.0, min(1.0, gain))\n'
        '            _e6_seen += 1\n'
        '            _e6_max_gain = max(_e6_max_gain, gain)\n'
        '            if not q or len(q) < 6 or not link or gain < min_gain:\n'
        '                continue\n'
        '            covers_raw = p.get("covers") or []\n',
        '        data = self.llm.parse_json(raw) or {}\n'
        '\n' + CAPTURE +
        '\n'
        '        out: List[dict] = []\n'
        '        _e6_seen = 0        # [E6] 候选探针数（含被剪掉的）\n'
        '        _e6_max_gain = 0.0  # [E6] 候选里最大的 G\n'
        '        for p in (data.get("probes") or []):\n'
        '            if not isinstance(p, dict):\n'
        '                continue\n'
        '            q = str(p.get("question", "")).strip()[:200]\n'
        '            link = str(p.get("link", "")).strip()[:120]\n'
        '            try:\n'
        '                gain = float(p.get("expected_gain", 0.0))\n'
        '            except (TypeError, ValueError):\n'
        '                gain = 0.0\n'
        '            gain = max(0.0, min(1.0, gain))\n'
        '            _e6_seen += 1\n'
        '            _e6_max_gain = max(_e6_max_gain, gain)\n'
        '            if not q or len(q) < 6 or not link or gain < min_gain:\n'
        '                continue\n'
        '            covers_raw = p.get("covers") or []\n',
        "research.capture", 1)

    # duel：其后 `out.append(... expected_gain ...})` 紧接 `for a in ... adjudications`
    t = sub(
        t,
        '        data = self.llm.parse_json(raw) or {}\n'
        '\n'
        '        out: List[dict] = []\n'
        '        _e6_seen = 0        # [E6] 候选探针数（含被剪掉的）\n'
        '        _e6_max_gain = 0.0  # [E6] 候选里最大的 G\n'
        '        for p in (data.get("probes") or []):\n'
        '            if not isinstance(p, dict):\n'
        '                continue\n'
        '            q = str(p.get("question", "")).strip()[:200]\n'
        '            link = str(p.get("link", "")).strip()[:120]\n'
        '            try:\n'
        '                gain = float(p.get("expected_gain", 0.0))\n'
        '            except (TypeError, ValueError):\n'
        '                gain = 0.0\n'
        '            gain = max(0.0, min(1.0, gain))\n'
        '            _e6_seen += 1\n'
        '            _e6_max_gain = max(_e6_max_gain, gain)\n'
        '            if not q or len(q) < 6 or not link or gain < min_gain:\n'
        '                continue\n'
        '            out.append({"question": q, "link": link,\n'
        '                        "expected_gain": round(gain, 2)})\n'
        '\n'
        '        for a in (data.get("adjudications") or []):\n',
        '        data = self.llm.parse_json(raw) or {}\n'
        '\n' + CAPTURE +
        '\n'
        '        out: List[dict] = []\n'
        '        _e6_seen = 0        # [E6] 候选探针数（含被剪掉的）\n'
        '        _e6_max_gain = 0.0  # [E6] 候选里最大的 G\n'
        '        for p in (data.get("probes") or []):\n'
        '            if not isinstance(p, dict):\n'
        '                continue\n'
        '            q = str(p.get("question", "")).strip()[:200]\n'
        '            link = str(p.get("link", "")).strip()[:120]\n'
        '            try:\n'
        '                gain = float(p.get("expected_gain", 0.0))\n'
        '            except (TypeError, ValueError):\n'
        '                gain = 0.0\n'
        '            gain = max(0.0, min(1.0, gain))\n'
        '            _e6_seen += 1\n'
        '            _e6_max_gain = max(_e6_max_gain, gain)\n'
        '            if not q or len(q) < 6 or not link or gain < min_gain:\n'
        '                continue\n'
        '            out.append({"question": q, "link": link,\n'
        '                        "expected_gain": round(gain, 2)})\n'
        '\n'
        '        for a in (data.get("adjudications") or []):\n',
        "duel.capture", 1)

    # meta：其后 `_valid_tids = ...`
    t = sub(
        t,
        '        data = self.llm.parse_json(raw) or {}\n'
        '\n'
        '        out: List[dict] = []\n'
        '        _e6_seen = 0        # [E6] 候选探针数（含被剪掉的）\n'
        '        _e6_max_gain = 0.0  # [E6] 候选里最大的 G\n'
        '        for p in (data.get("probes") or []):\n'
        '            if not isinstance(p, dict):\n'
        '                continue\n'
        '            q = str(p.get("question", "")).strip()[:200]\n'
        '            link = str(p.get("link", "")).strip()[:120]\n'
        '            try:\n'
        '                gain = float(p.get("expected_gain", 0.0))\n'
        '            except (TypeError, ValueError):\n'
        '                gain = 0.0\n'
        '            gain = max(0.0, min(1.0, gain))\n'
        '            _e6_seen += 1\n'
        '            _e6_max_gain = max(_e6_max_gain, gain)\n'
        '            if not q or len(q) < 6 or not link or gain < min_gain:\n'
        '                continue\n'
        '            out.append({"question": q, "link": link,\n'
        '                        "expected_gain": round(gain, 2)})\n'
        '\n'
        '        _valid_tids = {str(s.get("id")) for s in duel_tensions\n',
        '        data = self.llm.parse_json(raw) or {}\n'
        '\n' + CAPTURE +
        '\n'
        '        out: List[dict] = []\n'
        '        _e6_seen = 0        # [E6] 候选探针数（含被剪掉的）\n'
        '        _e6_max_gain = 0.0  # [E6] 候选里最大的 G\n'
        '        for p in (data.get("probes") or []):\n'
        '            if not isinstance(p, dict):\n'
        '                continue\n'
        '            q = str(p.get("question", "")).strip()[:200]\n'
        '            link = str(p.get("link", "")).strip()[:120]\n'
        '            try:\n'
        '                gain = float(p.get("expected_gain", 0.0))\n'
        '            except (TypeError, ValueError):\n'
        '                gain = 0.0\n'
        '            gain = max(0.0, min(1.0, gain))\n'
        '            _e6_seen += 1\n'
        '            _e6_max_gain = max(_e6_max_gain, gain)\n'
        '            if not q or len(q) < 6 or not link or gain < min_gain:\n'
        '                continue\n'
        '            out.append({"question": q, "link": link,\n'
        '                        "expected_gain": round(gain, 2)})\n'
        '\n'
        '        _valid_tids = {str(s.get("id")) for s in duel_tensions\n',
        "meta.capture", 1)

    # phase：`_p1 = _parse_probe_resp(data)` 之前
    t = sub(
        t,
        '        data = self.llm.parse_json(raw) or {}\n'
        '        _p1 = _parse_probe_resp(data)\n',
        '        data = self.llm.parse_json(raw) or {}\n'
        '        # [E5] 接住响应的根级 no_probe_reason（空探针的正当理由）。\n'
        '        _npr = str(data.get("no_probe_reason", "") or "").strip()\n'
        '        if _npr:\n'
        '            view.no_probe_reason = _npr\n'
        '        _p1 = _parse_probe_resp(data)\n',
        "phase.capture", 1)

    out = t.replace("\n", "\r\n")
    SRC.write_bytes(out.encode("utf-8"))
    print("STEP9C PATCH OK")


if __name__ == "__main__":
    main()
