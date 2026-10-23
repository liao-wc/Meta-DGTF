#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.6 配置文件同步：头部版本 + 【v1.23.5 → v1.23.6】升级段。

验收标准（本项目口径）：`load_config` 前后**逐字差异 0 项** —— 本版不加键、
不改默认值，所以必须严格相等。做法：改前先把 yaml 复制一份，
改后用新版引擎分别 `load_config` 旧/新 yaml，`json.dumps(sort_keys=True)` 对比。
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML = HERE / "dgtf_config.yaml"
BAK = HERE / "_bak_dgtf_config.pre_v1236"
SRC = HERE / "元DGTF-V1.23.6.py"

HEAD_OLD = "# 元 DGTF · v1.23.5 配置文件"
HEAD_NEW = "# 元 DGTF · v1.23.6 配置文件"
ANC = "# 【v1.23.4 → v1.23.5】清挂账：调度归一化收口 + 布尔兼容可观测化"

SEC = """# 【v1.23.5 → v1.23.6】代码正文不再留「版次批注」
#   ★ **本版不改任何配置键、不改任何默认值** ⇒ 升级后行为**逐字不变**。
#     改的是**主文件的注释与 docstring**：把散落在代码正文里的版次批注清掉
#     （378 个批注块 / 1476 行、9 处行尾批注、66 个函数 docstring 的前导版次
#     标记），变更记录统一由主文件顶部 docstring 的 changelog 承担。
#   ★ 对你的影响：**无** —— 阈值、常量、控制流、返回值一律未动。
#     可执行语句零改动有机器证明：删注释后 AST 严格等价；剥 docstring 前导标记后
#     只有那 66 处字符串常量变化、且每处都恰好等于「剥掉一个前导标记」。
#   ★ 被删内容**全文存档**：`docs/版次批注存档-v1.23.5.md`（3092 行，带行号与
#     最近的 def/class 归属），配 git 历史可完全复原。
#   ★ 判据随实现更新两处（是**判据过时**，不是放宽）：
#     · `check_v72_bbarrier_semantics` 原拿 `[v1.21.72 #13]` 当锚点 → 换成同一段
#       注释里的两条内容短语（`刻意的 barrier` + 既有的 `同时停掉所有层`）；
#     · 变异体 M3 的锚点原含两行注释 → 改成只锚代码行，变异意图一字未改。
#   ★ 升级后要做的：**无**。本文件无需改动（没有新键、没有改过的默认值）。

"""


def main():
    raw = YAML.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0, "yaml 不是纯 CRLF"
    t = raw.decode("utf-8").replace("\r\n", "\n")

    if HEAD_NEW in t:
        print("[skip] 已同步过")
        return 0

    n1 = t.count(HEAD_OLD)
    assert n1 == 1, "头部版本锚点命中 %d 次" % n1
    t = t.replace(HEAD_OLD, HEAD_NEW, 1)

    n2 = t.count(ANC)
    assert n2 == 1, "升级段锚点命中 %d 次" % n2
    t = t.replace(ANC, SEC + ANC, 1)

    if not BAK.exists():
        shutil.copy2(YAML, BAK)
        print("回滚点：%s" % BAK.name)
    out = t.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
    YAML.write_bytes(out)
    print("已写 yaml：头部版本 + 升级段")

    # ---- 验收：load_config 前后逐字差异 ----
    import importlib.util
    spec = importlib.util.spec_from_file_location("eng36", SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eng36"] = mod
    spec.loader.exec_module(mod)
    a = mod.load_config(str(BAK))
    b = mod.load_config(str(YAML))
    da = json.dumps(a, sort_keys=True, ensure_ascii=False)
    db = json.dumps(b, sort_keys=True, ensure_ascii=False)
    print("load_config 差异项 =", 0 if da == db else "★ 非 0")
    assert da == db, "★ 配置语义变了"
    print("load_config 前后逐字相同 ✓（%d 字符）" % len(da))
    # yaml 里 DEFAULT_CONFIG 的键是否列全
    miss = [k for k in mod.DEFAULT_CONFIG if k not in b]
    print("yaml 缺 DEFAULT_CONFIG 键 =", miss or "无")
    return 0


if __name__ == "__main__":
    sys.exit(main())
