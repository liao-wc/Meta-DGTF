# -*- coding: utf-8 -*-
"""修：读数**必须进日志**（改用 `logger.info`，不受 `verbose` 控制）。

## 逮到的问题
第一版用 `self.vp(...)` 输出读数 —— 但 `vp` **受 `output.verbose` 控制**，
而冒烟/多数调用是 `verbose=False` ⇒ **读数行被静默吞掉**。
用户要求是「运行中和结束时所有读数都**完整显示在日志中**」⇒
它属于**日志**（logging），不属于「啰嗦模式」。

## 为什么这算真缺陷
`logger` 是「总要写进日志的那一类」（真跑脚本把 logging 落到 `_fullrun_*.log`），
而 `vp` 是「仅 verbose 时的进度感」。读数是要**事后审计**的东西 ⇒ 归 logger。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

OLD1 = '''        # ★ [读数全量显示 · 运行中] 本层的全部读数打**一行**（不刷屏、不省略）。
        #   渲染自 `_readings_bundle`（与产物的总表**同源**，不可能漂移）。
        try:
            self.vp(_readings_line(entry, view))
        except Exception:
            pass'''
NEW1 = '''        # ★ [读数全量显示 · 运行中] 本层的全部读数打**一行**（不刷屏、不省略）。
        #   渲染自 `_readings_bundle`（与产物的总表**同源**，不可能漂移）。
        #   ★ 走 `logger`（**不受 verbose 控制**）：读数是事后审计用的，
        #     不是「啰嗦模式」的进度感 —— 用 vp 会被 verbose=False 静默吞掉。
        try:
            logger.info(_readings_line(entry, view))
        except Exception:
            pass'''

OLD2 = '''            if _rt_views:
                self.vp("")
                self.vp(_readings_table(_rt_views))
                packed["readings_table"] = _readings_table(_rt_views, as_md=True)'''
NEW2 = '''            if _rt_views:
                # ★ 同上：走 logger（真跑脚本把 logging 落到日志文件里）。
                logger.info("")
                logger.info(_readings_table(_rt_views))
                packed["readings_table"] = _readings_table(_rt_views, as_md=True)'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new, tag in ((OLD1, NEW1, "① 每层行改 logger"),
                          (OLD2, NEW2, "② 总表改 logger")):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（应为 1）" % (tag, n)
        s = s.replace(old, new, 1)
    assert "self.vp(_readings_line" not in s
    assert "self.vp(_readings_table" not in s
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 读数改走 logger；行数 %d" % out.count(b"\n"))


main()
