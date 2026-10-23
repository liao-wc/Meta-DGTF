#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.21.71 打补丁脚本：F1 ~ F11（11 处缺陷修复）

用法：
    python _mk_v71_patch.py 元DGTF-V1.21.70.py 元DGTF-V1.21.71.py

铁律（本项目固定流程）：
  · 主文件**纯 CRLF**：读 bytes → utf-8 decode → 断言 CRLF 一致
    → 归一成 LF → 替换 → 回写 CRLF → 双向断言。
  · 每次替换前断言**查找块出现次数 == 1**（重复插入是真实事故）。
  · docstring 里不写单反斜杠。
  · 改完打印各版本段的起始行号序列，确认最新在最前。
"""
import re
import sys
from pathlib import Path

SRC = Path(sys.argv[1]).resolve()
DST = Path(sys.argv[2]).resolve()

raw = SRC.read_bytes().decode("utf-8")
assert raw.count("\r\n") == raw.count("\n"), "源文件不是纯 CRLF"
assert raw.count("\r") == raw.count("\r\n"), "源文件里有裸 CR"
assert "__version__ = \"1.21.70\"" in raw, "源文件版本号不是 1.21.70"
s = raw.replace("\r\n", "\n")

BAR = "\u2550" * 60        # ═
LINE = "\u2500" * 60       # ─

REPL = []


def add(tag, old, new):
    REPL.append((tag, old, new))


# ======================================================================
# P0 · 版本号两处 + changelog 新段
# ======================================================================
add("P0-标题", "元 DGTF · v1.21.70\n", "元 DGTF · v1.21.71\n")
add("P0-版本号", '__version__ = "1.21.70"', '__version__ = "1.21.71"')

_NEW_SEC = """  @@BAR@@
v1.21.71 相对 v1.21.70 的改动（F1~F11 十一项缺陷修复）
@@BAR@@

  来源：外部代码检查报告（24 项）+ 修复任务书（F1~F11 十一项）。
  ★ 逐条**复核前提**之后才动手 —— 复核结论写进每条的「根因」里，
    其中一条（外部清单说 `_build_inp_duel` 也有 KeyError 风险）经实测
    **不成立**，登记在 F3 的注里，不作改动。

  @@LINE@@
  P0
  @@LINE@@

  **F1 · 单圈层跳过全部收尾逻辑**
  **位置**：`_run_layer` 收尾调用点；`_b_finalize_layer` 的守卫。
  **根因**：两处各有一道 `> 1` 门（serial 是 `rounds_n > 1`，B/C/D-H 是
  `state["total_rounds"] <= 1`），`rounds = 1` 的层于是拿到一个**没有
  roles_run / rounds_cap / round_log / stop_reason** 的 view，
  合并后二次去重与质量检查也全不执行。改前实测（`_probe_v71.py` [A]，
  四层各请求 1 圈）：0/1/both 三层这四个字段**全为 0 / 空**。
  更难看的是 entry == "all"：`_total_rounds = rounds_n + all_extra_rounds`
  实际跑了 2 圈，收尾照样被跳过 —— 「跑了两圈却不留收尾」。
  **做法**：serial 侧 `if view is not None and rounds_n > 1:` →
  `if view is not None:`；B/C/D-H 侧删掉 `total_rounds <= 1` 早返回。
  两处即本项目「同一条逻辑两条通道各写一份」的第 7 次，这次两处一起改。
  **连带**：`_finalize_layer_common` 的 docstring 里「调用方只在
  rounds_n > 1 时才进入」这句已经不成立，同步改掉（self 记忆仍然**不**
  放进去，双写风险不变）。

  **F2 · main() 里 save_result 没有兜底**
  **位置**：`main()` 末尾。
  **根因**：`_interactive_run` 早就有 `try/except`（打印「保存失败」继续），
  而 `main()` 直接裸调。改前实测（`_probe_v71.py` [B]，把 save_result
  打桩成抛 OSError）：异常**冲出 main()**，终端没有任何「保存失败」字样，
  整轮结果丢掉。
  **做法**：包 try/except，失败打印原因 + `sys.exit(1)`；成功路径不变
  （probe [B] 两个方向都测了）。

  @@LINE@@
  P1
  @@LINE@@

  **F3 · `_build_inp_meta` 的 KeyError 隐患**
  **位置**：`_build_inp_meta` 的 `upstream_pools=[self.pools[getattr(v,
  "entry", "0")] for v in up]`。
  **根因**：上游 view 的 entry 若不是四层之一（例如 "9"），配对取池会
  **KeyError 打崩元层**。改前实测（`_probe_v71.py` [C]）：`KeyError: '9'`。
  **做法**：配对过滤 —— entry 不在 `self.pools` 里的上游 view **与其池
  一起剔除**，并留痕两处以上（`logger.warning` + 实例字段
  `_build_inp_dropped` + verbose 终端）。★ 不静默换成默认池：换池等于让
  元层读错形状还不自知。
  **注**：外部清单说 `_build_inp_duel`「同样处理」—— **实测不成立**，
  那里 `upstream_pools` 是固定的 `[self.pools["0"], self.pools["1"]]`，
  没有这个风险，本版不动它。

  **F4 · `load_config("")` 误报解析失败**
  **位置**：`load_config` 的入口守卫。
  **根因**：`Path("")` 就是当前目录、`.exists()` 为真 → 继续走
  `open("")` → FileNotFoundError → 打出一条**误导性**的
  「读取  失败」（路径是空的，用户根本没给配置）。改前实测
  （`_probe_v71.py` [D] empty_path）：`警告=True`。
  **做法**：`if not path or not (HAS_YAML and Path(path).exists()):`。
  负对照：真正坏的 yaml 仍必须报「配置文件解析失败」（probe [D] bad_yaml
  改后仍为 True）；不存在的路径本来就不该报（外部清单说「不存在.yaml
  应打印警告」，**实测那是错的** —— 现在也是静默回落，本版不改这个语义）。

  **F5 · C / D-H 早退时 dispatch 为空**
  **位置**：`_run_parallel_C` 与 `_run_parallel_stage` 的 `if not active`。
  **根因**：这两条早退路径 `return self._pack_result(...)`，而
  `_pack_result` 里 dispatch 是**空 dict** —— `_layer_guard` 读
  `skipped` / `missing` 全读不到，守卫等于短路。改前实测
  （`_probe_v71.py` [E]）：两条路径的 dispatch 键集都是 `[]`。
  **做法**：早退也补 `_dispatch_for_pack(mode, {...})`，模式名**取实际
  变量**（C 处 "C"，D-H 处用 `mode`），不硬编码。

  **F6 · 单次运行跑两次外部可判定性评估**
  **位置**：`_route_by_decidability`（开跑前定 route）与
  `_assess_decidability_dynamic`（研究层拆解时读池）。
  **根因**：两处各自 `d._assess_decidability(question)`，一次 run 会打
  **两次**外部评估，白花 token。改前实测（`_probe_v71.py` [F]，站点计数）：
    外部评估调用次数 = 2  （route_by_decidability=1 / assess_dynamic=1）
  **做法**：加运行内缓存 `_ext_assess_cache`（`__init__` 建、`run()` 开头
  重置 —— 重置必须放在 `_route_by_decidability` **之前**，否则会把刚刚
  填进去的那条抹掉）+ 薄壳 `_cached_ext_assess`；两处调用点都改走它。
  **边界**：失败不缓存（异常照旧上抛给调用点的既有 except）；跨运行、
  跨配置不复用（每 run 重置）。

  **F7 · J 修承诺的「完整 evidence」没兑现**
  **位置**：`_assess_decidability_from_pool_view` 的返回值 /
  `_merge_decidability` 的兜底重算分支。
  **根因**：v1.21.70 [J] 在 changelog 里写明「缓存值用完整 evidence 算，
  重算路径读的是 `evidence[:8]`，两者会不一致」—— **只写了没改**，
  承诺与实现不符。改前实测（`_probe_v71.py` [G]，故意造 9 条 evidence、
  追溯落在第 9 条）：缓存路 `_und_untraced = []`，兜底路
  `= ['清分规则未定，断面客流与线路客流不可互证']`，两路口径不一致。
  **做法**：池评估返回值新增**加性**键 `_evidence_full`（不动 `evidence`
  本身），兜底分支优先用它；`_merge_decidability` 的注释同步说明。

  @@LINE@@
  P2
  @@LINE@@

  **F8 · 模块级 `auto_plan` 与方法级 `_auto_plan` 双实现**
  **位置**：`MetaDGTF._auto_plan` 与模块级 `auto_plan`（= `plan_orientation`
  + `plan_resources`）。
  **根因**：两份实现各写一份「模式白名单归一 + 逐层圈数钳到
  `[_layer_floor, _layer_ceil]` + 漏层按中位数补 + 低置信退 serial」，
  长期并行必然漂移；模块级那份在文件里没有任何内部调用点。
  **做法**（选**方案 A**，保守）：两份都留，`_auto_plan` 的 docstring 显式
  标注关系与共同遵守的规则，并加一条一致性冒烟
  （`check_v71_auto_plan_agreement`）：同一 mock 输入下两实现的
  `mode` 与（按 route 裁剪后的）`rounds` 必须逐字相同；负对照用子类把
  方法级那份的圈数改坏，断言**必须**判不一致。
  **未采纳**：方案 B（统一成唯一实现、`_auto_plan` 退成薄壳）改动面涉
  `plan_orientation` / `plan_resources` 的 `llm` 参数贯通，属架构批，
  本轮不做 —— 但**漂移检测器已经就位**。

  **F9 · `_STOPWORDS` 是一组字符不是词**
  **位置**：`_STOPWORDS` 定义 + `_tokenize` 的
  `len(t) >= 2 and t not in _STOPWORDS`。
  **根因**：原集合是**单字**集合，而 `len(t) >= 2` 已经把单字滤掉了 ——
  这份集合在分词结果里几乎不起作用；真正的多字停用词（的话 / 一种 /
  进行）一个都挡不住。改前实测（`_probe_v71.py` [H]）：
  `stopwords_is_chars=True`，分词结果里 `的话/我们/通过/一种/进行` 全在。
  **做法**：拆成 `_STOPCHARS`（原单字集合，保留、不再被引用——加性不动旧行）
  + `_STOPWORDS`（**按词**匹配的多字集合，取任务书给定的 21 个词）。
  `_tokenize` 一个字都不用改，它读的就是 `_STOPWORDS`。
  ★ 这是**运行期可见变化**：key_terms / 相似度会跟着变（内容词不受影响：
  螺旋 / 结构 / 整理 实测仍在）。

  **F10 · `coverage_parts(pool, {})` 的隐式假设**
  **位置**：`_refresh_settlement`。
  **根因**：签名要求一个 dict 而函数当前不读它；传 `{}` 等于隐式假设
  「这个函数永远不看 cfg」。将来给它加 cfg 相关分支，这里会静默走默认值。
  **做法**：签名改 `cfg: Optional[dict] = None`（docstring 说明）；调用点
  改传 `self.config`。改前实测（probe [I]）：`coverage_parts(pool)` 直接
  `TypeError: missing 1 required positional argument`。

  @@LINE@@
  P3
  @@LINE@@

  **F11 · 收尾二次 `_quality_check` 多写一份 position 诊断**
  **位置**：`_finalize_layer_common` 的收尾质量检查。
  **根因**：`_quality_check` 在 `position_all_same` 时会调
  `_dump_position_diagnostic` **写文件**；收尾（合并后重跑一次）会再写
  一份同名不同时间戳的 `outputs/diagnostic_position_*.log`。
  改前实测（`_probe_v71.py` [J]，一次 serial 四层跑）：
    dump 尝试次数 in_round=0 / in_finalize=4；13 次 `_quality_check`
    调用里 0 次带 write_diag=False。
  **做法**：`_quality_check` 加关键字参数 `write_diag: bool = True`
  （圈内调用**保持默认 True**，行为不变）；收尾调用传 `False`，
  且不静默 —— 压制时打一条 `logger.info` 说明「本该写、因收尾复核没写」。
  ★ 观测到的**副作用**必须记下来：在 mock 这一跑里 dump **全部**来自
  收尾站点（圈内的候选 position 是交错的，本来就不触发 all_same），
  所以改后该跑不再产出诊断文件。这是「不再重复」与「保住唯一那份」之间
  的取舍：真正的诊断对象是**圈内那一份**，收尾复核只是拿合并后的候选
  再看一眼。若日后要两个都留，正确做法是按内容去重而不是按站点关一张，
  归到可观测性批。

  @@LINE@@
  刻意不做（本轮明确不碰）
  @@LINE@@

  · #20 changelog 重复 / v1.21.68 与 v1.21.69 段序颠倒 —— 纯文档性，
    一次性脚本去重 + 重排，留待文档整理批。
  · #21 拆文件（17k 行 → 多模块）—— 结构性重构，涉全部 import / 循环
    依赖 / 打包 / 测试基线，单独立项。
  · #22 「同一逻辑两条通道各写一份」的全局调用图 —— 需要专门设计
    「机制 → 唯一实现点」的断言框架，留待 v1.22 架构批。本轮只在 F1 / F6
    的具体点上各配负对照。
  · #23 「零触发机制」的阈值复查（如 `escalate_starve_rounds`）——
    v1.21.65 已裁决「保留、题不匹配」，需后续交叉验证；本轮**不改任何
    阈值 / 常量**。
  · #24 `_OVERSIZED` 硬编码字段名清单 —— v1.21.70 [H] 有意只钉字段名、
    不维护清单（新增字段不误伤），理由仍成立。留待可观测性批。
  · #13 B 模式预算耗尽「停所有层」—— B 是 barrier 制，每波所有层一起跑，
    预算耗尽时一起停是**合理的**；与串行/C 的「本层截断」是刻意的语义
    差异，不是 bug。本版只在报告里写明，不改代码。

  @@LINE@@
  验证
  @@LINE@@

  **前置量化**：`_probe_v71.py`（接受目标 py 作参数，走生产入口：
  `MetaDGTF.run` / `_b_finalize_layer` / `DGTF._quality_check` /
  `load_config` / `main()`），改前 / 改后各跑一次对表
  （`_probe_v71_before.txt` / `_probe_v71_after.txt`）。判据：
    · [A] 四层各 1 圈：roles_run / rounds_cap / round_log 从 0/0/0 变成
      非零；`_b_finalize_layer(total_rounds=1)` 同样；
    · [B] 保存失败：从「异常冲出 main()」变成「SystemExit(1) + 打印」；
    · [C] 非法 entry：从 `KeyError: '9'` 变成被剔除 + 留痕；
    · [D] `load_config("")`：警告从 True 变 False，坏 yaml 仍 True；
    · [E] 空 active：dispatch 键集从 `[]` 变成含 ran/missing/failed/skipped；
    · [F] 外部评估次数从 2 变 1；
    · [G] 缓存 / 兜底两路口径从不一致变一致；
    · [H] 多字停用词从全在变被挡，内容词仍在；
    · [I] `coverage_parts(pool)` 从 TypeError 变可用；
    · [J] `in_finalize` 的 dump 尝试次数从 4 变 0；
    · [K] 两实现一致（负对照必须判不一致）。

  **冒烟**：`SRC` → v1.21.71；新增 11 条 `check_v71_*`，每条带**负对照**
  与接线断言（`inspect.getsource`）。判据：exit 0 / 0 个 ✗。

  **真跑验收**：serial 一次（四层各 1 圈，专门验 F1 的单圈收尾）、
  B 模式一次（验并行通道的同一处），`--rounds "0:1,1:1,both:1,all:1"`
  与默认四层 2 圈各跑，逐层核对【螺旋停止】与【收尾留痕】。

"""

add("P0-changelog",
    "\n  " + BAR + "\nv1.21.70 相对 v1.21.69 的改动（F~J 六项修复）\n" + BAR,
    "\n" + _NEW_SEC.replace("@@BAR@@", BAR).replace("@@LINE@@", LINE)
    + "  " + BAR + "\nv1.21.70 相对 v1.21.69 的改动（F~J 六项修复）\n" + BAR)


# ======================================================================
# F1 · 单圈层跳过全部收尾逻辑
# ======================================================================
add("F1-serial门",
    """        if view is not None and rounds_n > 1:
            self._finalize_layer_common(entry, view, {""",
    """        # [v1.21.71 F1] 去掉 `rounds_n > 1` 门：单圈层也要走完整收尾。
        #   改前实测（`_probe_v71.py` [A]，四层各请求 1 圈）：
        #   0/1/both 三层的 roles_run / rounds_cap / round_log 全是 0，
        #   stop_reason 也空 —— 产物里看不出这几层跑过什么。
        #   entry == "all" 更糟：`_total_rounds = rounds_n +
        #   all_extra_rounds` 会真跑 2 圈，收尾照样被跳过。
        if view is not None:
            self._finalize_layer_common(entry, view, {""")

add("F1-B门",
    """        view = state["view"]
        if state["total_rounds"] <= 1:
            return
        self._finalize_layer_common(entry, view, state)""",
    """        view = state["view"]
        # [v1.21.71 F1] 删掉 `total_rounds <= 1` 早返回。与 serial 通道
        #   同一处缺陷（本项目「同一条逻辑两条通道各写一份」的第 7 次）：
        #   单圈层的收尾字段同样整段丢失。
        self._finalize_layer_common(entry, view, state)""")

add("F1-docstring",
    """        ★ self 记忆**不在本函数里写**：serial 通道在调用方块外
          单独写、B/C/D-H 通道在 _run_one_round_B 里逐圈写。两处
          时机都要求「单圈的层也要写」——塞进本函数（调用方只在
          rounds_n > 1 时才进入）会让单圈层的 self 段为空。
        \"\"\"""",
    """        ★ self 记忆**不在本函数里写**：serial 通道在调用方块外
          单独写、B/C/D-H 通道在 _run_one_round_B 里逐圈写。两处
          时机都要求「单圈的层也要写」——塞进本函数会让单圈层的
          self 段被写两次。
          ★ [v1.21.71 F1] 上面这句本来写的是「塞进本函数会让单圈层
            的 self 段为空」，理由是「调用方只在 rounds_n > 1 时才
            进入」。F1 去掉那道门之后理由已不成立（调用方对**所有**
            层都进入），但结论不变 —— 改的是理由，不是时机。
        \"\"\"""")


# ======================================================================
# F2 · main() 里 save_result 没有兜底
# ======================================================================
add("F2-main保存兜底",
    """    print(f"{'═'*60}")

    save_result(result, cfg["output"]["save_dir"])


if __name__ == "__main__":
    main()""",
    """    print(f"{'═'*60}")

    # [v1.21.71 F2] 保存失败必须兜底：与 `_interactive_run` 对齐
    #   （那里本来就有 try/except 并打印「保存失败」）。改前实测
    #   （`_probe_v71.py` [B]，把 save_result 打桩成抛 OSError）：
    #   异常直接冲出 main()，终端一个「保存失败」字样都没有，
    #   整轮结果丢掉、也没有非零退出码给 shell 判。
    try:
        save_result(result, cfg["output"]["save_dir"])
    except Exception as e:
        print(f"\\n⚠️  保存失败：{type(e).__name__}: {e}")
        print("   本次结果**没有落盘**，上面的终端输出是唯一记录。")
        sys.exit(1)


if __name__ == "__main__":
    main()""")


# ======================================================================
# F3 · _build_inp_meta 的 KeyError 隐患
# ======================================================================
add("F3-配对过滤",
    """        up = [v for v in up if _view_usable(v)]
        # [v1.21.63 C1修-2] 守卫从 `len(up) < 2` 放宽成 `not up`：""",
    """        up = [v for v in up if _view_usable(v)]
        # [v1.21.71 F3] 配对过滤：entry 必须能索引到池。改前
        #   `upstream_pools` 用 `self.pools[getattr(v, "entry", "0")]`，
        #   上游 view 的 entry 非法（非四层之一，例如 "9"）时直接
        #   KeyError **打崩元层**（`_probe_v71.py` [C] 实测
        #   `KeyError: '9'`）。这里 view 与它的池要么都留、要么都丢，
        #   绝不静默换成默认池 —— 换池等于让元层读错形状还不自知。
        #   ★ 外部清单说 `_build_inp_duel`「同样处理」：**实测不成立**，
        #     那里的 upstream_pools 是固定的 [0,1] 池，没有这个风险。
        _pairs, _bad_entry = [], []
        for _v in up:
            _e = getattr(_v, "entry", "")
            if _e in self.pools:
                _pairs.append(_v)
            else:
                _bad_entry.append(str(_e))
        if _bad_entry:
            _note = (f"上游 view 的 entry 非法"
                     f"（{','.join(sorted(set(_bad_entry)))}）"
                     f"，已剔除 {len(_bad_entry)} 条、不参与元层配对")
            self._build_inp_dropped = _note
            logger.warning("%s", _note)
            self.vp(f"   ⚠️ {_note}")
        up = _pairs
        # [v1.21.63 C1修-2] 守卫从 `len(up) < 2` 放宽成 `not up`：""")


# ======================================================================
# F4 · load_config("") 误报
# ======================================================================
add("F4-空路径短路",
    """def load_config(path: str) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if not (HAS_YAML and Path(path).exists()):
        return cfg""",
    """def load_config(path: str) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    # [v1.21.71 F4] `not path` 短路：`Path("")` 就是当前目录、`.exists()`
    #   为真，于是会走到 `open("")` → FileNotFoundError → 打一条
    #   **误导性**的「读取  失败」（路径是空的，用户根本没给配置）。
    #   实测见 `_probe_v71.py` [D] empty_path。
    #   ★ 「路径不存在 → 静默回落默认配置」是**原有语义**，本版不改它
    #     （外部清单说"不存在.yaml 应打印警告"，实测与代码意图不符）。
    if not path or not (HAS_YAML and Path(path).exists()):
        return cfg""")


# ======================================================================
# F5 · C / D-H 早退时 dispatch 为空
# ======================================================================
add("F5-C早退dispatch",
    """        if not active:
            self.vp("\\n   ⚠️ route 为空，C 模式无事可做")
            return self._pack_result(question, route, keep, rounds, {})""",
    """        if not active:
            self.vp("\\n   ⚠️ route 为空，C 模式无事可做")
            packed = self._pack_result(question, route, keep, rounds, {})
            # [v1.21.71 F5] 早退也必须带 dispatch：`_layer_guard` 读的是
            #   packed["dispatch"]，拿空 dict 等于守卫短路 —— 计划里被
            #   跳过的层（skipped）与请求了却没产出的层（missing）
            #   一条都报不出来。模式名取实际变量，不硬编码。
            packed["dispatch"] = self._dispatch_for_pack(
                "C", {"_warmup_rounds": self._warmup_done})
            return packed""")

add("F5-stage早退dispatch",
    """        if not active:
            self.vp(f"\\n   ⚠️ route 为空，{mode} 模式无事可做")
            return self._pack_result(question, route, keep, rounds, {})""",
    """        if not active:
            self.vp(f"\\n   ⚠️ route 为空，{mode} 模式无事可做")
            packed = self._pack_result(question, route, keep, rounds, {})
            # [v1.21.71 F5] 同 C：早退也要带 dispatch，否则守卫短路。
            #   这里的模式名就是参数 `mode`（D~H 各自的实际名）。
            packed["dispatch"] = self._dispatch_for_pack(
                mode, {"_warmup_rounds": self._warmup_done})
            return packed""")


# ======================================================================
# F6 · 外部评估只跑一次
# ======================================================================
add("F6-init缓存",
    """        self.decidability_result: Dict[str, Any] = {}
        self._input_sanity: Dict[str, Any] = {}  # [P1-6]""",
    """        self.decidability_result: Dict[str, Any] = {}
        self._input_sanity: Dict[str, Any] = {}  # [P1-6]
        # [v1.21.71 F6] 运行内缓存：同题的外部可判定性评估只跑一次。
        #   命中点两处 —— `_route_by_decidability`（开跑前定 route）与
        #   `_assess_decidability_dynamic`（研究层拆解时读池）。改前实测
        #   （`_probe_v71.py` [F]，站点计数）一次 serial 四层跑会打**两次**
        #   外部评估（route_by_decidability=1 / assess_dynamic=1）。
        #   `run()` 开头会重置它（顺序必须在 `_route_by_decidability`
        #   之前，否则刚填进去的那条会被抹掉）。
        self._ext_assess_cache: Dict[str, dict] = {}""")

add("F6-run重置",
    """        route = route or ["0", "1", "both", "all"]
        # [v1.21.62 P2-7] 判据从"能不能判"改成"想要什么"
        route = self._route_by_decidability(question, route, orientation)""",
    """        route = route or ["0", "1", "both", "all"]
        # [v1.21.71 F6] 外部评估的运行内缓存**每次 run 重置**。
        #   ★ 位置必须在下面那条 `_route_by_decidability` **之前**：
        #     它自己就是第一个写缓存的人，放后面等于把刚填的抹掉。
        self._ext_assess_cache = {}
        # [v1.21.62 P2-7] 判据从"能不能判"改成"想要什么"
        route = self._route_by_decidability(question, route, orientation)""")

add("F6-薄壳",
    """    def _route_by_decidability(self, question: str,
                               route: List[str],
                               orientation: str = "auto") -> List[str]:
        \"\"\"[v1.21.62 P2-7] 前置判定：判据从"能不能判"改成"想要什么"。""",
    """    def _cached_ext_assess(self, question: str) -> dict:
        \"\"\"[v1.21.71 F6] 同题的外部可判定性评估，一次运行内只跑一次。

        ★ 为什么需要：`_route_by_decidability`（开跑前定 route）与
          `_assess_decidability_dynamic`（研究层拆解时读池）各自要一次
          **同题同配置**的外部评估，改前一次 run 打两次 API。
        ★ 边界：
          · 只在本实例的**一次 run** 内有效 —— `run()` 开头重置缓存；
          · 失败**不缓存**：`_assess_decidability` 抛异常时原样上抛，
            由两个调用点各自的 except 处理（行为与改前一致）；
          · 外判结果是 (问题, 配置) 的函数，与池内容无关，所以复用
            不会拿到"过期的池形状"（池那条走的是
            `_assess_decidability_from_pool_view`，不在本缓存里）。
        \"\"\"
        cache = getattr(self, "_ext_assess_cache", None)
        if cache is None:
            cache = {}
            self._ext_assess_cache = cache
        key = (question or "").strip()
        if key in cache:
            return cache[key]
        d = DGTF("1", self.llm, self.config)
        d.verbose = False
        res = d._assess_decidability(question)
        cache[key] = res
        return res

    def _route_by_decidability(self, question: str,
                               route: List[str],
                               orientation: str = "auto") -> List[str]:
        \"\"\"[v1.21.62 P2-7] 前置判定：判据从"能不能判"改成"想要什么"。""")

add("F6-road调用点",
    """        # _o == "decision"
        try:
            d = DGTF("1", self.llm, self.config)
            d.verbose = False
            ext = d._assess_decidability(question)
        except Exception as e:""",
    """        # _o == "decision"
        try:
            # [v1.21.71 F6] 走运行内缓存：研究层拆解那一步会再要一次同题的
            #   外部评估，改前这一跑会打两遍（probe 站点计数 1 + 1）。
            ext = self._cached_ext_assess(question)
        except Exception as e:""")

add("F6-动态调用点",
    """        ext_res: Optional[dict] = None
        if source_cfg in ("pool", "external"):
            d_assess = DGTF("1", self.llm, self.config)
            d_assess.verbose = False
            try:
                ext_res = d_assess._assess_decidability(question)
            except Exception as exc:
                logger.warning("外部可判定性评估失败: %s", exc)""",
    """        ext_res: Optional[dict] = None
        if source_cfg in ("pool", "external"):
            try:
                # [v1.21.71 F6] 与 `_route_by_decidability` 共用同一份
                #   外部评估（同一次运行内），改前这里会再打一次 API。
                ext_res = self._cached_ext_assess(question)
            except Exception as exc:
                logger.warning("外部可判定性评估失败: %s", exc)""")


# ======================================================================
# F7 · 完整 evidence
# ======================================================================
add("F7-带出完整evidence",
    """            "evidence": evidences[:8],
            "_source": "pool",""",
    """            "evidence": evidences[:8],
            # [v1.21.71 F7] 完整 evidence 一并带出，供 `_merge_decidability`
            #   的兜底重算用 —— 它原来读的是上面那个**截断**过的 [:8]，
            #   与缓存路径口径不同（v1.21.70 [J] 只在 changelog 里承诺了
            #   这件事，没真改）。新键是**加性**的，不改 `evidence` 本身，
            #   旧断言不受影响。
            "_evidence_full": list(evidences),
            "_source": "pool",""")

add("F7-兜底口径",
    """        #   ★ 兜底：万一调用方给的 pool_res 没带这个字段（历史数据 /
        #     手造桩 / external-only 路径），退回重算一次，不静默吞。""",
    """        #   ★ 兜底：万一调用方给的 pool_res 没带这个字段（历史数据 /
        #     手造桩 / external-only 路径），退回重算一次，不静默吞。
        #     [v1.21.71 F7] 重算**改用 `_evidence_full`**：口径必须与缓存
        #     那条一致（详见下面的实现）。""")

add("F7-兜底改用full",
    """        _cached = pool_res.get("_und_untraced")
        if isinstance(_cached, list):
            _untraced_pool = set(_cached)
        else:
            _untraced_pool = set(_untraced_undecidable(
                pool_res.get("undecidable_aspects", []),
                pool_res.get("evidence", [])))""",
    """        _cached = pool_res.get("_und_untraced")
        if isinstance(_cached, list):
            _untraced_pool = set(_cached)
        else:
            # [v1.21.71 F7] 兜底口径与缓存口径统一：用**完整** evidence。
            #   `pool_res["evidence"]` 是 [:8] 截断过的，拿它重算会把第 9
            #   条之后的追溯判成"无追溯"（`_probe_v71.py` [G] 实测：
            #   缓存路 [] vs 兜底路 ['清分规则未定，断面客流与线路客流不可
            #   互证']），而这条判据直接进 `_normalize_decidability` 的输入。
            _full_ev = list(pool_res.get("_evidence_full")
                            or pool_res.get("evidence") or [])
            _untraced_pool = set(_untraced_undecidable(
                pool_res.get("undecidable_aspects", []),
                _full_ev))""")


# ======================================================================
# F8 · 两份调度实现的关系标注（方案 A）
# ======================================================================
add("F8-docstring标注",
    """        ★ 边界：只在**用户什么都没指定**时才接管。指定了模式或圈数
        任一，就尊重用户，退回单目标决策 —— 自作主张覆盖显式参数
        是另一类 bug。
        \"\"\"""",
    """        ★ 边界：只在**用户什么都没指定**时才接管。指定了模式或圈数
        任一，就尊重用户，退回单目标决策 —— 自作主张覆盖显式参数
        是另一类 bug。

        ★★ [v1.21.71 F8] 与**模块级 `auto_plan()`** 的关系（两份实现，已
          知的双实现，本版**只加检测器、不合并**）：
            · 模块级 `auto_plan` = `plan_orientation` + `plan_resources`，
              **两次**调用、带 orientation 段、没有任何内部调用点，
              是给外部使用的 API；
            · 本方法 = **一次**调用同时定 mode + rounds，`run()` 的自动
              调度走的是它（`parallel_mode == "auto" and not rounds`）。
            · 两者**没有任何互相调用**，但各自都写了一份**同规则**的
              归一化：模式白名单（A~H 之外 → serial）+ 逐层圈数钳到
              `[_layer_floor, _layer_ceil]` + 漏层按已给合法值的**中位数**
              补 + 低置信（< `_PARALLEL_CONF_MIN`）退 serial。
              规则虽同、代码是两份 —— 长期并行必然漂移（本项目
              「同一条逻辑两条通道各写一份」的第 N 次）。
            · 本版的对策是**漂移检测器**：冒烟
              `check_v71_auto_plan_agreement` 用同一份 mock 输入分别喂两个
              实现，断言 mode 与（按 route 裁剪后的）rounds 逐字相同；
              负对照用子类把方法级那份的圈数改坏，断言**必须**判不一致。
            · 真正合并成唯一实现（模块级那份加 `llm` 参数、本方法退成
              薄壳）要贯通 `plan_orientation` / `plan_resources` 的
              签名，属架构批，本轮不做。
        \"\"\"""")


# ======================================================================
# F9 · 停用词按词匹配
# ======================================================================
add("F9-停用词拆两类",
    """_STOPWORDS = set(
    "的了是在和与或及之于以及为此则就也都还但而所以因为如果那么这那这些那些"
    "一种一个进行已经可以通过我们你们他们它们什么怎么如何为何哪些这个那个哪个"
)""",
    """# [v1.21.71 F9] 原来是**一组字符**却被当词用：`_tokenize` 里是
#   `len(t) >= 2 and t not in _STOPWORDS`，而单字早被 `len >= 2` 滤掉，
#   于是这份集合在分词结果里**几乎不起作用**；真正的多字停用词
#   （"的话" / "一种" / "进行"）反倒一个都挡不住。改前实测
#   （`_probe_v71.py` [H]）：`stopwords_is_chars=True`，分词结果里
#   `的话 / 我们 / 通过 / 一种 / 进行` 全在。
#   ★ 现在拆成两个：
#     · `_STOPCHARS` —— 原来的单字集合。**保留**（加性，不删旧行），
#       当前无引用；留着是为了「原来挡了什么」这件事有据可查。
#     · `_STOPWORDS`  —— **按词**匹配的多字停用词，`_tokenize` 直接读它，
#       所以 `_tokenize` 一个字都没改。
#   ★ 这是运行期可见变化：key_terms / 相似度会跟着变（内容词不受影响，
#     实测"螺旋 / 结构 / 整理"仍在）。
_STOPCHARS = set(
    "的了是在和与或及之于以及为此则就也都还但而所以因为如果那么这那这些那些"
    "一种一个进行已经可以通过我们你们他们它们什么怎么如何为何哪些这个那个哪个"
)
_STOPWORDS = {
    "的话", "一种", "一个", "进行", "已经", "可以", "通过",
    "我们", "你们", "他们", "它们", "什么", "怎么", "如何", "为何",
    "这个", "那个", "哪个", "这些", "那些", "哪些",
}""")


# ======================================================================
# F10 · coverage_parts 的 cfg 可选
# ======================================================================
add("F10-签名",
    """def coverage_parts(pool, cfg: dict):""",
    """def coverage_parts(pool, cfg: Optional[dict] = None):""")

add("F10-docstring",
    """    没有冻结标记的池（判决没跑成、或走了未覆盖的路径）回落到旧口径，
    不静默换算法。
    \"\"\"""",
    """    没有冻结标记的池（判决没跑成、或走了未覆盖的路径）回落到旧口径，
    不静默换算法。

    [v1.21.71 F10] `cfg` 改成**可选**。本函数目前**不读 cfg**（只用池
    字段），所以签名里那个必填的 dict 只是让人以为"必须给点什么"；
    `_refresh_settlement` 原来传 `{}`，等于隐式假设"这个函数永远不看
    cfg"，将来真加了 cfg 分支这里会静默走默认值。现在：签名可选 +
    调用点传真配置，两件事都做到。
    \"\"\"""")

add("F10-调用点",
    """            _x, _y, _cov = coverage_parts(self.pools["1"], {})""",
    """            # [v1.21.71 F10] 原来传 `{}`：等于隐式假设"这个函数永远
            #   不看 cfg"。改成把真配置传进去（签名现在也可选），
            #   将来它读 cfg 时这里不会静默走默认值。
            _x, _y, _cov = coverage_parts(self.pools["1"], self.config)""")


# ======================================================================
# F11 · 收尾不再重复写 position 诊断
# ======================================================================
add("F11-签名与说明",
    """    def _quality_check(self, view: View, pool: Pool,
                       round_no: int = 0) -> List[str]:
        flags = []""",
    """    def _quality_check(self, view: View, pool: Pool,
                       round_no: int = 0, *,
                       write_diag: bool = True) -> List[str]:
        \"\"\"质量线索。

        [v1.21.71 F11] `write_diag` 只管一件事：**position_all_same 的
        诊断文件写不写**。
          · 圈内调用（`DGTF.run` 里）**保持默认 True** —— 诊断的对象本来
            就是"这一圈的候选怎么会全挤在同一个 position"；
          · 收尾复核（`_finalize_layer_common` 里，合并后重跑一次）传
            False —— 同一层会再写一份同名不同时间戳的
            `outputs/diagnostic_position_*.log`，是重复留痕。
        ⚠️ 压制时**不静默**：打一条 `logger.info` 说明"本该写、因收尾
        复核没写"。
        \"\"\"
        flags = []""")

add("F11-诊断调用点",
    """                    dumped = self._dump_position_diagnostic(
                        view, view.anchor, round_no)
                    if dumped:
                        logger.info("position 诊断已写：%s", dumped)
                else:""",
    """                    if write_diag:
                        dumped = self._dump_position_diagnostic(
                            view, view.anchor, round_no)
                        if dumped:
                            logger.info("position 诊断已写：%s", dumped)
                    else:
                        logger.info(
                            "position_all_same（收尾复核）："
                            "write_diag=False，不重复写诊断文件")
                else:""")

add("F11-收尾不写诊断",
    """        # ---- 3. 质量检查（合并后重跑一次，用全量候选）----
        _dg = DGTF(entry, self.llm, self.config)
        _dg.verbose = False
        view.quality_flags = _keep_selfcheck_flags(
            view, _dg._quality_check(
                view, self.pools[entry], r_actual))""",
    """        # ---- 3. 质量检查（合并后重跑一次，用全量候选）----
        # [v1.21.71 F11] `write_diag=False`：收尾复核**不再**重复写
        #   position 诊断文件。改前实测（`_probe_v71.py` [J]，一次 serial
        #   四层跑）：dump 尝试次数 in_finalize=4（全部来自这里），
        #   13 次 _quality_check 调用里 0 次带 write_diag=False。
        _dg = DGTF(entry, self.llm, self.config)
        _dg.verbose = False
        view.quality_flags = _keep_selfcheck_flags(
            view, _dg._quality_check(
                view, self.pools[entry], r_actual, write_diag=False))""")


# ======================================================================
# 执行
# ======================================================================
print(f"打补丁：{SRC.name} → {DST.name}")
print(f"计划替换 {len(REPL)} 处\n")

fail = []
for tag, old, new in REPL:
    n = s.count(old)
    if n != 1:
        fail.append(f"{tag}: 命中 {n} 次（必须恰好 1 次）")
        continue
    s = s.replace(old, new, 1)
    print(f"   ✓ {tag}")

if fail:
    print("\n✗ 中止，未写文件：")
    for f in fail:
        print("   -", f)
    sys.exit(1)

# ---- 版本段顺序自检 ----
secs = [m.group(1) for m in re.finditer(r"^v(1\.21\.\d+) 相对", s, re.M)]
print(f"\n版本段起始序（行号 → 版本）：")
for m in re.finditer(r"^v(1\.21\.\d+) 相对", s, re.M):
    print(f"   {s[:m.start()].count(chr(10)) + 1:>6}  v{m.group(1)}")
assert secs[0] == "1.21.71", f"最新版本段不在最前：{secs[:4]}"
assert secs[1] == "1.21.70", f"第二段不是 v1.21.70：{secs[:4]}"
assert len(secs) == len(set(secs)), f"版本段有重复：{secs}"

# ---- 版本号两处 ----
assert '元 DGTF · v1.21.71' in s, "docstring 标题没改成 1.21.71"
assert '__version__ = "1.21.71"' in s, "__version__ 没改"

# ---- 回写 CRLF ----
out = s.replace("\n", "\r\n")
assert out.count("\n") == out.count("\r\n"), "回写后有裸 LF"
assert out.count("\r") == out.count("\r\n"), "回写后有裸 CR"
DST.write_bytes(out.encode("utf-8"))
print(f"\n✓ 已写出 {DST.name}（{len(out.encode('utf-8'))} 字节，"
      f"{out.count(chr(10))} 行按 LF 计）")
