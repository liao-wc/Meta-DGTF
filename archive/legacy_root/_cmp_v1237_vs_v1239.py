# -*- coding: utf-8 -*-
"""对照 v1.23.7 旧产物 与 v1.23.9 新产物（同题），逐项验四件事。

  ① 取向分流：落地层标题是 `## 落地层（decision 模式）` 还是 `## 落地层`
  ② 空节（v1.23.8 守卫 1）
  ③ 头部「**停止**：自然 n / 被截断 m」（v1.23.8 守卫 2）
  ④ 「决定不消解」重复合并（v1.23.8 守卫 3）

产物用**最新**（按 st_mtime 取），不写死文件名。
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE / "outputs" / "20261009_093317_新中国的成立时间是什么时候.md"


def _sections(txt):
    parts = re.split(r"(?m)^(#{3,4} .*)$", txt)
    out = []
    for i in range(1, len(parts) - 1, 2):
        out.append((parts[i].strip(), len(parts[i + 1].strip())))
    return out


def _probe(p: Path):
    t = p.read_text(encoding="utf-8", errors="replace")
    r = {"file": p.name}
    r["行数"] = t.count("\n") + 1
    r["取向模板"] = ("decision" if "## 落地层（decision 模式）" in t else
                     ("boundary" if "## 落地层" in t else "无落地层"))
    body = t.split("## 附录")[0]
    r["空节"] = [s for s, n in _sections(body) if n == 0]
    m = re.search(r"^\*\*停止\*\*：.*$", t, re.M)
    r["停因行"] = m.group(0) if m else "（无）"
    r["停因行数"] = len(re.findall(r"^\*\*停止\*\*：", t, re.M))
    r["决定不消解_条数"] = len(re.findall(r"^- .*（(?:explicit|intuitive)\)$",
                                          body, re.M))
    r["去重标注"] = "有" if "条同 target 重复" in t else "无"
    r["行动清单段"] = "有" if "### 二、行动清单" in t else "无"
    r["负责人行数"] = len(re.findall(r"^\s*- 负责人：", t, re.M))
    r["资源行"] = (re.search(r"^\*\*资源\*\*：.*$", t, re.M) or
                 [None])[0] if re.search(r"^\*\*资源\*\*：.*$", t, re.M) else "（无）"
    return r


def main():
    _outs = sorted((HERE / "outputs").glob("*.md"), key=lambda x: x.stat().st_mtime)
    NEW = _outs[-1]
    print("旧产物 =", OLD.name)
    print("新产物 =", NEW.name)
    print()
    a, b = _probe(OLD), _probe(NEW)
    keys = list(a)
    for k in keys:
        va, vb = a[k], b[k]
        flag = "  ← 变了" if va != vb else ""
        print(f"{k}")
        print(f"  旧: {va}")
        print(f"  新: {vb}{flag}")


main()
