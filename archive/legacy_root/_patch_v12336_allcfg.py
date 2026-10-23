# -*- coding: utf-8 -*-
"""「所有可配置行为纳入自我学习 + 与调度层融合」—— 核心框架。

## 用户口径
「将更多行为和功能数据（如思考，停止，等**所有可配置行为和参数**）量化为
自我学习迭代范围并与调度层进行融合。」

## 为什么能做（本轮调研的事实）
· `DGTF(entry, self.llm, self.config)` ⇒ `DGTF` 与 `MetaDGTF` **共用同一个
  config dict** ⇒ 往它里面挂一个 `_control`（控制面引用），`DGTF` 侧就能读到；
· 动作开关的**唯一读入口**是 `_action_on(config, name, default)`
  ⇒ 在这一处加「**运行时覆盖优先**」⇒ **所有 `actions.*`** 立刻变成可运行时调；
· 思考档的唯一读入口是 `LLM.call` 里的 `self.thinking_stages.get(stage)`
  ⇒ 改 `llm.thinking_stages[stage]` 立即生效。

## 四件事
① `_action_on` 加运行时覆盖（**运行时 > actions 段 > output 别名 > 默认**）；
② `MetaDGTF.run` 把 `self._control` 挂进 `config["_control"]`（**只加下划线键**：
   不进产物、不落盘、不给判据当配置读）；
③ 控制面**白名单**扩到 `actions.` / `thinking.` / `stop.` / `duty.`（+ 边界）；
④ EML 新增两个 `action.key`（**都接真实消费方**）：
   · `action_hint`  → `actions.<名>`（消费方 = `_action_on`，经 ①）
   · `thinking_hint`→ `thinking.<stage>`（消费方 = `LLM.call` 的思考档查表，
     由 `_eml_apply` **同步写进** `llm.thinking_stages`）

★ **零行为差**：`_control` 不在 ⇒ `_action_on` 走原路径，逐字不变；
  控制面里没有该 key ⇒ `read` 返回 None ⇒ 不覆盖。
★ **绝不写配置**：覆盖只在**内存 dict** 的 `_control` 里；`config["actions"]`
  本身一字不动（红线：建议与执行分开）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.36.py"

# ── ① `_action_on` 运行时覆盖 ──
OLD_AO = '''def _action_on(config: dict, name: str, default: bool = True) -> bool:
    """统一读动作开关。actions 段 > output 段（经别名映射）> 默认值。"""
    a = (config.get("actions") or {})'''
NEW_AO = '''def _action_on(config: dict, name: str, default: bool = True) -> bool:
    """统一读动作开关。★ 运行时覆盖 > actions 段 > output 段（别名）> 默认值。

    ★ [与调度融合] `config["_control"]` 是**本跑的内存态控制面**（由 `MetaDGTF`
      挂上）—— 心跳调度与 EML 在**运行中**改的开关都经它生效。
      ⇒ 于是**所有走 `_action_on` 的可配置行为**都成了「**可运行时调**」的，
      也就**可以被 EML 学**（学到的直接改下一次决策，而不是躺在记忆库里）。
    ★ 零行为差：没有 `_control`（或它没覆盖这个键）⇒ 走原路径，逐字不变。
    """
    _s = (config or {}).get("_control")
    if _s is not None:
        try:
            _ov = _s.read("actions.%s" % name)
            if _ov is not None:
                return bool(_ov)
        except Exception:
            pass
    a = (config.get("actions") or {})'''

# ── ② `MetaDGTF.run` 挂 `_control` ──
OLD_INJ = '''            _llm_ctx_set(web_searcher=self._web_search,
                         question=str(question or ""),
                         control=self._control)'''
NEW_INJ = '''            _llm_ctx_set(web_searcher=self._web_search,
                         question=str(question or ""),
                         control=self._control)
            # ★ [与调度融合] 把控制面挂进 config（**同一个 dict**，`DGTF` 也读它）
            #   ⇒ `_action_on` 的运行时覆盖生效 ⇒ **所有 actions.* 可运行时调**。
            #   ★ 只加一个**下划线键**：不参与产物导出、不落盘、不算"配置项"。
            if isinstance(self.config, dict):
                self.config["_control"] = self._control'''

# ── ③ 控制面白名单扩展 ──
OLD_SPEC = '''    _SPEC = {
        "rounds.": ("层圈数，1..hard_max", None, "EML `rounds_delta`（既经控制面等价物）"),
        "duty_floor": ("职责下限，0..1", None, "EML `duty_floor`（同上）"),
        "web.allow.": ("某 stage 是否允许联网，bool", None, "心跳调度（P1c）"),
        "web.quota.per_stage_round": ("每 stage 每圈上限，1..5", None, "心跳调度（P1c）"),
        "stop.anytime_alpha": ("anytime 停止 α，0..0.5", None, "心跳调度（P1c）"),
    }'''
NEW_SPEC = '''    _SPEC = {
        "rounds.": ("层圈数，1..hard_max", None, "EML `rounds_delta`/`carve_first`/`note_cost_no_gain`"),
        "duty_floor": ("职责下限，0..1", None, "EML `duty_floor`/`tri_advisory_only`"),
        "web.allow.": ("某 stage 是否允许联网，bool", None, "心跳调度（P1c）"),
        "web.quota.per_stage_round": ("每 stage 每圈上限，1..5", None, "心跳调度（P1c）"),
        "stop.anytime_alpha": ("anytime 停止 α，0..0.5", None, "心跳调度（P1c）"),
        # ★ [与调度融合 · 扩面] 下面这四类让「**所有可配置行为**」可运行时调：
        #   · `actions.*`  —— 所有动作开关（消费方 = `_action_on`，已加运行时覆盖）；
        #   · `thinking.*` —— 逐环节思考档（消费方 = `LLM.call` 的思考档查表）；
        #   · `stop.*`     —— 停止家族（消费方 = 停止判据侧，逐圈读）；
        #   · `duty.*`     —— 职责家族（消费方 = 职责读数侧）。
        "actions.": ("动作开关，bool", None, "EML `action_hint`（本轮新增）"),
        "thinking.": ("逐环节思考档，enabled/disabled",
                      None, "EML `thinking_hint`（本轮新增）"),
        "stop.": ("停止家族参数", None, "停止判据（逐圈读）"),
        "duty.": ("职责家族参数", None, "职责读数"),
    }'''

# ── ④ 控制面边界校验（新键）──
OLD_BOUND = '''            elif key == "stop.anytime_alpha":
                _v = float(val)
                if not (0.0 <= _v <= 0.5):
                    return "anytime_alpha 越界（应 0..0.5）"'''
NEW_BOUND = '''            elif key == "stop.anytime_alpha":
                _v = float(val)
                if not (0.0 <= _v <= 0.5):
                    return "anytime_alpha 越界（应 0..0.5）"
            elif key.startswith("actions."):
                if not isinstance(val, bool):
                    return "actions.* 应为 bool"
            elif key.startswith("thinking."):
                if str(val) not in ("enabled", "disabled"):
                    return "thinking.* 只能是 enabled / disabled"
            elif key.startswith("duty."):
                if not isinstance(val, (int, float)) or not (0.0 <= float(val) <= 1.0):
                    return "duty.* 应为 0..1 的数"
            elif key.startswith("stop."):
                if not isinstance(val, (int, float)) or not (0.0 <= float(val) <= 1.0):
                    return "stop.* 应为 0..1 的数"'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new, tag in ((OLD_AO, NEW_AO, "① _action_on 覆盖"),
                          (OLD_INJ, NEW_INJ, "② 挂 _control"),
                          (OLD_SPEC, NEW_SPEC, "③ 白名单扩面"),
                          (OLD_BOUND, NEW_BOUND, "④ 边界校验")):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（应为 1）" % (tag, n)
        s = s.replace(old, new, 1)
    assert 'self.config["_control"] = self._control' in s
    assert 'actions.%s" % name' in s
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 核心框架已加（_action_on 覆盖 + 挂 _control + 白名单扩面）；行数 %d"
          % out.count(b"\n"))


main()
