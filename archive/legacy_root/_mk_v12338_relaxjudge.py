# -*- coding: utf-8 -*-
"""[v1.23.38 补丁3] smoke_test.py：加 check_v12338_relax_targets。

判据：`_TICK_WEB_RELAX` 的**每个成员**必须在 `web_search.stages` 里存在
      —— 否则「放宽」是**死配置**（放宽了一个不存在的环节名，永远不生效）。

★ 这是「配置键两处定义」的直接应用：放宽表（引擎）与 stages（yaml）是
  两处定义，必须两向对账。
★ 纪律：判据里**不用带反斜杠的正则**（本项目反斜杠计数踩过太多次）——
  一律用 `str.find` / `endswith` / `split` 做定位与解析。
"""
from pathlib import Path

SM = Path(__file__).resolve().parent / "smoke_test.py"

NEW_FN = '''def check_v12338_relax_targets():
    """[v1.23.38] 圈级心跳的**放宽目标表**与 `web_search.stages` 两向对账。

    ★ 为什么需要：`_TICK_WEB_RELAX` 里的环节名若不在 `web_search.stages` 里，
      放宽就是**死配置**（写了个引擎不认的 stage ⇒ 永远不生效、且**不报错**）。
      「配置键两处定义」在本项目的经典坑 ⇒ 用判据钉住。
    ★ 定位/解析一律用纯字符串操作（`find` / `endswith` / `split`），不用正则 —— 
      避免反斜杠转义在「脚本 → 落盘 → 解析」三层里数错。
    """
    bad = []
    _members = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")

    _i = src.find("_TICK_WEB_RELAX = (")
    _j = src.find(")", _i + 1) if _i >= 0 else -1
    if _i < 0 or _j < 0:
        bad.append("[放宽表] 找不到 `_TICK_WEB_RELAX` 定义")
    else:
        _block = src[_i:_j + 1]
        _members = [x for x in _block.split('"')[1::2] if x.strip()]
        if len(_members) < 4:
            bad.append("[放宽表] 成员过少（%d）—— 至少保留原 4 个" % len(_members))

        # ── 与 yaml 的 web_search.stages 对账 ──
        _y = (HERE / "dgtf_config.yaml").read_text(
            encoding="utf-8").replace("\\r\\n", "\\n")
        _chunks = _y.split("\\n")
        _si = next((k for k, l in enumerate(_chunks)
                    if "30 个环节各自的开关" in l), -1)
        _sj = next((k for k, l in enumerate(_chunks)
                    if k > _si and l.strip().startswith("as_evidence")), -1)
        if _si < 0 or _sj < 0:
            bad.append("[放宽表] 定位不到 `web_search.stages` 段")
        else:
            _avail = set()
            for _l in _chunks[_si:_sj]:
                # 恰好 4 空格缩进（stages 段的键缩进）
                if _l.startswith("    ") and not _l.startswith("     "):
                    _s = _l.strip()
                    if _s.endswith(": true") or _s.endswith(": false"):
                        _avail.add(_s.split(":")[0].strip())
            _miss = [x for x in _members if x not in _avail]
            if _miss:
                bad.append("[放宽表] 成员不在 `web_search.stages` 里"
                           "（放宽了也不生效）：%r" % (_miss,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.38 放宽目标表（%d 个成员全部在 web_search.stages 里，"
          "两向对账过）全过" % len(_members))
    return True


def check_v12338_backfeed():'''

CALL_OLD = """    if not check_v12338_backfeed():
        return 1"""
CALL_NEW = """    if not check_v12338_relax_targets():
        return 1
    if not check_v12338_backfeed():
        return 1"""


def _rw(p, fn):
    raw = p.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "%s 不是纯 CRLF" % p.name
    assert b"\r\r\n" not in raw, "%s 含 CRLF 双写" % p.name
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out, "%s 写出后含 CRLF 双写" % p.name
    assert out.count(b"\n") == out.count(b"\r\n"), "%s 写出后不是纯 CRLF" % p.name
    p.write_bytes(out)


def apply(s):
    n = s.count("def check_v12338_backfeed():")
    assert n == 1, "check_v12338_backfeed 定义锚点命中 %d 次（要求 1）" % n
    s = s.replace("def check_v12338_backfeed():", NEW_FN)
    n = s.count(CALL_OLD)
    assert n == 1, "调用锚点命中 %d 次（要求 1）" % n
    s = s.replace(CALL_OLD, CALL_NEW)
    return s


if __name__ == "__main__":
    _rw(SM, apply)

    raw = SM.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n")
    assert b"\r\r\n" not in raw
    src = raw.decode("utf-8")
    assert src.count("def check_v12338_relax_targets():") == 1
    assert src.count("if not check_v12338_relax_targets():") == 1
    import ast
    ast.parse(src)
    print("[ok] smoke_test.py 已加 check_v12338_relax_targets + 调用")
    print("[ok] 行数（LF 计）=", src.count("\n"), "| 纯 CRLF | AST OK")
