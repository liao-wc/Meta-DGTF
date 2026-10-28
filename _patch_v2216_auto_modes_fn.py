import py_compile
from pathlib import Path

E = Path("dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.16.py")
raw = E.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n")
et = raw.decode("utf-8").replace("\r\n", "\n")

# 1) 纯函数：插在 _is_local_llm_endpoint 之后
ANCHOR = '''def auto_dispatch(question: str, config=None, explicit=None,
                  save_dir=None, history=None) -> dict:'''
FN = '''def _auto_local_modes(cfg, explicit=()) -> List[str]:
    """本地端点 ⇒ 自省/双判「默认档 llm」自动切 local；返回被切的键列表（纯函数）。

    ★ 为什么要有这条自动切档（V2.2.16，实测）：
      默认档 "llm" 在本地链路上会经 shim 把**自然语言 prompt** 发给 LoRA 适配器，
      而适配器训练契约是结构化 payload（服务端只在 text 是 JSON 形状时才转）。
      实测经 shim 的 dual_judge 74/74 条输出都不是 JSON ⇒ 判定全丢、还占墙钟。
      切 local 后引擎直连本地服务、按契约发结构化 payload（带置信度门控 + 回退）。
    ★ 只动「仍是默认 llm」的两项：显式 CLI（explicit）/ 配置里的非 llm 值一律尊重。
    ★ 云端端点返回空表（不做任何改动）——这条自动档只服务本地链路。
    """
    if not _is_local_llm_endpoint(cfg):
        return []
    oc = (cfg or {}).get("output")
    if not isinstance(oc, dict):
        return []
    changed: List[str] = []
    for _k in ("self_check_mode", "dual_judge_mode"):
        if _k in set(explicit or ()):
            continue
        if str(oc.get(_k) or "llm").strip().lower() == "llm":
            oc[_k] = "local"
            changed.append(_k)
    return changed


'''
assert et.count(ANCHOR) == 1, "auto_dispatch 锚点命中 %d" % et.count(ANCHOR)
et = et.replace(ANCHOR, FN + ANCHOR)

# 2) main：把内联块换成调用纯函数
OLD = '''    if _is_local_llm_endpoint(cfg):
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
NEW = '''    # ★ [V2.2.16] 本地端点自动切档（纯函数 _auto_local_modes，可单测）：
    #   只动「仍是默认 llm」的两项，显式 CLI / 配置非 llm 值一律尊重。
    if _is_local_llm_endpoint(cfg):
        _explicit_modes = tuple(
            _k for _k in ("self_check_mode", "dual_judge_mode")
            if getattr(args, _k, None))
        for _k in _auto_local_modes(cfg, _explicit_modes):
            print("   ✓ 本地端点：%s 自动切 local（适配器契约直连；"
                  "可用 --%s llm 强制回旧档）"
                  % (_k, _k.replace("_", "-")))
'''
assert et.count(OLD) == 1, "main 内联块锚点命中 %d" % et.count(OLD)
et = et.replace(OLD, NEW)

out = et.replace("\n", "\r\n").encode("utf-8")
E.write_bytes(out)
chk = E.read_bytes()
assert chk.count(b"\r\r\n") == 0
assert chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(E), doraise=True)
print("OK V2.2.16: _auto_local_modes 纯函数 + main 接线")
