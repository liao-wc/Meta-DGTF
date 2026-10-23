# -*- coding: utf-8 -*-
"""
v1.21.75 变异测试：把新改的每一处**撤掉**，判据必须报错。

结构不变式在现版必然通过 —— "全绿"本身不构成证据。
这里造 7 个畸形体，每个对应一处修复，全被抓到才算判据有判别力。

★ 落盘用 tempfile.mkdtemp（固定目录会跨进程累积，实测把 4 个数成 12）。
"""
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.75.py"
TMP = Path(tempfile.mkdtemp(prefix="v75mut_"))

BASE = SRC.read_bytes().decode("utf-8").replace("\r\r\n", "\n")
BASE = BASE.replace("\r\n", "\n").replace("\r", "\n")

# (名字, 原文片段, 替换成) —— 每个都必须是**唯一命中**
MUTANTS = [
    ("M1 撤掉圈循环里的检索调用（锚点永远不入池）",
     "            self._anchor_round(entry, pool, r)\n",
     "            pass\n"),
    ("M2 to_dict 无条件挂 anchors（关闭态加性破了）",
     '        if self.anchors:\n            d["anchors"] = self.anchors\n',
     '        d["anchors"] = self.anchors\n'),
    ("M3 引用表去掉授权守卫（锚点白拿证据资格）",
     '    if getattr(pool, "anchor_as_evidence", False):\n'
     '        for _xi, _xa in enumerate(\n'
     '                (getattr(pool, "anchors", None) or [])[:12], 1):\n'
     '            out.append((f"X{_xi}", str(_xa.get("claim", ""))))\n',
     '    for _xi, _xa in enumerate(\n'
     '            (getattr(pool, "anchors", None) or [])[:12], 1):\n'
     '        out.append((f"X{_xi}", str(_xa.get("claim", ""))))\n'),
    ("M4 元层也检索（元层的活是清算，不是核对）",
     'if not cfg.get("enabled") or entry == "all" or not self._anchors:',
     'if not cfg.get("enabled") or not self._anchors:'),
    ("M5 未实现的检索后端静默降级（假装搜过）",
     '        if mode != "snapshot":\n'
     '            raise RuntimeError(\n'
     '                f"external_anchor.retriever={mode!r} 尚未实现"\n'
     '                f"（当前只有 \'snapshot\'）；不静默降级")\n',
     '        if mode != "snapshot":\n'
     '            return []\n'),
    ("M6 预算漏算锚点调用（v1.21.73/74 的原坑）",
     '        used = (int(getattr(self.llm, "total_calls", 0) or 0)\n'
     '                + int(getattr(self, "_anchor_calls", 0) or 0))\n'
     '        return used >= b\n',
     '        return int(getattr(self.llm, "total_calls", 0) or 0) >= b\n'),
    ("M7 关闭态也给池判塞锚点块（prompt 加性破了）",
     '        if not cfg.get("enabled"):\n'
     '            return ""\n'
     '        pool = (self.pools or {}).get("0")',
     '        pool = (self.pools or {}).get("0")'),
]


def load(path: Path):
    spec = importlib.util.spec_from_file_location(
        "mut_" + path.stem, str(path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def main() -> int:
    import smoke_test as st

    def verdict(ok: bool) -> str:
        return "绿(通过)" if ok else "红(报错)"

    # ---- 正对照：原版必须全绿
    print("=== 正对照：v1.21.75 原版 ===")
    st.SRC = SRC
    st.mod = load(SRC)
    base_ok = st.check_v75_anchor_pool()
    print(f"  原版 -> {verdict(base_ok)}\n")
    if not base_ok:
        print("✗ 正对照就不该报错，先修判据")
        return 1

    print("=== 变异体：每个都该被抓到 ===")
    caught = 0
    for name, old, new in MUTANTS:
        c = BASE.count(old)
        if c != 1:
            print(f"  ⚠ {name}：锚点命中 {c} 次（应为 1），跳过")
            continue
        p = TMP / f"mut_{abs(hash(name)) % 100000}.py"
        p.write_bytes(
            BASE.replace(old, new).replace("\n", "\r\n").encode("utf-8"))
        st.SRC = p
        st.mod = load(p)
        ok = st.check_v75_anchor_pool()
        tag = "✗ 漏了" if ok else "✓ 抓到"
        if not ok:
            caught += 1
        print(f"  {tag} | {name}")

    total = sum(1 for n, o, _ in MUTANTS if BASE.count(o) == 1)
    print(f"\n结果：{caught}/{total} 个畸形体被抓到")
    shutil.rmtree(TMP, ignore_errors=True)
    if caught < total:
        print("✗ 有判据是永真的 —— 它证明不了任何事")
        return 1
    print("✓ 判据有判别力")
    return 0


if __name__ == "__main__":
    sys.exit(main())
