# -*- coding: utf-8 -*-
"""v1.23.28 D3 语义熵 —— **阈值解耦**（F1-R3）。

## 为什么还要再改（第三轮实测的最终根因）

F1-R2 把分组口径改成「以本条目为中心、按 `_sim3` 聚类」是对的，
但直测发现 **簇恒为单元素** ⇒ `occ_n` 恒 = 1 ⇒ 熵恒 `None`。

根因定位（直测，见本文件头注的读数）：
  `_sim3` 在中文上是**字符二元组 Jaccard**（`_tokenize` 按 bigram 切），
  于是「同一主张换个说法」的分值只有 0.41~0.79，而 `thr` 沿用了
  `sim.cluster = 0.70` —— **只有近乎逐字相同才够得着**。
  实测（同主张 / 不同主张两组，完全可分）：
      同主张：0.667 / 0.500 / 0.786 / 0.412 / 0.556
      不同主张：0.000 / 0.000 / 0.000
  ⇒ 两组之间有 **巨大空隙（0.0 ↔ 0.41）**，正确的阈值应落在空隙里。

## 修法：D3 用**自己的**阈值键，与 `sim.cluster` 解耦

  · `sim.cluster`（0.70）是 **E2 探针批选**的口径（聚类「相同探针」），
    与 D3「同一主张的历次说法」**不是同一件事** ⇒ 不该共用一把尺子。
  · 新增模块常量 `_SEM_CLUSTER_THR = 0.30`（落在实测空隙内、两侧留余量）
    与配置键 `belief.sem_entropy_thr`（默认 0.30）。
  · `semantic_entropy_of` 的**函数默认值**随之改为 0.30；外部显式传值
    逐位覆盖（可负对照）。

★ 为什么取 0.30 而不是空隙中点 0.20：Jaccard 对短句更敏感，取 0.30
  在「长句重述」上更保守（宁可少聚，不把不同主张混进同一簇 —— 混进来
  会把发散度**低估**，与本函数的保守取向一致）。
"""
SRC = "元DGTF-V1.23.28.py"


def _load(path=SRC):
    b = open(path, "rb").read()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n") - crlf
    assert crlf > 0, "主文件必须是 CRLF"
    assert lf == 0, "主文件混入裸 LF %d 处" % lf
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

    # ── R3a: 模块常量注释与数值 ──
    txt = patch(
        txt, "R3a-const",
        '''#: 语义熵聚类阈值（D3）。★ 与 `dgtf_config.yaml` 的 `sim.cluster`
#:   **同值**（0.70）—— 这里给的是「函数默认值」，配置侧由
#:   `semantic_entropy_of(..., thr=cfg)` 覆盖。默认值 = 出厂值 ⇒ 零行为差。
_SEM_CLUSTER_THR = 0.70
''',
        '''#: 语义熵聚类阈值（D3）。★ **与 `sim.cluster`（0.70）解耦** ——
#:   两者不是同一件事：`sim.cluster` 是 E2 **探针批选**的口径（把
#:   「同一个探针」聚起来），D3 要聚的是「**同一主张的历次说法**」。
#:   ★ 为什么必须是 0.30 而不是 0.70：`_sim3` 在中文上走字符二元组
#:     Jaccard，同一个主张换个说法只有 0.41~0.79，0.70 只有近乎逐字
#:     才够得着 ⇒ 簇恒单元素 ⇒ 熵恒 None（实测，见 _mk_v12328_d3thr 头注）。
#:     实测同主张 0.41~0.79、不同主张 0.00 —— 两组完全可分，取空隙内的
#:     0.30（长句重述上偏保守：宁可少聚，不把不同主张混进同一簇）。
#:   这里给的是「函数默认值」，配置侧由 `belief.sem_entropy_thr` 覆盖。
#:   默认值 = 出厂值 ⇒ 零行为差。
_SEM_CLUSTER_THR = 0.30
''',
    )

    # ── R3b: 函数默认注释同步 ──
    txt = patch(
        txt, "R3b-doc",
        '''    ★ 为什么聚类用「与簇代表的最大相似度」而不是两两平均：平均会被
      链式传递（A~B、B~C 但 A≁C）拉成大簇，把发散读成一致。
      用**单链到代表**（第一次进簇的那条）⇒ 同义反复的文本稳定聚在一起，
      真正发散的进不去。这是**保守**选择：宁可高估发散，不高估稳定
      （高估发散只是不判 stable，不改变任何主张的优劣）。
''',
        '''    ★ 为什么聚类用「与簇代表的最大相似度」而不是两两平均：平均会被
      链式传递（A~B、B~C 但 A≁C）拉成大簇，把发散读成一致。
      用**单链到代表**（第一次进簇的那条）⇒ 同义反复的文本稳定聚在一起，
      真正发散的进不去。这是**保守**选择：宁可高估发散，不高估稳定
      （高估发散只是不判 stable，不改变任何主张的优劣）。
    ★ `thr` 默认 `_SEM_CLUSTER_THR`（0.30）：**不是** `sim.cluster`
      （0.70）—— 后者是 E2 探针批选的口径。用 0.70 会让「换个说法」
      永远聚不起来 ⇒ 熵恒 None（实测）。详见模块常量处注释。
''',
    )

    # ── R3c: DEFAULT_CONFIG 修正注释 + 新增 belief.sem_entropy_thr ──
    txt = patch(
        txt, "R3c-default-comment",
        '''        # [D3] 语义熵聚类阈值。★ 曾在 yaml 里登记却没进 DEFAULT_CONFIG
        #   （yaml 记了引擎不认识的键 —— 用户改了没效果）⇒ 这里补上，
        #   与 `_SEM_CLUSTER_THR` 同值。拾取点：
        #   `select_probe_focus(..., thr=cfg.sim.cluster)`。
        "cluster": 0.70,
''',
        '''        # [E2] 探针批选聚类阈值（把「同一个探针」聚起来）。
        #   ★ 曾在 yaml 里登记却没进 DEFAULT_CONFIG（yaml 记了引擎不认识
        #     的键 —— 用户改了没效果）⇒ 这里补上。拾取点：
        #     `select_probe_focus(..., thr=cfg.sim.cluster)`。
        #   ★ **不要**被 D3 复用：D3 的语义熵阈值走
        #     `belief.sem_entropy_thr`（两者尺度不同，见该键注释）。
        "cluster": 0.70,
''',
    )

    txt = patch(
        txt, "R3c-belief-key",
        '''    "belief": {
        # [D2] `revoked` 需要的**不同攻击来源数**（与 `stable` 对称）。
        "revoke_sources": 2,
    },
''',
        '''    "belief": {
        # [D2] `revoked` 需要的**不同攻击来源数**（与 `stable` 对称）。
        "revoke_sources": 2,
        # [D3] 语义熵聚类阈值。★ **独立于 `sim.cluster`**：`_sim3` 在
        #   中文上走字符二元组 Jaccard，「同一主张换个说法」实测只有
        #   0.41~0.79、不同主张 0.00 ⇒ 用 `sim.cluster`(0.70) 会簇恒单
        #   元素 ⇒ 熵恒 None（真跑 + 直测共同证实）。默认 = `_SEM_CLUSTER_THR`。
        #   拾取点：`refresh_belief_entropy(..., thr=cfg.belief.sem_entropy_thr)`。
        "sem_entropy_thr": 0.30,
    },
''',
    )

    # ── R3d: Pool 字段 + 调用点接线（走 revoke_sources 同一套下发模式）──
    txt = patch(
        txt, "R3d-pool-field",
        '''    # [D2 可配] `revoked` 需要的不同攻击来源数（默认 = 模块常量）。
    #   ★ 配置键 `belief.revoke_sources` 的**落点**。纯函数
    #     `belief_transition` 不能读全局配置 ⇒ 由 Pool 携带并显式传入。
    revoke_sources: int = _BELIEF_REVOKE_SOURCES
''',
        '''    # [D2 可配] `revoked` 需要的不同攻击来源数（默认 = 模块常量）。
    #   ★ 配置键 `belief.revoke_sources` 的**落点**。纯函数
    #     `belief_transition` 不能读全局配置 ⇒ 由 Pool 携带并显式传入。
    revoke_sources: int = _BELIEF_REVOKE_SOURCES
    #: [D3 可配] 语义熵聚类阈值（默认 = 模块常量 `_SEM_CLUSTER_THR`）。
    #:   ★ 与 `revoke_sources` 同一套下发模式：配置键
    #:     `belief.sem_entropy_thr` 的落点，由 MetaDGTF 在构造时下发。
    #:   ★ 独立于 `sim.cluster`（E2 探针批选口径，0.70）—— 尺度不同。
    sem_entropy_thr: float = _SEM_CLUSTER_THR
''',
    )

    txt = patch(
        txt, "R3d-callsite",
        '''        try:
            self.refresh_belief_entropy()
        except Exception:
            pass
''',
        '''        try:
            self.refresh_belief_entropy(
                thr=getattr(self, "sem_entropy_thr", None))
        except Exception:
            pass
''',
    )

    txt = patch(
        txt, "R3d-dispatch",
        '''        for _p in self.pools.values():
            _p.revoke_sources = _rs
''',
        '''        for _p in self.pools.values():
            _p.revoke_sources = _rs
        # [D3 可配] `belief.sem_entropy_thr` 落到每个池上（默认 = 模块常量）。
        #   ★ 与 revoke_sources 同因：配置键不读 = 埋坑。这里显式下发。
        try:
            _se = float((config.get("belief") or {}).get(
                "sem_entropy_thr", _SEM_CLUSTER_THR))
        except (TypeError, ValueError):
            _se = _SEM_CLUSTER_THR
        for _p in self.pools.values():
            _p.sem_entropy_thr = _se
''',
    )

    _save(txt)
    _, crlf1, lf1 = _load()
    print("[out] CRLF=%d LF=%d  \\r\\r\\n=%d"
          % (crlf1, lf1, open(SRC, "rb").read().count(b"\r\r\n")))
    print("[OK] F1-R3 applied")


if __name__ == "__main__":
    main()
