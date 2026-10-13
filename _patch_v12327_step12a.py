# -*- coding: utf-8 -*-
"""Step12a：dgtf_config.yaml 同步 v1.23.27 新增的可配键。

补三个键（值 = 引擎里的默认，保证「出厂即默认」）：
  · `sim.cluster`      = 0.70   （D3 语义熵聚类阈值 `_SEM_CLUSTER_THR`）
  · `probe.submodular` = true   （E2 子模批选开关，默认开）
  · `probe.stop_floor` = 0.02   （E6 自适应停止阈值 `_GAIN_STOP_FLOOR`）

★ 头部版本号已是 v1.23.27（Step1b 改过），这里只补键。
★ 键的**读法**：`self.config.get("probe", {}).get("stop_floor", _GAIN_STOP_FLOOR)`
  ⇒ yaml 不写也走代码默认；写上等于把默认**显式化**（可读、可改）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "dgtf_config.yaml"


def sub(text, anchor, new, tag, count=1):
    n = text.count(anchor)
    assert n == count, (
        f"[{tag}] 锚点命中 {n} 次（期望 {count}）\n锚点={anchor[:160]!r}")
    return text.replace(anchor, new, count)


def main():
    raw = SRC.read_bytes()
    txt = raw.decode("utf-8")
    assert txt.count("\r\n") == txt.count("\n"), "yaml 不是纯 CRLF"
    assert "\r\r\n" not in txt, "含 \\r\\r\\n"
    t = txt.replace("\r\n", "\n")

    # 1) sim 段补 cluster（跟在 dedup_susp 之后、probe: 之前）
    t = sub(
        t,
        '  dedup_susp: 0.85\n'
        '\n'
        'probe:\n',
        '  dedup_susp: 0.85\n'
        '\n'
        '  # 【用途】D3 语义熵聚类阈值：同一主张的多次出现，sim3 ≥ 它\n'
        '  #         视为「同一个说法」（并入同簇）。簇越多 ⇒ 该主张越发散。\n'
        '  # 【来源】v1.23.27 新增（`_SEM_CLUSTER_THR`）；此前语义熵未落地。\n'
        '  # 【建议】\n'
        '  #   默认 0.70\n'
        '  #   太容易并簇（把分歧读成一致）→ 0.75 ~ 0.80\n'
        '  #   太难并簇（同义反复也判发散）→ 0.60 ~ 0.65\n'
        '  # 【注意】这是**观测**用的尺子，不直接判优劣 —— 调它只改读数。\n'
        '  cluster: 0.70\n'
        '\n'
        'probe:\n',
        "sim.cluster", 1)

    # 2) probe 段补 submodular / stop_floor（跟在 select_n 之后）
    t = sub(
        t,
        '  # 【注意】太多会稀释注意力。\n'
        '  select_n: 5\n',
        '  # 【注意】太多会稀释注意力。\n'
        '  select_n: 5\n'
        '\n'
        '  # 【用途】E2 子模批选开关。true ⇒ 用贪心 + 边际下限挑探针\n'
        '  #         （宁少勿滥：边际 G 低于下限就停手，不凑数）；\n'
        '  #         false ⇒ 退回旧的「按模型自报 gain 排序取前 n」。\n'
        '  # 【来源】v1.23.27 新增。\n'
        '  # 【建议】\n'
        '  #   默认 true\n'
        '  #   【注意】算不出 G（未决 < 2 条）时会**自动退回**旧路径，\n'
        '  #    所以打开它不会让「池子太小」的圈跑不动。\n'
        '  submodular: true\n'
        '\n'
        '  # 【用途】E6 自适应停止阈值：本轮所有候选探针的 expected_gain\n'
        '  #         都低于它 ⇒ 记一条停止信号（本轮只出不进，\n'
        '  #         探针数 0 是**合法**的）。\n'
        '  # 【来源】v1.23.27 新增（`_GAIN_STOP_FLOOR`）。\n'
        '  # 【建议】\n'
        '  #   默认 0.02（刻意压低：停止是强动作，宁可多跑一圈也别误停）\n'
        '  #   想更早收手省算力 → 0.05 ~ 0.10\n'
        '  # 【注意】它与 `min_gain` 是**两把尺子**：min_gain 管「模型自报\n'
        '  #   值不值得做」，stop_floor 管「还能不能推得动」。\n'
        '  #   两者都低 ⇒ 停止信号；`max_gain == stop_floor` **不算**停。\n'
        '  stop_floor: 0.02\n',
        "probe.submodular_stop", 1)

    out = t.replace("\n", "\r\n")
    SRC.write_bytes(out.encode("utf-8"))
    print("STEP12A YAML PATCH OK")


if __name__ == "__main__":
    main()
