# -*- coding: utf-8 -*-
"""v1.23.36 判据：**读数全量显示**（运行中 / 结束 / 产物 三处 + 同源）。

## 为什么这样写
用户要求「运行中和结束时所有读数都完整显示在日志中，同时结构化显示在产物文档中」。
判据必须同时钉住三件事：
  ① **日志里有**（跑一次 mock run，捕获 logging ⇒ 断言真有那两处输出）；
  ② **产物里有**（`packed["readings_table"]` 非空且是 Markdown 表）；
  ③ **同源**（日志总表与产物表的**数字**必须一致 ⇒ 防「两处各渲染一份」漂移）。
★ 抓 logging 而不是 stdout：`vp` 受 verbose 控制，读数走 `logger`（不受控）——
  这条判据本身就钉住了「不许改回 vp」（变异体 M60 背书）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "smoke_test.py"

NEW_FN = '''def check_v12336_readings():
    """[v1.23.36] 读数全量显示：运行中一行 + 结束总表 + 产物结构化（同源）。

    ★ 用户口径：「运行中和结束时所有读数都**完整显示在日志中**，同时
      **结构化显示在产物文档中**」。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    for _t in ("def _readings_bundle", "def _readings_line",
               "def _readings_table"):
        if _t not in src:
            bad.append("[读数] 缺 %s" % _t)
    if "logger.info(_readings_line(entry, view))" not in src:
        bad.append("[读数] 每层读数行**没走 logger**（走 vp 会被 verbose 吞掉）")
    if "logger.info(_readings_table(_rt_views))" not in src:
        bad.append("[读数] 结束总表**没走 logger**")
    if 'packed["readings_table"]' not in src:
        bad.append("[读数] 总表**没存进产物**（产物侧拿不到）")

    # ── 真实入口（零 API 花费）：跑一次 mock run，捕获 logging ──
    import logging as _lg
    _logger = _lg.getLogger("dgtf")
    _old_h = list(_logger.handlers)
    _old_lv = _logger.level
    _buf = io.StringIO()
    try:
        _logger.handlers = [_lg.StreamHandler(_buf)]
        _logger.setLevel(_lg.INFO)
        _cfg = build_cfg(False)
        _res = mod.MetaDGTF(_cfg).run("读数显示判据题",
                                      route=["0", "1"],
                                      rounds={"0": 2, "1": 2},
                                      parallel_mode="serial", run_id="")
    finally:
        _logger.handlers = _old_h
        _logger.setLevel(_old_lv)
    _log = _buf.getvalue()

    _lines = [l for l in _log.splitlines() if "📊 [" in l]
    if not _lines:
        bad.append("[读数] 日志里**没有**每层读数行（📊 [层]）")
    elif len(_lines) < 2:
        bad.append("[读数] 每层读数行只有 %d 行（两层应至少 2 行）" % len(_lines))
    if "读数总表（四层）" not in _log:
        bad.append("[读数] 日志里**没有**结束总表")

    _rt = (_res or {}).get("readings_table") or ""
    if not _rt:
        bad.append("[读数] 产物里没有 `readings_table`")
    elif "| 层 |" not in _rt or "---" not in _rt:
        bad.append("[读数] 产物总表不是 Markdown 表格：%r" % (_rt[:60],))
    else:
        # ★ 同源核对：日志表与产物表里的**圈数**必须一致（防两处各渲染一份）
        import re as _re2
        _nums_md = _re2.findall(r"\\| (\\d) \\| (\\d+) \\|", _rt)
        _ok_same = True
        for _e, _r in _nums_md:
            if ("[%s] 圈 %s" % (_e, _r)) not in _log:
                _ok_same = False
        if not _ok_same:
            bad.append("[读数] 日志表与产物表**对不上**（两处各渲染 ⇒ 会漂移）")

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.36 读数全量显示（每层一行 · 结束总表 · 产物 Markdown 表 · "
          "三处同源 · 走 logger 不受 verbose 控制）全过")
    return True


def check_v12336_allweb():'''

ANCHOR_CALL = '''    if not check_v12336_allweb():
        return 1'''
NEW_CALL = '''    if not check_v12336_allweb():
        return 1
    if not check_v12336_readings():
        return 1'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "smoke_test.py 应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    n = s.count("def check_v12336_allweb():")
    assert n == 1, "插入锚点命中 %d 次" % n
    s = s.replace("def check_v12336_allweb():", NEW_FN, 1)
    n2 = s.count(ANCHOR_CALL)
    assert n2 == 1, "调用锚点命中 %d 次" % n2
    s = s.replace(ANCHOR_CALL, NEW_CALL, 1)
    assert "import io" in s[:4000] or "\\nimport io" in s, "smoke_test 需 import io"
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 读数判据已加；smoke_test.py 行数 %d" % out.count(b"\n"))


main()
