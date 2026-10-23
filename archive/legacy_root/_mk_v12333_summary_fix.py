# -*- coding: utf-8 -*-
"""更新 v1.23.33 收束摘要：补第六期 + 第二期落点（换行风格跟随原文件）。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
CL = HERE / "CHANGELOG.md"

OLD = """  目标读数进入每层每圈运行（停止判据 + 层末并列判定）+ 停因级联两处修正
  （剥括号匹配 / 档 2 去重叠键）**。
  未做（有意）：anytime 只用于「结构增长」这一维（一致率每跑只采一次，无逐圈序列）；
  bandit 只做圈数上限（动作空间越大、探索代价越高）；
  锚点联网可达性验证留给联网通道（不把可选成本塞进主路径）；
  三阶段决策**只出建议不落地配置**（红线：建议与执行分开）；
  archive 只在后期学习段使用，不介入前期选择；
  **目标读数进圈内动作（改 role/prompt 路由）= 第二期，已排期**。"""

NEW = """  目标读数进入每层每圈运行（停止判据 + 层末并列判定）+ 停因级联两处修正
  （剥括号匹配 / 档 2 去重叠键）** +
  **目标读数进圈内动作（第二期：`layer_goal_action_hint` → `_goal_hint_next` →
  两条 prompt 的 `{goal_hint}` 注入；★ **零新增接线点**，复用第一期两处
  `_layer_goal_now`）** +
  **各环节量化 + 降本（第六期：激活阴阳合并 / 阴阳分歧度 / 锚点保真度 /
  语义密度，四项纯函数 + 零成本 + 可开关 + 有留痕 + 三处真实入口接线）**。
  未做（有意）：anytime 只用于「结构增长」这一维（一致率每跑只采一次，无逐圈序列）；
  bandit 只做圈数上限（动作空间越大、探索代价越高）；
  锚点联网可达性验证留给联网通道（不把可选成本塞进主路径）；
  三阶段决策**只出建议不落地配置**（红线：建议与执行分开）；
  archive 只在后期学习段使用，不介入前期选择；
  阴阳合并是 **opt-in**（`merge_expand` 默认 false ⇒ 零行为差）；
  语义密度只做**读数与告警**、不自动裁剪 prompt（压缩是不可逆的信息损失，
  要改行为必须显式开关）；分歧度/保真度只**标注不改流程**（红线：建议与执行分开）；
  RASC/DeepConf/Think@n 三类早停**只做了依据储备**，未接进主循环
  （它们要求「判据可提前评估」，本轮先补齐**判据的尺子**，早停留给下一期）。"""


def main() -> int:
    b = CL.read_bytes()
    txt = b.decode("utf-8")
    assert b"\r\r\n" not in b
    flat = txt.replace("\r\n", "\n")
    n = flat.count(OLD)
    assert n == 1, "锚点命中 %d 次（应 1）" % n
    out = flat.replace(OLD, NEW, 1)
    assert out.count(NEW) == 1
    data = out.encode("utf-8")
    assert b"\r\r\n" not in data
    CL.write_bytes(data)
    print("OK 收束摘要已更新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
