# -*- coding: utf-8 -*-
"""v1.23.49 冒烟补丁 2：堵「冒烟写生产记忆库」的两处泄漏。

背景（实测）：`dgtf_memory/` 的改动 **100% 来自冒烟**——
  · `check_cli()`：`-c smoke_config.yaml` 只写了 output/actions，`playbook.dir`
    回落出厂 `""` ⇒ 默认 `dgtf_memory/` ⇒ 每次冒烟塞一条
    「CLI 冒烟问题」episode + 抬真实条目证据/权重/bandit 计数。
  · `check_v12349_run_ckpt` ⑦ 端到端段：`load_config(dgtf_config.yaml)` 原样跑
    ⇒ 同样写生产记忆库，且 `save_dir=outputs` 往仓库丢 diagnostic_position 日志。

修法：两处都把**侧效应目录**重定向到临时目录（被测对象不变）。
CRLF 安全：read_bytes → 断言 → 替换 → write_bytes；跑完自检。
"""
from pathlib import Path

P = Path(__file__).resolve().parent / "smoke_test.py"
b = P.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF，先停"
assert b.count(b"\r\r\n") == 0, "已有 \\r\\r\\n 污染，先停"
t = b.decode("utf-8").replace("\r\n", "\n")

# ---------------- 补丁 A：check_cli() 记忆库目录隔离 ----------------
oldA = (
    '    cfg_path = HERE / "smoke_config.yaml"\n'
    '    cfg_path.write_text(\n'
    '        "output:\\n"\n'
    '        "  save_dir: smoke_outputs\\n"\n'
    '        "  verbose: false\\n"\n'
    '        "actions:\\n"\n'
    '        "  parallel_mode: B\\n",\n'
    '        encoding="utf-8")\n'
)
newA = (
    '    cfg_path = HERE / "smoke_config.yaml"\n'
    '    # \u2605 \u8bb0\u5fc6\u5e93\u76ee\u5f55\u5fc5\u987b\u9694\u79bb\uff1aCLI \u8d70 `-c` \u771f\u914d\u7f6e\u52a0\u8f7d\uff0c\u4e0d\u7ed9 `playbook.dir`\n'
    '    #   \u5c31\u56de\u843d\u51fa\u5382 `dgtf_memory/` \u21d2 **\u5192\u70df\u5199\u751f\u4ea7\u8bb0\u5fc6\u5e93**\uff08\u5b9e\u6d4b\uff1a\u6bcf\u6b21\u5192\u70df\u5f80\n'
    '    #   `episodes.jsonl` \u585e\u4e00\u6761\u300cCLI \u5192\u70df\u95ee\u9898\u300d\u3001\u5e76\u7ed9\u771f\u5b9e\u6761\u76ee\u62ac\u8bc1\u636e/\u6743\u91cd/\n'
    '    #   bandit \u8ba1\u6570 \u2014\u2014 \u6b63\u662f\u672c\u6587\u4ef6\u9876\u90e8\u300c\u7edd\u4e0d\u8bb8\u5199\u751f\u4ea7\u8bb0\u5fc6\u5e93\u300d\u70b9\u540d\n'
    '    #   \u7981\u6b62\u7684\u300c\u8ba9\u6d4b\u8bd5\u66ff\u751f\u4ea7\u5237\u7968\u300d\uff09\u3002\u6307\u5230\u4e34\u65f6\u76ee\u5f55\uff0c\u8dd1\u5b8c\u5373\u5f03\u3002\n'
    '    import tempfile as _tf_cli\n'
    '    _cli_mem = Path(_tf_cli.mkdtemp(prefix="dgtf_smoke_cli_mem"))\n'
    '    cfg_path.write_text(\n'
    '        "output:\\n"\n'
    '        "  save_dir: smoke_outputs\\n"\n'
    '        "  verbose: false\\n"\n'
    '        "actions:\\n"\n'
    '        "  parallel_mode: B\\n"\n'
    '        "playbook:\\n"\n'
    '        "  dir: \\"%s\\"\\n" % _cli_mem.as_posix(),\n'
    '        encoding="utf-8")\n'
)

# ---------------- 补丁 B：E2E 段侧效应隔离 ----------------
oldB = (
    '        _cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))\n'
    '        if not bool((_cfg.get("runtime") or {}).get("live_checkpoint", False)):\n'
    '            bad.append("[CK-\u7aef\u5230\u7aef] \u51fa\u5382 yaml \u7684 live_checkpoint \u7adf\u4e0d\u662f true")\n'
    '        mod.LLM.call = lambda system, user, *a, **k: (\n'
)
newB = (
    '        _cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))\n'
    '        if not bool((_cfg.get("runtime") or {}).get("live_checkpoint", False)):\n'
    '            bad.append("[CK-\u7aef\u5230\u7aef] \u51fa\u5382 yaml \u7684 live_checkpoint \u7adf\u4e0d\u662f true")\n'
    '        # \u2605 \u4fa7\u6548\u5e94\u9694\u79bb\uff1a\u51fa\u5382\u914d\u7f6e `playbook.dir=""`\uff08\u21d2 \u9ed8\u8ba4 dgtf_memory/\uff09\u3001\n'
    '        #   `output.save_dir="outputs"` \u2014\u2014 \u7167\u539f\u6837\u8dd1\u4f1a\u628a\u8fd9\u6b21\u5192\u70df\u5199\u8fdb**\u751f\u4ea7\n'
    '        #   \u8bb0\u5fc6\u5e93**\uff08episodes/nogoods/bandit/\u6743\u91cd\uff09\u5e76\u5f80\u4ed3\u5e93 outputs/ \u4e22\u8bca\u65ad\n'
    '        #   \u6587\u4ef6\uff08\u5b9e\u6d4b\u4e24\u6b21\uff1a13:47\u300113:59\uff09\u3002**\u88ab\u6d4b\u5bf9\u8c61\u662f `live_checkpoint`\n'
    '        #   \u51fa\u5382 true \u65f6\u5feb\u7167\u662f\u5426\u843d\u76d8\uff0c\u4e0d\u662f"\u5f80\u54ea\u513f\u5199"** \u21d2 \u53ea\u91cd\u5b9a\u5411\u8fd9\u4e24\u4e2a\n'
    '        #   \u76ee\u5f55\uff0clive_checkpoint \u4fdd\u6301\u51fa\u5382\u503c\u4e0d\u52a8\u3002\n'
    '        _cfg.setdefault("output", {})["save_dir"] = str(\n'
    '            Path(tempfile.mkdtemp(prefix="ckpt_e2e_out")))\n'
    '        _cfg.setdefault("playbook", {})["dir"] = str(\n'
    '            Path(tempfile.mkdtemp(prefix="ckpt_e2e_mem")))\n'
    '        mod.LLM.call = lambda system, user, *a, **k: (\n'
)

nA, nB = t.count(oldA), t.count(oldB)
print("锚点命中：A=%d B=%d" % (nA, nB))
assert nA == 1, "补丁 A 锚点不唯一/不存在"
assert nB == 1, "补丁 B 锚点不唯一/不存在"

t = t.replace(oldA, newA, 1).replace(oldB, newB, 1)

# 替换后校验
assert t.count("dgtf_smoke_cli_mem") == 1, "A 未生效"
assert t.count("ckpt_e2e_mem") == 1, "B 未生效"
assert t.count("ckpt_e2e_out") == 1, "B(output) 未生效"
assert '_orig_call = mod.LLM.call' in t, "差点覆盖上轮补丁"

out = t.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "写前自检失败"
P.write_bytes(out)

b2 = P.read_bytes()
assert b2.count(b"\r\n") == b2.count(b"\n"), "写后非纯 CRLF"
assert b2.count(b"\r\r\n") == 0, "写后 CRCRLF 污染"
print("OK：两处记忆库泄漏已隔离，纯 CRLF 保持。")
