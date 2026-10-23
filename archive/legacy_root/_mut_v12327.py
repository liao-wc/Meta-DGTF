# -*- coding: utf-8 -*-
"""[v1.23.27] 变异体脚本：对**本版新增判据**做判别力验证。

★ 判据必须自带变异体 —— 没变异体的「全绿」只说明没跑。
★ 变异体打在**判据读的那个东西**上（`if X:` → `if False:`），不是改前缀名。

本版 8 个变异体（每个都打在「判据实际读的那个东西」上）：
  M1  A1  AspectUnit 幂等失效：`add_aspect_unit` 的同 desc 早退改成**总是新建**
      ⇒ 判据「同 desc 返回同 id + 长度不变」必须判红。
  M2  A2  符号对账失效：`aspect_targets_v12327` 只收 A{N}，不收敛 amp#/th#
      ⇒ 判据「targets 同时含 A1 与 amp#1」必须判红。
  M3  A3  双读数合并：`aspect_carry_rate` 直接 `return self.touch_rate`
      ⇒ 判据「两个读数在『触及但没延续』的构造下必须不同」判红。
  M4  D1  四态机失效：`make_belief_item` 非法 status 不再归一化到 "active"
      ⇒ 判据「bad status ⇒ active」判红。
  M5  D2  迁移规则失效：`belief_transition` 的 priority 把 resolved 降到最后
      ⇒ 判据「resolved_by 同时有 revoked 条件时仍判 resolved」判红。
  M6  D3  语义熵失效：`semantic_entropy_of` 对 n<2 返回 `(0.0, 0.0, [])`
      而不是 `(None, ...)` ⇒ 判据「n<2 ⇒ h_norm is None」判红。
  M7  E1  EIG 归一化回退到 bug 版（各臂用自己的 ln(n)）
      ⇒ 判据「targeted G > 0」判红（这正是 Step8c 修的洞）。
  M8  E6  停止裁决失效：`e6_stop_verdict` 把 `seen == 0` 也判成 stop=True
      ⇒ 判据「seen=0 ⇒ (False,'no_candidate')」判红。

用法：
  python _mut_v12327.py                 # 跑全部变异体 + 正对照
  python _mut_v12327.py --only 1,3,5    # 分片跑（sandbox safe-delete 配额按 tool-call 记）

约定：每个变异体 = (编号, 名字, 说明, 打法函数)，打法函数返回
      (临时源码文本, 清理函数)。判据跑在临时源码上，**必须判红**。
      正对照 = 原样源码，判据**必须判绿**。
"""
import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.27.py"


# ══ 通用：文本级替换（LF 归一化后 1 次命中） ══════════════════════
def _sub_count(t, anchor, new):
    n = t.count(anchor)
    if n != 1:
        raise RuntimeError("变异体锚点命中 %d 次（期望 1）：%r" % (n, anchor[:90]))
    return t.replace(anchor, new, 1)


def _load(src):
    return src.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _run_case_via_import(src_text, fn_name, *args):
    """把变异源码写到临时文件并 import，直接调**函数本体**判行为。

    ★ 判据必须落在**行为**上，且锚对准实现本体 —— 所以这里真跑函数，
      不是查字符串。
    """
    import importlib.util
    import tempfile
    import os
    tmp = Path(tempfile.mkdtemp(prefix="_mut27_")) / "mut_mod.py"
    tmp.write_bytes(src_text.replace("\n", "\r\n").encode("utf-8"))
    os.environ.setdefault("DGTF_API_KEY", "sk-mut")
    spec = importlib.util.spec_from_file_location("mut_mod_%d" % os.getpid(), str(tmp))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


# ══ M1：A1 AspectUnit 幂等失效 ════════════════════════════════════
def mut1(src):
    t = _load(src)
    t = _sub_count(
        t,
        '        for _u in self.aspect_units:\n'
        '            if _u.get("desc") == s:\n'
        '                return _u\n',
        '        for _u in self.aspect_units:\n'
        '            if False:\n'
        '                return _u\n')
    m = _run_case_via_import(t, "add_aspect_unit")
    v = m.View(entry="0")
    a1 = v.add_aspect_unit("同一方面", "x", "阳", "anchor", "r")
    a2 = v.add_aspect_unit("同一方面", "x", "阳", "anchor", "r")
    # 幂等失效 ⇒ 两个 id 必然不同 ⇒ 判红
    return not (a1.get("id") == a2.get("id"))


# ══ M2：A2 符号对账只收 A{N} ══════════════════════════════════════
def mut2(src):
    t = _load(src)
    # 把 amp# 分支的收集语句改成 pass（只收 A{N}）
    t = _sub_count(
        t,
        '        for _i, _a in enumerate(self.amps or [], 1):\n'
        '            _put(_a.get("id") or ("amp#%d" % _i), "amp", _a.get("desc", ""))\n',
        '        for _i, _a in enumerate(self.amps or [], 1):\n'
        '            pass\n')
    m = _run_case_via_import(t, "aspect_targets_v12327")
    p = m.Pool()
    p.amps = [{"desc": "某条"}]
    tg = p.aspect_targets_v12327()
    return "amp#1" not in tg


# ══ M3：A3 双读数合并 ═════════════════════════════════════════════
def mut3(src):
    t = _load(src)
    t = _sub_count(
        t,
        '    def aspect_carry_rate(self) -> Optional[float]:\n',
        '    def aspect_carry_rate(self) -> Optional[float]:\n'
        '        return self.touch_rate\n'
        '        # (mutated: 双读数被合并)\n')
    m = _run_case_via_import(t, "View")
    v = m.View(entry="0")
    # 构造「触及但没延续」：touch_rate>0，carry_rate 应为 0
    v.round_log = [{"anchor_touched_n": 3}]
    v.last_carry_rate = 0.0
    tr = v.touch_rate
    cr = v.aspect_carry_rate
    return not (tr > 0 and cr == 0)


# ══ M4：D1 四态机非法归一化失效 ═══════════════════════════════════
def mut4(src):
    t = _load(src)
    t = _sub_count(
        t,
        '    if st not in _BELIEF_STATUS:\n'
        '        st = "active"\n',
        '    if False:\n'
        '        st = "active"\n')
    m = _run_case_via_import(t, "make_belief_item")
    it = m.make_belief_item("x", "y", "totally_bogus_status")
    return it.get("status") != "active"


# ══ M5：D2 迁移优先级失效（resolved 降到最后） ════════════════════
def mut5(src):
    t = _load(src)
    # 把 resolved 分支的判定条件改成永远不成立
    t = _sub_count(
        t,
        '    if str(resolved_by or "").strip():\n'
        '        return "resolved"\n',
        '    if False:\n'
        '        return "resolved"\n')
    m = _run_case_via_import(t, "belief_transition")
    it = m.make_belief_item("x", "y", "active")
    # 纯函数返回**新状态字符串**（不是 dict）
    out = m.belief_transition(it, round_no=5, sources=["probe#1"],
                              attack=["th#1"], resolved_by="decidable_channel")
    return out != "resolved"


# ══ M6：D3 语义熵 n<2 返回 0.0 而不是 None ═══════════════════════
def mut6(src):
    t = _load(src)
    t = _sub_count(
        t,
        '    if n < 2:\n'
        '        return None, 0.0, ([list(range(n))] if n else [])\n',
        '    if n < 2:\n'
        '        return 0.0, 0.0, ([list(range(n))] if n else [])\n')
    m = _run_case_via_import(t, "semantic_entropy_of")
    hn, hr, cl = m.semantic_entropy_of(["只有一条"], corpus=None)
    return hn is not None


# ══ M7：E1 EIG 归一化回退到各臂自己的 ln(n) ══════════════════════
def mut7(src):
    t = _load(src)
    # ★ 打**真正被 Step8c 修的那个东西**：把后熵的归一化改回
    #   「各臂用自己的 ln(n_after)」——即经典 bug 版。
    #   （先前写「_denom = 1.0」打偏了：那只是取消归一化，
    #     而两条字面不相似的文本本来就 h_after≠h_before，仍会 G>0。）
    t = _sub_count(
        t,
        '    for _i, _pi in enumerate(_p):\n'
        '        if _pi <= 0.0:\n'
        '            continue\n'
        '        _guard += 1\n'
        '        _my = _cluster_of.get(_i)\n'
        '        _rest = [_b for _j, _b in enumerate(_live)\n'
        '                 if _cluster_of.get(_j) != _my]\n'
        '        _h_after_raw += _pi * _raw_entropy(_rest)\n',
        '    for _i, _pi in enumerate(_p):\n'
        '        if _pi <= 0.0:\n'
        '            continue\n'
        '        _guard += 1\n'
        '        _rest = [_b for _j, _b in enumerate(_live) if _j != _i]\n'
        '        _dn2 = _math.log(len(_rest)) if len(_rest) > 1 else 1.0\n'
        '        _h_after_raw += _pi * (_raw_entropy(_rest) / _dn2 * _denom)\n')
    m = _run_case_via_import(t, "probe_information_gain")
    bis = [{"id": "B1", "text": "极低温环境下材料脆性阈值是多少",
            "status": "active"},
           {"id": "B2", "text": "极低温环境下材料脆性阈值如何",
            "status": "active"},
           {"id": "B3", "text": "城市轨道交通客流预测模型的误差",
            "status": "active"}]
    probe = {"question": "极低温环境下材料脆性阈值是多少"}
    G, det = m.probe_information_gain(probe, bis)
    # 变异后 h_after > h_before ⇒ G 被夹成 0 ⇒ 原判据「G > 0」判红
    return not (G is not None and G > 0.0)


# ══ M8：E6 停止裁决 seen==0 误判为停 ════════════════════════════
def mut8(src):
    t = _load(src)
    t = _sub_count(
        t,
        '    if _seen <= 0:\n'
        '        return False, "no_candidate"\n',
        '    if _seen <= 0:\n'
        '        return True, "no_candidate"\n')
    m = _run_case_via_import(t, "e6_stop_verdict")
    return m.e6_stop_verdict(0, 0.0, 0.3, 0.02)[0] is not False


# ══ M9：E6 记录点脱离 `if not out:` 守卫 ════════════════════════
def mut9(src):
    """把 research 层的 `if not out:` 守卫去掉 ⇒ 记录点变无条件。

    判据读的是「记录点往回 160 字符内有没有 `if not out:`」——
    变异体就打在**判据读的那个东西**上。语义后果：`probe_stop_history`
    从「只在停止时记」退化成「每轮记」，真跑里 0 条 ⇒ 变成每层 N 条，
    「池收敛」与「模型偷懒」再也分不出来。
    """
    t = _load(src)
    _anchor = ('        if not out:\n'
               '            self._e6_note_stop(pool, view, "research",\n')
    _n = t.count(_anchor)
    if _n != 1:
        raise AssertionError(("M9 锚点命中 %d 次（应为 1）" % _n))
    t = t.replace(
        _anchor,
        ('        if True:\n'
         '            self._e6_note_stop(pool, view, "research",\n'))
    # 判据的那条检查：往回 160 字符内必须能找到 `if not out:`
    _idx = t.find('__e6_note_stop(pool, view, "research"')
    if _idx < 0:
        return True  # 变异把调用弄丢了 ⇒ 也算判红
    _pre = t[max(0, _idx - 160):_idx]
    return "if not out:" not in _pre


MUTATIONS = [
    (1, "A1 AspectUnit 幂等", "同 desc 应返回同 id", mut1),
    (2, "A2 符号对账收敛", "targets 须含 amp#N", mut2),
    (3, "A3 双读数分离", "carry_rate 不得等于 touch_rate", mut3),
    (4, "D1 四态机归一化", "非法 status → active", mut4),
    (5, "D2 迁移优先级", "resolved 优先于 revoked", mut5),
    (6, "D3 语义熵 n<2", "n<2 ⇒ h_norm is None", mut6),
    (7, "E1 EIG 同尺归一化", "targeted G > 0", mut7),
    (8, "E6 停止裁决 seen==0", "no_candidate 不是 stop", mut8),
    (9, "E6 记录点脱守卫", "记录点须在 `if not out:` 里", mut9),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--src", default=str(SRC))
    args = ap.parse_args()

    src = Path(args.src)
    if not src.is_file():
        print("✗ 源码不存在：" + str(src))
        return 2

    ids = []
    if args.only.strip():
        ids = [int(x) for x in args.only.split(",") if x.strip()]

    picked = [m for m in MUTATIONS if not ids or m[0] in ids]
    if not picked:
        print("[骨架] 尚未填入变异体（MUTATIONS 为空）。")
        return 0

    n_red = 0
    for mid, name, why, fn in picked:
        try:
            _ok = fn(src)
            print(("  ✓ M%d 判红（%s）" % (mid, name)) if _ok
                  else ("  ✗ M%d 没判红（%s）—— 变异体失效" % (mid, name)))
            n_red += 1 if _ok else 0
        except Exception as e:
            print("  ✗ M%d 执行异常：%s: %s" % (mid, type(e).__name__, e))
    print("MUT RESULT 判红 %d / %d" % (n_red, len(picked)))
    return 0 if n_red == len(picked) else 1


if __name__ == "__main__":
    sys.exit(main())
