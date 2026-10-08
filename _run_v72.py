# -*- coding: utf-8 -*-
"""[v1.21.60] 真跑验收 wrapper（按项目约定：load_dotenv → import → run →
日志落盘 → 追加调用数/耗时）。

用法：
  python _run_v60.py <mode> <rounds> <tag> "<question>"
例：
  python _run_v60.py serial 12 cls  "复杂问题被拆成几个部分分别研究之后，剩下的那个整体到底是什么"
  python _run_v60.py C 4 modeC "AI 能否独立完成数字 IC 设计流程"

产出：
  outputs/<时间>_<题目前缀>.md   ← 产物
  v60_<tag>.log                  ← verbose 日志（含结尾的元信息）
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


class _Tee:
    """把 verbose 输出同时写到「捕获缓冲」和「真实 stdout」。

    [v1.21.60] 后台批次若用工具自带后台任务会被回收，只能在独立控制台窗口里跑；
    那种场景要让人**看见过程**，所以 V60_STREAM=1 时把 stdout 也接上。
    真实 stdout 会再被 shell 的 `tee` 落盘，两边都不丢。
    """

    def __init__(self, *streams):
        self._streams = [s for s in streams if s is not None]

    def write(self, text):
        for st in self._streams:
            try:
                st.write(text)
            except Exception:
                pass
        return len(text)

    def flush(self):
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                pass

    def isatty(self):
        return False


def load_dotenv(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(),
                              v.strip().strip('"').strip("'"))


def load_module():
    spec = importlib.util.spec_from_file_location(
        "dgtf72", HERE / "元DGTF-V1.21.72.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf72"] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        return 2
    mode, rounds_s, tag, question = (sys.argv[1], sys.argv[2],
                                     sys.argv[3], " ".join(sys.argv[4:]))
    load_dotenv(HERE / ".env")
    mod = load_module()
    cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))

    # ★ V60_MAX_CALLS：强制设总调用预算，用于**实证动态提前停**。
    # 正常路径下预算由 auto_plan 给，而它给的预算总是高于实际消耗
    # （实测 160>155、150>126），于是提前停永远触发不到 —— 一个机制
    # 写了却从没在真跑里跑过。要验证就得能强行压低预算。
    # ★ V60_ROUTE：显式指定跑哪几层（逗号分隔，如 "0,1" 或 "0,1,both,all"）。
    #   route 是**最粗的成本旋钮**（2 层 61 calls vs 4 层 159），但原来只有
    #   auto 路径能设它 —— 想做「同题 2 层 vs 4 层」对照就没法跑，而那正是
    #   验证「砍层伤不伤质量」必须做的实验。也认 light/no_meta/full 预设名。
    _route_override = None
    _rt = os.environ.get("V60_ROUTE", "").strip()
    if _rt:
        _preset = {"light": ["0", "1"], "no_meta": ["0", "1", "both"],
                   "duel_only": ["0", "1", "both"],
                   "full": ["0", "1", "both", "all"]}
        if _rt.lower() in _preset:
            _route_override = _preset[_rt.lower()]
        else:
            _route_override = [x.strip() for x in _rt.split(",") if x.strip()]

    # ★ V60_THINKING：[fix-111] 按实验需要覆盖思考档位。
    #   格式：`default=disabled,reasoner=enabled,effort=low`，任一段可省。
    #   ★ 在 load_config **之后显式覆盖** cfg，不走环境变量合并 ——
    #     yaml 一旦写了某个键，`_deep_merge` 会让环境变量失效（§7.18⑤），
    #     靠 env 传进去会被静默吞掉，实验就白跑了。
    _tk = os.environ.get("V60_THINKING", "").strip()
    _tk_note = ""
    if _tk:
        th = dict(cfg["api"].get("thinking") or {})
        for seg in _tk.split(","):
            if "=" not in seg:
                continue
            k, v = seg.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k not in ("default", "reasoner", "effort"):
                continue
            th[k] = None if v.lower() in ("none", "null", "off") else v
        cfg["api"]["thinking"] = th
        _tk_note = f"🧠 thinking 覆盖（V60_THINKING）：{th}"

    # ★ V60_STAGE_THINKING：[fix-112] 覆盖逐环节档位，供对照实验用。
    #   格式：`off`（全部关）或 `stage1=enabled,stage2=disabled,...`。
    #   ★ 用途：mx batch01 这类**预注册对照批**必须在旧档位下跑完，
    #     以免「改档位」和「改旋钮」两个处理混在一起分不清。
    _sk = os.environ.get("V60_STAGE_THINKING", "").strip()
    if _sk:
        th = dict(cfg["api"].get("thinking") or {})
        st = dict(th.get("stages") or {})
        if _sk.lower() == "off":
            st = {k: "disabled" for k in st}
        else:
            for seg in _sk.split(","):
                if "=" not in seg:
                    continue
                k, v = seg.split("=", 1)
                st[k.strip()] = v.strip()
        th["stages"] = st
        cfg["api"]["thinking"] = th
        _tk_note += f" | stage 覆盖（V60_STAGE_THINKING）：{_sk}"

    _mc = os.environ.get("V60_MAX_CALLS", "").strip()
    _forced_calls = None
    if _mc:
        try:
            _forced_calls = int(_mc)
            cfg["max_calls"] = _forced_calls
        except ValueError:
            print(f"⚠️ V60_MAX_CALLS={_mc!r} 不是整数，忽略")

    # "auto" 的两档：
    #   mode=auto + rounds=auto → 完整规划（route/mode/rounds/成本档/预算），
    #                            **在构造 MetaDGTF 之前**跑（成本档要那时才生效）
    #   只有 mode=auto          → 只定模式，圈数走配置（原行为）
    plan = None
    _plan_note = ""
    if str(rounds_s).strip().lower() == "auto":
        if mode == "auto":
            plan = mod.auto_plan(question, cfg)
            cfg["cost_profile"] = plan["cost_profile"]
            # ★ 强制预算优先于规划预算：规划给的预算总是高于实际消耗，
            #   一被覆盖就永远触发不到提前停，机制等于没验过。
            cfg["max_calls"] = _forced_calls if _forced_calls else plan["max_calls"]
            mode = plan["mode"]
            rounds = plan["rounds"] or 0
            # ★ 存下来，进下面的 buf —— 直接 print 的话落在 redirect
            # 之前，会被吞掉，子日志里看不到规划到底给了什么。
            _plan_note = (
                f"🧭 自动规划：route={plan['route']} mode={mode} "
                f"rounds={plan['rounds']} 成本档={plan['cost_profile']} "
                f"预算={cfg['max_calls'] or '不限'}"
                + (f"（规划给 {plan['max_calls']}，被 V60_MAX_CALLS 压到 "
                   f"{_forced_calls}）" if _forced_calls else "") + "\n"
                f"   理由：{plan['reason']}"
                f"（置信 {plan['confidence']:.2f}）")
        else:
            # ⚠️ 原来这里直接 `rounds = 0`，于是圈数**静默**落到配置
            #   hard_max（12）。踩过的坑：想做「同题不同 mode」对照时
            #   写 `_run_v60.py F auto ...`，mode 显式 → rounds 丢弃 →
            #   四层各 12 圈 → 185 calls，而对照组是 4 圈 159 calls。
            #   成本差是圈数造成的，却被记成了 mode 的差。
            #   圈数没指定就该问规划，跟 mode 指不指定无关。
            _p = mod.auto_plan(question, cfg)
            rounds = _p.get("rounds") or 0
            _plan_note = (f"🧭 mode={mode} 用户指定；圈数未指定，"
                          f"取自规划 {rounds}（不再静默落 hard_max）")
    else:
        try:
            rounds = int(rounds_s)
        except ValueError:
            rounds = rounds_s                # 允许 "0:4,both:6" 这种

    round_tag = str(rounds_s).replace(":", "-").replace(",", "_")
    log_path = HERE / f"v60_{tag}_r{round_tag}_{mode}.log"
    t0 = time.time()
    buf = io.StringIO()
    err = None
    meta = None
    try:
        _stream = os.environ.get("V60_STREAM") == "1"
        _ctx = (contextlib.redirect_stdout(_Tee(buf, sys.stdout))
                if _stream else contextlib.redirect_stdout(buf))
        with _ctx:
            if _plan_note:
                print(_plan_note)
            if _tk_note:
                print(_tk_note)
            meta = mod.MetaDGTF(cfg)
            res = meta.run(
                question, parallel_mode=mode, rounds=rounds,
                route=(_route_override
                       or (plan["route"] if plan else None)))
    except Exception as exc:                 # 真跑不该崩；崩了要留全
        import traceback
        err = traceback.format_exc()
        res = None

    dt = time.time() - t0
    log = buf.getvalue().replace("\r\n", "\n")
    tail = [f"\n{'='*60}",
            f"tag={tag} mode={mode} rounds={rounds_s}",
            # [fix-111] 每跑都必须答得出「实际用了哪些模型」。
            #   此前 124 跑全部答不出（配置写 A，实际服务 B），所谓复现
            #   一直是悬空的。见 §7.18②。
            f"served_by={sorted(meta.llm.SERVED_SEEN) if meta else '?'}",
            f"耗时 {dt:.0f}s = {dt/60:.1f}min"]
    if res is not None:
        tail += [
            f"llm_calls={res['llm_calls']} tokens={res['llm_tokens']}",
            f"dispatch.order={res['dispatch'].get('order')}",
            f"dispatch.ran={res['dispatch'].get('ran')}",
            f"dispatch.missing={res['dispatch'].get('missing')}",
            f"dispatch.skipped={res['dispatch'].get('skipped')}",
            f"decidability={ (res.get('decidability') or {}).get('decidability') }",
            f"dec_src={(res.get('decidability') or {}).get('_source')}",
            # [v1.21.61] 判据字段：分叉（池/外各是什么）+ 无追溯的不可判定条数。
            # 验收看这两个，不靠"某道题应该判成什么"。
            f"分叉={(res.get('decidability') or {}).get('_divergent')}"
            f"(池={(res.get('decidability') or {}).get('_pool_status')}"
            f"/外={(res.get('decidability') or {}).get('_ext_status')})",
            "无追溯="
            f"{len((res.get('decidability') or {}).get('_und_untraced') or [])}",
            f"views={sorted(res['views'])}",
            # [v1.21.63] 层贡献：{层: {rounds, stop, idle}}，分领域跑题时积累
            # 「哪层真有贡献、哪层空转」，为「通过数据按需调度」提供地基。
            f"layer_contribution={res.get('layer_contribution')}",
        ]
        # ★ 落盘失败**不能吞掉整份日志**：跑批里出现过
        #   `ValueError: I/O operation on closed file`（save_result 末尾那句
        #   print），一崩就整份日志都没写、只剩 runner 里被截断的三行堆栈，
        #   事后根本查不到在哪一层崩的。这里把异常收进 tail，日志照写。
        try:
            p = mod.save_result(res, str(HERE / "outputs"))
            tail.append(f"产物={p}")
        except Exception:
            import traceback as _tb
            # ★ [v1.21.63] 别急着报「落盘失败」——先查文件到底在不在。
            #   真跑 up_tech 时 save_result 抛了
            #   `OSError: [Errno 22] Invalid argument`，位置在**写完文件之后**
            #   那句 `print(f"📁 已保存: {md}")`。产物 md 其实已经躺在
            #   outputs/ 里，却被记成「落盘失败」，害得那一题判分缺一份。
            #   所以这里兜底找「本轮开始之后新写的 md」：找得到就记为已落盘，
            #   把 print 的报错降级成附注；找不到才是真的失败。
            _saved = [q for q in (HERE / "outputs").glob("*.md")
                      if q.stat().st_mtime >= t0 - 1]
            if _saved:
                _saved.sort(key=lambda q: q.stat().st_mtime, reverse=True)
                tail.append(f"产物={_saved[0]}")
                tail.append("⚠️ save_result 收尾提示语 print 失败"
                            "（文件已写入，非落盘失败）：\n"
                            + _tb.format_exc())
            else:
                tail.append("❌ 产物落盘失败（跑批本身已完成）：\n"
                            + _tb.format_exc())
    if err:
        tail.append("异常：\n" + err)
    tail.append("=" * 60)
    log = log + "\n".join(tail) + "\n"
    log_path.write_text(log, encoding="utf-8")
    print(f"[{tag}/{mode}] {'OK' if res else 'FAIL'}  "
          f"{dt/60:.1f}min  calls="
          f"{res['llm_calls'] if res else '-'}  → {log_path.name}")
    if res:
        print(f"   missing={res['dispatch'].get('missing')}  "
              f"skipped={res['dispatch'].get('skipped')}")
    return 0 if res else 1


if __name__ == "__main__":
    sys.exit(main())
