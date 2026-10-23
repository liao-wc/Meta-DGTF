# -*- coding: utf-8 -*-
"""**链后**批量执行：切 SRC → 加圈级心跳判据 → 加变异体。

## 为什么拆成"链后"
验证跑（变异体全量 + 真跑 V1236FULL2）**正在读** `smoke_test.py` / `_mut_v12332.py`
⇒ 期间改它们会**让前后不一致**、把"全绿"变成无意义。
⇒ 本脚本只在 `WB_SM=1` 时执行；链跑完我会显式设这个环境变量。

## 本批三件
① `smoke_test.py` / `_mut_v12332.py` 的 `SRC` → `元DGTF-V1.23.37.py`
   （★ 用户口径：副本做完、**上一次验收完再并入** ⇒ 现在才切）；
② `check_v12337_roundtick()`：圈级心跳判据（**构造性**：造池增量、看是否放宽）；
③ 变异体 M78~M79（扩内存，append）。
"""
import io
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"
MU = HERE / "_mut_v12332.py"
DO = os.environ.get("WB_SM") == "1"
if not DO:
    raise SystemExit("⏸ 本脚本要在验证跑**之后**执行：WB_SM=1 python %s"
                     % Path(__file__).name)

# ── ② 判据 ──
SM_FN = '''def check_v12337_roundtick():
    """[v1.23.37] **圈级心跳**：用「池增量」当上一圈产出的代理，只改一处。

    ★ 为什么用池增量而不是 view：`view` 每圈新建 ⇒ 要跨圈就得在两个圈循环里
      各存一次（本项目反复踩的「同一条逻辑两处各写一份」）。
      `_before_round` **每圈都调** ⇒ 在它里记基线，下一圈的增量就是上一圈产出。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    if "_tick_prev_n" not in src:
        bad.append("[圈心跳] 缺 `_tick_prev_n`（跨圈基线没记）")
    if "def _before_round" not in src:
        bad.append("[圈心跳] 找不到 `_before_round`")
    else:
        _i = src.find("def _before_round")
        _j = src.find("\\n    def ", _i + 10)
        _body = src[_i:_j if _j > 0 else _i + 4000]
        if "_tick_prev_n" not in _body:
            bad.append("[圈心跳] 基线逻辑**不在 `_before_round` 里**"
                       "（那就不是「只改一处」）")
    if "self._last_view = view" not in src:
        bad.append("[圈心跳] 没存 `_last_view`（trace 无处落笔）")

    # ── 构造性：造「上一圈零增量」⇒ 本圈应放宽；「有增量」⇒ 不该放宽 ──
    try:
        _cfg = build_cfg(False)
        _mt = mod.MetaDGTF(_cfg)
        class _P:
            amps = []
            threads = []
        _p = _P()
        # 第一圈：只记基线，不该有任何调整
        _mt._before_round("0", _p, 1)
        _n1 = len(_mt._control.applied or [])
        if _n1 != 0:
            bad.append("[圈心跳] 第一圈（无基线）就动了：%r"
                       % ([x.get("key") for x in _mt._control.applied],))
        # 第二圈：池**零增量** ⇒ 应放宽
        _mt._before_round("0", _p, 2)
        _keys = [x.get("key") for x in (_mt._control.applied or [])]
        if not any(str(k).startswith("web.allow.") for k in _keys):
            bad.append("[圈心跳] 上一圈零增量却**没放宽**（触发条件失效）：%r"
                       % (_keys,))
        # 第三圈：池**有增量** ⇒ 不该再放宽（负对照）
        _mt2 = mod.MetaDGTF(build_cfg(False))
        _p2 = _P()
        _mt2._before_round("0", _p2, 1)
        _p2.amps = [{"desc": "新 & 1"}]           # 有产出
        _mt2._before_round("0", _p2, 2)
        _k2 = [x.get("key") for x in (_mt2._control.applied or [])]
        if any(str(k).startswith("web.allow.") for k in _k2):
            bad.append("[圈心跳] 上一圈**有增量**却也放宽了（负对照失败）：%r"
                       % (_k2,))
    except Exception as _e:
        bad.append("[圈心跳] 构造性验证抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.37 圈级心跳（池增量代理 · 只改一处 · 首圈不动 · "
          "零增量放宽 · 有增量不放宽）全过")
    return True


def check_v12336_webneed():'''

SM_CALL_OLD = '''    if not check_v12336_webneed():
        return 1'''
SM_CALL_NEW = '''    if not check_v12336_webneed():
        return 1
    if not check_v12337_roundtick():
        return 1'''

MU_NEW = '''    #   ★ M78 打在**圈级心跳的跨圈基线**上：不记基线 ⇒ 触发条件永远为假
    #     （判据的「零增量应放宽」必判红）。
    ("M78 圈级心跳不记基线（触发条件恒假）",
     '            self._tick_prev_n = _n_now',
     '            self._tick_prev_n = _n_now if False else None'),
    #   ★ M79 打在**"有增量不该放宽"**上：去掉增量判断 ⇒ 每圈都放宽
    #     （判据的负对照必判红）。
    ("M79 圈级心跳不看增量（有产出也放宽）",
     '                if _grew <= 0:',
     '                if True:'),
'''


def _rw_crlf(p, fn):
    """**纯 CRLF 往返**：read_bytes → 断言纯 CRLF → 转 LF → 变换 → 转回 → write_bytes。

    ★ 为什么不用 `write_text`：`smoke_test.py` / `_mut_v12332.py` 都是**纯 CRLF**；
      `write_text` 用 os 默认（LF）⇒ 会把整份文件的换行**改掉**（本项目纪律里
      明令禁止，且 `write_text` 产 `\\r\\r\\n` 时**不报错**）。
    """
    raw = p.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "%s 不是纯 CRLF" % p.name
    assert b"\r\r\n" not in raw, "%s 含 CRLF 双写" % p.name
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s = fn(s)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out, "%s 写出后含 CRLF 双写" % p.name
    p.write_bytes(out)


def main():
    # ① SRC 切换（★ 纯 CRLF 往返）
    for p in (SM, MU):
        s0 = p.read_bytes().decode("utf-8")
        if "元DGTF-V1.23.37.py" in s0:
            print("%s SRC 已是 37（跳过）" % p.name)
            continue
        assert "元DGTF-V1.23.36.py" in s0, "%s 里找不到 36 的 SRC" % p.name
        _rw_crlf(p, lambda s: s.replace("元DGTF-V1.23.36.py",
                                        "元DGTF-V1.23.37.py", 1))
        print("%s SRC → V1.23.37" % p.name)

    # ② 判据（★ 纯 CRLF 往返）
    sm0 = SM.read_bytes().decode("utf-8").replace("\r\n", "\n")
    if "def check_v12337_roundtick" in sm0:
        print("判据已存在（跳过）")
    else:
        assert sm0.count("def check_v12336_webneed():") == 1, "判据插入锚点不对"
        assert sm0.count(SM_CALL_OLD) == 1, "判据调用锚点不对"

        def _patch(s):
            s = s.replace("def check_v12336_webneed():", SM_FN, 1)
            s = s.replace(SM_CALL_OLD, SM_CALL_NEW, 1)
            return s
        _rw_crlf(SM, _patch)
        print("OK check_v12337_roundtick 已加")

    # ③ 变异体（append，★ 纯 CRLF 往返）
    m0 = MU.read_bytes().decode("utf-8").replace("\r\n", "\n")
    if "M78 圈级心跳不记基线" in m0:
        print("M78~M79 已存在（跳过）")
    else:
        assert m0.count("\n]") >= 1, "MUTS 收尾 `\\n]` 找不到"

        def _append(s):
            _t = s.rfind("\n]")
            return s[: _t] + "\n" + MU_NEW.rstrip("\n") + s[_t:]
        _rw_crlf(MU, _append)
        print("OK M78~M79 已 append")


main()
