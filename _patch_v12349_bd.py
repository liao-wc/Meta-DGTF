# -*- coding: utf-8 -*-
"""v1.23.49 冒烟补丁 3：堵第三条记忆库泄漏 —— bandit.json。

根因（实测调用栈）：出厂 `dgtf_config.yaml` 有 `all_on: true`（本机真跑全开）
⇒ `_apply_all_on` 把 `auto.bandit.enabled` 置 True ⇒ E2E 的 `_m.run(...)`
走到 `_pack_result` 里的 `_save_bandit(self._bandit, self._bandit_cfg)`；
而 `_save_bandit` 的目录是 `cfg.get("dir") or eml_dir()` —— `_bandit_cfg` 来自
`config["auto"]["bandit"]`（无 dir）⇒ **恒指仓库 `dgtf_memory/`**，`playbook.dir`
隔离不到它（实测 n[0] 5→6）。

修法：E2E 段给 `auto.bandit.dir` 一个临时目录（`_save_bandit` 优先读 `cfg["dir"]`）。
★ 引擎侧「记忆库目录两处解析」不合并（属架构批）—— 挂账。
"""
from pathlib import Path

P = Path(__file__).resolve().parent / "smoke_test.py"
b = P.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF，先停"
assert b.count(b"\r\r\n") == 0, "已有 \\r\\r\\n 污染，先停"
t = b.decode("utf-8").replace("\r\n", "\n")

old = (
    '        _cfg.setdefault("output", {})["save_dir"] = str(\n'
    '            Path(tempfile.mkdtemp(prefix="ckpt_e2e_out")))\n'
    '        _cfg.setdefault("playbook", {})["dir"] = str(\n'
    '            Path(tempfile.mkdtemp(prefix="ckpt_e2e_mem")))\n'
)
new = (
    '        _cfg.setdefault("output", {})["save_dir"] = str(\n'
    '            Path(tempfile.mkdtemp(prefix="ckpt_e2e_out")))\n'
    '        _e2e_mem = str(Path(tempfile.mkdtemp(prefix="ckpt_e2e_mem")))\n'
    '        _cfg.setdefault("playbook", {})["dir"] = _e2e_mem\n'
    '        # \u2605 bandit \u7684\u76ee\u5f55\u89e3\u6790\u8d70 `eml_dir()`\uff08\u6052\u6307\u4ed3\u5e93 dgtf_memory\uff09\uff0c**\u4e0d\u5403**\n'
    '        #   `playbook.dir`\uff1b\u800c\u51fa\u5382 yaml \u7684 `all_on: true` \u4f1a\u628a `auto.bandit`\n'
    '        #   \u6253\u5f00 \u21d2 \u8fd9\u6b21\u8dd1\u4f1a\u5199\u751f\u4ea7 `dgtf_memory/bandit.json`\uff08\u5b9e\u6d4b\uff1an[0] 5\u21926\uff09\u3002\n'
    '        #   \u5c31\u5730\u7ed9\u5b83\u4e00\u4e2a `dir`\uff08`_save_bandit` \u4f18\u5148\u7ea7 `cfg["dir"] or eml_dir()`\uff09\u3002\n'
    '        _cfg.setdefault("auto", {}).setdefault("bandit", {})["dir"] = _e2e_mem\n'
)

n = t.count(old)
print("锚点命中：%d" % n)
assert n == 1, "锚点不唯一/不存在"
t = t.replace(old, new, 1)
assert t.count('["dir"] = _e2e_mem') == 2, "应有两处用 _e2e_mem"
assert 'auto", {}).setdefault("bandit"' in t

out = t.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "写前自检失败"
P.write_bytes(out)

b2 = P.read_bytes()
assert b2.count(b"\r\n") == b2.count(b"\n"), "写后非纯 CRLF"
assert b2.count(b"\r\r\n") == 0, "写后 CRCRLF 污染"
print("OK：bandit 目录已隔离，纯 CRLF 保持。")
