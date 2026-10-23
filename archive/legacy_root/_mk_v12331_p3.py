#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.31 补丁 · 第 3+4 阶段：EML 渲染 + 配置段。

★ 用 `@@NL@@` 占位再替换成 2 字符的 `\\n` —— 直接在三引号里写 `\\n`
  会被 Python 先解析成真换行，注入目标文件后就成语法错（本轮已踩一次）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.31.py"
BSNL = chr(92) + "n"          # 目标文件里要的 2 字符字面：反斜杠 + n


def _load(p=SRC):
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "含 CRCRLF"
    return b.decode("utf-8").replace("\r\n", "\n")


def _save(s, p=SRC):
    assert "\r\r\n" not in s
    p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))


def rep(s, old, new, what, expect=1):
    _o = old.replace("@@NL@@", BSNL)
    _n = new.replace("@@NL@@", BSNL)
    n = s.count(_o)
    assert n == expect, "%s：命中 %d 次（要求 %d）" % (what, n, expect)
    return s.replace(_n if False else _o, _n)


OLD_H = '''        if _duty_lines:
            f.write("**层职责（LDG · 停止处实算）**：@@NL@@")
            for _dl in _duty_lines:
                f.write(f"{_dl}@@NL@@")
            f.write("@@NL@@")'''

NEW_H = '''        if _duty_lines:
            f.write("**层职责（LDG · 停止处实算）**：@@NL@@")
            for _dl in _duty_lines:
                f.write(f"{_dl}@@NL@@")
            f.write("@@NL@@")
        # ★ [EML] 本次记忆：用了哪几条经验、哪几条真生效、跑后写进去什么。
        #   ★ 它是**留痕**（读数），不是打分：不排序、不给「学习效果」分数。
        _pbk = result.get("playbook") or {}
        if _pbk and not _pbk.get("error"):
            f.write("**本次记忆（EML 经验回路）**：@@NL@@")
            f.write(f"  - 模式：`{_pbk.get('mode')}`（off 不读不写 / "
                    f"shadow 只记不生效 / on 生效）@@NL@@")
            _u = _pbk.get("used") or []
            _uids = "、".join(str(x.get("id")) for x in _u[:6])
            f.write(f"  - 读到（active）{len(_u)} 条"
                    f"{'：' + _uids if _uids else ''}@@NL@@")
            _ap = _pbk.get("applied") or []
            f.write(f"  - **真生效 {len(_ap)} 条**"
                    f"{'：' + str(_ap[:4]) if _ap else '（shadow 模式下恒为 0 —— 这是设计，不是失效）'}"
                    f"@@NL@@")
            f.write(f"  - 跑后过闸新增 {len(_pbk.get('merged') or [])} 条 / "
                    f"被闸拒 {len(_pbk.get('gated_out') or [])} 条 / "
                    f"升级 {len(_pbk.get('promoted') or [])} / "
                    f"遗忘 {len(_pbk.get('retired') or [])} / "
                    f"库内 {_pbk.get('n_playbook', 0)} 条@@NL@@")
            _go = _pbk.get("gated_out") or []
            if _go:
                _cnt = {}
                for _g in _go:
                    _k = _g.get("why", "?")
                    _cnt[_k] = _cnt.get(_k, 0) + 1
                f.write("      ↳ 被闸拒的原因分类："
                        + "、".join("%s×%d" % (k, v)
                                    for k, v in sorted(_cnt.items()))
                        + "@@NL@@")
            f.write("@@NL@@")'''

NEW_CFG = '''        "remedy_rounds": 1,
    },

    "playbook": {
        # [EML] 经验记忆回路：跨跑**储存记忆**并让下次跑用它。
        #   mode：off（不读不写）/ shadow（**出厂默认**：只记不生效 ⇒
        #         零行为差）/ on（生效：只作用于调度与守卫阈值，不碰答案）。
        #   dir：记忆库目录（默认仓库根 `dgtf_memory/`）。
        #   top_k / promote_n：每次读几条 / 同向证据几次才 shadow→active。
        #   halflife_days：检索排序与遗忘共用的半衰期（与 auto 同源）。
        #   ★ 学坏防线：新条目一律 shadow；只省成本（quality_delta≤0 且
        #     cost_delta<0）**不许**升级；遗忘只改状态位、不删行。
        "mode": "shadow",
        "dir": "",
        "top_k": 3,
        "promote_n": 3,
        "halflife_days": 14.0,
    },'''

OLD_CFG = '''        "remedy_rounds": 1,
    },'''


def main():
    s = _load()
    s = rep(s, OLD_H, NEW_H, "头部 EML 块")
    s = rep(s, OLD_CFG, NEW_CFG, "playbook 配置段")
    _save(s)
    print("OK 第 3+4 阶段（EML 渲染 + 配置）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert "**本次记忆（EML 经验回路）**" in s2
    assert '"playbook": {' in s2 and '"mode": "shadow",' in s2
    print("复读校验通过")


if __name__ == "__main__":
    main()
