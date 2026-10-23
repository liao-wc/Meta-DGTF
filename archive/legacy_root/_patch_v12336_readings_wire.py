# -*- coding: utf-8 -*-
"""v1.23.36：读数显示的**三处接线**（运行中 / 结束 / 产物）。

## 用户要求
「运行中和结束时所有读数都完整显示在日志中，同时结构化显示在产物文档中。」

## 三处（都渲染自**同一份** `_readings_bundle`）
  ① **运行中** · `_finalize_layer_common` 末尾 —— 每层一行紧凑读数（`vp`）；
  ② **结束时** · `MetaDGTF.run` 的 return 前 —— 跨层**总表**打进日志，
     并把 **Markdown 版**存进 `packed["readings_table"]`（供产物用）；
  ③ **产物** · `save_result` 写 md 时 —— 把 ② 存的那张表原样写进正文。

★ ②与③是**同一张表**（`as_md=True` 的那次渲染）⇒ 日志与产物**不可能漂移**。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

# ── ① 每层读数行（挂在 `_stop_criteria_check` 调用之后 —— 那一处是本函数末尾）──
OLD1 = '''        # ★ [停止判据联网] 停止理由复核：**默认关**；打开后只留痕、不改决策。
        #   放在本函数末尾是因为此刻 `stop_reason` 的所有来源（自然停 /
        #   体力耗尽 / 停因级联）都已确定（本函数是两条通道共用的唯一收尾）。
        try:
            self._stop_criteria_check(entry, view)
        except Exception as _e_sc2:  # noqa: BLE001
            logger_web.warning("[W-STOP-CRIT] 调用失败：%s", _e_sc2)'''
NEW1 = '''        # ★ [停止判据联网] 停止理由复核：**默认关**；打开后只留痕、不改决策。
        #   放在本函数末尾是因为此刻 `stop_reason` 的所有来源（自然停 /
        #   体力耗尽 / 停因级联）都已确定（本函数是两条通道共用的唯一收尾）。
        try:
            self._stop_criteria_check(entry, view)
        except Exception as _e_sc2:  # noqa: BLE001
            logger_web.warning("[W-STOP-CRIT] 调用失败：%s", _e_sc2)

        # ★ [读数全量显示 · 运行中] 本层的全部读数打**一行**（不刷屏、不省略）。
        #   渲染自 `_readings_bundle`（与产物的总表**同源**，不可能漂移）。
        try:
            self.vp(_readings_line(entry, view))
        except Exception:
            pass'''

# ── ② 结束时的总表（run 的唯一 return 之前）──
OLD2 = '''            try:
                packed["playbook"] = self._eml_finish(packed)
            except Exception as _ef:
                packed["playbook"] = {"error": "%s: %s"
                                      % (type(_ef).__name__, _ef)}
        return packed'''
NEW2 = '''            try:
                packed["playbook"] = self._eml_finish(packed)
            except Exception as _ef:
                packed["playbook"] = {"error": "%s: %s"
                                      % (type(_ef).__name__, _ef)}
        # ★ [读数全量显示 · 结束] 跨层读数总表：**日志 + 产物同一张表**。
        #   日志版（等宽对齐）进 vp；Markdown 版存进产物（`save_result` 原样写出）。
        try:
            _rt_views = {}
            for _e in ("0", "1", "both", "all"):
                _v = (self._results or {}).get(_e)
                if _v is not None:
                    _rt_views[_e] = _v
            if _rt_views:
                self.vp("")
                self.vp(_readings_table(_rt_views))
                packed["readings_table"] = _readings_table(_rt_views, as_md=True)
        except Exception as _er:
            logger.warning("读数总表渲染失败：%s", _er)
        return packed'''

# ── ③ 产物 md（在「分层目标」块之后）──
OLD3 = '''        f.write("**分层目标**：\\n")
        for _ol in _layer_objective_lines(result):
            f.write(f"{_ol}\\n")
        f.write("\\n")'''
NEW3 = '''        f.write("**分层目标**：\\n")
        for _ol in _layer_objective_lines(result):
            f.write(f"{_ol}\\n")
        f.write("\\n")
        # ★ [读数全量显示 · 产物] 跨层读数总表（**与日志里那张同源**：
        #   由 `MetaDGTF.run` 渲染一次、存进 `readings_table`，这里原样写出）。
        _rt = result.get("readings_table")
        if _rt:
            f.write("## 读数总表（四层）\\n\\n")
            f.write(str(_rt) + "\\n\\n")'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new, tag in ((OLD1, NEW1, "① 每层读数行"),
                          (OLD2, NEW2, "② 结束总表"),
                          (OLD3, NEW3, "③ 产物总表")):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（应为 1）" % (tag, n)
        s = s.replace(old, new, 1)
    assert s.count("_readings_line(entry, view)") == 1
    assert s.count("_readings_table(") == 3, \
        "总表应为 1 定义 + 2 调用（实得 %d）" % s.count("_readings_table(")
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 读数三处接线已加；行数 %d" % out.count(b"\n"))


main()
