# -*- coding: utf-8 -*-
"""[v1.23.2] 整体性检查探针：对**整份工程**做机械审计（不只针对本轮改动）。

用法：python _probe_v1232_audit.py [Meta-DGTF-V1.23.2.py]

八类检查（每一类都对应本项目真实踩过的坑）：
  A 出口完整性 / 死类          —— `to_dict` 白名单漏字段；定义了没人用的类
  B 白名单四处一致            —— prompt schema ↔ 归一化白名单 ↔ 抽取 ↔ 渲染
  C 版本一致性                —— docstring / `__version__` / smoke SRC / yaml 头
  D 宪法红线（W# 不进候选/对撞）—— 「检索结果不是内容，是参照」
  E 圈号口径一致性            —— 每个 `_web_search` 调用点传的是什么
  F `used_as` 枚举与消费方     —— 写进去的标签必须有人读，且取值封闭
  G 登记表两向对账            —— 死类/白名单豁免表：未登记判红 + 过期登记判红
  H 报告/文档引用的文件在不在

★ 判据一律「先证非空再判」——空集合通过等于没测（本项目老坑）。
"""

# ── [v1.23.64] 终端编码兜底：Windows 管道下默认 cp936，打印非 ASCII 会崩 ──
import sys as _sys_utf8
for _s_utf8 in (_sys_utf8.stdout, _sys_utf8.stderr):
    try:
        _s_utf8.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "Meta-DGTF-V1.23.2.py"
if not SRC.is_absolute():
    SRC = HERE / SRC

raw = SRC.read_bytes().decode("utf-8")
txt = raw.replace("\r\n", "\n")
LINES = txt.split("\n")

# ── [perf 2026-10-28] AST **一次解析、多处复用** ——
# 原实现 body_of() 每次调用都 ast.parse(全文)；V2.2.15（33k 行）上 audit 实测 181.1s，
# 根因是 O(n²) 反复解析。这里把「目标引擎全文」解析恰好一次：
#   · _AST          = 目标引擎全文 AST（唯一一次全文解析）
#   · _FUNCS        = {函数名: 函数节点}，body_of 直接查表（与 ast.walk 首命中同序）
#   · _parse_cached = 目标文本返回 _AST；别的文本（合成/变异体）才真正解析
# 判据（scripts/tests_acceptance_semantics.py E 组）：monkeypatch ast.parse 计数，
# 目标全文解析次数必须 == 1；变异体（body_of 恢复逐次解析）必须被判红。
_AST = ast.parse(txt)


def _parse_cached(src):
    """同一文本只解析一次：目标引擎全文直接复用 _AST（其余文本按需解析）。"""
    return _AST if src is txt else ast.parse(src)


def _index_ast(tree):
    """**一次** O(n) 遍历建好后续各判据要用的索引（原先每条判据各自 ast.walk 全文）。

    - funcs: {函数名: 节点}（setdefault 保留 ast.walk 首命中，与 body_of 原语义同序）
    - classes: 类定义节点列表（ast.walk 顺序）
    - name_counts: {裸 ast.Name id: 次数}（死类判据 A2/A3 用）
    - stages: 代码里所有字面 stage= 取值（K4 用）
    - wired: {_thinking_stage 第 2 实参: 行号}（K1–K3 用，后写覆盖 = 原语义）
    - web_calls: [(Call 节点, 第 3 实参源码, 是否缺参)]（E1 用）
    """
    funcs, classes, name_counts = {}, [], {}
    stages, wired, web_calls = set(), {}, []
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef):
            funcs.setdefault(n.name, n)
        elif isinstance(n, ast.ClassDef):
            classes.append(n)
        elif isinstance(n, ast.Name):
            name_counts[n.id] = name_counts.get(n.id, 0) + 1
        elif isinstance(n, ast.Call):
            for _kw in n.keywords:
                if (_kw.arg == "stage" and isinstance(_kw.value, ast.Constant)
                        and isinstance(_kw.value.value, str)):
                    stages.add(_kw.value.value)
            _fn = n.func
            if (isinstance(_fn, ast.Name) and _fn.id == "_thinking_stage"
                    and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant)):
                wired[n.args[1].value] = n.lineno
            elif (isinstance(_fn, ast.Attribute)
                    and _fn.attr == "_web_search"):
                _a = n.args[2] if len(n.args) > 2 else None
                web_calls.append((n,
                                  ast.get_source_segment(txt, _a)
                                  if _a is not None else None,
                                  _a is None))
    return {"funcs": funcs, "classes": classes, "name_counts": name_counts,
            "stages": stages, "wired": wired, "web_calls": web_calls}


_IDX = _index_ast(_AST)
_FUNCS = _IDX["funcs"]

R = []


def ck(tag, cond, note=""):
    R.append((tag, bool(cond), note))


spec = importlib.util.spec_from_file_location("dgtf_audit", SRC)
mod = importlib.util.module_from_spec(spec)
sys.modules["dgtf_audit"] = mod
spec.loader.exec_module(mod)


def body_of(name):
    """函数体源码 + 节点。★ 查表复用唯一一次全文 AST（原先每次调用都全文解析）。"""
    n = _FUNCS.get(name)
    if n is None:
        return "", None
    return "\n".join(LINES[n.lineno - 1:n.end_lineno]), n


# ============================================================ A 出口 / 死类
print("── A 出口完整性 / 死类 ──")
_EXPORT_CLASSES = ("Candidate", "Probe", "View", "Pool")


def _seed(o, cls):
    """按**类型注解**播种所有字段；返回「注解认不出」的清单。

    ★ `object.__new__` 不跑 `__init__` ⇒ 没有类级默认值的字段 `getattr`
      拿不到东西（第一版因此 4 个类全部「不可测」——判据跑不起来比没有更糟）。
    """
    unseed = []
    for f, fl in cls.__dataclass_fields__.items():
        ann = str(fl.type)
        if ("List" in ann or "list" in ann or "Tuple" in ann
                or "tuple" in ann or "Sequence" in ann):
            setattr(o, f, [{"_probe": 1}])
        elif "Dict" in ann or "dict" in ann or "Mapping" in ann:
            setattr(o, f, {"_probe": 1})
        elif "bool" in ann:
            setattr(o, f, True)
        elif "str" in ann:
            setattr(o, f, "x")
        elif "int" in ann or "float" in ann:
            setattr(o, f, 1)
        else:
            unseed.append((f, ann))
            setattr(o, f, None)
    return unseed


def _export_miss(mm):
    """返回 {类名: (未出口字段, 认不出的注解, 异常)} —— 供**变异体复算**用。

    ★ 抽成函数是为了让「审计本身有判别力」可测：把字段从 `to_dict` 里抠掉，
      再调一次本函数，必须能看见「未出口」。
    """
    out = {}
    for cn in _EXPORT_CLASSES:
        cls = getattr(mm, cn, None)
        if cls is None or not hasattr(cls, "to_dict"):
            continue
        try:
            o = object.__new__(cls)
            unseed = _seed(o, cls)
            d = o.to_dict()
            miss = [f for f in cls.__dataclass_fields__ if f not in d]
            out[cn] = (miss, unseed, None)
        except Exception as e:  # noqa: BLE001
            out[cn] = ([], [], "%s: %s" % (type(e).__name__, e))
    return out


_EFFECTIVE = getattr(mod, "_AUDIT_EXPORT_EXEMPT", {})
_MISS = _export_miss(mod)
for _cn in _EXPORT_CLASSES:
    _m = _MISS.get(_cn)
    if _m is None:
        ck("A1.%s 有 to_dict（否则登记豁免）" % _cn, _cn in _EFFECTIVE,
           "未登记：%s 没有 to_dict" % _cn)
        continue
    _miss, _unseed, _err = _m
    _miss = [f for f in _miss if f not in _EFFECTIVE.get(_cn, ())]
    ck("A1.%s ★ 全字段出口（填满后必须都在 to_dict）" % _cn,
       (not _miss) and (not _unseed) and (_err is None),
       "未出口：%r；种子认不出：%r；异常：%r" % (_miss, _unseed, _err))

# 死类：定义后**零引用**（按 AST 数真实引用，不数文本）
#   ★ 文本计数会被骗：changelog 里提一句类名、登记表里写个字符串，
#     都会被算成「有引用」，于是过期登记判据恒红（第一版就这样）。
#   ★ 只数**裸 `ast.Name`**（真实代码引用），**不数 `ast.Attribute`**：
#     —— 字符串常量不算引用（登记表里的名字就是字符串）；
#     —— `threading.Thread` 这种「模块.属性」访问**不是**对全局类 `Thread`
#        的引用（它是标准库类），若数 Attribute 会把 `threading.Thread` 误判成
#        本地死类 `Thread` 的「真实引用」，导致 A3 过期登记恒红。
#        全局类被使用时的代码形态必然是裸名（`Thread(...)` / `x: Thread`），
#        所以裸名计数既是正确语义、又能避开模块属性碰撞。
_DEAD_REG = set(getattr(mod, "_AUDIT_DEAD_CLASSES", ()) or ())
_TREEA = _AST   # ★ 复用唯一一次全文解析（perf 2026-10-28）


#: ★ [perf 2026-10-28] 原实现每个类都 ast.walk(全文) 数裸名引用（22 个类 × 33k 行
#:   AST = 实测 36.8s，仅次于 AST 重复解析的第二大热点）。_IDX 已一次遍历建好
#:   name_counts，这里 O(1) 查表。语义逐字不变：仍只数裸 ast.Name（理由见 A2 注释）。
_NAME_COUNTS = _IDX["name_counts"]


def _code_refs(name):
    # 只数裸名引用（见上方说明）。★ 查表 O(1)。
    return _NAME_COUNTS.get(name, 0)


_DEAD_FOUND = set()
for _n in _IDX["classes"]:       # ★ 复用一次遍历的类列表（原先再 ast.walk 全文）
    _nm = _n.name
    if _code_refs(_nm) == 0:
        _DEAD_FOUND.add(_nm)
        ck("A2.%s ★ 死类已登记（定义后零引用）" % _nm, _nm in _DEAD_REG,
           "未登记：%s 定义后零引用" % _nm)
    else:
        ck("A2.%s 非死类" % _nm, True, "")
for _d in sorted(_DEAD_REG):
    # ★ 判据方向：登记了**且确实死** → 绿；登记了却被引用 → **过期登记** → 红。
    #   （第一版写成 `_d not in _DEAD_FOUND` —— 方向反了，恒红。）
    ck("A3.%s 死类登记有效（无过期）" % _d, _d in _DEAD_FOUND,
       "%s 已登记为死类，但它有真实引用（过期登记）" % _d)

# ============================================================ B 白名单四处一致
print("── B 白名单四处一致 ──")


def _lit_text(line):
    """把一行 Python 字面量的**内容**抠出来（去引号、还原 \\n）。

    ★ 不能用 `re.findall(r"['\\"]([^'\\"]*)['\\"]", line)` 配成对引号 ——
      外引号是 `'`、内容里又含 `"` 时（本项目 prompt schema 全是这种写法）
      配对会错位，抠出来的串是垃圾 ⇒ 后面「抠到空集 ⇒ 空集合通过」。
      正解：取该行**第一个引号**与**最后一个同种引号**之间的内容。
    """
    s = line.strip()
    cand = [x for x in (s.find("'"), s.find('"')) if x >= 0]
    if not cand:
        return ""
    a = min(cand)
    q = s[a]
    b = s.rfind(q)
    if b <= a:
        return ""
    return (s[a + 1:b].replace("\\n", "\n").replace("\\'", "'")
            .replace('\\"', '"'))


def _schema_keys(product, _lines=None):
    """从 prompt 字面量里抠 `"<product>": {` 段的**顶层**键。

    ★ 必须按括号层数取 —— 第一版只按行扫，把 `actions[]` / `not_do[]` 里的
      `verb/object/owner_role/...` 也算成顶层键，于是**假报**「7 个键被吞」。
    ★ 第二版按「紧跟 `{` 或 `,`」判键 → 又漏掉**行首**的键（`"answer":` 前面
      没有 `{`/`,`），于是抠到空集 ⇒ 空集合通过等于没测。
    最终版：先把整段拼成一串，再**逐字符**扫、只在 depth==1 时**任意位置**
      尝试匹配 `"key":`（空格会自然跳过），depth 归零即结束。
    """
    _ls = _lines if _lines is not None else LINES
    _start = None
    for i, l in enumerate(_ls):
        if re.search(r"\"%s\": \{" % re.escape(product), _lit_text(l)):
            _start = i
            break
    if _start is None:
        return set()
    blob = " ".join(_lit_text(l) for l in _ls[_start:])
    keys, depth, i, opened = set(), 0, 0, False
    while i < len(blob):
        ch = blob[i]
        if ch == "{":
            depth += 1
            opened = True
            i += 1
            continue
        if ch == "}":
            depth -= 1
            i += 1
            if opened and depth <= 0:
                break
            continue
        if depth == 1:
            m = re.match(r'"(\w+)":', blob[i:])
            if m:
                keys.add(m.group(1))
                i += m.end()
                continue
        i += 1
    return keys


def _norm_keys(var, _lines=None):
    """从 `var = {` 段里抠键（显式白名单）。"""
    _ls = _lines if _lines is not None else LINES
    _start = None
    for i, l in enumerate(_ls):
        if re.search(r"^\s*%s = \{" % re.escape(var), l):
            _start = i
            break
    if _start is None:
        return set()
    keys = set()
    for l in _ls[_start + 1:]:
        if re.match(r"^\s*\}", l):
            break
        m = re.match(r'\s*"(\w+)":', l)
        if m:
            keys.add(m.group(1))
    return keys


for _prod, _normvar in (("decidable_product", "dec_norm"),
                        ("undecidable_product", "und_norm")):
    _sk = _schema_keys(_prod)
    _nk = _norm_keys(_normvar)
    ck("B1.%s schema 抠到键（非空）" % _prod, bool(_sk), repr(sorted(_sk)))
    ck("B2.%s 白名单抠到键（非空）" % _prod, bool(_nk), repr(sorted(_nk)))
    _lost = sorted(_sk - _nk)
    ck("B3.%s ★ schema 的键必须都过白名单（否则静默吞字段）" % _prod,
       not _lost, "被吞：" + repr(_lost))

# ============================================================ C 版本一致性
print("── C 版本一致性 ──")
_ver = str(getattr(mod, "__version__", ""))
_m = re.search(r"(?:元 DGTF|Meta-DGTF(?:-道生三阶模型)?) · [vV]([\d.]+)", txt[:4000])
_docver = _m.group(1) if _m else ""
ck("C1 docstring 标题版本 == __version__", bool(_ver) and _docver == _ver,
   "doc=%r ver=%r" % (_docver, _ver))
_sm = (HERE / "smoke_test.py")
if _sm.is_file():
    _st = _sm.read_bytes().decode("utf-8")
    _ms = re.search(r'SRC = HERE / "([^"]+)"', _st)
    if "V1-only smoke gate" in _st:
        ck("C2 smoke_test.py 是 V1-only 门禁",
           bool(_ms) and _ms.group(1) == "dgtf_engine/dgtf_v1/engine/元DGTF-V1.30.4.py"
           and "DGTF_V1_SMOKE" in _st,
           "smoke SRC=%r，门禁=%r" % (_ms.group(1) if _ms else None,
                                      "V1-only" if "V1-only smoke gate" in _st else "?"))
    else:
        ck("C2 smoke_test.py 的 SRC 指向本版", bool(_ms) and _ms.group(1) == SRC.name,
           "smoke SRC=%r，本版=%r" % (_ms.group(1) if _ms else None, SRC.name))
else:
    ck("C2 smoke_test.py 存在", False, "")
_y = HERE / "dgtf_config.yaml"
if _y.is_file():
    _yl = _y.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
    _yv = ""
    for _l in _yl[:6]:
        _mm = re.search(r"(?:元 DGTF|Meta-DGTF(?:-道生三阶模型)?) · [vV]([\d.]+) 配置文件", _l)
        if _mm:
            _yv = _mm.group(1)
    ck("C3 yaml 头部版本 == __version__", _yv == _ver, "yaml=%r ver=%r" % (_yv, _ver))
else:
    ck("C3 dgtf_config.yaml 存在", False, "")
_canon_report = HERE / ("V%s-发布报告.md" % _ver)
_legacy_report = HERE / ("v%s_报告.md" % _ver.replace(".", ""))
ck("C4 本版报告存在", _canon_report.is_file() or _legacy_report.is_file(),
   "缺 V%s-发布报告.md" % _ver)

# ============================================================ D 宪法红线
print("── D 宪法红线（W# 不进候选 / 不进对撞第三者）──")
_WEB = ("web_results", "web_arbitration", "web_clean_check", "_web_search",
        "_web_digest", "_web_client", "web_tier_proposals")
_cand = [l for l in LINES
         if re.search(r"(candidates?\.append|candidates? =|upstream_views\s*=)", l)
         and any(k in l for k in _WEB)]
ck("D1 ★ `view.candidates` 的写入点没有 web 来源", not _cand, repr(_cand[:3]))
_duel = body_of("_build_inp_duel")[0]
ck("D2 ★ 对撞层的输入构造里没有 web 来源（未对齐合法）",
   bool(_duel) and not any(k in _duel for k in _WEB), "")
_ing = body_of("_ing")[0]
ck("D3 ★ `_ing` 里没有 web 符号（C3 复核）",
   bool(_ing) and not any(k in _ing for k in _WEB), "")

# ============================================================ E 圈号口径
print("── E 圈号口径一致性 ──")
_ROUND_OK = re.compile(r"^(0|_rn|self\._research_round_no\(\)|"
                       r"max\(1, int\(round_no or 1\)\)|int\(layer or 0\) or 1)$")
def _round_args(txtx):
    """返回 (所有调用点的第 3 实参源码, 不合规清单)。抽成函数供变异体复算。"""
    bad, seen = [], []
    for _n in ast.walk(_parse_cached(txtx)):
        if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
                and _n.func.attr == "_web_search"):
            _a = _n.args[2] if len(_n.args) > 2 else None
            if _a is None:
                bad.append("缺第 3 实参 @%d" % _n.lineno)
                continue
            _s = ast.get_source_segment(txtx, _a) or ""
            seen.append(_s)
            if not _ROUND_OK.match(_s.strip()):
                bad.append("line %d: %s" % (_n.lineno, _s.strip()))
    return seen, bad


# ★ [perf 2026-10-28] 复用 _IDX 里的 _web_search 调用索引（原先再 ast.walk 全文一遍）
_seen, _bad = [], []
for _n, _s, _miss in _IDX["web_calls"]:
    if _miss:
        _bad.append("缺第 3 实参 @%d" % _n.lineno)
        continue
    _seen.append(_s or "")
    if not _ROUND_OK.match((_s or "").strip()):
        _bad.append("line %d: %s" % (_n.lineno, (_s or "").strip()))
ck("E1 每个 `_web_search` 调用点都传真圈号（或前置 0）", not _bad,
   repr(_bad))
ck("E2 调用点数 ≥ 6（非空，防空过）", len(_seen) >= 6, repr(sorted(set(_seen))))
_rno, _ = body_of("_research_round_no")
_ret = [l.strip() for l in _rno.split("\n") if l.strip().startswith("return")]
ck("E3 ★ `_research_round_no()` 只返回常量 0（不再返回拆解序号）",
   _ret == ["return 0"], repr(_ret))
ck("E3b 前置调用点带 `pre_seq=`（序号仍有出口，不丢信息）",
   txt.count("pre_seq=_pre") == 2 and txt.count('"pre_seq"') >= 1,
   "pre_seq=_pre 出现 %d 次" % txt.count("pre_seq=_pre"))

# ============================================================ F used_as
print("── F used_as 枚举与消费方 ──")
_ENUM = set(getattr(mod, "_WEB_USED_AS", ()) or ())
_found = set(re.findall(r'used_as="(\w+)"', txt))
_found |= set(re.findall(r"used_as='(\w+)'", txt))
ck("F1 `_WEB_USED_AS` 非空（登记表存在）", bool(_ENUM), repr(_ENUM))
_unreg = sorted(_found - _ENUM)
ck("F2 ★ 所有 used_as 取值都在枚举里", not _unreg, "未登记：" + repr(_unreg))
_stale = sorted({x for x in _ENUM if x not in _found})
ck("F3 枚举里没有过期取值", not _stale, "过期：" + repr(_stale))
_consumers = [f for f in ("_w6_analyze.py", "_run_v1230_w6.py")
              if (HERE / f).is_file()
              and "used_as" in (HERE / f).read_text(encoding="utf-8")]
ck("F4 ★ 每个 used_as 取值至少有消费者（分析脚本读它）", bool(_consumers),
   "没有消费者：used_as 就是纯死字段")

# ============================================================ G 登记表对账
print("── G 登记表两向对账 ──")
for _nm, _const in (("死类", "_AUDIT_DEAD_CLASSES"),
                    ("出口豁免", "_AUDIT_EXPORT_EXEMPT")):
    _v = getattr(mod, _const, None)
    ck("G.%s `%s` 存在（登记表本身要有出口）" % (_nm, _const),
       _v is not None, "常量不存在")

# ============================================================ H 文档引用
print("── H 文档引用的文件 ──")
_rep = HERE / ("V%s-发布报告.md" % _ver)
if not _rep.is_file():
    _rep = HERE / ("v%s_报告.md" % _ver.replace(".", ""))
if _rep.is_file():
    _rt = _rep.read_text(encoding="utf-8")
    _refs = set(re.findall(r"`([\w\u4e00-\u9fff\-.]+\.(?:py|md|json|yaml))`", _rt))
    # ★ 报告里会用缩写（如 `_mk_v1231_fill.py` / `_fill2.py`）⇒ 允许 endswith；
    #   运行时产物（如 `_domains.json`）在 cache/websearch/ 下，也要算存在。
    _pool = [p.name for p in HERE.glob("*")]
    _cw = HERE / "cache" / "websearch"
    if _cw.is_dir():
        _pool += [p.name for p in _cw.glob("*")]
    _missing = sorted(r for r in _refs
                      if not (HERE / r).exists()
                      and not any(a == r or a.endswith(r) for a in _pool))
    ck("H1 ★ 报告里引用的文件都存在", not _missing, "缺：" + repr(_missing[:8]))
else:
    ck("H1 报告存在（才能查引用）", False, repr(_rep.name))

# ============================================================ J 配置键可达性
# ★「定义了但没人读」的配置键 = 装饰品：用户改了它却毫无效果，而且
#   下一次审计也看不出来。本类判据：DEFAULT_CONFIG 里的每个键，在
#   **DEFAULT_CONFIG 块之外**的源码里至少出现一次（作为字符串字面量）。
#   留一张豁免表（确实要预留的键），两向对账。
print("── J 配置键可达性 ──")
_dccfg = _AST   # ★ 复用（perf 2026-10-28）
_dc_node = None
for _n in ast.walk(_dccfg):
    if isinstance(_n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "DEFAULT_CONFIG"
            for t in _n.targets):
        _dc_node = _n.value
        break
_KEYS = []


def _walk_keys(node, prefix=""):
    if isinstance(node, ast.Dict):
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                path = (prefix + "." + k.value) if prefix else k.value
                _KEYS.append((path, k.lineno))
                _walk_keys(v, path)


if _dc_node is not None:
    _walk_keys(_dc_node)
ck("J1 ★ DEFAULT_CONFIG 抠到键（非空）", len(_KEYS) > 5, "抠到 %d 个" % len(_KEYS))
_dc_lo = min(l for _, l in _KEYS) if _KEYS else 0
_dc_hi = (max(l for _, l in _KEYS) if _KEYS else 0) + 2
_CFG_EXEMPT = set(getattr(mod, "_AUDIT_CONFIG_EXEMPT", ()) or ())
# ★ [perf 2026-10-28] 原实现每个配置键都扫一遍 33k 行 LINES（≈700 键 × 33k 行
#   = O(键数×行数)，实测是第三大热点）。改为**一次**扫描 DEFAULT_CONFIG 块之外的
#   引号字面量集合，逐键 O(1) 查表 —— 判据语义不变（"key" / 'key' / ['key'] 都覆盖）。
_QUOTED_OUTSIDE = set()
for _i, _l in enumerate(LINES, 1):
    if _dc_lo <= _i <= _dc_hi:
        continue
    _QUOTED_OUTSIDE.update(re.findall(r'"([^"]*)"', _l))
    _QUOTED_OUTSIDE.update(re.findall(r"'([^']*)'", _l))
_unread = []
for _path, _ln in _KEYS:
    _leaf = _path.split(".")[-1]
    if _leaf not in _QUOTED_OUTSIDE and _path not in _CFG_EXEMPT:
        _unread.append(_path)
ck("J2 ★ 每个配置键都有人读（否则是装饰品）", not _unread,
   "没人读：" + repr(_unread))
_stale_cfg = sorted(_CFG_EXEMPT - {p for p, _ in _KEYS})
ck("J3 配置豁免表无过期项", not _stale_cfg, "过期：" + repr(_stale_cfg))
ck("J4 `_AUDIT_CONFIG_EXEMPT` 存在（登记表本身要有出口）",
   getattr(mod, "_AUDIT_CONFIG_EXEMPT", None) is not None, "常量不存在")

# ============================================================ K thinking stage
# ★ 审计发现的第 3 类真问题：15 个 `api.thinking.stages.*` 键**永远选不中**，
#   因为调用点根本没传 `stage=`（一律掉回 default）⇒ 用户改配置毫无效果。
#   判据四向：声明的键都要能选到 / 接线不改行为 / 无拼写错 / 传的都要有声明。
print("── K thinking stage 接线 ──")
_TH_CFG = (mod.DEFAULT_CONFIG.get("api") or {}).get("thinking") or {}
_TH_STAGES = dict(_TH_CFG.get("stages") or {})
_TH_DEF = _TH_CFG.get("default")
# ★ [perf 2026-10-28] 复用 _IDX 一次遍历建好的 stage 索引（原先再 ast.walk 全文）
_lit_stages = set(_IDX["stages"])
_wired = dict(_IDX["wired"])
ck("K1 ★ 声明过的 thinking stage 都能被选中（不被静默忽略）",
   set(_TH_STAGES) <= (_lit_stages | set(_wired)),
   "永远选不中：" + repr(sorted(set(_TH_STAGES) - _lit_stages - set(_wired))))
ck("K2 ★ 接线不改行为（新接线的 key 出厂值 == thinking.default）",
   all(_TH_STAGES.get(k) == _TH_DEF for k in _wired),
   "会改行为的 key：" + repr([k for k in _wired
                              if _TH_STAGES.get(k) != _TH_DEF]))
ck("K3 `_thinking_stage` 的第 2 实参都已在配置里声明（拼写守卫）",
   set(_wired) <= set(_TH_STAGES),
   "未声明：" + repr(sorted(set(_wired) - set(_TH_STAGES))))
ck("K4 ★ 代码里传的字面 stage 都必须在配置里声明（否则静默掉回 default）",
   _lit_stages <= set(_TH_STAGES),
   "传了但没声明：" + repr(sorted(_lit_stages - set(_TH_STAGES))))
ck("K5 抽样非空（防空过）", bool(_wired) and bool(_lit_stages),
   "wired=%d lit=%d" % (len(_wired), len(_lit_stages)))

# ============================================================ L 模型 id
# ★ 一类 bug，不是一个点：凡「读模型返回的 id、再按本地 1..N 对齐」的地方，
#   都可能因为模型给 0 起而**整票错位一格、且完全无声**（v1.23.3 实测）。
#   做成机械判据：这些调用点所在函数体里必须出现 `_normalize_judgment_ids(`。
print("── L 模型返回的 id 归一化 ──")


def _unnormalized_id_sites(txtx):
    """返回 [(函数名, 行号)]：读了模型返回的 id 但**没有**归一化的位置。"""
    _bad = []
    _tr = _parse_cached(txtx)
    _L = txtx.split(chr(10))
    for _fn in ast.walk(_tr):
        if not isinstance(_fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        _body = chr(10).join(_L[_fn.lineno - 1:_fn.end_lineno])
        # 两条合法的归一化出口：票 id（按基准）与子问题 id（按位置重编号）。
        if ("_normalize_judgment_ids(" in _body
                or "_canonical_sub_ids(" in _body):
            continue
        for _n in ast.walk(_fn):
            # 形状：int(<expr>.get("id" ...))
            if not (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
                    and _n.func.id == "int" and _n.args):
                continue
            _a = _n.args[0]
            if (isinstance(_a, ast.Call) and isinstance(_a.func, ast.Attribute)
                    and _a.func.attr == "get" and _a.args
                    and isinstance(_a.args[0], ast.Constant)
                    and _a.args[0].value == "id"):
                _bad.append((_fn.name, _n.lineno))
    return _bad


ck("L1 ★ 存在纯函数 `_normalize_judgment_ids`",
   hasattr(mod, "_normalize_judgment_ids"), "改前版本没有这个符号")
_bad_sites = _unnormalized_id_sites(txt)
ck("L2 ★ 所有「读模型返回的 id」的调用点都过了归一化", not _bad_sites,
   "未归一化：" + repr(_bad_sites))
_N = [i for i, l in enumerate(LINES, 1) if "int(it.get(" in l
      and chr(34) + "id" + chr(34) in l]
ck("L2.b 抽样非空（防空过）", len(_N) >= 2,
   "命中 %d 处（应 ≥2：多票 + 单票）" % len(_N))
_SYN = ("def f(it):" + chr(10) + "    sid = int(it.get(" + chr(34) + "id"
        + chr(34) + ", 0))" + chr(10) + "    return sid" + chr(10))
ckt = _unnormalized_id_sites(_SYN)
ck("L3 自检：合成源码（一处未归一化）必须被报出", len(ckt) == 1, repr(ckt))
_SYN2 = ("def g(it):" + chr(10) + "    sid = int(it.get(" + chr(34) + "id"
         + chr(34) + ", 0))" + chr(10)
         + "    return _normalize_judgment_ids(sid, 3)" + chr(10))
ck("L3.b 自检（负）：归一化过的合成源码**不**报出",
   not _unnormalized_id_sites(_SYN2), "")

# ============================================================ I 自检
# ★ 审计本身要有**判别力**：把每一类要抓的问题**真的造出来**，看对应判据是否判红。
#   变异体必须打在「判据读的那个东西」上（本项目踩过：给留痕前缀改名 ⇒ 判据仍命中）。
print("── I 自检（变异体：审计必须判红）──")
_NL = chr(10)
_MUT_I = (
    ("I1 ★ 抠掉 `to_dict` 的 web_results 出口 → A1.Pool 必须报未出口",
     '            d["web_results"] = self.web_results' + _NL,
     '            pass' + _NL,
     "A1"),
    ("I2 ★ 抠掉 dec_norm 的 not_do 白名单行 → B3 必须报被吞",
     '                "not_do": _norm_schema_not_do(dec.get("not_do")),' + _NL,
     '                pass' + _NL,
     "B3"),
    ("I4 ★ 把活类 `View` 也登记成死类 → A3 必须报过期登记",
     None, None, "A3"),
    ("I3 ★ 把证据钩子的圈号换回拆解序号 → E1 必须报不合规",
     '        return self._web_search("research_evidence", _qs, _rn,'
     + _NL,
     '        return self._web_search("research_evidence", _qs,'
     ' self._web_prep_seq,' + _NL,
     "E1"),
)
_TDI = HERE / "_audit_tmp"
_TDI.mkdir(exist_ok=True)
for _nm, _o, _n, _kind in _MUT_I:
    if _kind == "A3":
        # ★ [perf 2026-10-28] 不再为变异体重解析/重走全文 AST（原实现 ~2-3s）。
        #   变异点只是「把活类 View 也登记成死类」；A3 判据读的是
        #   「_d in _DEAD_FOUND」—— 用真实 _DEAD_FOUND + 注入登记表直接复算，
        #   与「文本替换后重跑 A3」等价（A2 已把真实死类集合算好）。
        _reg = set(_DEAD_REG) | {"View"}
        _red = ("View" in _reg) and ("View" not in _DEAD_FOUND)
        ck(_nm, _red, "" if _red else "过期登记没被判红")
        continue
    if txt.count(_o) != 1:
        ck(_nm[:3] + " 变异体可构造", False,
           "锚点命中 %d 次（应 1）：%r" % (txt.count(_o), _o[:40]))
        continue
    if _kind == "I3":
        # ★ [perf 2026-10-28] 变异体只需判 E1 对「第 3 实参=self._web_prep_seq」
        #   的反应；用最小合成片段打 _round_args 即可（原实现重解析 1.6MB 全文）。
        _syn = ('class X:' + _NL
                + '    def f(self, _qs):' + _NL
                + '        return self._web_search("research_evidence", _qs,'
                + ' self._web_prep_seq, 1)' + _NL)
        _, _bd = _round_args(_syn)
        ck(_nm, bool(_bd), "变异体下判据**没判红**（审计无判别力）"
           if not _bd else "")
        continue
    _mt = txt.replace(_o, _n)
    _mp = _TDI / ("mut_%s.py" % _kind)
    _mp.write_bytes(_mt.replace("\n", "\r\n").encode("utf-8"))
    _red = False
    try:
        if _kind == "A1":
            _sp = importlib.util.spec_from_file_location("mut_i_A1", str(_mp))
            _mm = importlib.util.module_from_spec(_sp)
            sys.modules["mut_i_A1"] = _mm
            _sp.loader.exec_module(_mm)
            _r = _export_miss(_mm).get("Pool") or ([], [], "")
            _red = "web_results" in _r[0]
        elif _kind == "B3":
            _lk = _norm_keys("dec_norm", _mt.split("\n"))
            _sk = _schema_keys("decidable_product", _mt.split("\n"))
            _red = bool(_sk - _lk)
        else:
            _, _bd = _round_args(_mt)
            _red = bool(_bd)
    except Exception as _e:  # noqa: BLE001
        _red = True
    ck(_nm, _red, "变异体下判据**没判红**（审计无判别力）" if not _red else "")

# ============================================================ 汇总
print()
for t, ok, note in R:
    print(("  ✓ " if ok else "  ✗ ") + t + (("　" + str(note)[:130])
                                            if note and not ok else ""))
_p = sum(1 for _, ok, _ in R if ok)
print("\nAUDIT PASS %d / FAIL %d  （%s）" % (_p, len(R) - _p, SRC.name))
sys.exit(0 if _p == len(R) else 1)
