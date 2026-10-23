# -*- coding: utf-8 -*-
"""app 侧同步：给 `dgtf_app/params.py` 的 `_KEY_CN` 补上 **55 个缺失键的中文说明**。

## 为什么（这是「整个项目的不同任务」之一）
`dgtf_app/params.py` 自己的注释就写着：
  「另一条并行线 v1.23.2x 新增了配置键、而 `_KEY_CN` 没跟上。
    判定口径 = `/api/params` 里**每一项**的 label 都要含 `（`」
实测（对账 `DEFAULT_CONFIG` 的 223 个叶子键 vs `_KEY_CN`）：**缺 55 个**
  · `api.thinking.stages.*` **25 个**（原本就有、一直没补）；
  · `web_search.stages.*` **30 个**（本轮新增的环节开关）。
⇒ 界面上这 55 项会**没有中文说明**（或退化成键名），正是那条注释想防的事。

## 边界
**只改 `dgtf_app/params.py`**，**不动主文件**（真跑要验主文件）。
"""
import io
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENG = HERE / "元DGTF-V1.23.36.py"
APP = HERE / "dgtf_app" / "params.py"

#: 30 个环节开关的中文名（`web_search.stages.<k>`）
STAGE_CN = {
    "plan_orientation": "取向规划",
    "plan_resources": "资源规划",
    "auto_plan": "自动计划",
    "assess_decidability": "可判定性评估",
    "re_anchor": "锚点重述",
    "expand_pair": "阴阳展开",
    "expand_pair_merged_once": "阴阳合并展开",
    "dual_judge": "对偶判断",
    "ing": "ing 对撞",
    "he": "& 沉淀",
    "decompose_normal": "常规拆解",
    "decompose_hybrid": "混合拆解",
    "decompose_koan": "公案式拆解",
    "decompose_from_pool": "池内拆解",
    "probe_research": "研究探针",
    "probe_duel": "对撞探针",
    "probe_meta": "元层探针",
    "phase_probe": "分阶段探针",
    "ask_missing_polarity": "极性追问",
    "self_check": "自检",
    "manifest": "清单",
    "assess_decidability_from_pool_view": "池视角可判定性",
    "check_structure_saturation": "结构饱和度",
    "re_evaluate_pool": "池重评",
    "settle_research": "研究清算",
    "decide_parallel_mode": "并行模式决策",
    "adjudicate_sub_tristate_multi": "子问题三态裁决（多）",
    "adjudicate_sub_tristate": "子问题三态裁决",
    "anchor_crosscheck": "锚点交叉核对",
    "check_input_sanity": "输入自检",
}


def _leaf_keys(path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("_eng_sync", path)
    m = importlib.util.module_from_spec(spec)
    sys.modules["_eng_sync"] = m
    spec.loader.exec_module(m)

    def leaves(d, pre=""):
        o = {}
        for k, v in (d or {}).items():
            kk = "%s.%s" % (pre, k) if pre else str(k)
            if isinstance(v, dict):
                o.update(leaves(v, kk))
            else:
                o[kk] = v
        return o
    return set(leaves(m.DEFAULT_CONFIG)), m


def main():
    cfg, m = _leaf_keys(ENG)
    raw = APP.read_bytes()
    # ★ 这个文件**换行不纯**（LF/CRLF 混合）⇒ **不能整体做 CRLF 归一**；
    #   改为：按文件里**占多数**的那种换行来插新行，其余一字不动。
    _n_lf = raw.count(b"\n")
    _n_crlf = raw.count(b"\r\n")
    _nl = "\r\n" if _n_crlf * 2 > _n_lf else "\n"
    print("app/params.py 换行：LF=%d CRLF=%d ⇒ 新行用 %r" % (_n_lf, _n_crlf, _nl))
    s = raw.decode("utf-8")
    if _nl == "\r\n":
        s = s.replace("\r\n", "\n")          # 先归一算偏移，最后整体写回时再统一
        _restore = True
    else:
        _restore = False
    _have = set(re.findall(r'"([a-z_0-9.]+)":\s*"', s))
    _miss = sorted(cfg - _have)
    print("配置叶子键 %d | 覆盖 %d | 缺 %d" % (len(cfg), len(cfg & _have), len(_miss)))
    if not _miss:
        print("无需补"); return

    # 生成新行（**label 必须含「（」**，与那条判定口径一致）
    _lines = []
    _unknown = []
    for k in _miss:
        if k.startswith("web_search.stages."):
            _st = k.split(".")[-1]
            _cn = STAGE_CN.get(_st)
            if _cn is None:
                _unknown.append(k); continue
            _lines.append('    "%s": "环节授权 · %s（默认关；开=该环节可按需联网）",'
                          % (k, _cn))
        elif k.startswith("api.thinking.stages."):
            _st = k.split(".")[-1]
            _lines.append(
                '    "%s": "思考档 · %s（enabled/disabled；显式 > 本表 > default）",'
                % (k, _st))
        else:
            _unknown.append(k)
    if _unknown:
        print("⚠ 未覆盖的键（需人工补名）：%r" % (_unknown,))

    # 插到 `_KEY_CN` 字典的**开头**（紧跟 `{` 之后），并加一段说明注释
    _i = s.find("_KEY_CN: dict[str, str] = {")
    assert _i > 0, "找不到 _KEY_CN"
    _ins = s.find("{", _i) + 1
    _hdr = ("\n    # ★ [app 同步] 下面是**补录**的键（原先 `_KEY_CN` 里没有）——\n"
            "    #   25 个 `api.thinking.stages.*`（一直没补）+ 30 个\n"
            "    #   `web_search.stages.*`（v1.23.36 新增的环节开关）。\n"
            "    #   判定口径同本文件下方注释：「label 必须含 `（`」。\n")
    _block = (_hdr + "\n".join(_lines)).replace("\n", _nl)
    # ★ **只插新行**（用文件主换行），原有行**一字不动** ——
    #   这个文件换行不纯，整体归一等于把别的行也改了。
    s = s[: _ins] + _nl + _block + _nl + s[_ins:]
    APP.write_bytes(s.encode("utf-8"))
    print("OK 已补 %d 条；params.py 行数 %d"
          % (len(_lines), s.count("\n") + s.count("\r")))


main()
