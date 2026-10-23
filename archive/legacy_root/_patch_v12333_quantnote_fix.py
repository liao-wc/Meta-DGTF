# -*- coding: utf-8 -*-
"""[第六期 · 真缺陷修复] `_quant_note` 定义在 `MetaDGTF`，却被 `DGTF.run` 调用。

## 缺陷（真跑 + 打点探针逮到，**不是探针问题**）
  · 接线点：`DGTF.run` L8776 / L8812 / L8874 调 `self._quant_note(...)`；
  · 定义：`_quant_note(self, view, key, val)` **只定义在 `MetaDGTF`**（L16636），
    而 `MetaDGTF` **不继承** `DGTF`（`MetaDGTF` 每跑一层**新建 `DGTF` 实例**）；
  · ⇒ `DGTF` 实例上查不到该属性 ⇒ **AttributeError**；
  · ⇒ 三处调用都在 `try: ... except Exception: pass` 里 ⇒ **静默吞掉**；
  · ⇒ 表现：真跑 `quant_readings` **四层全空**，而三个纯函数**都跑了**（探针 Q2 有读数）。
  · ★ 这正是本项目错型「**有接线 ≠ 这跑走得到**」+「静默失败」的合体。
  · ★ 判据 ㉛ 只查「`self._quant_note(view,` 出现 ≥2 次」（**存在性**）⇒ 抓不到。
    修完必须补一条**可达性**判据（调用点的宿主类上真的能解析到这个方法）。

## 修法
  把 `_quant_note` **降为模块级函数**（它本就是纯写入口，**不依赖 self**，
  只用 `view`），然后：
    ① `DGTF.run` 三处：`self._quant_note(view, k, v)` → `_quant_note(view, k, v)`
    ② `MetaDGTF` 里的方法定义：整段删掉（避免两份实现 —— 本项目错型
       「同一条逻辑两条实现」）
    ③ 保留 `MetaDGTF` 上的**同名薄转发**？**不保留** —— 少一个真相源更安全；
       全仓已确认 `self._quant_note` 只有那 3 处调用（AST 实测）。

## 锚点纪律
  · 每个锚点先断言 `count == 1`（命中 0 会**静默跳过**）；
  · 全文先转 LF、替换、再转回 CRLF（主文件**纯 CRLF** 铁律）；
  · `write_bytes`（**绝不 write_text**）；写完自检 CR-CR-LF 三元组 = 0。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

# ── A1：在 `def yin_yang_divergence(` 之前插模块级 `_quant_note` ──
A1_ANCHOR = "_YY_DIV_LOW = 0.30"
A1_NEW = '''def _quant_note(view, key: str, val) -> None:
    """[第六期] 把一条量化读数写进 `view.quant_readings`（**唯一写入口**）。

    ★ 纪律：**值不可用（None / 空 dict / 空串）就不写键** ——
      与 `goal_trace` 出口同款（产物里不出现空壳读数）。
    ★ 只记读数，**不改任何判定**（红线：读数不是分数）。
    ★ **模块级函数、不是方法** —— 它只用 `view`，不碰 `self`；
      接线点在 `DGTF.run`（`DGTF` 与 `MetaDGTF` **无继承关系**），
      做成方法会让 `DGTF` 实例上解析不到 ⇒ `AttributeError` 被
      `except Exception: pass` 静默吞掉（真跑 `quant_readings` 恒空）。
    """
    if view is None or not key:
        return
    if val is None or val == "" or val == {}:
        return
    try:
        _d = getattr(view, "quant_readings", None)
        if _d is None:
            view.quant_readings = {}
            _d = view.quant_readings
        _d[str(key)] = dict(val) if isinstance(val, dict) else {"value": val}
    except Exception:
        pass


_YY_DIV_LOW = 0.30'''

# ── A2：删 MetaDGTF 里的方法版（连同 __quant_note_anchor__ 到下一个 def）──
A2_ANCHOR = '''    def _quant_note(self, view, key: str, val) -> None:
        """[第六期] 把一条量化读数写进 `view.quant_readings`（**唯一写入口**）。

        ★ 纪律：**值不可用（None / 空 dict / 空串）就不写键** ——
          与 `goal_trace` 出口同款（产物里不出现空壳读数）。
        ★ 只记读数，**不改任何判定**（红线：读数不是分数）。
        """
        if view is None or not key:
            return
        if val is None or val == "" or val == {}:
            return
        try:
            _d = getattr(view, "quant_readings", None)
            if _d is None:
                view.quant_readings = {}
                _d = view.quant_readings
            _d[str(key)] = dict(val) if isinstance(val, dict) else {"value": val}
        except Exception:
            pass

    def _goal_action_hint(self, entry: str, view) -> str:'''
A2_NEW = '''    def _goal_action_hint(self, entry: str, view) -> str:'''

# ── A3~A5：三处调用改裸名 ──
A3_ANCHOR = '                self._quant_note(view, "restate_fidelity", _rf)'
A3_NEW = '                _quant_note(view, "restate_fidelity", _rf)'
A4_ANCHOR = '                self._quant_note(view, "yin_yang_divergence", _yy)'
A4_NEW = '                _quant_note(view, "yin_yang_divergence", _yy)'
A5_ANCHOR = '                        self._quant_note(view, "ing_density", {'
A5_NEW = '                        _quant_note(view, "ing_density", {'

PATCHES = [
    ("A1 模块级 _quant_note", A1_ANCHOR, A1_NEW),
    ("A2 删 MetaDGTF 方法版", A2_ANCHOR, A2_NEW),
    ("A3 restate_fidelity 调用", A3_ANCHOR, A3_NEW),
    ("A4 yin_yang_divergence 调用", A4_ANCHOR, A4_NEW),
    ("A5 ing_density 调用", A5_ANCHOR, A5_NEW),
]


def main() -> int:
    bak = HERE / "_bak_v12333_pre_quantnote.py"
    raw = SRC.read_bytes()
    txt = raw.decode("utf-8")
    crlf = txt.count("\r\n")
    lf = txt.count("\n") - crlf
    assert lf == 0, "主文件非纯 CRLF（LF-only=%d）" % lf
    assert b"\r\r\n" not in raw
    if not bak.exists():
        bak.write_bytes(raw)
        print("备份 ->", bak.name)

    s = txt.replace("\r\n", "\n")
    # 幂等：已修过就直接退出
    if "def _quant_note(view, key: str, val) -> None:" in s:
        print("已是修后状态（幂等跳过）")
        return 0

    for name, a, b in PATCHES:
        n = s.count(a)
        assert n == 1, "[%s] 锚点命中 %d 次（应 1）" % (name, n)
        s = s.replace(a, b, 1)
        print("  ✓ %s" % name)

    # 自洽：A2 删干净后，不该再有 `self._quant_note`
    n_self = s.count("self._quant_note")
    assert n_self == 0, "仍有 %d 处 self._quant_note（A2 未删干净）" % n_self
    # 不该有两份定义
    assert s.count("def _quant_note(") == 1, "定义份数 != 1"
    # 调用点 3 处（★ `def _quant_note(view,` 也含该子串 ⇒ 用行首缩进区分）
    _calls = [ln for ln in s.splitlines()
              if "_quant_note(view," in ln and not ln.lstrip().startswith("def ")]
    assert len(_calls) == 3, "调用点应为 3 处（实得 %d）" % len(_calls)

    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out, "写出 CR-CR-LF 三元组（换行被污染）"
    SRC.write_bytes(out)
    back = SRC.read_bytes().decode("utf-8")
    assert back.count("\r\n") == out.count(b"\r\n")
    assert back.count("\n") - back.count("\r\n") == 0
    print("OK 主文件已修（%d 行 / 纯 CRLF / CR-CR-LF=0）"
          % (back.count("\n") + 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
