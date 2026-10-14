# -*- coding: utf-8 -*-
"""P1b：`ControlSurface` —— 所有**运行时调度调整**的唯一收口。

## 前沿依据
E³-Agent（arXiv 2605.27428, 2026）：fast-path 调度与 slow-path 元控制器之间
必须有**一个小的、显式的控制面**（tool interface）——「自由调度」与「自我学习」
才能既自由、又**可控 + 可追溯**。

## 三件事一次做到
  ① **可控**：**白名单 + 边界**；白名单外一律**拒**（拒也要留痕）；
  ② **可追溯**：每次写入必须给 `why` + `trace_ref`，**缺则拒**；
  ③ **不越红线**：只改**本次跑的内存态**，**绝不写配置**
     （红线「建议与执行分开」）。

## 与既有 `_eml_apply` 的关系
`_eml_apply` 已在改 `rounds_plan` / `self._duty_floor` —— 那是 EML 的生效面。
本类**不改它**（避免动既有行为），而是：
  · 提供**统一的写入 API**给**新增的**调度路径（心跳 / 元层调整）；
  · `_eml_apply` 的既有两键**登记为「已走控制面的等价物」**（在 `_SPEC` 里标注），
    将来可平滑迁入 —— 一次改一处、不做大爆炸式重构。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

# ── A：模块级类（放在 `_render_layer_glance` 之前 —— 同一批「渲染/调度辅助」）──
ANCHOR_CLS = '''def _render_layer_glance(view) -> str:'''
NEW_CLS = '''class ControlSurface:
    """[显式控制面] 运行时调度调整的**唯一收口**（白名单 + 边界 + 必留痕）。

    ★ 为什么要有它（依据 E³-Agent）：调度要「自由」，就必须有一处**显式**的
      写入面 —— 否则「谁在什么时候把什么改成了什么」散落在各处，既不可控
      也不可追溯。
    ★ 三条硬约束（都在 `write()` 里强制）：
      ① 白名单外**直接拒**（并记 `refused`）；
      ② 缺 `why` 或 `trace_ref` **直接拒**（可追溯性的本体）；
      ③ 值超边界**拒**（不夹取 —— 夹取会让调用方以为设成功了）。
    ★ 只改内存态：本类**没有任何**写配置文件的能力（红线：建议与执行分开）。
    """

    #: 白名单：key 前缀 → (边界描述, 校验函数, 来源标注)
    #: ★ 「来源标注」写清这条路径**当前由谁在调**（迁移进度可见）。
    _SPEC = {
        "rounds.": ("层圈数，1..hard_max", None, "EML `rounds_delta`（既经控制面等价物）"),
        "duty_floor": ("职责下限，0..1", None, "EML `duty_floor`（同上）"),
        "web.allow.": ("某 stage 是否允许联网，bool", None, "心跳调度（P1c）"),
        "web.quota.per_stage_round": ("每 stage 每圈上限，1..5", None, "心跳调度（P1c）"),
        "stop.anytime_alpha": ("anytime 停止 α，0..0.5", None, "心跳调度（P1c）"),
    }

    def __init__(self, owner):
        self._owner = owner
        self._values: dict = {}          # 被改过的键（只存**改过**的）
        self.applied: list = []          # 成功写入的留痕
        self.refused: list = []          # 被拒的留痕（★ 拒也要留痕）

    # ── 白名单/边界 ──
    def _lookup(self, key: str):
        k = str(key or "")
        for _pre, _spec in self._SPEC.items():
            if k.startswith(_pre):
                return _pre, _spec
        return None, None

    def read(self, key: str):
        """读当前值：**改过就返回改后的**，没改过返回 owner 上的实际值。"""
        k = str(key or "")
        if k in self._values:
            return self._values[k]
        return getattr(self._owner, "_ctl_get_" + k.replace(".", "_"), None)

    def snapshot(self) -> dict:
        """供产物对账：当前**被改过**的键 + 全部写入/拒绝留痕。"""
        return {"values": dict(self._values),
                "applied": list(self.applied),
                "refused": list(self.refused)}

    def write(self, key: str, val, why: str, trace_ref=None) -> bool:
        """写入一个调度参数。**白名单外 / 缺 reasons / 超边界 ⇒ 拒且留痕。**

        返回 True = 已生效；False = 被拒（原因进 `refused`）。
        """
        _pre, _spec = self._lookup(key)
        _rec = {"key": str(key), "val": val, "why": str(why or ""),
                "ref": trace_ref}
        if _spec is None:
            _rec["refused"] = "白名单外（运行时不许调这个参数）"
            self.refused.append(_rec)
            return False
        if not str(why or "").strip():
            _rec["refused"] = "缺 why（可追溯性要求：每次调整都要说明理由）"
            self.refused.append(_rec)
            return False
        if trace_ref is None or trace_ref == "":
            _rec["refused"] = "缺 trace_ref（调不回去查不到）"
            self.refused.append(_rec)
            return False
        # 边界校验（**不夹取**：夹取会让调用方以为设成功了）
        _old = self.read(key)
        _err = self._check_bounds(str(key), val)
        if _err:
            _rec["refused"] = _err
            self.refused.append(_rec)
            return False
        if _old == val:
            _rec["noop"] = "值未变（幂等，不记入 applied）"
            self.refused.append(_rec)
            return False
        self._values[str(key)] = val
        _rec["old"] = _old
        self.applied.append(_rec)
        return True

    def _check_bounds(self, key: str, val):
        """边界：只做**拒绝**，不做夹取。返回 None = 通过。"""
        try:
            if key.startswith("rounds."):
                _hi = int(((self._owner.config or {}).get("spiral") or {})
                          .get("hard_max", 12) or 12)
                _v = int(val)
                if not (1 <= _v <= _hi):
                    return "圈数越界（应 1..%d）" % _hi
            elif key == "duty_floor":
                _v = float(val)
                if not (0.0 <= _v <= 1.0):
                    return "duty_floor 越界（应 0..1）"
            elif key.startswith("web.allow."):
                if not isinstance(val, bool):
                    return "web.allow.* 应为 bool"
            elif key == "web.quota.per_stage_round":
                _v = int(val)
                if not (1 <= _v <= 5):
                    return "per_stage_round 越界（应 1..5）"
            elif key == "stop.anytime_alpha":
                _v = float(val)
                if not (0.0 <= _v <= 0.5):
                    return "anytime_alpha 越界（应 0..0.5）"
        except (TypeError, ValueError):
            return "值类型不对：%r" % (val,)
        return None


def _render_layer_glance(view) -> str:'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    n = s.count(ANCHOR_CLS)
    assert n == 1, "锚点命中 %d 次（应为 1）" % n
    s = s.replace(ANCHOR_CLS, NEW_CLS, 1)
    assert s.count("class ControlSurface") == 1
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK P1b ControlSurface 已加；行数 %d" % out.count(b"\n"))


main()
