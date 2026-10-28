# -*- coding: utf-8 -*-
"""V2.2.7 → V2.2.8 补丁：产物落盘不再被「单层渲染异常」拖死。

背景（实测，不是推断）
----------------------
把本地链路的生成长度压到 stage 训练长度后，整跑第一次能跑完（70s / 13 次调用），
结果**产物没落盘**：

    ⚠️  保存失败：KeyError: 'anchor'
       本次结果**没有落盘**，上面的终端输出是唯一记录。

抓 traceback 定位到 `save_result()` 的逐层明细循环：
    · views["1"]（研究层）是标准 View.to_dict()，有 anchor
    · views["0"]（修行层）是 **zero_generation 模块的另一套结构**，
      键 = aspect_map/claim_gaps/duty/fact_contract/manifest/zero_generation …
      **没有 anchor / candidates / collision / amps / threads**
    渲染器对四层**假设同构**，直接 `v['anchor']` ⇒ KeyError ⇒ 整份产物丢失。

★ 这正是「修好一个锁会让被它挡住的 bug 显形」：本地跑以前根本跑不完
  （单次调用 110s 超时），这个 bug 一直被超时盖着。

改动（三处，全部只做降级与留痕，不改判定）
------------------------------------------
1. 逐层明细的**必填下标**改 `.get()` 兜底（anchor/candidates/collision/amps/threads）
2. 逐层明细**整块包 try/except**：一层崩了只降级该层（写明原因 + 原始字段留痕），
   不许拖累其他层、更不许拖累落盘 —— 与上面「落地层/显化层」同一条纪律
3. 落盘失败时：打印 traceback（原来只打印一行 `KeyError: 'anchor'`，没法定位）
   + **应急落盘**原始 result 到 outputs/_crash/（一整跑的读数不许白丢）
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "dgtf_engine" / "dgtf_v2" / "engine" / "Meta-DGTF-V2.2.7.py"
DST = ROOT / "dgtf_engine" / "dgtf_v2" / "engine" / "Meta-DGTF-V2.2.8.py"


def die(msg: str) -> None:
    print("❌ " + msg)
    sys.exit(1)


raw = SRC.read_bytes()
crlf = raw.count(b"\r\n")
lf = raw.count(b"\n")
if crlf != lf:
    die(f"源文件不是纯 CRLF（CRLF={crlf} LF={lf}）")
if DST.exists():
    die(f"目标已存在：{DST}")
shutil.copyfile(SRC, DST)

text = raw.decode("utf-8").replace("\r\n", "\n")
lines = text.split("\n")

# ───────────────────────── 1. 版本号（两处） ─────────────────────────
def sub1(old: str, new: str) -> None:
    """字面量替换：锚点必须命中**恰好一次**（命中 0 = 静默不改）。"""
    global text
    n = text.count(old)
    if n != 1:
        die(f"锚点命中 {n} 次（应为 1）：{old[:70]!r}")
    text = text.replace(old, new)
    print(f"  ✓ {old[:56]!r} → 已替换")


sub1('__version__ = "2.2.7"', '__version__ = "2.2.8"')
sub1("Meta-DGTF-道生三阶模型 · V2.2.7", "Meta-DGTF-道生三阶模型 · V2.2.8")
sub1("★ V2.2.7 补丁（新增读数，默认不改判定）：答案门 answer_gates。",
     "★ V2.2.8 补丁（产物落盘不再被单层渲染拖死）：逐层明细渲染失败只降级该层\n"
     "   （实测：0 层由 zero_generation 产出的是**另一套结构**、没有 anchor，\n"
     "     渲染器假设四层同构 ⇒ KeyError ⇒ 整份产物丢失）。\n"
     "★ V2.2.7 补丁（新增读数，默认不改判定）：答案门 answer_gates。")

# ────────────────── 2. 必填下标改 .get() 兜底 ──────────────────
# 只改 save_result 里逐层明细那几处；每处断言命中 1 次。
sub1('            f.write(f"**锚点**：{v[\'anchor\']}\\n\\n")',
     '            f.write(f"**锚点**：{v.get(\'anchor\') or \'（本层未产出锚点）\'}\\n\\n")')
sub1('            for c in v["candidates"]:',
     '            for c in (v.get("candidates") or []):')
sub1('            f.write(f"\\n**ing 对撞**：\\n\\n{v[\'collision\']}\\n\\n")',
     '            f.write(f"\\n**ing 对撞**：\\n\\n{v.get(\'collision\') or \'（无）\'}\\n\\n")')
sub1('            for a in v["amps"]:',
     '            for a in (v.get("amps") or []):')
sub1('            for t in v["threads"]:',
     '            for t in (v.get("threads") or []):')

# ────────────── 3. 逐层明细整块包 try/except（降级 + 留痕） ──────────────
ANCHOR = (
    '        for key in ("0", "1", "both", "all"):\n'
    '            v = result["views"].get(key)\n'
    '            if not v:\n'
    '                continue\n'
    '            f.write(f"### {_LAYER_LABEL.get(key, key)}层 `{key}`\\n\\n")\n'
)
n = text.count(ANCHOR)
if n != 1:
    die(f"逐层循环锚点命中 {n} 次（应为 1）")
i0 = text.index(ANCHOR)
head = text[:i0]
body_start = i0 + len(ANCHOR)

# 循环体结束：第一个缩进 < 12 的非空行
rest = text[body_start:]
rl = rest.split("\n")
j0 = None
for k, l in enumerate(rl):
    if not l.strip():
        continue
    if len(l) - len(l.lstrip()) < 12:
        j0 = k
        break
if j0 is None:
    die("找不到逐层循环体的结束位置")
if j0 < 50:
    die(f"循环体只有 {j0} 行，疑似锚点定位错了")

body = rl[:j0]
tail = "\n".join(rl[j0:])

# 循环体里不许有多行字面串（缩进会改内容）—— 逐行扫三引号
for _l in body:
    if '"""' in _l or "'''" in _l:
        die("循环体内含三引号字符串，缩进重构会改内容")

indented = [("    " + l) if l.strip() else l for l in body]

EXCEPT = [
    "            except Exception as _lde:",
    "                # ★ 一层渲染崩掉不许拖累**整份产物落盘**：其他层照常写，",
    "                #   这一层写明失败原因，并把原始字段列出来留痕 ——",
    "                #   否则「这层没内容」和「这层渲染崩了」在产物里长得一样。",
    "                f.write(f\"❌ 本层明细渲染失败：{type(_lde).__name__}: \"",
    "                         f\"{_lde}\\n\\n**原始字段留痕**：\\n\")",
    "                try:",
    "                    for _k in sorted(v.keys()):",
    "                        f.write(f\"- `{_k}`\\n\")",
    "                except Exception:",
    "                    pass",
    "                f.write(\"\\n---\\n\\n\")",
]
new_block = head + ANCHOR + "            try:\n" + "\n".join(indented) \
    + "\n" + "\n".join(EXCEPT) + "\n" + tail
text = new_block
print(f"  ✓ 逐层明细 {j0} 行已包进 try/except（降级 + 留痕）")

# ────────── 4. 落盘失败：打印 traceback + 应急落盘 ──────────
sub1('''    except Exception as e:
        print(f"\\n⚠️  保存失败：{type(e).__name__}: {e}")
        print("   本次结果**没有落盘**，上面的终端输出是唯一记录。")
        sys.exit(1)''',
     '''    except Exception as e:
        print(f"\\n⚠️  保存失败：{type(e).__name__}: {e}")
        # ★ 只打印一行 `KeyError: 'anchor'` 是定位不了的（实测就是靠外部
        #   monkeypatch 才拿到堆栈）⇒ 保存失败必须带 traceback。
        try:
            import traceback as _tb
            print(_tb.format_exc().strip()[-2500:])
        except Exception:
            pass
        _emergency_dump(result, cfg["output"]["save_dir"])
        sys.exit(1)''')

sub1('''        except Exception as e:
            print(f"⚠️ 保存失败：{e}")''',
     '''        except Exception as e:
            print(f"⚠️ 保存失败：{type(e).__name__}: {e}")
            try:
                import traceback as _tb
                print(_tb.format_exc().strip()[-2500:])
            except Exception:
                pass
            _emergency_dump(result, run_cfg["output"]["save_dir"])''')

# 应急落盘函数：放在 save_result 之前
sub1("def save_result(result: dict, save_dir: str = \"outputs\") -> Path:",
     '''def _emergency_dump(result: dict, save_dir: str) -> str:
    """渲染/落盘失败时把**原始 result** 应急写盘（不是产物，只是不让它消失）。

    ★ 为什么需要：一整跑要几十次 LLM 调用、十几分钟墙钟。渲染器崩在最后一
      步就把全部读数丢掉，代价太大了 —— 应急文件让「跑完了但没落盘」仍
      有可审计的原始记录。`default=str` 保证任何不可序列化的字段也不会让
      应急落盘本身再失败。
    """
    try:
        d = Path(save_dir) / "_crash"
        d.mkdir(parents=True, exist_ok=True)
        fp = d / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_unsaved.json")
        fp.write_text(json.dumps(result, ensure_ascii=False, default=str),
                      encoding="utf-8")
        print(f"   原始 result 已应急落盘：{fp}")
        return str(fp)
    except Exception as _ce:
        print(f"   应急落盘也失败：{_ce}")
        return ""


def save_result(result: dict, save_dir: str = "outputs") -> Path:''')

# ───────────────────────── 写回（纯 CRLF） ─────────────────────────
out = text.replace("\n", "\r\n").encode("utf-8")
if b"\r\r\n" in out:
    die("写出内容含 \\r\\r\\n")
DST.write_bytes(out)

chk = DST.read_bytes()
if chk.count(b"\r\n") != chk.count(b"\n"):
    die("目标不是纯 CRLF")
import ast  # noqa: E402
try:
    ast.parse(chk.decode("utf-8"))
except SyntaxError as e:
    die(f"语法错误：{e}")

print("─" * 60)
print(f"✅ {DST.name} 生成：{chk.count(b'\\n') + 1} 行，纯 CRLF，语法 OK")
