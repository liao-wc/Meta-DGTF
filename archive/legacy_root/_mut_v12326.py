#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 变异体：证明 `check_v12326_sim3` 真的有判别力。

做法（沿用 v1.23.25 的可复用套路）：把 `smoke_test.py` 的 `SRC` 行换成
畸形体路径（**绝对路径**），把 smoke 源码 exec 成独立 module —— 每个畸形体
一个 module，互不污染；然后让**原样的判据函数**去跑，必须判红
（正对照跑真文件判绿）。

★ 变异体一律打在「判据读的那个东西」上，不是改判据的文案。
★ 抛错**不算判红** —— 那只说明畸形体没被加载起来，判据根本没执行。

八个变异体对应本次四组判据：
  A 组（sim3 修正短句高估）
    ① BM25 的 pair 用法换回 best ⇒ 无关对被抬高（Step8 修的正是这个）
    ② Jaccard 分母换回 min ⇒ 退回短句高估
    ③ 结构层比较去掉 ⇒ T3 vs T3 不再得 1.0
  B 组（BM25 通道）
    ④ _BM25_MIN_CORPUS 降到 0 ⇒ 语料不足时不再降级
    ⑤ BM25 归一化去掉 ⇒ 分数无上界
  C 组（池内阈值可配）
    ⑥ _DEDUP_SIM 默认改 0.5 ⇒ 与旧版行为不一致
    ⑦ merge 忽略 thr 参数 ⇒ 阈值改不动行为
  D 组（covers 语义校验）
    ⑧ 数字分支退回裸 True ⇒ 乱指 T1 不报红

★ M1 的沿革：最初打的是 `_sent_is_rephrase` 里的 sim3 阈值（抬到 0.99），
  实测**判绿**——因为该位置 sim3 被宽尺子（_similar/_overlap_coef）遮蔽，
  行为上不可观测（这也直接挖出 Step8 的 BM25 方向 bug）。现在 M1 改打
  `_bm25_pair` → `_bm25_best`（**回到那个方向性错误**），判据 B 组读它。
"""
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "元DGTF-V1.23.26.py"
SMOKE = HERE / "smoke_test.py"
TMP = HERE / "_audit_tmp"
TMP.mkdir(exist_ok=True)

MUTANTS = {

    # ① BM25 的 pair 用法换回 best ⇒ 两条各自与语料相关、彼此无关的句子
    #    会被抬高（这正是 Step8 修掉的方向性 bug）
    "M1_BM25退回best": (
        '        bm1 = _bm25_pair(a, b, corpus)\n'
        '        bm2 = _bm25_pair(b, a, corpus)\n',
        '        bm1 = _bm25_best(a, corpus)\n'
        '        bm2 = _bm25_best(b, corpus)\n',
    ),

    # ② Jaccard 分母换回 min ⇒ 退回短句高估（判据 A 的分母来源）
    "M2_Jaccard分母回min": (
        '    return len(ka & kb) / len(ka | kb)\n',
        '    return len(ka & kb) / min(len(ka), len(kb))\n',
    ),

    # ③ 结构层比较去掉 ⇒ 编号相等不再短路为 1.0
    "M3_结构层短路去掉": (
        '    if ma and mb:\n'
        '        return 1.0 if ma.group(1) == mb.group(1) else 0.0\n',
        '    if ma and mb:\n'
        '        return 0.0\n',
    ),

    # ④ 语料下限降到 0 ⇒ 「语料不足自动降级」这条判据失去意义
    "M4_语料下限降0": (
        '_BM25_MIN_CORPUS = 4    # 语料 < 4 篇时 BM25 不可靠，跳过该通道\n',
        '_BM25_MIN_CORPUS = 0    # 语料 < 4 篇时 BM25 不可靠，跳过该通道\n',
    ),

    # ⑤ BM25 归一化去掉 ⇒ 分数无上界（不相干对也可能被抬高）
    "M5_BM25不归一化": (
        '    if best <= 0:\n'
        '        return 0.0\n'
        '    return best / (best + _BM25_K1)\n',
        '    if best <= 0:\n'
        '        return 0.0\n'
        '    return best\n',
    ),

    # ⑥ 池内去重默认值改掉 ⇒ 与旧版行为不再一致
    "M6_去重默认值改0.5": (
        '_DEDUP_SIM = 0.90        # amp / thread / probe 入池去重\n',
        '_DEDUP_SIM = 0.50        # amp / thread / probe 入池去重\n',
    ),

    # ⑦ merge 忽略 thr ⇒ 阈值接不上（判据 C 的行为部分失效）
    "M7_merge忽略thr": (
        '        _t = _DEDUP_SIM if thr is None else float(thr)\n',
        '        _t = _DEDUP_SIM\n',
    ),

    # ⑧ covers 数字分支退回裸 True ⇒ 乱指 T1 不报红
    "M8_covers退回裸True": (
        '                        if 0 <= idx < len(untouched_items):\n'
        '                            # ★ 编号合法只是**必要条件**：还要语义对得上。\n'
        '                            #   原来这里直接 has_touch = True，covers 乱指\n'
        '                            #   T1 也算覆盖 —— 负对照实测不报。\n'
        '                            #   比较对象是**探针问题 vs 该项**（不是两项互比）。\n'
        '                            if (_similar(_pq, untouched_items[idx],\n'
        '                                         _QC_DUP_SIM)\n'
        '                                    or _overlap_coef(_pq,\n'
        '                                                     untouched_items[idx])\n'
        '                                    >= _COV_OVERLAP_MIN):\n'
        '                                has_touch = True\n'
        '                                break\n',
        '                        if 0 <= idx < len(untouched_items):\n'
        '                            has_touch = True\n'
        '                            break\n',
    ),
}


def _load_smoke_with(src_path: Path, tag: str):
    """把 smoke 源码的 SRC 指到 src_path，exec 成独立 module。

    ★ SRC 必须换成**绝对路径**：畸形体写在 `_audit_tmp/` 下，而 smoke 里的
      `HERE` 是仓库根 ⇒ `HERE / "<畸形体名>"` 指不到，会 FileNotFoundError
      ——那是「路径错」冒充的判红，等于没跑。
    """
    txt = SMOKE.read_text(encoding="utf-8")
    _abs = src_path.resolve().as_posix()
    assert re.search(r'^SRC = .*$', txt, flags=re.M), "smoke 里没有 SRC 行"
    txt = re.sub(r'^SRC = .*$', f'SRC = Path(r"{_abs}")',
                 txt, count=1, flags=re.M)
    assert _abs in txt, "SRC 替换失败"
    if not src_path.exists():
        raise FileNotFoundError(f"变异体文件不存在：{src_path}")
    mod_name = f"_smoke_{tag}"
    m = types.ModuleType(mod_name)
    m.__file__ = str(SMOKE)
    sys.modules[mod_name] = m
    exec(compile(txt, str(SMOKE), "exec"), m.__dict__)
    return m


def _run_check(m):
    return m.check_v12326_sim3()


print("=" * 82)
print("v1.23.26 变异体（打 sim3 尺子 / BM25 通道 / 池内阈值 / covers 校验）")
print("=" * 82)

# ---- 正对照：真文件必须判绿 ----
print("\n[正对照] 真文件（无变异）")
_m = _load_smoke_with(BASE, "ctrl")
try:
    _r = _run_check(_m)
except Exception as e:  # noqa: BLE001
    print(f"  ✗ 正对照抛错：{type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
assert _r, "★ 正对照失败：真文件下 check_v12326_sim3 没判绿"
print("  ✓ 判据判绿（正对照成立 → 后面的判红才是变异体造成的）")

# ---- 各变异体 ----
passed = 0
failed = []
for tag, (old, new) in MUTANTS.items():
    src = BASE.read_text(encoding="utf-8").replace("\r\n", "\n")
    cnt = src.count(old)
    if cnt != 1:
        failed.append(f"{tag}: 锚点命中 {cnt} 次（期望 1）")
        print(f"  ✗ {tag}: 锚点命中 {cnt} 次")
        continue
    src = src.replace(old, new, 1)
    out = TMP / f"_mut_v12326_{tag}.py"
    out.write_text(src, encoding="utf-8", newline="\n")

    print(f"\n[{tag}]")
    try:
        _mm = _load_smoke_with(out, tag)
        _a = _run_check(_mm)
    except Exception as e:  # noqa: BLE001
        # ★ 抛错**不算判红**：那只说明畸形体没被加载起来（多半是锚点/路径问题），
        #   判据根本没执行 ⇒ 得不到「有判别力」的结论。必须当失败。
        failed.append(f"{tag}: 加载/执行抛错（不是判红）："
                      f"{type(e).__name__}: {e}")
        print(f"  ✗ 加载/执行抛错 ⇒ 判据没跑，不能算判红："
              f"{type(e).__name__}: {e}")
        continue
    if _a:
        failed.append(f"{tag}: 判据判绿 ⇒ 变异体没被发现")
        print("  ✗ 没被发现（判据判绿）")
    else:
        print("  ✓ 判红")
        passed += 1

print()
print("=" * 82)
print(f"变异体判红：{passed} / {len(MUTANTS)}")
if failed:
    for f in failed:
        print(f"  ✗ {f}")
    sys.exit(1)
print("★ 全部变异体判红 + 正对照判绿 ⇒ 判据有判别力")
print("=" * 82)
