# -*- coding: utf-8 -*-
"""构造 B 段真跑用的**临时注入版**（跑完即删，不进交付物）。

原提示词的注入有两处硬错误，这里按它的**意图**（"主动注入一条必然
不合格的 deferral，强制触发留痕路径"）改成可用的形式：

  ✗ 原写法 1：在 `_valid_revisit` **函数体开头**加
      `if "ZZTEST_INVALID" in c: return False`
      —— 那时 `c` 还没赋值，直接 NameError。
      → 改：放在 `c = (cond or "").strip()` 之后。

  ✗ 原写法 2：只靠那个魔法子串。真实 LLM **永远不会**产出含
      "ZZTEST_INVALID" 的 revisit_condition，判据分支根本进不去。
      → 改：在 `update_deferrals` 里**真的塞一条**带该子串的 deferral。

  ✗ 原写法 3（第一跑实测撞上的）：`update_deferrals` 的第三参数是
      **圈号**，而 `_run_layer` 每圈新建 view、`return view` 只交出
      **最后一圈**那个 —— 所以按"只在第 1 圈注入"写，那条留痕会随第 1
      圈的 view 一起被丢掉，产物里什么都看不到。
      → 改：**每圈都注入**。
"""
import io
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.62.py"
DST = HERE / "_tmp_B_inject.py"

s = io.open(SRC, encoding="utf-8", newline="").read().replace("\r\n", "\n")


def rep(old, new, tag):
    global s
    n = s.count(old)
    assert n == 1, "%s：命中 %d 次（要求唯一）" % (tag, n)
    s = s.replace(old, new, 1)


# ---- 注入 1：_valid_revisit 拒绝魔法子串 ----
rep('''def _valid_revisit(cond: str) -> bool:
    """检查 revisit_condition 是否含**可观测锚点**。''',
    '''def _valid_revisit(cond: str) -> bool:
    """检查 revisit_condition 是否含**可观测锚点**。（B 段临时注入版）''',
    "注入1a 文档串")

rep('''    c = (cond or "").strip()
    if len(c) < 4:
        return False
    # 黑名单优先：纯空词一律拦''',
    '''    c = (cond or "").strip()
    # [临时注入 · B 段真跑用，跑完即删] 端到端留痕验证
    if "ZZTEST_INVALID" in c:
        return False
    if len(c) < 4:
        return False
    # 黑名单优先：纯空词一律拦''',
    "注入1b 判据分支")

# ---- 注入 2：每圈都塞一条必然不合格的 deferral ----
rep('''def update_deferrals(pool, view, layer: int, cfg: dict) -> dict:
    """研究层延迟债务更新 + refinement 记录。"""
    stats = {"new": 0, "confirmed": 0, "handled": 0,''',
    '''def update_deferrals(pool, view, layer: int, cfg: dict) -> dict:
    """研究层延迟债务更新 + refinement 记录。（B 段临时注入版）"""
    # [临时注入 · B 段真跑用，跑完即删] 端到端留痕验证：真塞一条
    #   revisit_condition 含 ZZTEST_INVALID 的 deferral，必然被
    #   _valid_revisit 判不合格 → 必须走到留痕分支。
    # ★ 每圈都注入，不只第 1 圈 —— 见本脚本顶部 写法 3。
    if not pool.sub_questions:
        pool.sub_questions.append(
            {"id": "_B_inject", "question": "B 段注入子问题",
             "status": "open", "decidability": "partial"})
    view.deferrals = list(view.deferrals or []) + [{
        "sub_id": pool.sub_questions[0].get("id"),
        # ★ 条件里带**圈号**：否则每圈注入的文本完全相同，跨圈合并时会被
        #   去重成 1 条，就验不出"跨圈累积"了。
        "revisit_condition": f"ZZTEST_INVALID（B 段注入：第 {layer} 圈，必然不合格）",
        "reason": "B 段注入：验 view.errors → 产物【失败记录】链路",
    }]
    stats = {"new": 0, "confirmed": 0, "handled": 0,''',
    "注入2 每圈注入")

io.open(DST, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n"))
chk = io.open(DST, encoding="utf-8", newline="").read()
assert chk.count("\r\n") == chk.count("\n"), "写回后不是纯 CRLF"
t = chk.replace("\r\n", "\n")
print("已生成 %s（%d 行，纯 CRLF）" % (DST.name, chk.count("\n")))
for tag in ('if "ZZTEST_INVALID" in c:', 'ZZTEST_INVALID（B 段注入'):
    print("  注入点 L%d  %s" % (t.index(tag) and t[:t.index(tag)].count("\n") + 1, tag))
print("  每圈注入守卫：", "if layer == 1:" not in t)
