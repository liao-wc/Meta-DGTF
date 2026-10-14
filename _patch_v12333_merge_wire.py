# 第六期补丁 P6-2：**激活阴阳合并**（L1 降本，接线孤儿函数）。
# ★ 背景：`_expand_pair_merged_once` 自 v1.23.16 删档后是**孤儿函数**
#   （能力存在但不可达 = 本项目第 1 类失败）。它一次调用拿两臂，
#   **省 1 次往返 + 1 份重复 user 输入 token**。
# ★ 依据：Tokonomics 2025 生产案例（叠加降本 85%，批处理是第一杠杆）+
#   信息瓶颈（重复输入是无信息 token，>5 个即降性能 15%+）。
# ★ 开关 `actions.merge_expand` **默认 false ⇒ 零行为差**（与既有一致）。
# ★ 兜底已在（缺分段标记则补跑另一臂），最坏退化 = 现状，不亏。
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

ANCHOR = '''        raws: Dict[str, Optional[str]] = {}
        parallel = (len(jobs) > 1
                    and _action_on(self.config, "parallel_expand"))
        if parallel:'''

NEW = '''        raws: Dict[str, Optional[str]] = {}
        # ★ [第六期 L1 · 降本] 阴阳合并成**一次**调用（opt-in，默认关）。
        #   依据：Tokonomics 2025（批处理是第一降本杠杆）+ 信息瓶颈
        #   （阴阳 user 完全相同 ⇒ 第二份是**无信息输入**）。
        #   ★ 开关默认 false ⇒ 与历史行为**逐字一致**（零行为差）。
        #   ★ 只合并恰好两臂的情形；单臂（另一开关关掉）走原路径。
        if len(jobs) == 2 and _action_on(self.config, "merge_expand", False):
            _mg = self._expand_pair_merged_once(jobs)
            if _mg is not None:
                return _mg
            # 合并失败 ⇒ 落回原路径（下方并行/串行），**不丢内容**。
            self.vp("   ↩ 合并展开不可用，回落两臂独立调用")
        parallel = (len(jobs) > 1
                    and _action_on(self.config, "parallel_expand"))
        if parallel:'''


def main():
    b = SRC.read_bytes()
    txt = b.decode("utf-8")
    if txt.count("\r\n") != txt.count("\n") or "\r\r\n" in txt:
        print("X 非纯 CRLF"); sys.exit(1)
    s = txt.replace("\r\n", "\n")
    n = s.count(ANCHOR)
    if n != 1:
        print("X 锚点命中 %d 次" % n); sys.exit(1)
    s = s.replace(ANCHOR, NEW, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    if out.decode("utf-8").count("\r\r\n"):
        print("X r-r-n"); sys.exit(1)
    SRC.write_bytes(out)
    print("OK 第六期补丁 P6-2 已打：阴阳合并接线（opt-in）")


if __name__ == "__main__":
    main()
