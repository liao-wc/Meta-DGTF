# -*- coding: utf-8 -*-
"""v1.23.12：配置文件同步（头部版本 + 升级段；无新键 ⇒ 行为逐字不变）。"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YML = HERE / "dgtf_config.yaml"
BAK = HERE / "_bak_dgtf_config.pre_v12312"
MAIN = HERE / "元DGTF-V1.23.12.py"

raw = YML.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
if not BAK.exists():
    BAK.write_bytes(raw)
    print("回滚点：", BAK.name)
s = raw.decode("utf-8").replace("\r\n", "\n")

OLD = "# 元 DGTF · v1.23.11 配置文件"
assert s.count(OLD) == 1, "头部版本命中 %d 次" % s.count(OLD)
s = s.replace(OLD, "# 元 DGTF · v1.23.12 配置文件", 1)

UP = """# 【v1.23.11 → v1.23.12】外部锚点拆成两条通道分别写明（文本 / 联网）
#   ★ **本版不改任何配置键、不改任何默认值** ⇒ 升级后行为**逐字不变**。
#   问题：旧产物只写一行「**外部锚点**：无」—— 而真跑里 `web_search`
#   **联网确实收了 6 条**（W1–W6，两个环节，零失败）。读者看到「无」
#   会以为本次没做任何外部校验。
#   做法：新增纯函数 `_web_lane_stats` / `_anchor_lane_lines`，在产物**四处**
#   （头部 / 显化说明 / decision 落地 / boundary 落地）分别写明：
#     · **外部锚点 · 文本**（锚点文件 `external_anchor`）：接了 N 条 / 对照结果
#     · **外部锚点 · 联网**（`web_search`）：**开/关** + 收 N 条（W#）/ 环节数 /
#       tier 分布 / 失败条数
#   两条通道**互相独立**，一条没有时也各自写明（不省略、不合并）。
#   另：旧的「本次未接入外部校验」留痕改为**仅在联网关时**出现
#   （原来只看锚点文件有没有）—— 联网开着却写「未接入」是口径错位。
#   ★ 对你的影响：**无**。本文件无需改动（没有新键、没有改过的默认值）。
#   ★ 判据：`check_v12312_anchor_lanes`（四处渲染点 + 开/关/未记录三态 +
#      失败与零条读数 + 负对照）+ 5 个变异体。
#
"""
ANCHOR = "# 【v1.23.10 → v1.23.11】把「如实记账」里剩下的两条做完"
assert s.count(ANCHOR) == 1, "升级段锚点命中 %d 次" % s.count(ANCHOR)
s = s.replace(ANCHOR, UP + ANCHOR, 1)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
YML.write_bytes(out)

spec = importlib.util.spec_from_file_location("cfgsync12", MAIN)
m = importlib.util.module_from_spec(spec)
sys.modules["cfgsync12"] = m
spec.loader.exec_module(m)
a, b = m.load_config(str(BAK)), m.load_config(str(YML))
ja = json.dumps(a, sort_keys=True, ensure_ascii=False)
jb = json.dumps(b, sort_keys=True, ensure_ascii=False)
print("load_config 键数：改前 %d / 改后 %d" % (len(a), len(b)))
print("load_config 逐字差异：", "0 项（行为逐字不变）" if ja == jb else "★ 有差异")
print("yaml 缺 DEFAULT_CONFIG 键：", [k for k in m.DEFAULT_CONFIG if k not in a] or "无")
print("头部版本行：", [l for l in
                      YML.read_bytes().decode("utf-8").split("\r\n")[:6]
                      if "配置文件" in l])
sys.exit(0 if ja == jb else 1)
