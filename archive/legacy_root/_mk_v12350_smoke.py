# -*- coding: utf-8 -*-
"""v1.23.50 冒烟补丁：① SRC 指新版；② 新增 `check_v12350_resume`；③ main() 接线。

判据内容 = 开发期构造性验证（`_chk_v12350_dev.py`，14 条全过）压成冒烟一条：
  ① 快照含层 0 + 记账 + route 非空 + mode + 池（源码 token + 行为双查）；
  ② 续跑：**不重跑**已完成层、只跑缺层、层 0 产物**逐字复用**、池还原；
  ③ 负对照：题面不同 ⇒ 拒绝续跑；
  ④ 负对照：模式非 serial ⇒ 拒绝且给理由（+ serial 正对照）；
  ⑤ 墙钟预算 ⇒ 优雅停（`paused` + 待续层交代 + 快照状态可续）。

CRLF 安全。
"""
from pathlib import Path

P = Path(__file__).resolve().parent / "smoke_test.py"
b = P.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n") and b.count(b"\r\r\n") == 0
t = b.decode("utf-8").replace("\r\n", "\n")

JUDGE = '''def check_v12350_resume():
    """[v1.23.50] 断点续跑（复用已完成层）+ 快照记账 + route 死捕获 + 墙钟预算。

    \u2605 为什么必须有它：真实事故（今天两次 A/B 真跑被宿主回收）证明 \u2014\u2014 快照只
      \u300c留痕\u300d不能\u300c接着跑\u300d \u21d2 **烧掉的钱不可回收**。本判据做**构造性证明**：
      造一份\u300c层 0 已完成\u300d的快照 \u21d2 续跑必须 (a) 不重跑层 0、(b) 逐字复用其产物、
      (c) 还原其池（下游读上游池）、(d) 只跑缺的层。
    \u2605 负对照两条（判据要有牙）：题面不同 \u21d2 **拒绝续跑**；模式非 serial \u21d2 **拒绝**。
    \u2605 记账/route/预算同理：被杀跑次也要能**结算成本**；`route` 原本是死捕获（恒 `[]`）。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    for tok in ('resume_ckpt: str = ""', "max_minutes: float = 0.0",
                "def from_dict(cls, d: dict)", "def load_resume_snapshot(",
                "self._route = list(route)", "if entry in self._results:",
                '"llm_calls": int(getattr(_llm, "total_calls", 0) or 0),',
                '"pools": pools,',
                '"mode": str(getattr(engine, "_parallel_mode"'):
        if tok not in src:
            bad.append("[RS] \u6e90\u7801\u7f3a\uff1a%s" % tok)

    _ck = Path(_tf.mkdtemp(prefix="v50ck_"))
    _mem = Path(_tf.mkdtemp(prefix="v50mem_"))
    _orig_dir = mod.run_ckpt_dir
    _orig_layer = mod.MetaDGTF._run_layer
    mod.run_ckpt_dir = lambda base=None: _ck
    _ran = []

    def _spy(self, entry, n):
        _ran.append(entry)
        return _orig_layer(self, entry, n)

    def _cfg():
        c = build_cfg(False)
        c["output"]["save_dir"] = str(Path(_tf.mkdtemp(prefix="v50out_")))
        c["playbook"]["dir"] = str(_mem)
        c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_mem)
        c["runtime"] = dict(c.get("runtime") or {})
        c["runtime"]["live_checkpoint"] = True
        c["runtime"]["ckpt_interval"] = 0.05
        c["all_on"] = False
        return c

    _q = "\u5192\u70df\u9898\u9762\uff1a\u8fd9\u4ef6\u4e8b\u7684\u8fb9\u754c\u5728\u54ea\u91cc\uff08v12350 \u7eed\u8dd1\u5224\u636e\uff09"
    try:
        mod.MetaDGTF(_cfg()).run(_q, route=["0"], rounds={"0": 1},
                                 parallel_mode="serial", run_id="RS1")
        _p = _ck / "RS1.json"
        if not _p.is_file():
            bad.append("[RS] \u5f15\u64ce\u6ca1\u5199\u51fa\u5feb\u7167")
            raise RuntimeError("no snapshot")
        _s = json.loads(_p.read_text(encoding="utf-8"))
        if not isinstance((_s.get("views") or {}).get("0"), dict):
            bad.append("[RS] \u5feb\u7167\u91cc\u6ca1\u6709\u5c42 0 \u7684 view")
        if int(_s.get("llm_calls") or 0) <= 0 or int(_s.get("llm_tokens") or 0) <= 0:
            bad.append("[RS] \u5feb\u7167\u6ca1\u5e26\u8bb0\u8d26\uff1acalls=%r tokens=%r"
                       % (_s.get("llm_calls"), _s.get("llm_tokens")))
        if not _s.get("route"):
            bad.append("[RS] \u5feb\u7167 route \u4ecd\u662f\u7a7a\uff08\u6b7b\u6355\u83b7\u6ca1\u4fee\uff09")
        if _s.get("mode") != "serial":
            bad.append("[RS] \u5feb\u7167\u6ca1\u8bb0 mode\uff1a%r" % (_s.get("mode"),))
        if not ((_s.get("pools") or {}).get("0")):
            bad.append("[RS] \u5feb\u7167\u6ca1\u5e26\u6c60\uff08\u7eed\u8dd1\u8fd8\u539f\u4e0d\u4e86\u4e0a\u6e38\uff09")
        _s["status"] = "interrupted"
        _p.write_text(json.dumps(_s, ensure_ascii=False, indent=1), encoding="utf-8")

        mod.MetaDGTF._run_layer = _spy
        _m2 = mod.MetaDGTF(_cfg())
        _r2 = _m2.run(_q, route=["0", "1"], rounds={"0": 1, "1": 1},
                      parallel_mode="serial", run_id="RS2", resume_ckpt=str(_p))
        if "0" in _ran:
            bad.append("[RS] \u7eed\u8dd1**\u91cd\u8dd1\u4e86**\u5df2\u5b8c\u6210\u7684\u5c42 0\uff08\u767d\u70e7\u94f1\uff09\uff1a%r" % (_ran,))
        if "1" not in _ran:
            bad.append("[RS] \u7eed\u8dd1\u6ca1\u8dd1\u7f3a\u7684\u5c42 1\uff1a%r" % (_ran,))
        if json.dumps((_r2.get("views") or {}).get("0"), sort_keys=True,
                      ensure_ascii=False, default=str) != json.dumps(
                _s["views"]["0"], sort_keys=True, ensure_ascii=False,
                default=str):
            bad.append("[RS] \u5c42 0 \u7684\u4ea7\u7269\u4e0e\u5feb\u7167\u90a3\u4efd\u4e0d\u4e00\u81f4\uff08\u4e0d\u662f\u9010\u5b57\u590d\u7528\uff09")
        _p0 = _m2.pools.get("0")
        if len(getattr(_p0, "amps", []) or []) != len(
                ((_s.get("pools") or {}).get("0") or {}).get("amps") or []):
            bad.append("[RS] \u5c42 0 \u7684\u6c60\u6ca1\u8fd8\u539f\uff08\u4e0b\u6e38\u4f1a\u770b\u5230\u7a7a\u4e0a\u6e38\uff09")

        _ran.clear()
        mod.MetaDGTF(_cfg()).run("\u5b8c\u5168\u4e0d\u540c\u7684\u9898\u9762", route=["0"],
                                 rounds={"0": 1}, parallel_mode="serial",
                                 run_id="RS3", resume_ckpt=str(_p))
        if "0" not in _ran:
            bad.append("[RS-\u8d1f\u5bf9\u7167] \u9898\u9762\u4e0d\u540c\u7adf\u4e5f\u7eed\u8dd1\u4e86\uff08\u4f1a\u628a\u4e24\u8dd1\u6df7\u4e00\u8d77\uff09")

        _rs_b = mod.load_resume_snapshot(str(_p), question=_q, mode="B")
        if _rs_b.get("ok") or not _rs_b.get("why"):
            bad.append("[RS-\u8d1f\u5bf9\u7167] mode=B \u7adf\u5141\u8bb8\u7eed\u8dd1 / \u6ca1\u7ed9\u7406\u7531\uff1a%r" % (_rs_b,))
        if not mod.load_resume_snapshot(str(_p), question=_q,
                                        mode="serial").get("ok"):
            bad.append("[RS-\u6b63\u5bf9\u7167] serial + \u540c\u9898\u7adf\u4e0d\u5141\u8bb8\u7eed\u8dd1")

        _ran.clear()
        _r4 = mod.MetaDGTF(_cfg()).run(_q, route=["0", "1"],
                                       rounds={"0": 1, "1": 1},
                                       parallel_mode="serial", run_id="RS4",
                                       max_minutes=1e-6)
        if not _r4.get("paused") or _ran:
            bad.append("[RS] \u9884\u7b97\u5230\u70b9\u6ca1\u4f18\u96c5\u505c/\u4ecd\u8d77\u4e86\u5c42\uff1apaused=%r ran=%r"
                       % (_r4.get("paused"), _ran))
        if list(_r4.get("pending_layers") or []) != ["0", "1"]:
            bad.append("[RS] \u5f85\u7eed\u5c42\u6ca1\u4ea4\u4ee3\uff1a%r" % (_r4.get("pending_layers"),))
        _s4 = json.loads((_ck / "RS4.json").read_text(encoding="utf-8"))
        if _s4.get("status") != "paused":
            bad.append("[RS] \u4f18\u96c5\u505c\u7684\u5feb\u7167\u72b6\u6001\u4e0d\u662f paused\uff08\u4e0b\u6b21\u7eed\u4e0d\u4e86\uff09\uff1a%r"
                       % (_s4.get("status"),))
    except Exception as _e:  # noqa: BLE001
        bad.append("[RS] \u9a71\u52a8\u629b\u9519\uff1a%r" % (_e,))
    finally:
        mod.MetaDGTF._run_layer = _orig_layer
        mod.run_ckpt_dir = _orig_dir

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  \u2713 v1.23.50 \u65ad\u70b9\u7eed\u8dd1\uff08\u6784\u9020\u6027\uff1a\u5feb\u7167\u542b\u5c42 0 \u21d2 \u7eed\u8dd1**\u4e0d\u91cd\u8dd1**\u5df2\u5b8c\u6210\u5c42\u3001"
          "\u9010\u5b57\u590d\u7528 + \u6c60\u8fd8\u539f + \u53ea\u8dd1\u7f3a\u5c42\uff1b\u8d1f\u5bf9\u7167\uff1a\u9898\u9762\u4e0d\u540c/mode \u975e serial \u62d2\u7edd\uff1b"
          "\u8bb0\u8d26 + route \u6b7b\u6355\u83b7 + \u5899\u949f\u9884\u7b97\u4f18\u96c5\u505c paused\uff09\u5168\u8fc7")
    return True


'''

# ① SRC 指新版
old_src = 'SRC = HERE / "\u5143DGTF-V1.23.49.py"\n'
new_src = 'SRC = HERE / "\u5143DGTF-V1.23.50.py"\n'
assert t.count(old_src) == 1, "SRC 锚点不唯一"
t = t.replace(old_src, new_src, 1)

# ② 插判据（放在 check_v12349_run_ckpt 之后、check_v12348_eml_semantic 之前）
old_ins = 'def check_v12348_eml_semantic():\n'
assert t.count(old_ins) == 1, "插入点不唯一"
t = t.replace(old_ins, JUDGE + old_ins, 1)

# ③ main() 接线
old_call = ('    if not check_v12349_run_ckpt():\n'
            '        return 1\n')
new_call = ('    if not check_v12349_run_ckpt():\n'
            '        return 1\n'
            '    if not check_v12350_resume():\n'
            '        return 1\n')
assert t.count(old_call) == 1, "main 接线锚点不唯一"
t = t.replace(old_call, new_call, 1)

assert t.count("def check_v12350_resume():") == 1
assert t.count("if not check_v12350_resume():") == 1
out = t.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
P.write_bytes(out)
b2 = P.read_bytes()
assert b2.count(b"\r\n") == b2.count(b"\n") and b2.count(b"\r\r\n") == 0
print("OK：smoke 已指 v1.23.50 + 新判据接线（纯 CRLF 保持）")
