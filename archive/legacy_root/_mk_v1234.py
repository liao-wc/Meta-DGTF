#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.3 -> v1.23.4：给联网 / 思考 / 思考强度加**运行期三项总控**。

设计要点（写在这里，免得只留在报告里）：

1. 三项总控放在**顶层 `runtime` 段**，与既有的 `cost_profile`（顶层总控）
   同构。默认三项全 `"auto"` = **不覆盖任何既有键** ⇒ 本版与 v1.23.3 的
   行为逐字相同（有判据钉住）。
2. 生效靠一个**纯函数** `_apply_runtime(base, rt)`：深拷一份再改，**不改
   入参**。交互循环里如果就地改 cfg，第二轮选 auto 就会读到第一轮改过的
   值 —— 「auto」会变成「跟上一次一样」，那是另一个语义。
3. `load_config` 外面**套一层**而不是在函数体中间插：它有四个 return 出口
   （空路径 / 解析失败 / 顶层非 mapping / 正常），插在中间必须改四处，
   漏一处就「某些路径不生效」而且没有判据看得见。
4. 「思考总开关」必须连 `api.thinking.stages` **整表**一起改写 ——
   `LLM.call` 的优先级是「显式 thinking > stage > default」，只改 default
   会被 stage 表盖住 ⇒ 总开关变成一句空话。
5. 交互 `_ask_runtime` + CLI `--web/--thinking/--effort`，两条入口都走
   同一个 `_apply_runtime`，避免两份实现。

★ 一律 write_bytes + CRLF 往返；替换前断言锚点命中 1 次。
"""
import ast
import difflib
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.3.py"
DST = HERE / "元DGTF-V1.23.4.py"

raw = SRC.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n"), "源文件不是纯 CRLF"
src = raw.decode("utf-8").replace("\r\n", "\n")
print("源：%s（%d 行）" % (SRC.name, src.count("\n") + 1))


def rep(old, new, tag):
    """唯一性断言的替换。"""
    n = src.count(old)
    assert n == 1, "%s 锚点命中 %d 次（应 1）" % (tag, n)
    return src.replace(old, new, 1)


NL = chr(10)

# ============================================================ S1 常量 + 纯函数
S1 = NL.join([
    "# ============================================================",
    "# 运行期总控（runtime）· v1.23.4",
    "# ============================================================",
    "# 三项**面向人的**可选项：联网 / 思考 / 思考强度。",
    "#   ★ 与 `cost_profile`（成本档）的区别：成本档是**内部优化强度**，",
    "#     由开发者按预算调；这三项是**用户的当场决定** —— 「这一问要不要",
    "#     联网、要不要思考、思考多用力」，在交互里就能选，不必改 yaml。",
    "#   ★ 出厂默认三项全 `auto` = **不覆盖任何既有配置** ⇒ 与 v1.23.3",
    "#     行为逐字相同（判据见冒烟 `check_v1234_runtime`）。",
    "#   ★ `auto` 的语义是「**按配置文件**」，不是「跟上次一样」：每次",
    "#     应用都从**未被改写的**配置上算（见 `_apply_runtime` 的深拷）。",
    "_RUNTIME_SWITCHES = (\"auto\", \"on\", \"off\")",
    "_RUNTIME_EFFORTS = (\"auto\", \"low\", \"medium\", \"high\")",
    "",
    "# 开关的字面别名 -> 归一值。交互里允许用户敲 y/n/1/0/开/关 这类。",
    "#   ★ 只归一**明确**的别名；认不出一律返回 None（由调用方报错），",
    "#     绝不静默回落到 auto —— 「敲错了但没反应」是最难查的一类。",
    "_RUNTIME_SWITCH_ALIASES = {",
    "    \"\": \"auto\", \"a\": \"auto\", \"auto\": \"auto\",",
    "    \"默认\": \"auto\", \"缺省\": \"auto\", \"按配置\": \"auto\",",
    "    \"on\": \"on\", \"y\": \"on\", \"yes\": \"on\", \"1\": \"on\",",
    "    \"true\": \"on\", \"开\": \"on\", \"启用\": \"on\", \"打开\": \"on\",",
    "    \"off\": \"off\", \"n\": \"off\", \"no\": \"off\", \"0\": \"off\",",
    "    \"false\": \"off\", \"关\": \"off\", \"禁用\": \"off\", \"关闭\": \"off\",",
    "}",
    "",
    "",
    "def _normalize_runtime_switch(raw) -> Optional[str]:",
    "    \"\"\"归一开关：auto/on/off；认不出返回 None（**不静默回落**）。\"\"\"",
    "    return _RUNTIME_SWITCH_ALIASES.get(str(raw or \"\").strip().lower())",
    "",
    "",
    "def _normalize_runtime_effort(raw) -> Optional[str]:",
    "    \"\"\"归一强度：auto/low/medium/high；认不出返回 None。\"\"\"",
    "    v = str(raw or \"\").strip().lower()",
    "    return v if v in _RUNTIME_EFFORTS else None",
    "",
    "",
    "def _runtime_thinking_on(cfg: dict) -> bool:",
    "    \"\"\"本跑「思考」到底是不是开的（看 `default`；stages 由总控同步）。\"\"\"",
    "    _th = ((cfg or {}).get(\"api\") or {}).get(\"thinking\") or {}",
    "    return str(_th.get(\"default\") or \"\").strip().lower() == \"enabled\"",
    "",
    "",
    "def _apply_runtime(base_cfg: dict, runtime=None):",
    "    \"\"\"[v1.23.4] 把运行期总控**写进**具体配置键。返回 `(新 cfg, 留痕行)`。",
    "",
    "    ★ **纯函数**：深拷一份再改，**绝不改入参**。交互循环若就地改 cfg，",
    "      用户第二轮选 \"auto\" 就会读到第一轮被改过的值 —— 「auto」会",
    "      变成「跟上一次一样」，那是**另一个语义**。",
    "    ★ 用 `json` 往返做深拷（与 `load_config` 同一手法，不引入 `copy`）。",
    "      若 cfg 里有不可 JSON 化的对象，这里**应当**炸 —— 换成浅拷会把",
    "      「不改入参」这条保证静默破坏掉（嵌套 dict 仍是同一个对象）。",
    "    \"\"\"",
    "    cfg = json.loads(json.dumps(base_cfg or {}))",
    "    rt = dict(runtime if runtime is not None else (cfg.get(\"runtime\") or {}))",
    "    notes: List[str] = []",
    "",
    "    # ---- ① 联网总开关：`web_search.enabled` ----",
    "    web = _normalize_runtime_switch(rt.get(\"web\", \"auto\"))",
    "    if web is None:",
    "        notes.append(\"⚠️ runtime.web 取值非法（%r），已忽略（可选 auto/on/off）\"",
    "                     % (rt.get(\"web\"),))",
    "    elif web != \"auto\":",
    "        cfg.setdefault(\"web_search\", {})[\"enabled\"] = (web == \"on\")",
    "        notes.append(\"联网：强制**%s**（runtime.web=%s）\"",
    "                     % (\"开\" if web == \"on\" else \"关\", web))",
    "",
    "    # ---- ② 思考总开关：`default` + **整张 stages 表** ----",
    "    #   ★ 只改 default 是不够的：`LLM.call` 的优先级是",
    "    #     「显式 thinking > stage 配置 > default」，stage 表会**盖住**",
    "    #     default ⇒ 「总开关」变成一句空话（`check_v1234_runtime` 与",
    "    #     探针的变异体 M2 专门钉这一条）。",
    "    th = _normalize_runtime_switch(rt.get(\"thinking\", \"auto\"))",
    "    if th is None:",
    "        notes.append(\"⚠️ runtime.thinking 取值非法（%r），已忽略\"",
    "                     % (rt.get(\"thinking\"),))",
    "    elif th != \"auto\":",
    "        _thc = cfg.setdefault(\"api\", {}).setdefault(\"thinking\", {})",
    "        _val = \"enabled\" if th == \"on\" else \"disabled\"",
    "        _thc[\"default\"] = _val",
    "        _stages = _thc.get(\"stages\") or {}",
    "        for _k in list(_stages):",
    "            _stages[_k] = _val",
    "        _thc[\"stages\"] = _stages",
    "        notes.append(\"思考：强制**%s**（runtime.thinking=%s；%d 个环节档位\"",
    "                     \"一并改写）\"",
    "                     % (\"开\" if th == \"on\" else \"关\", th, len(_stages)))",
    "        if th == \"on\":",
    "            notes.append(\"   ★ 思考开 ⇒ 每次调用 `max_tokens ≥ 32000`，\"",
    "                         \"成本显著上升（这是**成本决策**）。\")",
    "",
    "    # ---- ③ 思考强度：`api.thinking.effort` ----",
    "    ef = _normalize_runtime_effort(rt.get(\"effort\", \"auto\"))",
    "    if ef is None:",
    "        notes.append(\"⚠️ runtime.effort 取值非法（%r），已忽略（可选 %s）\"",
    "                     % (rt.get(\"effort\"), \"/\".join(_RUNTIME_EFFORTS)))",
    "    elif ef != \"auto\":",
    "        cfg.setdefault(\"api\", {}).setdefault(\"thinking\", {})[\"effort\"] = ef",
    "        notes.append(\"思考强度：%s（runtime.effort=%s）\" % (ef, ef))",
    "",
    "    # ---- ④ 防「配了却不生效」：强度只在思考开启时才随请求发出 ----",
    "    #   `LLM.call` 里 effort 只在 `is_thinking` 为真时进 extra_body。",
    "    #   用户设了 high 而思考是关的 ⇒ 这一项**完全没有效果**。必须说出来，",
    "    #   否则就是「配置写了但没生效」那一类 bug（v1.23.2 整体审计的主题）。",
    "    if ef not in (None, \"auto\") and not _runtime_thinking_on(cfg):",
    "        notes.append(\"⚠️ 强度已设为 %s，但本跑**思考是关的** ⇒ 强度不生效\"",
    "                     \"（`effort` 只在 thinking 开启时随请求发出）\" % ef)",
    "    return cfg, notes",
    "",
    "",
    "def _runtime_snapshot(cfg: dict) -> dict:",
    "    \"\"\"本跑**实际生效**的三项读数（写进产物，供复盘）。\"\"\"",
    "    _ws = (cfg or {}).get(\"web_search\") or {}",
    "    _th = ((cfg or {}).get(\"api\") or {}).get(\"thinking\") or {}",
    "    _st = dict(_th.get(\"stages\") or {})",
    "    _on = sorted(k for k, v in _st.items()",
    "                 if str(v).strip().lower() == \"enabled\")",
    "    return {",
    "        \"requested\": dict((cfg or {}).get(\"runtime\") or {}),",
    "        \"web_enabled\": bool(_ws.get(\"enabled\")),",
    "        \"thinking_default\": str(_th.get(\"default\") or \"\"),",
    "        \"thinking_stages_enabled\": _on,",
    "        \"thinking_stages_off_n\": len(_st) - len(_on),",
    "        \"effort\": str(_th.get(\"effort\") or \"\"),",
    "    }",
    "",
    "",
    "def _runtime_summary_line(cfg: dict) -> str:",
    "    \"\"\"一行人类可读的生效摘要（交互与 CLI **共用**，避免两处各写一份）。\"\"\"",
    "    s = _runtime_snapshot(cfg)",
    "    return (\"联网 %s | 思考 %s（%d 个环节开档 / %d 关）| 强度 %s\"",
    "            % (\"开\" if s[\"web_enabled\"] else \"关\",",
    "               \"开\" if _runtime_thinking_on(cfg) else \"关\",",
    "               len(s[\"thinking_stages_enabled\"]), s[\"thinking_stages_off_n\"],",
    "               s[\"effort\"] or \"—\"))",
    "",
    "",
])

src = rep("# ============================================================" + NL
          + "# 成本档位（cost_profile）" + NL
          + "# ============================================================",
          S1 + "# ============================================================" + NL
          + "# 成本档位（cost_profile）" + NL
          + "# ============================================================",
          "S1")
print("  · S1 常量与纯函数已插入")

# ============================================================ S2 DEFAULT_CONFIG
S2 = NL.join([
    "    # ============================================================",
    "    # 运行期总控（[v1.23.4] 顶层，三项；与上面的 cost_profile 同构）",
    "    #   web      —— 联网总开关：auto / on / off",
    "    #   thinking —— 思考总开关：auto / on / off",
    "    #   effort   —— 思考强度：auto / low / medium / high",
    "    # ★ 默认三项全 auto = **不覆盖任何既有键** ⇒ 与 v1.23.3 行为逐字",
    "    #   相同。`auto` 的语义是「按本文件的既有键」（不是「跟上次一样」）。",
    "    # ★ on/off 会**改写** `web_search.enabled` 与 `api.thinking.default`",
    "    #   **加整张 `api.thinking.stages` 表**；effort 会改写",
    "    #   `api.thinking.effort`。",
    "    # ★ 命令行 `--web/--thinking/--effort` 与本段同名；命令行覆盖本段",
    "    #   （与 `--profile` 覆盖 `cost_profile` 同一条纪律）。交互模式里",
    "    #   每轮单独询问，**不改本文件、也不跨轮记忆**。",
    "    \"runtime\": {",
    "        \"web\": \"auto\",",
    "        \"thinking\": \"auto\",",
    "        \"effort\": \"auto\",",
    "    },",
    "",
])
src = rep("    \"cost_profile\": \"balanced\"," + NL + NL + "    \"api\": {",
          "    \"cost_profile\": \"balanced\"," + NL + NL + S2 + "    \"api\": {",
          "S2")
print("  · S2 DEFAULT_CONFIG.runtime 已加")

# ============================================================ S3 load_config
src = rep("def load_config(path: str) -> dict:" + NL
          + "    cfg = json.loads(json.dumps(DEFAULT_CONFIG))",
          "def _load_config_raw(path: str) -> dict:",
          "S3a")
O3b = ("    cfg = _deep_merge(cfg, user_cfg)" + NL
       + "    return cfg")
N3b = (O3b + NL + NL + NL
       + "def load_config(path: str) -> dict:" + NL
       + "    \"\"\"[v1.23.4] 在 `_load_config_raw` 之上套一层**运行期总控**。" + NL
       + "" + NL
       + "    ★ 套在**最外层**而不是插进函数体中间：`_load_config_raw` 有" + NL
       + "      **四个** return 出口（空路径 / yaml 解析失败 / 顶层非 mapping /" + NL
       + "      正常）。插在中间就得改四处，漏一处就会「某些路径不生效」，" + NL
       + "      而且**没有任何判据看得见**（那正是最难查的一类）。" + NL
       + "    ★ 出厂 `runtime` 三项全 auto ⇒ 这一步对绝大多数调用是**恒等" + NL
       + "      变换**（`check_v1234_runtime` 用「逐字相同」钉住）。" + NL
       + "    \"\"\"" + NL
       + "    cfg, notes = _apply_runtime(_load_config_raw(path))" + NL
       + "    for n in notes:" + NL
       + "        print(\"   · \" + n)" + NL
       + "    return cfg")
src = rep(O3b, N3b, "S3b")
print("  · S3 load_config 已套外层")

# ============================================================ S4 产物留痕
src = rep("            \"_config\": {\"actions\": dict(self.config.get(\"actions\") or {})},",
          "            \"_config\": {\"actions\": dict(self.config.get(\"actions\") or {})}," + NL
          + "            # [v1.23.4] 运行期总控的**实际生效**读数：三项到底把配置" + NL
          + "            #   改成了什么，必须在产物里能读出来 —— 否则「这跑到底" + NL
          + "            #   联网没有 / 思考开没开」又成黑箱（与 served_by 同理）。" + NL
          + "            \"_runtime\": _runtime_snapshot(self.config),",
          "S4")
print("  · S4 _pack_result._runtime 已加")

# ============================================================ S5 交互询问
S5 = NL.join([
    "def _ask_runtime(cfg):",
    "    \"\"\"[v1.23.4] 三项运行期总控：联网 / 思考 / 强度。返回 dict（**不改 cfg**）。\"\"\"",
    "    print(\"\\n运行期总控（3 项；直接回车 = auto = 按配置文件）\")",
    "    print(\"   当前生效：\" + _runtime_summary_line(cfg))",
    "    out = {}",
    "    for key, label, tip in (",
    "            (\"web\", \" 联网总开关\",",
    "             \"on=强制联网（仍受 web_search.stages / 配额约束）/ off=强制不联网\"),",
    "            (\"thinking\", \" 思考总开关\",",
    "             \"on=全环节开思考（成本↑，max_tokens≥32000）/ off=全关\"),",
    "            (\"effort\", \" 思考强度  \",",
    "             \"low / medium / high（**只在思考开启时生效**）\")):",
    "        _opts = (_RUNTIME_EFFORTS if key == \"effort\" else _RUNTIME_SWITCHES)",
    "        while True:",
    "            try:",
    "                r = input(\"   %s [%s，回车=auto]> \" % (label, \"/\".join(_opts)))",
    "            except (EOFError, KeyboardInterrupt):",
    "                print()",
    "                return None",
    "            _v = (_normalize_runtime_effort(r) if key == \"effort\"",
    "                  else _normalize_runtime_switch(r))",
    "            if _v is not None:",
    "                out[key] = _v",
    "                break",
    "            print(\"      ✗ 可选：%s\" % \" / \".join(_opts))",
    "            print(\"        %s\" % tip)",
    "    return out",
    "",
    "",
])
src = rep("def _ask_config(cfg=None):", S5 + "def _ask_config(cfg=None):", "S5a")
src = rep("    return route_str, rounds_str, channels_str, parallel_str",
          NL.join([
              "    runtime = _ask_runtime(cfg if cfg is not None else DEFAULT_CONFIG)",
              "    if runtime is None:",
              "        return None",
              "    return route_str, rounds_str, channels_str, parallel_str, runtime",
          ]),
          "S5b")
src = rep("    \"\"\"v1.21.50：返回值加 parallel_str（4 元组）。\"\"\"",
          "    \"\"\"v1.21.50：返回值加 parallel_str（4 元组）。" + NL
          + "    v1.23.4：再加 runtime（**5 元组**）—— 联网 / 思考 / 强度总控。\"\"\"",
          "S5c")
print("  · S5 _ask_runtime 已加并接入 _ask_config")

# ============================================================ S6 交互循环
src = rep("        route_str, rounds_str, channels_str, parallel_str = cfg_result",
          NL.join([
              "        (route_str, rounds_str, channels_str, parallel_str,",
              "         runtime) = cfg_result",
              "        # [v1.23.4] 总控在**深拷出来的副本**上生效：共享的 `cfg` 不被",
              "        #   改写 ⇒ 下一轮选 auto 一定回到 yaml 的值（不是「跟上一次",
              "        #   一样」）。这一条由探针 `T4`（连问两轮）钉住。",
              "        run_cfg, _rt_notes = _apply_runtime(cfg, runtime)",
          ]),
          "S6a")
src = rep(NL.join([
    "        print(f\"回来通道：{ch_disp}\")",
    "        print(f\"{'═'*60}\")",
    "",
    "        meta = MetaDGTF(cfg)",
]),
          NL.join([
              "        print(f\"回来通道：{ch_disp}\")",
              "        print(f\"运行期总控：{_runtime_summary_line(run_cfg)}\")",
              "        for _n in _rt_notes:",
              "            print(f\"  · {_n}\")",
              "        print(f\"{'═'*60}\")",
              "",
              "        meta = MetaDGTF(run_cfg)",
          ]),
          "S6b")
src = rep("            save_result(result, cfg[\"output\"][\"save_dir\"])" + NL
          + "        except Exception as e:" + NL
          + "            print(f\"⚠️ 保存失败：{e}\")",
          "            save_result(result, run_cfg[\"output\"][\"save_dir\"])" + NL
          + "        except Exception as e:" + NL
          + "            print(f\"⚠️ 保存失败：{e}\")",
          "S6c")
print("  · S6 交互循环已接线")

# ============================================================ S7 CLI
src = rep(NL.join([
    "    parser.add_argument(\"--actions-on\", default=\"\",",
    "                        help=\"开启的动作，逗号分隔。\")",
    "    args = parser.parse_args()",
]),
          NL.join([
              "    parser.add_argument(\"--actions-on\", default=\"\",",
              "                        help=\"开启的动作，逗号分隔。\")",
              "    # [v1.23.4] 运行期三项总控（与配置顶层 `runtime` 段同名）。",
              "    #   ★ 默认全 auto = 不改任何东西；命令行覆盖配置文件。",
              "    parser.add_argument(\"--web\", default=\"auto\",",
              "                        choices=list(_RUNTIME_SWITCHES),",
              "                        help=\"联网总开关：auto（按配置）/ on / off\")",
              "    parser.add_argument(\"--thinking\", default=\"auto\",",
              "                        choices=list(_RUNTIME_SWITCHES),",
              "                        help=\"思考总开关：auto（按配置）/ on / off\")",
              "    parser.add_argument(\"--effort\", default=\"auto\",",
              "                        choices=list(_RUNTIME_EFFORTS),",
              "                        help=\"思考强度：auto / low / medium / high\"",
              "                             \"（只在思考开启时生效）\")",
              "    args = parser.parse_args()",
          ]),
          "S7a")
src = rep(NL.join([
    "    for _name in (args.actions_on or \"\").split(\",\"):",
    "        _name = _name.strip()",
    "        if _name:",
    "            cfg.setdefault(\"actions\", {})[_name] = True",
    "            print(f\"   ✓ 已开启动作：{_name}\")",
]),
          NL.join([
              "    for _name in (args.actions_on or \"\").split(\",\"):",
              "        _name = _name.strip()",
              "        if _name:",
              "            cfg.setdefault(\"actions\", {})[_name] = True",
              "            print(f\"   ✓ 已开启动作：{_name}\")",
              "",
              "    # [v1.23.4] 运行期总控落到具体键。位置在 `load_config` **之后**",
              "    #   （yaml 里的 `runtime:` 段由 load_config 内部那层负责），",
              "    #   命令行覆盖 yaml —— 与 `--profile` 覆盖 cost_profile 同纪律。",
              "    cfg, _rt_notes = _apply_runtime(cfg, {",
              "        \"web\": args.web, \"thinking\": args.thinking,",
              "        \"effort\": args.effort})",
              "    for _n in _rt_notes:",
              "        print(f\"   · {_n}\")",
          ]),
          "S7b")
src = rep(NL.join([
    "    print(f\"回来通道：{'、'.join(ch) if ch else '全关（历史不参与本次）'}\")",
    "    print(f\"{'═'*60}\")",
]),
          NL.join([
              "    print(f\"回来通道：{'、'.join(ch) if ch else '全关（历史不参与本次）'}\")",
              "    print(f\"运行期总控：{_runtime_summary_line(cfg)}\")",
              "    print(f\"{'═'*60}\")",
          ]),
          "S7c")
print("  · S7 CLI --web/--thinking/--effort 已加")

# ============================================================ S8 版本 + changelog
CHANGELOG = NL.join([
    "v1.23.4 相对 v1.23.3",
    "",
    "【主题】给「联网 / 思考 / 思考强度」加**运行期三项总控**，并让它们在**交互与",
    "  命令行**里可选 —— 之前这三项只能靠改 `dgtf_config.yaml` 再重跑，",
    "  交互里问不到、命令行也传不了。",
    "",
    "  【形态】顶层新增一段（与既有的 `cost_profile` 顶层总控同构）：",
    "      runtime:",
    "        web: auto        # auto | on | off      联网总开关",
    "        thinking: auto   # auto | on | off      思考总开关",
    "        effort: auto     # auto | low | medium | high   思考强度",
    "    ★ 默认三项全 `auto` = **不覆盖任何既有键** ⇒ 本版与 v1.23.3 的行为",
    "      **逐字相同**（判据：冒烟 `check_v1234_runtime` 对「配置逐字相同」",
    "      做断言）。",
    "    ★ `auto` 的语义是「**按配置文件**」，不是「跟上次一样」。",
    "",
    "  【为什么「思考总开关」要连 stages 整表一起改】",
    "    `LLM.call` 的档位优先级是「显式 thinking > 环节 stage 配置 > default」",
    "    （fix-112）。只改 `default` 会被 `stages` 表**盖住** ⇒ 用户以为关了、",
    "    实际大半环节还在开 —— 「总开关」成了一句空话。所以 on/off 一律把",
    "    `default` 与 `stages` 的**每个键**写成同一个值（探针变异体 M2 专钉",
    "    这一条：只改 default 必须判红）。",
    "    ★ 同理，`effort` 只在思考**开启**时才会进 `extra_body`；用户设了",
    "      强度而思考是关的，这一项**完全无效果** —— 这种「配了却不生效」",
    "      必须当场说出来（`_apply_runtime` 的最后一条留痕）。",
    "",
    "  【实现】一个纯函数 + 两条入口：",
    "    · `_apply_runtime(base_cfg, runtime=None) -> (cfg, notes)`：**深拷**",
    "      一份再改，**绝不改入参**。交互里若就地改 cfg，第二轮选 auto 就会",
    "      读到第一轮改过的值 —— 「auto」会退化成「跟上一次一样」。",
    "    · `_runtime_snapshot()` / `_runtime_summary_line()`：生效读数与一行",
    "      摘要，写进产物 `_runtime` 键、并在两处横幅里打印（**共用同一个",
    "      函数**，避免交互与 CLI 各写一份而慢慢走样）。",
    "    · `load_config` 外面**套一层**（`_load_config_raw` 仍是原体）。",
    "      为什么不在函数体中间插：它有**四个** return 出口（空路径 / yaml",
    "      解析失败 / 顶层非 mapping / 正常），插中间要改四处、漏一处就",
    "      「某些路径不生效」且**没有判据看得见**。",
    "    · 交互：`_ask_runtime()` 三项逐个问（回车=auto），`_ask_config`",
    "      的返回值由 4 元组变 **5 元组**；总控在**深拷副本** `run_cfg` 上",
    "      生效，共享 cfg 不动 ⇒ 每轮独立、不跨轮记忆。",
    "    · 命令行：`--web / --thinking / --effort`（choices 收紧在 3~4 个",
    "      合法值上，敲错 argparse 直接拦）；位置在 `load_config` 之后 ⇒",
    "      命令行覆盖 yaml。",
    "",
    "  【验收】冒烟 `check_v1234_runtime`（auto 恒等 + 三项各自落键 + 思考关",
    "    必须连 stages 全关 + 非法值不静默 + 强度在思考关时给出提示）；",
    "    探针 `_probe_v1234_runtime.py`（与 `LLM(cfg)` 联动验真实解析，",
    "    含 **3 个变异体**必须判红）；验收档 `--phase v1234`。",
    "",
])

src = rep("元 DGTF · v1.23.3" + NL, "元 DGTF · v1.23.4" + NL, "S8a")
src = rep("v1.23.3 相对 v1.23.2", CHANGELOG + "v1.23.3 相对 v1.23.2", "S8b")
src = rep('__version__ = "1.23.3"', '__version__ = "1.23.4"', "S8c")
print("  · S8 版本与 changelog 已改")

# ============================================================ 写盘
ast.parse(src)
out = src.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "出现 CRCRLF（write_text 陷阱）"
DST.write_bytes(out)
print("已写出 %s（%d 行，纯 CRLF）" % (DST.name, out.count(b"\n") + 1))

a = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
c = DST.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
sm = difflib.SequenceMatcher(None, a, c, autojunk=False)
d = sum(i2 - i1 for t, i1, i2, j1, j2 in sm.get_opcodes() if t == "delete")
i_ = sum(j2 - j1 for t, i1, i2, j1, j2 in sm.get_opcodes() if t == "insert")
print("vs v1.23.3：纯删除 %d 行 / 纯新增 %d 行 / 总行数 %d -> %d"
      % (d, i_, len(a) - 1, len(c) - 1))
