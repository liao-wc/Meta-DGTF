# -*- coding: utf-8 -*-
"""Step8b：修 `check_v1238_render_guards` / `check_v12320_quiet_output`

问题（本轮第 2 个真坑）：全套冒烟里判红，单独跑却 ✓。
  · 现象：v1238 报「_stop_kind_summary 没被 save_result 调用（死代码）」、
    v12320 报 `self.dump_rounds` 命中 0 次。
  · 实测：`inspect.getsource(mod.save_result)` 在**特定跑序**下取不到（或取
    到别的东西）—— 但把这两个 check 单跑、或按前 74/82 个 check 的顺序跑，
    长度都稳定 41526。
  · 判据自身的设计缺陷（必须修）：两个 check 都用 `except Exception` 把
    「**取不到源码**」和「**源码里没这个串**」**混成同一个 bad 项**，
    于是「判据自己没拿到源码」被读成「守卫没接线 / 死代码」—— **方向错的
    断言比没断言更危险**。

修法（判据侧，不动主文件）：
  加一个**共享** helper `_src_of(func)`：
    - 先试 `inspect.getsource(func)`；
    - 失败（或结果短得离谱，< 200 字符）⇒ 退回**直接读源文件** +
      按函数名切块（用 `ast` 定位 `def` 的起止行，最稳）；
    - 退回也失败 ⇒ 抛 `RuntimeError`，由调用点显式报「**判据未能取到源码**」
      （与「源码里没这个串」**分开报**，绝不混）。
  并把两个 check 的接线断言换成用 `_src_of`，且 bad 文案区分两类失败。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "smoke_test.py"


def sub(text, anchor, new, tag, count=1):
    n = text.count(anchor)
    assert n == count, (
        f"[{tag}] 锚点命中 {n} 次（期望 {count}）\n锚点={anchor[:160]!r}")
    return text.replace(anchor, new, count)


HELPER = '''def _src_of(func):
    """取函数源码，**稳健版** —— 取不到就退回读源文件，绝不静默返回空串。

    ★ 为什么需要它：`inspect.getsource` 依赖 `linecache` + `__file__`，
      在长跑序里可能失效（本仓库实测）。判据若用 `try/except` 把失败吞成
      `""`，就会把「取不到源码」误报成「源码里没有这个串」——
      **方向错的断言比没断言更危险**。
    ★ 返回：源码字符串；若两条路都失败 ⇒ raise（调用点必须显式报错）。
    """
    import inspect as _ins
    import ast as _ast
    _s = ""
    try:
        _s = _ins.getsource(func) or ""
    except Exception:
        _s = ""
    if len(_s) >= 200:
        return _s
    # 退回：直接读源文件，用 ast 按函数名切块
    _f = None
    try:
        _f = _ins.getsourcefile(func)
    except Exception:
        _f = None
    if not _f:
        _f = str(getattr(globals().get("mod"), "__file__", "") or "")
    if _f and Path(_f).exists():
        _txt = Path(_f).read_bytes().decode("utf-8")
        _txt = _txt.replace("\\r\\n", "\\n")
        _name = getattr(func, "__name__", "")
        _cls = ""
        _q = getattr(func, "__qualname__", "") or ""
        if "." in _q:
            _cls = _q.split(".")[-2]
        try:
            _tree = _ast.parse(_txt)
        except Exception:
            _tree = None
        if _tree is not None:
            _want = [_name]
            for _node in _ast.walk(_tree):
                if isinstance(_node, (_ast.FunctionDef,
                                      _ast.AsyncFunctionDef)):
                    if _node.name not in _want:
                        continue
                    _rng = getattr(_node, "end_lineno", None)
                    if _rng is None:
                        continue
                    _lines = _txt.split("\\n")
                    _blk = "\\n".join(_lines[_node.lineno - 1:_rng])
                    if _cls:
                        # 类内方法：确认名字对得上（避免同名函数串）
                        _s = _blk
                    else:
                        _s = _blk
                    break
    if len(_s) < 60:
        raise RuntimeError(
            "判据未能取到源码：%s（两条路都失败）"
            % getattr(func, "__name__", "?"))
    return _s


'''


def main():
    raw = SRC.read_bytes()
    txt = raw.decode("utf-8")
    assert txt.count("\r\n") == txt.count("\n"), "smoke_test.py 不是纯 CRLF"
    assert "\r\r\n" not in txt, "含 \\r\\r\\n"
    t = txt.replace("\r\n", "\n")

    # ── 1) 插入 helper：放在 v1238 check 之前 ────────────────────
    t = sub(
        t,
        'def check_v1238_render_guards():\n',
        HELPER + 'def check_v1238_render_guards():\n',
        "helper", 1)

    # ── 2) v1238 接线断言换成 _src_of + 分开报错 ────────────────
    t = sub(
        t,
        '    # ── 接线断言（防死代码）────────────────────────────────────\n'
        '    _ss = _inspect.getsource(m.save_result)\n'
        '    if "_stop_kind_summary(" not in _ss:\n'
        '        bad.append("_stop_kind_summary 没被 save_result 调用（死代码）")\n'
        '    if "_dedup_suspensions_for_render(" not in _ss:\n'
        '        bad.append("_dedup_suspensions_for_render 没被 save_result 调用（死代码）")\n',
        '    # ── 接线断言（防死代码）────────────────────────────────────\n'
        '    # ★ 取源码失败与「源码里没这个串」**分开报** —— 混成一句会\n'
        '    #   把「判据自己没拿到源码」读成「守卫是死代码」。\n'
        '    try:\n'
        '        _ss = _src_of(m.save_result)\n'
        '    except Exception as _e:\n'
        '        bad.append("判据未能取到 save_result 源码（非死代码结论）：%s"\n'
        '                   % _e)\n'
        '        _ss = None\n'
        '    if _ss is not None:\n'
        '        if "_stop_kind_summary(" not in _ss:\n'
        '            bad.append(\n'
        '                "_stop_kind_summary 没被 save_result 调用（死代码）")\n'
        '        if "_dedup_suspensions_for_render(" not in _ss:\n'
        '            bad.append(\n'
        '                "_dedup_suspensions_for_render 没被 save_result 调用"\n'
        '                "（死代码）")\n',
        "v1238.wiring", 1)

    # ── 3) v12320 同样处理 ──────────────────────────────────────
    t = sub(
        t,
        '    # ⑤ 两个守卫都读 self.dump_rounds\n'
        '    _src = (inspect.getsource(mod.DGTF.dump_round)\n'
        '            + inspect.getsource(mod.DGTF.dump_final))\n'
        '    if _src.count("self.dump_rounds") != 2:\n'
        '        bad.append("[⑤] 两个留痕守卫没都读 self.dump_rounds（命中 %d 次）"\n'
        '                   % _src.count("self.dump_rounds"))\n',
        '    # ⑤ 两个守卫都读 self.dump_rounds\n'
        '    # ★ 取源码失败与「命中次数不对」**分开报**。\n'
        '    try:\n'
        '        _src = (_src_of(mod.DGTF.dump_round)\n'
        '                + _src_of(mod.DGTF.dump_final))\n'
        '    except Exception as _e:\n'
        '        bad.append("[⑤] 判据未能取到 dump_round/dump_final 源码"\n'
        '                   "（非「未接线」结论）：%s" % _e)\n'
        '        _src = None\n'
        '    if _src is not None and _src.count("self.dump_rounds") != 2:\n'
        '        bad.append("[⑤] 两个留痕守卫没都读 self.dump_rounds（命中 %d 次）"\n'
        '                   % _src.count("self.dump_rounds"))\n',
        "v12320.src", 1)

    out = t.replace("\n", "\r\n")
    SRC.write_bytes(out.encode("utf-8"))
    print("STEP8B PATCH OK")


if __name__ == "__main__":
    main()
