# -*- coding: utf-8 -*-
"""往 `smoke_test.py` 加一条**元判据**：判据体系自身的两条纪律。

1. 每个 `check_*` 都必须在 `main()` 里被调用（否则"存在≠在跑"；
   本次实测逮到 `check_p0_156_units` 从没跑过）；
2. 任何打印 `✗` 的判据都必须带失败标记（`return False` / `ok = False` /
   `bad.append`），否则会出现"打了 ✗ 但门禁放过"——门禁按退出码判，
   实测验收日志里就有 ✗ 藏在**数据值**里，按文本扫会误杀，所以只能靠这条静态纪律。

★ 这条判据**不吃变异体**：变异体机制是拿 SRC（引擎）造副本，而本判据的输入是
  `smoke_test.py` 自己。所以改用**构造性证明**：`check_v12362_judges_wired(src_text)`
  接受可选源码，开发期喂一份"故意坏掉"的样本，断言它返回 False。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "smoke_test.py"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")

NEW_CHECK = '''def check_v12362_judges_wired(src_text: str = None):
    """[元判据] 判据体系自身的两条纪律。

    1. **每个 `check_*` 都必须在 `main()` 里被调用** —— 否则"存在 ≠ 在跑"。
       本仓实测逮到 `check_p0_156_units` 写好了却从没被 main 调到（签名吃 `src`，
       与其余无参判据不同），已补线。
    2. **任何打印 `✗` 的判据都必须带失败标记**（`return False` / `ok = False` /
       `bad.append`）—— 门禁按**退出码**判，不是按 ✗ 文本（实测验收日志里就有
       ✗ 藏在数据值里，按文本扫会误杀）。所以"只喊不判"会被静默放过。

    ★ `src_text` 可选：开发期传一份"故意坏掉"的源码进来做**构造性证明**
      （本判据的输入是 `smoke_test.py` 自己，变异体机制够不到它）。
    """
    import ast as _a
    bad = []
    _src = src_text if src_text is not None else \\
        Path(__file__).read_text(encoding="utf-8")
    try:
        _tree = _a.parse(_src)
    except SyntaxError as _e:
        print("  ✗ [META] 源码解析失败：%r" % (_e,))
        return False
    _defined = [_n.name for _n in _tree.body
                if isinstance(_n, _a.FunctionDef) and _n.name.startswith("check_")]
    _main = ""
    for _n in _tree.body:
        if isinstance(_n, _a.FunctionDef) and _n.name == "main":
            _main = _a.get_source_segment(_src, _n) or ""
            break
    if not _main:
        bad.append("[META] 找不到 main()")
    _unwired = [d for d in _defined if ("%s(" % d) not in _main]
    # 本判据自身不调 main（它是被 main 调的），排除它自己与 main 的存在性噪声
    _unwired = [x for x in _unwired if x != "check_v12362_judges_wired"]
    if _unwired:
        bad.append("[META] 未接线的判据 %d 条：%s"
                   % (len(_unwired), "、".join(_unwired[:4])))
    _shout = []
    for _n in _tree.body:
        if not isinstance(_n, _a.FunctionDef) or not _n.name.startswith("check_"):
            continue
        _b = _a.get_source_segment(_src, _n) or ""
        if "✗" not in _b:
            continue
        if not any(_k in _b for _k in
                   ("return False", "ok = False", "bad.append", "bad = True")):
            _shout.append(_n.name)
    if _shout:
        bad.append("[META] 只喊不判 %d 条：%s"
                   % (len(_shout), "、".join(_shout[:4])))
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.62 判据体系自检（%d 项）" % len(bad))
        return False
    print("✓ v1.23.62 判据体系自检：%d 条判据全部接线 · 无「只喊不判」"
          % len(_defined))
    return True


'''

# 1) 插函数（放在 check_v12362_contra_live 前面）
OLD_INS = "def check_v12362_contra_live():"
assert s.count(OLD_INS) == 1
s = s.replace(OLD_INS, NEW_CHECK + OLD_INS)

# 2) main 接线（放在 contra 判据之后、最后一条之前的位置都行，放末尾组）
OLD_MAIN = """    if not check_v12362_contra_live():
        return 1
"""
NEW_MAIN = """    if not check_v12362_contra_live():
        return 1
    if not check_v12362_judges_wired():
        return 1
"""
assert s.count(OLD_MAIN) == 1
s = s.replace(OLD_MAIN, NEW_MAIN)

ast.parse(s)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
p.write_bytes(out)
print("已插入元判据并接线；%d → %d 行" % (n0, s.count("\n")))
