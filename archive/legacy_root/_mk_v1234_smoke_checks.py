# -*- coding: utf-8 -*-
"""[v1.23.4] 冒烟注入器扩展：SRC → v1.23.4，并加 1 档判据。

  · `check_v1234_runtime` —— 运行期三项总控（联网 / 思考 / 强度）：
      auto 恒等（== v1.23.3 行为） / 三项各自落键 / **思考关必须连 stages
      整表一起关** / 空输入(回车)=auto / 非法值不静默且不改任何键 /
      纯函数不改入参 / 强度在思考关时给提示 / 生效读数与摘要
      + **3 个变异体**（auto 当 on / 只改 default 不改 stages / effort 不校验）。

★ 注入的代码里**不用反斜杠**：换行一律 chr(10) 拼，断行用括号。
★ 必须排在 `_mk_v1233_smoke_checks.py` **之后**跑：那个脚本从
  `def check_v1233_vote_ids` 换到 MARK，会把 MARK 之前新加的东西抹掉。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "_mk_v1230_smoke_checks.py"
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

NEW_CHECK = '''def check_v1234_runtime(SRC=None):
    """[v1.23.4] 运行期三项总控（联网 / 思考 / 强度）。

    背景：这三项此前只能靠改 `dgtf_config.yaml` 再重跑；交互里问不到、
    命令行也传不了。本版给它们一个顶层 `runtime` 段 + 交互/CLI 两条入口。

    判据重点（都是「不做会静默出错」的地方）：
      · auto 必须**逐字恒等** —— 否则默认出厂就跑偏了；
      · **思考关必须连 stages 整表一起关** —— `LLM.call` 的优先级是
        「显式 > stage > default」，只改 default 会被 stage 表盖住，
        总开关就是一句空话；
      · 非法值**不静默**（不改任何键 + 有告警），空输入(回车)=auto；
      · 纯函数**不改入参**（否则交互第二轮选 auto 会读到第一轮的值）。
    """
    try:
        import json as _json
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)
        NL = chr(10)
        D = _json.loads(_json.dumps(m.DEFAULT_CONFIG))
        J = lambda o: _json.dumps(o, sort_keys=True, ensure_ascii=False)

        # ---- 1 接口齐全 ----
        for _n in ("_apply_runtime", "_runtime_snapshot",
                   "_runtime_summary_line", "_normalize_runtime_switch",
                   "_normalize_runtime_effort", "_runtime_thinking_on"):
            assert hasattr(m, _n), "缺 " + _n
        assert m._RUNTIME_SWITCHES == ("auto", "on", "off"), "开关集合"
        assert m._RUNTIME_EFFORTS == ("auto", "low", "high", "max"), (
            "强度集合应为 low/high/max（出厂 yaml 记录的实测集）")
        print("  ✓ v1.23.4 总控：6 个符号与两个取值集都对")

        # ---- 2 ★ auto 恒等：不覆盖任何既有键 ----
        c0, n0 = m._apply_runtime(D)
        assert J(c0) == J(D), "runtime 全 auto 竟然改了配置（不是恒等变换）"
        assert n0 == [], "auto 不该产生任何留痕行：" + repr(n0)
        c0b, _ = m._apply_runtime(D, {"web": "auto", "thinking": "auto",
                                      "effort": "auto"})
        assert J(c0b) == J(D), "显式 auto 也必须是恒等"
        print("  ✓ v1.23.4 总控：三项 auto = 配置逐字恒等（与 v1.23.3 同行为）")

        # ---- 3 联网总开关落键 ----
        cw, nw = m._apply_runtime(D, {"web": "on"})
        assert cw["web_search"]["enabled"] is True, "web=on 没开"
        assert any("联网" in x for x in nw), "web=on 没留痕"
        cw2, _ = m._apply_runtime(D, {"web": "off"})
        assert cw2["web_search"]["enabled"] is False, "web=off 没关"
        print("  ✓ v1.23.4 总控：联网 on/off 正确落到 web_search.enabled")

        # ---- 4 ★★ 思考总开关：default + 整张 stages 表 ----
        co, no = m._apply_runtime(D, {"thinking": "off"})
        _t = co["api"]["thinking"]
        assert _t["default"] == "disabled", "thinking=off 的 default 没改"
        _vals = set(_t["stages"].values())
        assert _vals == {"disabled"}, (
            "thinking=off 没有把 stages 整表关掉：剩余取值 " + repr(_vals))
        assert len(_t["stages"]) == len(D["api"]["thinking"]["stages"]), (
            "stages 的键数变了（应当只改值、不改键集）")
        cn, _ = m._apply_runtime(D, {"thinking": "on"})
        _t2 = cn["api"]["thinking"]
        assert _t2["default"] == "enabled", "thinking=on 的 default 没改"
        assert set(_t2["stages"].values()) == {"enabled"}, (
            "thinking=on 没有把 stages 整表打开")
        print("  ✓ v1.23.4 总控：思考 on/off 同时改写 default 与 stages 整表")

        # ---- 5 ★ 与 LLM 的真实解析联动（比只看配置键强一档）----
        #   ★ 这里**不设** process 级环境变量去凑一个假 key —— 冒烟是同进程
        #     跑几十条判据，改 `os.environ` 会污染后面所有环节（本项目
        #     「判据不能有跨条副作用」的纪律）。有 key 就真构造 LLM 核对，
        #     没有就退回「按 call 的优先级模拟解析」——两条路量的是同一件事。
        _L = None
        try:
            _L = m.LLM(co)
            assert str(_L.thinking_default).lower() == "disabled", (
                "LLM 真实解析：thinking=off 的 default 不对")
            assert not [k for k, v in _L.thinking_stages.items()
                        if str(v).lower() == "enabled"], (
                "LLM 真实解析：thinking=off 仍有环节开档")
        except Exception as _e:  # noqa: BLE001
            print("  · LLM 构造不可用（" + type(_e).__name__
                  + "），改用解析顺序模拟")

        def _resolve(cfg, stage=None):
            th = None
            if stage:
                th = ((cfg.get("api") or {}).get("thinking")
                      or {}).get("stages", {}).get(stage)
            if th is None:
                th = ((cfg.get("api") or {}).get("thinking")
                      or {}).get("default")
            return str(th or "").lower() == "enabled"

        assert _resolve(co, "auto_plan") is False, (
            "thinking=off 后 auto_plan（出厂为 enabled）仍然是 True")
        assert _resolve(co, "从未声明过的环节") is False, (
            "thinking=off 后未声明环节（掉 default）仍是 True")
        assert _resolve(cn, "decompose_koan") is True, (
            "thinking=on 后 decompose_koan（出厂为 disabled）仍是 False")
        print("  ✓ v1.23.4 总控：思考关/开后，**按 call 的优先级解析**结果正确")

        # ---- 6 强度落键 + 只在思考开启时有意义 ----
        ce, ne = m._apply_runtime(D, {"effort": "max"})
        assert ce["api"]["thinking"]["effort"] == "max", "effort 没落键"
        ce2, ne2 = m._apply_runtime(D, {"thinking": "off", "effort": "high"})
        assert any("不生效" in x for x in ne2), (
            "思考关时设了强度，却没有提示「不生效」")
        print("  ✓ v1.23.4 总控：强度落键，且思考关时明确提示「不生效」")

        # ---- 7 ★ 非法值不静默：不改任何键 + 有告警 ----
        for _k, _bad in (("web", "yes_please"), ("thinking", "maybe"),
                         ("effort", "mediun")):
            _cb, _nb = m._apply_runtime(D, {_k: _bad})
            assert J(_cb) == J(D), (
                "%s=%r 非法值竟然改了配置（静默回落）" % (_k, _bad))
            assert any("非法" in x for x in _nb), (
                "%s=%r 非法值没有告警" % (_k, _bad))
            # ★ 不变式：`runtime` 段里**永远是合法的归一值**（非法输入由
            #   `⚠️` 留痕报告，不落进配置）。这条是「记录可被下游直接消费」
            #   的前提 —— 也是我第一版把原始输入写回去时**当场判红**的那条。
            assert all(
                ((_cb.get("runtime") or {}).get(_kk)
                 in (m._RUNTIME_EFFORTS if _kk == "effort"
                     else m._RUNTIME_SWITCHES))
                for _kk in ("web", "thinking", "effort")), (
                "runtime 段被写入集合外的值：" + repr(_cb.get("runtime")))
        print("  ✓ v1.23.4 总控：三个非法值都被拒 + 告警，配置一字未改"
              "（且 runtime 段三值恒合法）")

        # ---- 8 ★ 空输入（回车）= auto：交互提示写的就是「回车=auto」 ----
        for _v in ("", None, "  "):
            assert m._normalize_runtime_switch(_v) == "auto", (
                "开关空输入应为 auto：%r" % (_v,))
            assert m._normalize_runtime_effort(_v) == "auto", (
                "强度空输入应为 auto：%r" % (_v,))
        assert m._normalize_runtime_switch("y") == "on"
        assert m._normalize_runtime_switch("关") == "off"
        assert m._normalize_runtime_effort("MAX") == "max"
        assert m._normalize_runtime_effort("medium") is None, (
            "medium 不在实测取值集里，必须被拒（不能悄悄发出去）")
        print("  ✓ v1.23.4 总控：空输入/别名归一正确，集合外的值被拒")

        # ---- 9 ★ 纯函数：不改入参 ----
        _before = J(D)
        m._apply_runtime(D, {"web": "on", "thinking": "on", "effort": "max"})
        assert J(D) == _before, (
            "`_apply_runtime` 改了入参 —— 交互第二轮选 auto 会读到第一轮的值")
        print("  ✓ v1.23.4 总控：纯函数，入参配置一字未改")

        # ---- 10 生效读数与摘要 ----
        cs, _ = m._apply_runtime(D, {"web": "on", "effort": "high"})
        _snap = m._runtime_snapshot(cs)
        assert _snap["web_enabled"] is True, "snapshot.web_enabled 不对"
        assert _snap["effort"] == "high", "snapshot.effort 不对"
        assert isinstance(_snap["thinking_stages_enabled"], list), (
            "snapshot 必须报出开档环节清单")
        _line = m._runtime_summary_line(cs)
        assert ("联网" in _line) and ("思考" in _line) and ("强度" in _line), (
            "摘要行缺字段：" + _line)
        assert _snap["requested"] == {"web": "on", "thinking": "auto",
                                      "effort": "high"}, (
            "snapshot.requested 必须回显本次请求（而不是 yaml 的值）："
            + repr(_snap["requested"]))
        print("  ✓ v1.23.4 总控：生效读数 + 一行摘要都可读")

        # ---- 10b ★ `requested` 必须回显**本次真正请求的**三项 ----
        #   ★ 这条是「产物可复盘」的关键：`_apply_runtime` 会把请求值写回
        #     副本的 `runtime` 段。不这么做的话产物里的 `requested` 永远是
        #     yaml 的值 —— 命令行/交互给的三项在产物里**看不到**。
        assert _snap["requested"] == {"web": "on", "thinking": "auto",
                                      "effort": "high"}, (
            "snapshot.requested 必须回显本次请求（而不是 yaml 的值）："
            + repr(_snap["requested"]))
        _sn0 = m._runtime_snapshot(c0)
        assert _sn0["requested"] == dict(D.get("runtime") or {}), (
            "全 auto 时 requested 应与出厂 runtime 段逐字相同（恒等）")
        print("  ✓ v1.23.4 总控：`requested` 回显请求值（全 auto 时仍恒等）")

        # ---- 11 ★ load_config 外层套对了（四个出口都过它）----
        _dr = _P(_tf.mkdtemp())
        _y1 = _dr / "rt.yaml"
        _y1.write_bytes(("runtime:" + NL + "  web: off" + NL
                         + "  thinking: off" + NL + "  effort: max"
                         + NL).encode("utf-8"))
        _lc = m.load_config(str(_y1))
        assert _lc["web_search"]["enabled"] is False, "yaml 的 runtime.web 没生效"
        assert _lc["api"]["thinking"]["default"] == "disabled", "yaml 没关思考"
        assert _lc["api"]["thinking"]["effort"] == "max", "yaml 没设强度"
        # 缺路径 / 空路径 / 坏 yaml 三个出口也必须不炸（且仍恒等）
        assert J(m.load_config(str(_dr / "no_such.yaml"))) == J(D), "缺路径出口变了"
        assert J(m.load_config("")) == J(D), "空路径出口变了"
        _y2 = _dr / "bad.yaml"
        _y2.write_bytes(b"a: [1, 2" + bytes([10]))
        assert isinstance(m.load_config(str(_y2)), dict), "坏 yaml 出口炸了"
        print("  ✓ v1.23.4 总控：load_config 四个出口都过总控且不炸")

        # ---- 12 ★ CLI 三个开关真的接上了 ----
        for _flag, _opt in (("--web", "--web {auto,on,off}"),
                            ("--thinking", "--thinking {auto,on,off}"),
                            ("--effort", "--effort {auto,low,high,max}")):
            assert _flag in src, "CLI 缺 " + _flag
        assert "choices=list(_RUNTIME_SWITCHES)" in src, "CLI 开关没收紧取值"
        assert "choices=list(_RUNTIME_EFFORTS)" in src, "CLI 强度没收紧取值"
        assert "cfg, _rt_notes = _apply_runtime(cfg, {" in src, (
            "CLI 没有把三个开关应用下去")
        # 交互侧
        assert "def _ask_runtime(cfg):" in src, "缺 _ask_runtime"
        assert "runtime = _ask_runtime(" in src, "_ask_runtime 没被调用"
        assert ("(route_str, rounds_str, channels_str, parallel_str,"
                + NL + "         runtime) = cfg_result") in src, (
            "_ask_config 的返回值没扩成 5 元组 / 没解包")
        assert "run_cfg, _rt_notes = _apply_runtime(cfg, runtime)" in src, (
            "交互没有在**深拷副本**上应用（会污染跨轮的 cfg）")
        assert "meta = MetaDGTF(run_cfg)" in src, "交互还在用未应用的 cfg"
        print("  ✓ v1.23.4 总控：CLI 三开关 + 交互询问 + 深拷副本都已接线")

        # ---- 13 ★ 产物留痕 ----
        assert '"_runtime": _runtime_snapshot(self.config)' in src, (
            "产物没有 `_runtime` 生效读数（「这跑到底联网没有」又成黑箱）")
        print("  ✓ v1.23.4 总控：产物带 `_runtime` 生效读数")

        # ================= 变异体 =================
        _td = _P(_tf.mkdtemp())

        def _mut(name, old, new):
            assert src.count(old) == 1, (
                "变异体 " + name + " 锚点命中 " + str(src.count(old)) + " 次")
            _p = _td / ("mut_rt_" + name + ".py")
            _p.write_bytes(src.replace(old, new).replace(
                NL, chr(13) + NL).encode("utf-8"))
            return _v1221_mod(_p)

        # M1 ★ 把 auto 当成 on ⇒ auto 恒等判据必须判红
        _M1 = _mut("auto_as_on",
                   '"": "auto", "a": "auto", "auto": "auto",',
                   '"": "auto", "a": "auto", "auto": "on",')
        _c1, _n1 = _M1._apply_runtime(_json.loads(_json.dumps(
            _M1.DEFAULT_CONFIG)))
        assert J(_c1) != J(_M1.DEFAULT_CONFIG), (
            "变异体 M1『auto 当 on』没被判红（auto 恒等判据失效）")
        print("  ✓ v1.23.4 变异体 M1：把 auto 当 on ⇒ auto 恒等判据判红")

        # M2 ★ 思考总开关只改 default、不碰 stages ⇒ 必须判红
        #   ★ 内含双引号的锚点一律用 `chr(34)` 拼：这段代码本身是包在
        #     三引号单引号字符串里的，写反斜杠加引号会被**吃掉一层反斜杠**
        #     ⇒ 生成出来的 smoke 里引号裸奔 ⇒ 整个文件 SyntaxError。
        #     （本轮实踩；v1.23.3 的注入器同样用 chr(34) 绕开。）
        #   ★ 也别在本字符串里写「三个单引号」本身 —— 那会**提前闭合**外层。
        _Q = chr(34)
        _old2 = NL.join([
            "        _stages = _thc.get(" + _Q + "stages" + _Q + ") or {}",
            "        for _k in list(_stages):",
            "            _stages[_k] = _val",
            "        _thc[" + _Q + "stages" + _Q + "] = _stages",
        ])
        _M2 = _mut("default_only", _old2,
                   "        _stages = _thc.get(" + _Q + "stages" + _Q
                   + ") or {}")
        _c2, _ = _M2._apply_runtime(_json.loads(_json.dumps(
            _M2.DEFAULT_CONFIG)), {"thinking": "off"})
        _v2 = set(_c2["api"]["thinking"]["stages"].values())
        assert _v2 != {"disabled"}, (
            "变异体 M2『只改 default』没被判红（总开关成了空话却测不出来）")
        print("  ✓ v1.23.4 变异体 M2：只改 default 不改 stages ⇒ 判红")

        # M3 ★ effort 不做集合校验 ⇒ 非法值静默通过 ⇒ 必须判红
        _M3 = _mut("effort_nocheck",
                   "    return v if v in _RUNTIME_EFFORTS else None",
                   "    return v if v else None")
        assert _M3._normalize_runtime_effort("mediun") is not None, (
            "变异体 M3『effort 不校验』没被判红")
        _c3, _n3 = _M3._apply_runtime(_json.loads(_json.dumps(
            _M3.DEFAULT_CONFIG)), {"effort": "mediun"})
        assert J(_c3) != J(_M3.DEFAULT_CONFIG), (
            "变异体 M3 下非法值竟然改了配置却没被拦住")
        print("  ✓ v1.23.4 变异体 M3：effort 不校验 ⇒ 非法值静默通过，判红")

        # M4 ★ 抠掉「把请求值写回副本」⇒ 产物 requested 只剩 yaml 的值
        _M4 = _mut("no_request_echo", "    cfg[" + _Q + "runtime"
                   + _Q + "] = _rec", "    pass")
        _c4, _ = _M4._apply_runtime(_json.loads(_json.dumps(
            _M4.DEFAULT_CONFIG)), {"web": "on", "thinking": "off",
                                   "effort": "high"})
        _r4 = _M4._runtime_snapshot(_c4)["requested"]
        assert _r4 != {"web": "on", "thinking": "off", "effort": "high"}, (
            "变异体 M4『不写回请求值』没被判红")
        print("  ✓ v1.23.4 变异体 M4：不写回请求值 ⇒ requested 只剩 yaml，判红")

        return True
    except Exception as e:
        print("  ✗ v1.23.4 运行期总控失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False


'''

_HEAD = "def check_v1234_runtime"

# ★ 注入前先自证「注入的代码本身是合法 Python」：三层字符串最容易吃掉一层
#   转义（本轮 M2 的锚点就被吃掉反斜杠 ⇒ 生成出来的 smoke 整个 SyntaxError）。
#   这条自检 0 成本，却能把「改完才发现生成物坏了」变成「当场拦下」。
import ast as _ast_check  # noqa: E402
_ast_check.parse(NEW_CHECK)
print("  · 注入代码自检：语法 OK")

if _HEAD in s:
    _i, _j = s.index(_HEAD), s.rindex("# <<<end v123 checks>>>")
    s = s[: _i] + NEW_CHECK + s[_j:]
    print("  · CHECKS 里的 v1234 档已**就地更新**")
else:
    # ★ 不要拿「固定的尾巴字面量」当锚：每一档注入器在自己那段的末尾留的
    #   空行数都不一样（v1.23.3 留了两个 ⇒ 带一个空行的锚点命中 **0** 次，
    #   本轮实踩）。正解是**直接定位 MARK** —— `rindex` 取**最后一个**
    #   （MARK 在本文件里出现两次：变量定义 + 字面量内，用 index 会取反）。
    #   插进去多几个空行无害（Python 不介意函数之间的空行数）。
    _j = s.rindex("# <<<end v123 checks>>>")
    s = s[: _j] + NEW_CHECK + s[_j:]
    print("  · CHECKS 已加 check_v1234_runtime（按 MARK 定位）")

_NEW = 'NEW_SRC_NAME = "元DGTF-V1.23.4.py"'
if _NEW in s:
    print("  · SRC 已是 v1.23.4，跳过")
else:
    O2 = 'NEW_SRC_NAME = "元DGTF-V1.23.3.py"'
    assert s.count(O2) == 1, "SRC 锚点命中 %d 次" % s.count(O2)
    s = s.replace(O2, _NEW)
    print("  · SRC -> v1.23.4")

O3 = ('               "    if not check_v1233_vote_ids():\\n'
      '        return 1\\n")')
if "if not check_v1234_runtime()" in s:
    print("  · 守卫已含 runtime，跳过")
else:
    assert s.count(O3) == 1, "守卫块锚点 %d 次" % s.count(O3)
    s = s.replace(O3,
                  '               "    if not check_v1233_vote_ids():\\n'
                  '        return 1\\n"\n'
                  '               "    if not check_v1234_runtime():\\n'
                  '        return 1\\n")')
    print("  · 守卫块 +check_v1234_runtime")

P.write_bytes(s.encode("utf-8"))
import ast  # noqa: E402
ast.parse(s)
print("[done] v1.23.4 冒烟注入器已扩展")
