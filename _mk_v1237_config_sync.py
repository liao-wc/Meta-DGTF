#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.7 配置文件同步：头部版本 + 【v1.23.6 → v1.23.7】升级段；验收 = load_config 差异 0。"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML = HERE / "dgtf_config.yaml"
BAK = HERE / "_bak_dgtf_config.pre_v1237"
SRC = HERE / "元DGTF-V1.23.7.py"

HEAD_OLD = "# 元 DGTF · v1.23.6 配置文件"
HEAD_NEW = "# 元 DGTF · v1.23.7 配置文件"
ANC = "# 【v1.23.5 → v1.23.6】代码正文不再留「版次批注」"

SEC = """# 【v1.23.6 → v1.23.7】changelog 搬出代码，落到 `CHANGELOG.md`
#   ★ **本版不改任何配置键、不改任何默认值** ⇒ 升级后行为**逐字不变**。
#   ① 模块 docstring 里的版本段（4954 行 / 占全文件 22.7%）**原样**搬进仓库根目录
#      `CHANGELOG.md`；代码里的 docstring 换成短版（标题 + 一句话 + 指向）。
#      ★ 标题必须留在前 4000 字符内 —— `_probe_v1232_audit.py` 的 C1
#        「docstring 标题版本 == __version__」按这个范围取。
#   ② 规模：21841 → **16894 行**（-4954）。
#   ③ 引擎自己**不读自己的 `__doc__`**（全文件仅 1 处 `__doc__`，且在注释里），
#      模块 docstring 不参与执行 ⇒ 硬断言：抠掉 docstring 后代码部分逐字相同 +
#      AST 严格等价。
#   ④ 判据随实现更新 2 处（是**位置变了**，不是放宽）：`check_v72_changelog_hygiene`
#      与 `check_v76_changelog_wording` 的取源从「源码/模块 docstring」改到
#      `CHANGELOG.md`；前者另抽纯函数 `_changelog_lint()` 并用**合成坏样本**做
#      负对照（旧负对照手法「把 SRC 指回旧版」在取源外移后失效）。
#   ⑤ 新增 `check_v1237_changelog_outside_code`（两向对账：代码里 0 处版本段，
#      且 `CHANGELOG.md` 段数 ≥ 10，防「搬出去」变成「删掉」）。
#   ★ 对你的影响：**无**。本文件无需改动（没有新键、没有改过的默认值）。

"""


def main():
    raw = YAML.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
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

    import importlib.util
    spec = importlib.util.spec_from_file_location("eng37", SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eng37"] = mod
    spec.loader.exec_module(mod)
    da = json.dumps(mod.load_config(str(BAK)), sort_keys=True, ensure_ascii=False)
    db = json.dumps(mod.load_config(str(YAML)), sort_keys=True, ensure_ascii=False)
    print("load_config 差异项 =", 0 if da == db else "★ 非 0")
    assert da == db, "★ 配置语义变了"
    print("load_config 前后逐字相同 ✓（%d 字符）" % len(da))
    miss = [k for k in mod.DEFAULT_CONFIG if k not in mod.load_config(str(YAML))]
    print("yaml 缺 DEFAULT_CONFIG 键 =", miss or "无")
    return 0


if __name__ == "__main__":
    sys.exit(main())
