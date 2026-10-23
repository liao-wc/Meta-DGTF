# -*- coding: utf-8 -*-
"""v1.23.28 补丁：`dgtf_config.yaml` 同步新增键 `belief.sem_entropy_thr`。

冒烟套件的「配置两向对账」判据抓到：DEFAULT_CONFIG 有、yaml 没有 ⇒ 判红。
这正是那条判据该干的事（v1.23.27 就吃过「yaml 记了引擎不认识的键」的亏）。
"""
SRC = "dgtf_config.yaml"


def _load(path=SRC):
    b = open(path, "rb").read()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n") - crlf
    assert crlf > 0, "yaml 必须是 CRLF"
    assert lf == 0, "yaml 混入裸 LF %d 处" % lf
    assert b.count(b"\r\r\n") == 0, "已存在 \\r\\r\\n"
    return b.decode("utf-8").replace("\r\n", "\n"), crlf, lf


def _save(txt, path=SRC):
    out = txt.replace("\r\n", "\n").replace("\n", "\r\n")
    data = out.encode("utf-8")
    assert data.count(b"\r\r\n") == 0, "写出前 \\r\\r\\n 非 0"
    open(path, "wb").write(data)


def patch(txt, name, old, new, count=1):
    n = txt.count(old)
    assert n == count, "[%s] 锚点命中 %d 次（期望 %d）" % (name, n, count)
    return txt.replace(old, new)


def main():
    txt, crlf0, lf0 = _load()
    print("[in] CRLF=%d LF=%d" % (crlf0, lf0))

    # ── ① belief 段新增键（跟在 revoke_sources 后）──
    txt = patch(
        txt, "y1-key",
        '''  revoke_sources: 2


# ------------------------------------------------------------
# 三通道记忆参数
''',
        '''  revoke_sources: 2

  # 【用途】D3 语义熵的**聚类阈值**：判定「两种说法是不是同一主张」的
  #         相似度门槛（`_sim3` 口径）。
  # 【来源】v1.23.28 新增（`_SEM_CLUSTER_THR`）。
  #   ★ 为什么**必须独立于 `sim.cluster`（0.70）**：那个键是 **E2 探针
  #     批选**的口径（把「同一个探针」聚起来），与本键不是同一件事。
  #     `_sim3` 在中文上走**字符二元组 Jaccard** ⇒ 实测同一主张换个说法
  #     只有 0.41~0.79、不同主张 0.00。沿用 0.70 的后果是**簇恒为单元素**
  #     ⇒ 语义熵恒 `None`（真跑 + 直测共同证实的退化）。
  # 【建议】
  #   默认 0.30（实测「同主张 0.41~0.79 / 不同主张 0.00」两组的空隙内，
  #   长句重述上偏保守：宁可少聚，不把不同主张混进同一簇）。
  #   ⚠️ 调高到 0.70 ⇒ 语义熵退化成恒 `None`（= 观测失效，不是「更严」）。
  sem_entropy_thr: 0.30


# ------------------------------------------------------------
# 三通道记忆参数
''',
    )

    # ── ② 升级说明段：新增「五、」小节 + 改「新增 1 个键」为 2 个 ──
    txt = patch(
        txt, "y2-count",
        '''#   ★ 本版**新增 1 个配置键**（`belief.revoke_sources`），默认值 = 引擎常量
#     ⇒ **不改这个键时行为与 v1.23.28 的引擎默认一致**。''',
        '''#   ★ 本版**新增 2 个配置键**（`belief.revoke_sources` / `belief.sem_entropy_thr`），
#     默认值 = 引擎常量 ⇒ **不改这些键时行为与引擎默认一致**。''',
    )

    txt = patch(
        txt, "y3-section",
        '''#   【怎么退回旧行为】用 v1.23.27 主文件（本版改的是接线与一个默认值，无
#     整体回退开关；若要单独把 `revoked` 退回旧口径，把
#     `belief.revoke_sources` 设为 1 —— 但那样「同一来源反复骂」也算了，
#     不建议）。''',
        '''#   五、真跑核对产物后的**第二轮**修复（D3 语义熵的三次迭代）
#     交付前用真跑产物逐字段核对新落盘项，抓到 D3 的读数**无信息量**：
#     出厂版实测 6/6 恒 `h_norm = 1.0`。三轮定位与重设计：
#       · 第 1 轮：`_txt = [本条目text] + 全池structural_amps` —— 任何条目
#         都摊上一批**其他主张**的文本 ⇒ 簇必然全异 ⇒ 恒为上界。**推倒**。
#       · 第 2 轮：改为按条目自身 `occurrences`（逐字重复才累加）——
#         但 `upsert_belief` 按**精确文本**认领 ⇒ 换说法 = 新条目
#         ⇒ **无论怎么走都得到 `None`**。仍无信息量（换了个方向）。
#       · 第 3 轮（定稿）：语义熵度量的是「**同一条主张**的历次说法有多
#         发散」⇒ 分组必须用 `_sim3` 聚类（**只取包住本条目的那个簇**），
#         候选集 = 本条 occurrences + 池内其他条目 text（它们可能是同一
#         主张的另一种说法）；簇内出现数 < 2 ⇒ `None`（诚实缺省）、
#         ≥2 且全同簇 ⇒ `0.0`（说法收敛）、分裂 ⇒ `> 0`（说法发散）。
#       · 同时发现根因：`_sim3` 是字符二元组 Jaccard，0.70 只有近乎逐字
#         才够得着 ⇒ 新增 `belief.sem_entropy_thr`（默认 0.30，见该键）。
#       · 附带修好 `View.belief_items`：**声明了、也出口了、但从不被赋值**
#         的死字段（`View.to_dict = asdict(self)` ⇒ 该键恒 `[]`），改为在
#         `_apply_view_to_pool_locked` 里回填本轮相关条目。
#
#   【怎么退回旧行为】用 v1.23.27 主文件（本版改的是接线与默认值，无整体
#     回退开关；若要单独把 `revoked` 退回旧口径，把
#     `belief.revoke_sources` 设为 1 —— 但那样「同一来源反复骂」也算了，
#     不建议。D3 若要退回「恒 1.0」的旧读数，把 `belief.sem_entropy_thr`
#     设为 0.70 —— 但那等于让观测失效，同样不建议）。''',
    )

    _save(txt)
    _, crlf1, lf1 = _load()
    print("[out] CRLF=%d LF=%d  \\r\\r\\n=%d"
          % (crlf1, lf1, open(SRC, "rb").read().count(b"\r\r\n")))
    print("[OK] yaml synced")


if __name__ == "__main__":
    main()
