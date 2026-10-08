# -*- coding: utf-8 -*-
"""
输入自检（`_check_input_sanity`）的**负对照**。

为什么必须有它：244 份真跑日志里 `❓ 输入自检` 一次都没打出来过，
packed 里也永远是 `issues: []`。但**这证明不了它没用** ——
同样解释得通的是「题面本来就干净」。两种解释靠现有数据分不开。

判据：
  · 喂明显有悬空符号的题面（源码 docstring 里记的真实事故：`P=PN`，
    PN 不是任何标准复杂度类）→ 必须报出 issue，否则检测器是摆设。
  · 喂干净题面 → 必须不报，否则是「逢反」。
"""
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.76.py"

DIRTY = [
    "分析 P=PN 对现代密码学的影响",           # PN 不是标准复杂度类（笔误）
    "用 QFT 算法优化我们的 ERP 库存模块可以吗",  # QFT 悬空（量子傅里叶？还是别的）
    "这个方案要满足 ISO-27001x 和 SOC2-Plus 两个认证",  # 两个都不是真标准号
]
CLEAN = [
    "现金流紧张的中小制造企业，上自动化产线还是维持人工加局部优化？怎么决策？",
    "社区医院人力有限，慢性病管理推远程监测还是加派人手上门随访？资源怎么配？",
]


def load_dotenv(p: Path) -> None:
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    load_dotenv(HERE / ".env")
    spec = importlib.util.spec_from_file_location("d75n", str(SRC))
    m = importlib.util.module_from_spec(spec)
    sys.modules["d75n"] = m
    spec.loader.exec_module(m)

    cfg = m.load_config(str(HERE / "dgtf_config.yaml"))
    mt = object.__new__(m.MetaDGTF)
    mt.config = cfg
    mt.llm = m.LLM(cfg)
    mt.vp = lambda *a, **k: None

    print("=== 负对照：喂**脏**题面（应该报出）===")
    hit = 0
    for q in DIRTY:
        r = mt._check_input_sanity(q)
        issues = (r or {}).get("issues") or []
        tag = "✓ 报出" if issues else "✗ 没报"
        if issues:
            hit += 1
        print(f"  {tag} | {q[:34]}")
        for it in issues:
            print(f"        · {it.get('term')} — {it.get('why')}")
        if not issues:
            print(f"        note: {(r or {}).get('note', '')[:70]}")

    print("\n=== 正对照：喂**干净**题面（不该乱报）===")
    false_alarm = 0
    for q in CLEAN:
        r = mt._check_input_sanity(q)
        issues = (r or {}).get("issues") or []
        if issues:
            false_alarm += 1
        print(f"  {'✗ 误报' if issues else '✓ 没报'} | {q[:34]}")
        for it in issues:
            print(f"        · {it.get('term')} — {it.get('why')}")

    print("\n=== 判定 ===")
    print(f"  脏题面报出 {hit}/{len(DIRTY)}，干净题面误报 {false_alarm}/{len(CLEAN)}")
    if hit == 0:
        print("  ✗ **检测器是摆设**：真有悬空符号都报不出来 —— "
              "「244 份零触发」不是题面干净，是它压根不工作。")
        print("    建议：砍掉，或重写判据（且重写后必须重跑这个负对照）。")
        return 1
    if false_alarm > 0:
        print("  ✗ 逢反：干净题面也报 —— 阈值太松，报了也没人信。")
        return 1
    print("  ✓ 检测器会判脏、也不会逢反 —— 「244 份零触发」应解释为"
          "「历史题面确实干净」，机制本身有效，保留。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
