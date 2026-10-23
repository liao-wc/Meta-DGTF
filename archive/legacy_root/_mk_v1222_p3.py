# -*- coding: utf-8 -*-
"""[v1.22.2 P3] answers 最短长度约束 —— 打补丁脚本（唯一事实源）。

据 _taskbook_audit_v1222.md 的 #1/#2 改过：
  · 任务书要复用 `_anchor_answers_warning` —— 该属性**已被 P2b 占用**
    （「全部 N 条锚点未声明 answers」）。直接赋值会静默摧毁既有留痕，
    且过滤后 answers 全空会**反向**触发它，说出假话。本版新增独立属性
    `_anchor_answers_filtered`，并把「已声明但被过滤」从「未声明」里刨掉。
  · `answers_max_n=5` 原先是硬编码（`[:5]`），本版提成配置。
  · 不动 `_overlap_coef` / `0.6` 阈值（任务书禁令）。
幂等：哨兵串。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.2.py"
SENTINEL = "[v1.22.2 P3]"

src = TARGET.read_bytes().decode("utf-8")
assert src.count("\r\n") == src.count("\n"), "源文件不是纯 CRLF"
src = src.replace("\r\n", "\n")
if SENTINEL in src:
    print("== 已打过 v1.22.2 P3 补丁，跳过 =="); sys.exit(0)


def sub_once(text, old, new, tag):
    n = text.count(old)
    assert n == 1, f"[{tag}] 锚点出现 {n} 次（应为 1）"
    return text.replace(old, new)


# ---------------------------------------------------------- 1. 配置键
C_OLD = (
    '        # [v122 P4 G4.1] 引用表只收 tier ≤ 此值的锚点（1 最硬）。\n'
    '        "tier_floor": 2,\n'
)
C_NEW = (
    '        # [v122 P4 G4.1] 引用表只收 tier ≤ 此值的锚点（1 最硬）。\n'
    '        "tier_floor": 2,\n'
    '        # [v1.22.2 P3] answers 最短长度（中文字符）。短 answer 会让\n'
    '        #   `_overlap_coef` 假命中 —— 它分母取 min，2 字 answer 被长\n'
    '        #   aspect 包住就是 1.000。0 = 不过滤（退回 v1.22.1 行为）。\n'
    '        "answers_min_len": 6,\n'
    '        # [v1.22.2 P3] 单条锚点 answers 上限。原先硬编码 `[:5]`，\n'
    '        #   本版提成配置（值不变 = 行为不变）。\n'
    '        "answers_max_n": 5,\n'
)
src = sub_once(src, C_OLD, C_NEW, "配置键")

# ---------------------------------------------------------- 2. 初始化新属性
I_OLD = (
    '        self._anchor_answers_warning = ""\n'
    '        self._anchor_tier_warning = ""\n'
    '        if not cfg.get("enabled"):\n'
)
I_NEW = (
    '        self._anchor_answers_warning = ""\n'
    '        self._anchor_tier_warning = ""\n'
    '        # [v1.22.2 P3] 与上面那条**分开**：那条说「没声明 answers」，\n'
    '        #   这条说「声明了但太短被丢弃」。两者语义相反，必须能分开读。\n'
    '        self._anchor_answers_filtered = ""\n'
    '        if not cfg.get("enabled"):\n'
)
src = sub_once(src, I_OLD, I_NEW, "初始化")

# ---------------------------------------------------------- 3. 计数变量
N_OLD = (
    '        out: List[dict] = []\n'
    '        _n_explicit_tier = 0     # [v1.22.1 P6] 显式声明 tier 的条数\n'
)
N_NEW = (
    '        out: List[dict] = []\n'
    '        _n_explicit_tier = 0     # [v1.22.1 P6] 显式声明 tier 的条数\n'
    '        _n_declared_ans = 0      # [v1.22.2 P3] 原始条目里声明了 answers 的\n'
    '        _n_dropped_ans = 0       # [v1.22.2 P3] 因过短被丢弃的 answer 条数\n'
    '        _min_len = int(cfg.get("answers_min_len", 6) or 0)\n'
    '        _max_n = int(cfg.get("answers_max_n", 5) or 5)\n'
)
src = sub_once(src, N_OLD, N_NEW, "计数变量")

# ---------------------------------------------------------- 4. 过滤 + 写入锚点
F_OLD = (
    '            if str(a.get("tier") if a.get("tier") is not None else "").strip():\n'
    '                _n_explicit_tier += 1\n'
    '            out.append({"id": str(a.get("id") or ("a" + str(i))),\n'
    '                        "tier": max(1, min(4, _t)),\n'
    '                        "claim": claim[:400],\n'
    '                        # [v1.22.1 P2b] answers：该锚点能回答的侧面（可选）。\n'
    '                        #   缺省 [] → 匹配时回落 claim 路径，行为不变。\n'
    '                        "answers": [str(x)[:60] for x in\n'
    '                                    (a.get("answers") or [])][:5],\n'
)
F_NEW = (
    '            if str(a.get("tier") if a.get("tier") is not None else "").strip():\n'
    '                _n_explicit_tier += 1\n'
    '            # [v1.22.2 P3] answers 过滤：**在原始条目上判**（与 tier 同款\n'
    '            #   纪律 —— 补默认值/截断之后再判就恒真/恒假）。\n'
    '            #   · 空串丢弃（本来也不该进）；\n'
    '            #   · 短于 `answers_min_len` 丢弃并**留痕**（分母取 min 会假命中）；\n'
    '            #   · 最多 `answers_max_n` 条。\n'
    '            _raw_ans = a.get("answers") or []\n'
    '            if isinstance(_raw_ans, list) and _raw_ans:\n'
    '                _n_declared_ans += 1\n'
    '            _ans_kept: List[str] = []\n'
    '            _ans_dropped: List[str] = []\n'
    '            for _x in (_raw_ans if isinstance(_raw_ans, list) else []):\n'
    '                _sx = str(_x).strip()\n'
    '                if not _sx:\n'
    '                    continue\n'
    '                if _min_len > 0 and len(_sx) < _min_len:\n'
    '                    _ans_dropped.append(_sx[:30])\n'
    '                    _n_dropped_ans += 1\n'
    '                    continue\n'
    '                _ans_kept.append(_sx[:60])\n'
    '                if len(_ans_kept) >= _max_n:\n'
    '                    break\n'
    '            out.append({"id": str(a.get("id") or ("a" + str(i))),\n'
    '                        "tier": max(1, min(4, _t)),\n'
    '                        "claim": claim[:400],\n'
    '                        # [v1.22.1 P2b] answers：该锚点能回答的侧面（可选）。\n'
    '                        #   缺省 [] → 匹配时回落 claim 路径，行为不变。\n'
    '                        # [v1.22.2 P3] 加最短长度过滤（见上）。\n'
    '                        "answers": _ans_kept,\n'
    '                        "_answers_dropped": _ans_dropped,\n'
)
src = sub_once(src, F_OLD, F_NEW, "过滤")

# ---------------------------------------------------------- 5. 修「未声明」的口径 + 新增过滤留痕
W_OLD = (
    '        _n_no_ans = sum(1 for x in out if not x.get("answers"))\n'
    '        if out and _n_no_ans == len(out):\n'
    '            self._anchor_answers_warning = (\n'
    '                "全部 " + str(len(out)) + " 条锚点未声明 answers，triage 只能走"\n'
    '                " claim 路径（历史实测：claim 路径对「缺什么」型侧面命中率"\n'
    '                " ≈ 0）")\n'
    '            logger.warning("锚点 answers 全部缺失：%s",\n'
    '                           self._anchor_answers_warning)\n'
)
W_NEW = (
    '        # [v1.22.2 P3] ★ 口径修正：只有在**原始条目**上就没声明 answers\n'
    '        #   的那些，才算「未声明」。被最短长度过滤掉的**不算** ——\n'
    '        #   否则过滤会让这条告警说出假话（"未声明" 明明声明了）。\n'
    '        _n_no_ans = len(out) - _n_declared_ans\n'
    '        if out and _n_no_ans == len(out):\n'
    '            self._anchor_answers_warning = (\n'
    '                "全部 " + str(len(out)) + " 条锚点未声明 answers，triage 只能走"\n'
    '                " claim 路径（历史实测：claim 路径对「缺什么」型侧面命中率"\n'
    '                " ≈ 0）")\n'
    '            logger.warning("锚点 answers 全部缺失：%s",\n'
    '                           self._anchor_answers_warning)\n'
    '        else:\n'
    '            self._anchor_answers_warning = ""\n'
    '        # [v1.22.2 P3] 过滤留痕：被丢弃的 answer 单列。**不与上面那条\n'
    '        #   混用同一个字段** —— 两条告警语义相反，混用会互相覆盖。\n'
    '        if _n_dropped_ans:\n'
    '            self._anchor_answers_filtered = (\n'
    '                str(_n_dropped_ans) + " 条 answer 因短于 "\n'
    '                + str(_min_len) + " 字被丢弃"\n'
    '                "（overlap_coef 分母取 min，短 answer 会产生假命中）")\n'
    '            logger.warning("锚点 answers 过滤：%s",\n'
    '                           self._anchor_answers_filtered)\n'
    '        else:\n'
    '            self._anchor_answers_filtered = ""\n'
)
src = sub_once(src, W_OLD, W_NEW, "告警口径")

# ---------------------------------------------------------- 6. packed 挂键
P_OLD = (
    '            "answers_all_missing": bool(getattr(\n'
    '                self, "_anchor_answers_warning", "")),\n'
)
P_NEW = (
    '            "answers_all_missing": bool(getattr(\n'
    '                self, "_anchor_answers_warning", "")),\n'
    '            # [v1.22.2 P3] 被最短长度过滤的 answer 条数留痕（0 也写）。\n'
    '            "answers_filtered": str(getattr(\n'
    '                self, "_anchor_answers_filtered", "") or ""),\n'
)
src = sub_once(src, P_OLD, P_NEW, "packed 挂键")

# ---------------------------------------------------------- 7. 产物头部渲染
R_OLD = (
    '            if result.get("_anchor_tier_warning"):\n'
    '                f.write(f"⚠️ **锚点 tier 警告**："\n'
    '                        f"{result[\'_anchor_tier_warning\']}\\n\\n")\n'
)
R_NEW = (
    '            if result.get("_anchor_tier_warning"):\n'
    '                f.write(f"⚠️ **锚点 tier 警告**："\n'
    '                        f"{result[\'_anchor_tier_warning\']}\\n\\n")\n'
    '            # [v1.22.2 P3] answers 过滤留痕（**不阻断**）。与 tier 警告\n'
    '            #   并列，让「锚点接进来了但侧面全被过滤」变成可读。\n'
    '            if result.get("_anchor_answers_filtered"):\n'
    '                f.write(f"⚠️ **锚点 answers 警告**："\n'
    '                        f"{result[\'_anchor_answers_filtered\']}\\n\\n")\n'
)
src = sub_once(src, R_OLD, R_NEW, "产物渲染")

# ---------------------------------------------------------- 8. 实例属性声明
A_OLD = (
    '        self._anchor_answers_warning: str = ""\n'
)
A_NEW = (
    '        self._anchor_answers_warning: str = ""\n'
    '        # [v1.22.2 P3] 「声明了但太短被丢弃」—— 与上一条语义相反，分开存。\n'
    '        self._anchor_answers_filtered: str = ""\n'
)
src = sub_once(src, A_OLD, A_NEW, "属性声明")

# ---------------------------------------------------------- 写回
out = src.replace("\n", "\r\n")
b = out.encode("utf-8")
assert b.count(b"\r\n") == b.count(b"\n")
assert b.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert b.count(b"\r") == b.count(b"\r\n"), "出现裸 CR"
TARGET.write_bytes(b)
print("OK: v1.22.2 P3 补丁已写入")
print("  配置 answers_min_len=6 / answers_max_n=5 / 过滤 + 双告警分离 / "
      "packed 键 / 产物渲染")
