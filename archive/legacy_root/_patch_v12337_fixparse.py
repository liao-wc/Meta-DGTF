# -*- coding: utf-8 -*-
"""修「按需协议」降级分支的真缺口（探针抓到）+ 同步源头补丁脚本。

## 缺口
`parse_web_need` 的**降级分支**（JSON 解不出时逐行取）里有一句
`len(_l) > 2` —— 它把**单字/双字**的查询滤掉（如「丙」）。
而这一支存在的意义正是「**环节写了、但格式不标准**」⇒ 那时**更不该丢需求**。

## 修法
把长度阈值换成**只滤 JSON 残渣**：
  · 空行；· 以 `queries` 开头的键行；· 纯括号/逗号构成的行。
其余**一律收**（真正的句子/词会长于两个字符，而短词也该收）。

## 同步
同一个逻辑在**两处**：副本 `元DGTF-V1.23.37.py` 与**生成它的补丁脚本**
`_patch_v12336_webneed.py`（否则将来从脚本重建会把这个修复丢掉）。
"""
import io
from pathlib import Path

HERE = Path(__file__).resolve().parent
COPY = HERE / "元DGTF-V1.23.37.py"
SRC_PATCH = HERE / "_patch_v12336_webneed.py"

OLD = '''    # ② 退一步：逐行取（去掉 JSON 残渣与空行）
    _out = []
    for _l in _tail.split("\\n"):
        _l = _l.strip().strip('",[]{}')
        if _l and not _l.startswith("queries") and len(_l) > 2:
            _out.append(_l)
    return _out[:limit]'''

NEW = '''    # ② 退一步：逐行取（**只滤 JSON 残渣**，不设长度阈值）
    #   ★ 这里原先写的是 `len(_l) > 2` —— 它把「丙」这样的**单字查询滤掉了**，
    #     而这一支存在的意义正是「环节写了、但格式不标准」⇒ **更不该丢需求**
    #     （探针 `_probe_v12337_new.py` 抓到的真缺口）。
    _out = []
    for _l in _tail.split("\\n"):
        _l = _l.strip().strip('",')
        if not _l:
            continue
        if _l.startswith("queries"):
            continue
        if _l.strip("{}[]") == "":
            continue
        _out.append(_l)
    return _out[:limit]'''


def main():
    # ① 副本
    raw = COPY.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    n = s.count(OLD)
    assert n == 1, "副本锚点命中 %d 次" % n
    s = s.replace(OLD, NEW, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    COPY.write_bytes(out)
    print("OK 副本 V1.23.37 已修（降级分支不设长度阈值）；行数 %d" % out.count(b"\n"))

    # ② 源头补丁脚本（同一个逻辑的第二处）
    p = SRC_PATCH.read_text(encoding="utf-8")
    if "只滤 JSON 残渣" in p:
        print("源头脚本已是新版（跳过）")
    else:
        _old_in_patch = OLD.replace("\\n", "\\\\n")
        _new_in_patch = NEW.replace("\\n", "\\\\n")
        assert p.count(_old_in_patch) == 1, \
            "源头脚本锚点命中 %d 次（需人工核对）" % p.count(_old_in_patch)
        p = p.replace(_old_in_patch, _new_in_patch, 1)
        SRC_PATCH.write_text(p, encoding="utf-8")
        print("OK 源头补丁脚本已同步")


main()
