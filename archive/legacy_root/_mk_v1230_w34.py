# -*- coding: utf-8 -*-
"""[v1.23.0 W3+W4] 对撞层/元层接入 + 三票正交化。幂等：哨兵串。

W3：`duel_arbitration`（仲裁材料**不进对撞内容**）+ `meta_clean_check`
    （只对 uncovered 核对，**清算不发起新检索**）。
    接入点收在 `_finalize_layer_common` —— 那是研究/对撞/元三层**唯一**
    共用的收尾（v122 P3-1 已收口），不再往两条通道各写一份。
W4：三票里的**第三票**改为「外部证据裁判」（只看 W# + X#，不看池内产物）；
    仅当联网开启且该环节授权时替换，否则三票逐字与 v1.22.2 相同。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.23.0.py"
SENTINEL = "[v1.23.0 W3]"

src = TARGET.read_bytes().decode("utf-8")
assert src.count("\r\n") == src.count("\n"), "源文件不是纯 CRLF"
src = src.replace("\r\n", "\n")
if SENTINEL in src:
    print("== 已打过 W3/W4 补丁，跳过 =="); sys.exit(0)


def sub_once(text, old, new, tag):
    n = text.count(old)
    assert n == 1, f"[{tag}] 锚点出现 {n} 次（应为 1）"
    return text.replace(old, new)


# ============================================================ 1 Pool 两池
P_OLD = (
    '    # 本次是否授权 W# 作为**可引用对象**（进 _citation_table）。\n'
    '    # ★ 默认 False；由 web_search.as_evidence ∈ {evidence, gate} 打开。\n'
    '    #   即便进了表，W# 也**只允许支撑 →partial**（硬约束见\n'
    '    #   apply_decidability_change 里的 W# 特例）。\n'
    '    web_as_evidence: bool = False\n'
)
P_NEW = (
    P_OLD
    + '    # ---- [v1.23.0 W3] 三池分离：证据（web_results）/ 仲裁 / 核对。\n'
    '    #   为什么不共用一个 list：三者的**消费方**不同（判定 / 对撞 / 元层），\n'
    '    #   混在一起后「W# 有没有进对撞内容」这件事就没法按池判了。\n'
    '    web_arbitration: List[dict] = field(default_factory=list)\n'
    '    web_clean_check: List[dict] = field(default_factory=list)\n'
)
src = sub_once(src, P_OLD, P_NEW, "Pool 两池")

# ============================================================ 2 两个 query 构造
Q_OLD = 'def _web_digest_block(results) -> str:\n'
Q_NEW = '''def _duel_arbitration_queries(tensions) -> List[str]:
    """[W3·duel_arbitration] 把对撞层的张力改写成「哪边更合理」的仲裁问句。

    ★ 结果只作**仲裁材料** —— 不进 ing、不进对撞第三者（宪法级：未对齐合法）。
    """
    out: List[str] = []
    for t in (tensions or []):
        s = str(t).strip()
        if not s:
            continue
        out.append((s[:60] + " 哪个更合理？")[:160])
        if len(out) >= 2:
            break
    return out


def _meta_clean_queries(uncovered) -> List[str]:
    """[W3·meta_clean_check] 把元层的「未覆盖区间」改写成存在性问句。

    ★ 只用于 `uncovered` 核对；**不得**用于 deferred 的清算
      （宪法级：停止与清算分开 —— 见 `settle_deferrals` 的零调用断言）。
    """
    out: List[str] = []
    for u in (uncovered or []):
        s = str(u).strip()
        if not s:
            continue
        out.append(s[:100])
        if len(out) >= 2:
            break
    return out


def _web_digest_block(results) -> str:\n'''
src = sub_once(src, Q_OLD, Q_NEW, "两个 query 构造")

# ============================================================ 3 W3 两个接入方法 + W4 第三票
M_OLD = '    def _web_evidence_hook(self, prop: dict, layer: int) -> List[dict]:\n'
M_NEW = '''    def _web_duel_arbitration(self, view) -> List[dict]:
        """[W3] 对撞层 · 第三方仲裁材料。**结果不进对撞内容**。

        进 `pool.web_arbitration`，并在池级留痕（view.meta）说明「有材料、
        但它只作参照」—— 让「跑了但没用上」与「没跑」能分开读。
        """
        pool = self.pools.get("both")
        _tx: List[str] = []
        for a in (getattr(view, "adjudications", None) or [])[:2]:
            _t = str((a or {}).get("tension", "")).strip()
            if _t:
                _tx.append(_t)
        _qs = _duel_arbitration_queries(_tx)
        if not _qs:
            return []
        _res = self._web_search("duel_arbitration", _qs,
                                self._research_round_no(), used_as="arbitration")
        if _res and pool is not None:
            for _x in _res:
                pool.web_arbitration.append(dict(_x))
            view.meta.append(
                "[W-ARB] 外部仲裁材料 " + str(len(_res)) + " 条"
                "（**只作参照**：不进 ing、不进对撞第三者）")
        return _res

    def _web_meta_clean_check(self, view, uncovered) -> List[dict]:
        """[W3] 元层 · 缺失区间核对（**只对 uncovered**）。

        ★ 不碰 deferred 的清算 —— 那属于「停止与清算分开」这条红线。
        """
        pool = self.pools.get("all")
        _qs = _meta_clean_queries(uncovered)
        if not _qs:
            return []
        _res = self._web_search("meta_clean_check", _qs,
                                self._research_round_no(), used_as="clean_check")
        if pool is not None:
            for _x in _res:
                pool.web_clean_check.append(dict(_x))
        if _res and view is not None:
            view.meta.append(
                "[W-CHK] 缺失区间外部核对 " + str(len(_res)) + " 条命中"
                "（仅作核对，不改判定）")
        return _res

    def _web_evidence_hook(self, prop: dict, layer: int) -> List[dict]:\n'''
src = sub_once(src, M_OLD, M_NEW, "W3 接入方法")

# ============================================================ 4 接入 _finalize_layer_common
F_OLD = (
    '        # ---- 1. 把跨圈累积回填到 view ----\n'
)
F_NEW = (
    '        # ---- [v1.23.0 W3] 联网：对撞层仲裁 / 元层缺失核对 ----\n'
    '        #   ★ 位置在这里而不是两条通道各自的前置步骤：本方法是三层\n'
    '        #     **唯一**共用的收尾（v122 P3-1 已收口），加在这里天然\n'
    '        #     只有一份实现。\n'
    '        #   ★ 失败一律吞掉只留痕：联网是一次锦上添花，绝不能把层带走。\n'
    '        try:\n'
    '            if entry == "both":\n'
    '                self._web_duel_arbitration(view)\n'
    '            elif entry == "all":\n'
    '                self._web_meta_clean_check(\n'
    '                    view, list(getattr(view, "uncovered_aspects", None)\n'
    '                               or []))\n'
    '        except Exception as _ew3:  # noqa: BLE001\n'
    '            logger_web.warning("[W-W3] %s", _ew3)\n'
    '\n'
    '        # ---- 1. 把跨圈累积回填到 view ----\n'
)
src = sub_once(src, F_OLD, F_NEW, "接入 finalize")

# ============================================================ 5 W4 第三票改「外部证据裁判」
V_OLD = (
    '        votes: Dict[int, List[str]] = {}\n'
    '        ok_votes = 0\n'
    '        for sysp in _TRI_VOTE_PROMPTS:\n'
)
V_NEW = (
    '        votes: Dict[int, List[str]] = {}\n'
    '        ok_votes = 0\n'
    '        # [v1.23.0 W4] 三票正交化：第三票改「外部证据裁判」——\n'
    '        #   它**只看** W#（联网）与 X#（锚点），不看池内产物。\n'
    '        #   ★ 只有联网开启且本环节授权时才替换；否则三票逐字同 v1.22.2。\n'
    '        _sys_list = list(_TRI_VOTE_PROMPTS)\n'
    '        try:\n'
    '            _ext_ok, _ = (self._web_gate.allow("research_evidence",\n'
    '                                              self._research_round_no())\n'
    '                          if getattr(self, "_web_gate", None) else (False, ""))\n'
    '        except Exception:  # noqa: BLE001\n'
    '            _ext_ok = False\n'
    '        if _ext_ok:\n'
    '            _ev = self._web_search(\n'
    '                "research_evidence",\n'
    '                _research_evidence_queries({"to": "partial",\n'
    '                                            "_sq_text": question[:120]}),\n'
    '                self._research_round_no(), used_as="arbitration")\n'
    '            if _ev:\n'
    '                _sys_list[2] = _TRI_VOTE_PROMPTS[2] + _web_digest_block(_ev)\n'
    '                _sys_list[2] += ("\\n【裁判口径】你的这一票**只看**上面这些"\n'
    '                                 "外部材料与锚点；池内产物一律不计入。\\n")\n'
    '        for sysp in _sys_list:\n'
)
src = sub_once(src, V_OLD, V_NEW, "W4 第三票")

# ============================================================ 6 changelog
CL = """v1.23.0 W3+W4 ── 对撞层/元层接入（仲裁材料 / 缺失核对）+ 三票正交化

  【W3 · 三池分离】`Pool` 新增 `web_arbitration` / `web_clean_check`。
    为什么不共用一个 list：三者**消费方**不同（判定 / 对撞 / 元层），
    混在一起后「W# 到底有没有进对撞内容」就没法按池判。
    新增 `_duel_arbitration_queries(tensions)` / `_meta_clean_queries(uncovered)`。

  【W3 · 接入点收在 `_finalize_layer_common`】
    · `entry == "both"` → `_web_duel_arbitration(view)`：从本层
      `adjudications[*].tension` 出仲裁问句；结果进 `pool.web_arbitration`
      + 池级留痕 `[W-ARB]`。**不进 ing、不进对撞第三者**（未对齐合法）。
    · `entry == "all"` → `_web_meta_clean_check(view, uncovered_aspects)`：
      只对 `uncovered` 核对；结果进 `pool.web_clean_check` + `[W-CHK]`。
      **不碰 deferred 的清算**（停止与清算分开）。
    · 两条都 try/except 吞掉只留痕 —— 联网是锦上添花，绝不能把层带走。

  【W4 · 三票正交化】第三票改「外部证据裁判」：system 追加
    【外部检索摘要】+ 一句「**只看**外部材料与锚点，池内产物不计入」。
    仅当 `web_search.enabled` 且 `research_evidence` 授权**且**该次检索
    确有结果时替换；否则三票逐字与 v1.22.2 相同（加性）。

"""
src = sub_once(src, "\nv1.23.0 W1 ── 核心联网",
               "\n" + CL + "v1.23.0 W1 ── 核心联网", "changelog")

# ============================================================ 写回
out = src.replace("\n", "\r\n")
b = out.encode("utf-8")
assert b.count(b"\r\n") == b.count(b"\n")
assert b.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert b.count(b"\r") == b.count(b"\r\n"), "出现裸 CR"
TARGET.write_bytes(b)
print("OK: v1.23.0 W3+W4 补丁已写入")
