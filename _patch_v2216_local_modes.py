import py_compile
from pathlib import Path

E = Path("dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.16.py")
raw = E.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n"), "预期纯 CRLF"
et = raw.decode("utf-8")
et = et.replace("\r\n", "\n")

OLD = '''    if getattr(args, "dual_judge_mode", None):
        cfg.setdefault("output", {})["dual_judge_mode"] = args.dual_judge_mode
        print(f"   ✓ 双判档位：{args.dual_judge_mode}")
'''
NEW = OLD + '''
    # ★ [V2.2.16] 本地端点（api.base_url 指本机）⇒ 自省/双判「默认档 llm」自动切 local：
    #   "llm" 档在本地链路上会经 shim 把**自然语言 prompt** 发给 LoRA 适配器，
    #   而适配器的训练契约是结构化 payload（服务端只在 text 是 JSON 形状时才转），
    #   实测经 shim 的 dual_judge 74/74 条输出都不是 JSON（全在瞎编）。
    #   切 local 后引擎直连本地服务、按适配器契约发结构化 payload（带置信度门控，
    #   失败回退 llm 并留痕）。显式 CLI / 配置里非 "llm" 的值一律尊重。
    if _is_local_llm_endpoint(cfg):
        _oc = cfg.setdefault("output", {})
        for _k in ("self_check_mode", "dual_judge_mode"):
            if getattr(args, _k, None):
                continue          # 显式 CLI 优先
            if str(_oc.get(_k) or "llm").strip().lower() == "llm":
                _oc[_k] = "local"
                print("   ✓ 本地端点：%s 自动切 local（适配器契约直连；"
                      "可用 --%s llm 强制回旧档）"
                      % (_k, _k.replace("_", "-")))
'''
assert et.count(OLD) == 1, "锚点命中 %d 次" % et.count(OLD)
et = et.replace(OLD, NEW)

# docstring 补一句
OLD2 = ('    判据：tests_json_force.py（纯函数 + 接线 + 变异体）、test_graph_decode\n'
        '     G11/G12（显式 JSON 通道/首 token 约束）。\n')
NEW2 = ('    判据：tests_json_force.py（纯函数 + 接线 + 变异体）、test_graph_decode\n'
        '     G11/G12（显式 JSON 通道/首 token 约束）。\n'
        '     另：本地端点（base_url 指本机）时，output.self_check_mode /\n'
        '     output.dual_judge_mode 的**默认档 llm** 自动切 local —— 原来 llm 档\n'
        '     经 shim 把自然语言 prompt 发给 LoRA 适配器，契约不符（适配器要结构化\n'
        '     payload），实测 dual_judge 74/74 条输出都不是 JSON。显式 CLI / 配置\n'
        '     非 llm 值一律尊重（只动「还是默认 llm」的两项）。\n')
assert et.count(OLD2) == 1, "docstring 锚点命中 %d 次" % et.count(OLD2)
et = et.replace(OLD2, NEW2)

out = et.replace("\n", "\r\n").encode("utf-8")
E.write_bytes(out)
chk = E.read_bytes()
assert chk.count(b"\r\r\n") == 0
assert chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(E), doraise=True)
print("OK V2.2.16: 本地端点自省/双判自动 local 档")
