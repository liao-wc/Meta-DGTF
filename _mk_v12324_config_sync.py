#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.24 配置同步：头部版本 + 升级段；并证明「出厂配置语义逐字未变」。

★ 本版**无新增配置键、无默认值改动** ⇒ 验收 = 改前/改后 `load_config`
  逐字差异 ∅ + yaml 里 DEFAULT_CONFIG 的键仍然列全。
★ 幂等：marker 已在则跳过插入；可重复执行。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML = HERE / "dgtf_config.yaml"
BAK = HERE / "_bak_dgtf_config.pre_v12324.yaml"
TGT = HERE / "元DGTF-V1.23.24.py"

OLD_HEAD = "# 元 DGTF · v1.23.23 配置文件"
NEW_HEAD = "# 元 DGTF · v1.23.24 配置文件"
ANCHOR = "# 【v1.23.18 → v1.23.19】锚点「真检索」这条路够得到（修一条死路 + 一处过期前提）"

SECTION = """# 【v1.23.23 → v1.23.24】两个读数口径的「正名」+ 修行层停止判据与文案
#   ★ **无新增配置键、无默认值改动** ⇒ 本文件除本段与头部版本外一字未动。
#   一、结构覆盖率 → **独立度**（换的是口径，不只是改名）
#     · 旧读数 = 「被 structural_amps 命中的 und_aspects 条数 / und_aspects 条数」，
#       而喂模型的提示词明确要求 structural_amps「独立提炼、**不得直接复述**
#       und_aspects 的原话」⇒ 一个要求「别跟它一致」、一个用「跟它一致的比例」
#       打分，两侧方向相反 —— 实测 7 份产物里 6 份恒 0.00，且读者会当成不及格。
#     · 新读数 = 「structural_amps 里**不与任何 und_aspects 重合**（overlap < 0.3）
#       的条数 / structural_amps 条数」。分母是**结构条数**，越高越合规。
#       空池记 None（不可计算），**不印 0.00** 冒充读数。
#     · 旧键（`last_struct_coverage` / `struct_coverage_history` /
#       `last_struct_hit`）**一字未动** —— 历史 packed 与命中轨迹照旧解析；
#       渲染到只有旧键的 dict 时显式标「旧口径」，不丢信息也不误导。
#     · ★ 运行期可见变化：喂模型的 shape 那一行由「不可判定结构覆盖 X」改成
#       「不可判定独立度 X」。旧口径下值为 0.00 时该行**本来就不出现**
#       （`if value:` 门），所以这是一条**新增提示**，不是把旧提示换掉。
#   二、修行层停止判据与文案（去借词 / 补空括号 / 一律附体检）
#     · 条件 1 文案不再写「ing 连续 N 圈复述」——「ing」是**对撞层**的输入名，
#       修行/研究/元层没有这个输入。改成「{层名}层连续 N 圈复述」。
#       ★ 条件 1 **仍对四层生效**（v1.23.17 的设计不变，`check_v12317_stop_all_layers` 照旧）。
#     · 条件 3 新增 `stall_is_sat` 支路：sat 判「无新维度」时把 idle_stall 顶到
#       门槛上，而那一刻 `stall_why` 是空串 ⇒ 停因印成「…无推进（）」。
#       现在这一支印「连续 N 轮无新结构维度（结构饱和度判定，不是新增停滞）」。
#     · 修行层**任何**停止（自然停住 / 体力耗尽截断）都补「本轮显形 + 未生质量」，
#       不再只在截断时补 —— 让「停得合理」这件事可核。
#     · 红线表述由「修行层不追求收敛」改成「修行层本来就能停，要的是停得合理」。
#   【怎么退回旧行为】没有配置开关（改的是文案与口径）；退回 = 用 v1.23.23 主文件。

"""


def main():
    if not BAK.exists():
        BAK.write_bytes(YAML.read_bytes())
        print("已备份出厂 yaml → %s" % BAK.name)

    raw = YAML.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n"), "yaml 不是纯 CRLF"
    assert raw.count(b"\r\r\n") == 0, "yaml 含 CRCRLF"
    s = raw.decode("utf-8").replace("\r\n", "\n")

    changed = []
    if NEW_HEAD in s:
        print("· 头部版本已是 v1.23.24，跳过")
    else:
        assert s.count(OLD_HEAD) == 1, "头部版本行命中 %d" % s.count(OLD_HEAD)
        s = s.replace(OLD_HEAD, NEW_HEAD)
        changed.append("头部版本")

    if "【v1.23.23 → v1.23.24】" in s:
        print("· 升级段已存在，跳过")
    else:
        assert s.count(ANCHOR) == 1, "升级段锚点命中 %d" % s.count(ANCHOR)
        s = s.replace(ANCHOR, SECTION + ANCHOR)
        changed.append("升级段")

    # 幂等硬断言：本段标记恰好 1 次、头部恰好 1 次
    assert s.count("【v1.23.23 → v1.23.24】") == 1, "新升级段出现次数 != 1"
    assert s.count(NEW_HEAD) == 1
    assert s.count(OLD_HEAD) == 0

    out = s.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0, "产出含 CRCRLF"
    assert out.count(b"\n") == out.count(b"\r\n"), "产出不是纯 CRLF"
    assert out.count(b"\r") == out.count(b"\r\n"), "产出有游离 CR"
    YAML.write_bytes(out)
    assert YAML.read_bytes() == out, "回读不一致"
    print("yaml 已改：" + ("、".join(changed) if changed else "（无变化）"))

    # ---------- 验收：出厂配置语义逐字未变 ----------
    spec = importlib.util.spec_from_file_location("dgtf_cfgsync", str(TGT))
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_cfgsync"] = m
    spec.loader.exec_module(m)

    a = m.load_config(str(BAK))
    b = m.load_config(str(YAML))
    da, db = (json.dumps(a, sort_keys=True, ensure_ascii=False),
              json.dumps(b, sort_keys=True, ensure_ascii=False))
    if da != db:
        ja, jb = json.loads(da), json.loads(db)
        print("★ load_config 差异非空！")
        for k in sorted(set(ja) | set(jb)):
            if ja.get(k) != jb.get(k):
                print("  " + k)
        return 1
    print("✅ load_config(改前) == load_config(改后) —— 逐字差异 0 项")

    # 键列全（第三向）：yaml 覆盖 DEFAULT_CONFIG 的全部键
    def _flat(d, pre=""):
        out = {}
        for k, v in (d or {}).items():
            kk = pre + k
            if isinstance(v, dict):
                out.update(_flat(v, kk + "."))
            else:
                out[kk] = v
        return out

    fy = _flat(b)
    fd = _flat(m.DEFAULT_CONFIG)
    missing = sorted(k for k in fd if k not in fy)
    print("· DEFAULT_CONFIG 键 %d 个；yaml 未列出 %d 个" % (len(fd), len(missing)))
    if missing:
        for k in missing:
            print("   缺 " + k)
    return 0


if __name__ == "__main__":
    sys.exit(main())
