# -*- coding: utf-8 -*-
"""[v1.23.3] 出厂 yaml 同步：头部版本 + 【v1.23.2 → v1.23.3】升级段。

本版**没有**新增/改动任何 `DEFAULT_CONFIG` 键（只加函数与判据）
⇒ 四件事里只要做前两件：头部版本、升级段。
并附机器证明：`load_config` 前后**逐字相同**。
"""
from pathlib import Path
import importlib.util
import json
import shutil
import sys

HERE = Path(__file__).resolve().parent
Y = HERE / "dgtf_config.yaml"
BAK = HERE / "_bak_dgtf_config.pre_v1233"
if not BAK.exists():
    shutil.copyfile(Y, BAK)
    print("  · 已备份 %s" % BAK.name)

b = Y.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "yaml 不是纯 CRLF"
s = b.decode("utf-8").replace("\r\n", "\n")

O = "# 元 DGTF · v1.23.2 配置文件"
assert s.count(O) == 1, "头部版本锚点 %d 次" % s.count(O)
s = s.replace(O, "# 元 DGTF · v1.23.3 配置文件")

SEC = """# 【v1.23.2 → v1.23.3】§十「仍未做 / 如实记账」五条全清
#   ★ **本版不改任何配置键**（只在引擎侧加函数与判据）⇒ 升级后行为不变。
#   ① 正交度：判据从「观测式采样」改成**受控实验**
#      （固定子问题 × W4 开/关 × 温度 0.0/0.7 × 证据反事实）。
#      ★ 原因：观侧口径**结构性不可判定** —— 子问题每跑重新拆解，
#        「组内变异」里混进了上游拆解的变异（实测同题两跑 agree13 = 0.0 vs 1.0）。
#   ② 思考分档：那 15 行「无收益」的结论由 `_ab_thinking_v1233.py` 的
#      录播式 A/B **实测**后写入本文件（见 `api.thinking.stages` 段注释）。
#   ③ tier 确认：`tier_confirmed` 由**真跑旁证**补上（空表 → 实填 + 应用）。
#   ⑤ triage 频度：`_run_v1233_triage.py` 专项批 + Wilson 区间 + 负对照。
#   ★ 引擎侧修掉一类静默 bug（**不改配置**）：模型返回的 id 未归一化
#     会**整票错位一格且无声**（`_normalize_judgment_ids`）；
#     子问题 id 改为本地重编号（`_canonical_sub_ids`）；三票 `voter`
#     记**真票号**（丢票时不再重编号）。
#
"""
O2 = "\n#\n#\n# 【v1.23.1 → v1.23.2】整体审计 + 遗留收尾\n"
assert s.count(O2) == 1, "升级段位置锚点 %d 次" % s.count(O2)
s = s.replace(O2, "\n#\n#\n" + SEC + "# 【v1.23.1 → v1.23.2】整体审计 + 遗留收尾\n")

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
Y.write_bytes(out)
print("  · yaml 头部 + 升级段已写")


def _load(path):
    spec = importlib.util.spec_from_file_location("m_cfg1233",
                                                  str(HERE / "元DGTF-V1.23.3.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["m_cfg1233"] = m
    spec.loader.exec_module(m)
    return m.load_config(str(path))


a = _load(BAK)
c = _load(Y)
sa = json.dumps(a, sort_keys=True, ensure_ascii=False)
sc = json.dumps(c, sort_keys=True, ensure_ascii=False)
print("  · load_config 前后逐字相同：%s" % (sa == sc))
if sa != sc:
    raise SystemExit("!! 配置解析结果变了 —— 本版不该改任何值")
print("[done] v1.23.3 yaml 同步完成（零键改动）")
