# -*- coding: utf-8 -*-
"""[v1.23.27 Step8] E3 · covers 双查 + E4 · link 反查 + E5 · 双向判据。

设计（`_设计_五机制算法重构_v12326.md` §3.5 E3/E4/E5）：

E3 —— `covers` 语义校验（修「只查编号范围」）：
    有了 `AspectUnit.id`（A1）与 `BeliefItem.id`（D1），`covers` 变成
    **可判定引用**：
      · `c` 命中 id 集合，但 `sim3(question, target.text) < covers_thr`
        ⇒ 报 `probe_no_target_covered`（★ 编号对但语义错）
      · `c` **不在任何 id 集合里** ⇒ 报 `probe_covers_bad_ref`（编号不存在）
  ★ 负对照（写进冒烟）：covers 乱指 T1（编号在范围内但语义无关）⇒ **必须判红**。

E4 —— `link` 语义校验（现在只查非空）：
    `link` 必须能**反查**到池内条目（`AspectUnit.ref` / `BeliefItem.ground` /
    上游 view 的 `manifest`），否则报 `probe_link_dangling`。
    **只留痕，不拦**（红线「未对齐合法」）—— 所以它**不进** quality_verdict
    的拦截项，只进 flags。

E5 —— 修方向矛盾（提示词 ↔ 判据对齐）：
    · 提示词改为：「若你判断**所有未触及项都推不动**，返回 `{"probes": []}`，
      并在 `no_probe_reason` 里说明为什么」——**给「空」一个正当出口**；
    · 判据 `probe_return_empty` **改为双向**：
        - 空 **且** `no_probe_reason` 非空 **且** 理由与 untouched 清单
          **对得上** ⇒ 通过（记 `honest_empty`）
        - 空 **且** 理由空洞/缺失 ⇒ 记 `lazy_empty`（留痕，**不罚分**）

★ 红线核对：未对齐合法（link dangling 只留痕）；判据落在行为上（每类新报错
  都可负对照）；「悬置不打分」（E5 的 honest/lazy 是**姿态标注**，不是分数）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.27.py"

raw = SRC.read_bytes()
txt = raw.decode("utf-8")
assert txt.count("\r\n") == txt.count("\n"), "源文件不是纯 CRLF"
assert "\r\r\n" not in txt

lf = txt.replace("\r\n", "\n")
orig_lf = lf
HITS = []


def sub(anchor, new, tag, count=1):
    global lf
    n = lf.count(anchor)
    assert n == count, "%s：锚点命中 %d 次（要求 %d）\n---\n%s" % (
        tag, n, count, anchor[:260])
    lf = lf.replace(anchor, new)
    HITS.append((tag, n))


# ══════════════════════════════════════════════════════════════════
# 1. 模块级常量：covers 的语义下限 + 空探针理由的最小长度
# ══════════════════════════════════════════════════════════════════
sub(
    "_GAIN_ASSIGN_MIN = 0.15\n",
    "_GAIN_ASSIGN_MIN = 0.15\n"
    "#: [E3] `covers` 命中 id 后，探针问题与靶子文本的 sim3 下限。\n"
    "#: ★ 低于它 = 「编号对、语义错」⇒ 报 probe_no_target_covered。\n"
    "#:   与 `_COV_OVERLAP_MIN`（0.50，语言判据）分开：那是给「无 id」\n"
    "#:   场景兜底的宽尺子，这是给「有 id」场景的**严尺子**。\n"
    "_COVERS_SIM_MIN = 0.30\n"
    "#: [E5] `no_probe_reason` 的最小字数；短于它 = 空洞理由 ⇒ lazy_empty。\n"
    "_NO_PROBE_REASON_MIN = 8\n",
    "E3/E5 常量")

# ══════════════════════════════════════════════════════════════════
# 2. E3+E4+E5：_quality_check 里的探针段整体重写
# ══════════════════════════════════════════════════════════════════
sub(
    "        if (self.entry == \"1\" and view.untouched and view.probes):\n"
    "            untouched_items = [str(u.get(\"desc\", \"\")).strip()\n"
    "                               for u in view.untouched\n"
    "                               if str(u.get(\"desc\", \"\")).strip()]\n"
    "            has_touch = False\n"
    "            covers_seen = False\n"
    "            for p in view.probes:\n"
    "                _pq = str(p.get(\"question\", \"\")).strip()\n"
    "                _pc = [str(x).strip() for x in (p.get(\"covers\") or [])\n"
    "                       if str(x).strip()]\n"
    "                for c in (p.get(\"covers\") or []):\n"
    "                    c = str(c).strip()\n"
    "                    if not c:\n"
    "                        continue\n"
    "                    covers_seen = True\n"
    "                    m = re.match(r\"^T?(\\d+)$\", c)\n"
    "                    if m:\n"
    "                        idx = int(m.group(1)) - 1\n"
    "                        if 0 <= idx < len(untouched_items):\n"
    "                            # ★ 编号合法只是**必要条件**：还要语义对得上。\n"
    "                            #   原来这里直接 has_touch = True，covers 乱指\n"
    "                            #   T1 也算覆盖 —— 负对照实测不报。\n"
    "                            #   比较对象是**探针问题 vs 该项**（不是两项互比）。\n"
    "                            if (_similar(_pq, untouched_items[idx],\n"
    "                                         _QC_DUP_SIM)\n"
    "                                    or _overlap_coef(_pq,\n"
    "                                                     untouched_items[idx])\n"
    "                                    >= _COV_OVERLAP_MIN):\n"
    "                                has_touch = True\n"
    "                                break\n"
    "                    else:\n"
    "                        if any(_similar(c, d, _QC_DUP_SIM)\n"
    "                               for d in untouched_items):\n"
    "                            has_touch = True\n"
    "                            break\n"
    "                if has_touch:\n"
    "                    break\n"
    "            if not covers_seen:\n"
    "                has_touch = any(\n"
    "                    _similar(p.get(\"question\", \"\"), u.get(\"desc\", \"\"), 0.6)\n"
    "                    for p in view.probes for u in view.untouched)\n"
    "            if not has_touch:\n"
    "                flags.append(\"probe_no_target_covered\")\n",
    "        if (self.entry == \"1\" and view.untouched and view.probes):\n"
    "            untouched_items = [str(u.get(\"desc\", \"\")).strip()\n"
    "                               for u in view.untouched\n"
    "                               if str(u.get(\"desc\", \"\")).strip()]\n"
    "            # [E3] 靶子集合：**id → 文本**。优先用 A1 的 AspectUnit.id\n"
    "            #   （本层未触及项的稳定编号）；没有 id 时退回「T{i+1}」\n"
    "            #   这个**位置编号** —— 两种都要认，否则老产物会全判 bad_ref。\n"
    "            _cov_targets: dict = {}\n"
    "            for _i, _u in enumerate(view.untouched or []):\n"
    "                _t = str(_u.get(\"desc\", \"\")).strip()\n"
    "                if not _t:\n"
    "                    continue\n"
    "                _uid = str(_u.get(\"id\", \"\") or \"\").strip()\n"
    "                _pos = \"T%d\" % (_i + 1)\n"
    "                _cov_targets[_pos] = _t\n"
    "                if _uid:\n"
    "                    _cov_targets[_uid] = _t\n"
    "                elif _uid is None or _uid == \"\":\n"
    "                    # 位置编号与裸数字两种写法都收（模型老习惯）\n"
    "                    _cov_targets[str(_i + 1)] = _t\n"
    "            has_touch = False\n"
    "            covers_seen = False\n"
    "            bad_ref = False\n"
    "            for p in view.probes:\n"
    "                _pq = str(p.get(\"question\", \"\")).strip()\n"
    "                for c in (p.get(\"covers\") or []):\n"
    "                    c = str(c).strip()\n"
    "                    if not c:\n"
    "                        continue\n"
    "                    covers_seen = True\n"
    "                    _tgt = _cov_targets.get(c)\n"
    "                    if _tgt is None:\n"
    "                        # [E3] 归一化后再试一次（去 T 前缀 / 去 # 号）\n"
    "                        _c2 = re.sub(r\"^#\", \"\", re.sub(r\"^T(?=\\d)\", \"\", c))\n"
    "                        _tgt = _cov_targets.get(_c2)\n"
    "                    if _tgt is None:\n"
    "                        # [E3] ★ 编号**不在任何 id 集合里** ⇒ 报 bad_ref。\n"
    "                        #   这是「只查编号范围」永远抓不到的一类：\n"
    "                        #   编号越界会被当「没覆盖」，但**不区分**是\n"
    "                        #   「模型瞎指」还是「模型指对了但没写全覆盖」。\n"
    "                        bad_ref = True\n"
    "                        continue\n"
    "                    # [E3] 编号对只是**必要条件**：还要**语义对得上**。\n"
    "                    if (_similar(_pq, _tgt, _QC_DUP_SIM)\n"
    "                            or _sim3(_pq, _tgt) >= _COVERS_SIM_MIN\n"
    "                            or _overlap_coef(_pq, _tgt)\n"
    "                            >= _COV_OVERLAP_MIN):\n"
    "                        has_touch = True\n"
    "                        break\n"
    "                if has_touch:\n"
    "                    break\n"
    "            if not covers_seen:\n"
    "                has_touch = any(\n"
    "                    _similar(p.get(\"question\", \"\"), u.get(\"desc\", \"\"), 0.6)\n"
    "                    for p in view.probes for u in view.untouched)\n"
    "            if bad_ref:\n"
    "                flags.append(\"probe_covers_bad_ref\")\n"
    "            if not has_touch:\n"
    "                flags.append(\"probe_no_target_covered\")\n"
    "\n"
    "        # ── [E4] link 反查（**只留痕，不拦**：红线「未对齐合法」） ──\n"
    "        #  ★ 反查靶子 = 池内条目的 id（Amp/Thread/Probe/AspectUnit）\n"
    "        #    + 上游 manifest 的文本片段。查不到只记 probe_link_dangling，\n"
    "        #    **不进** quality_verdict 的拦截项。\n"
    "        try:\n"
    "            _link_ids = set()\n"
    "            for _i, _a in enumerate(pool.amps or [], 1):\n"
    "                _link_ids.add(str(_a.get(\"id\") or (\"amp#%d\" % _i)))\n"
    "            for _i, _t2 in enumerate(pool.threads or [], 1):\n"
    "                _link_ids.add(str(_t2.get(\"id\") or (\"th#%d\" % _i)))\n"
    "            for _i, _p2 in enumerate(pool.probes or [], 1):\n"
    "                _link_ids.add(str(_p2.get(\"id\") or (\"probe#%d\" % _i)))\n"
    "            for _u2 in (view.aspect_units or []):\n"
    "                _uid2 = str(_u2.get(\"id\") or \"\").strip()\n"
    "                if _uid2:\n"
    "                    _link_ids.add(_uid2)\n"
    "            _dangling = 0\n"
    "            for _p3 in (view.probes or []):\n"
    "                _lk = str(_p3.get(\"link\", \"\")).strip()\n"
    "                if not _lk:\n"
    "                    continue\n"
    "                _hit = False\n"
    "                for _lid in _link_ids:\n"
    "                    if _lid and re.search(\n"
    "                            r\"(?<![\\w#])\" + re.escape(_lid) + r\"(?![\\w#])\",\n"
    "                            _lk):\n"
    "                        _hit = True\n"
    "                        break\n"
    "                if not _hit:\n"
    "                    _dangling += 1\n"
    "            if _dangling:\n"
    "                flags.append(\"probe_link_dangling(%d)\" % _dangling)\n"
    "        except Exception:\n"
    "            pass\n"
    "\n"
    "        # ── [E5] 空探针的**双向**判据：honest_empty vs lazy_empty ──\n"
    "        #  ★ 旧行为：`probe_return_empty` 一律罚空 —— 与提示词\n"
    "        #    「推不动就返回空数组」**方向正好相反**。\n"
    "        #  ★ 新行为：空 + 有理由 + 理由与 untouched 对得上 ⇒ honest_empty\n"
    "        #    （**不罚**）；空 + 理由空洞/缺失 ⇒ lazy_empty（**留痕不罚分**）。\n"
    "        if \"probe_return_empty\" in flags:\n"
    "            _reason = \"\"\n"
    "            for _p4 in (view.probes or []):\n"
    "                _reason = str(_p4.get(\"no_probe_reason\", \"\") or \"\").strip()\n"
    "                if _reason:\n"
    "                    break\n"
    "            _vr = str(getattr(view, \"no_probe_reason\", \"\") or \"\").strip()\n"
    "            _reason = _reason or _vr\n"
    "            _ut_all = [str(u.get(\"desc\", \"\")).strip()\n"
    "                       for u in (view.untouched or [])\n"
    "                       if str(u.get(\"desc\", \"\")).strip()]\n"
    "            _honest = False\n"
    "            if len(_reason) >= _NO_PROBE_REASON_MIN:\n"
    "                # ★ 「对得上」= 理由里提到了 untouched 清单里至少一项\n"
    "                #   的语义内容（用 sim3 严尺子 + 词面兜底）。\n"
    "                #   只是「写了一段长理由」不算 —— 那是换个方式空洞。\n"
    "                _honest = any(\n"
    "                    _sim3(_reason, _u) >= _COVERS_SIM_MIN\n"
    "                    for _u in _ut_all) if _ut_all else False\n"
    "            if _honest:\n"
    "                flags = [f for f in flags if f != \"probe_return_empty\"]\n"
    "                flags.append(\"honest_empty\")\n"
    "            else:\n"
    "                flags = [f for f in flags if f != \"probe_return_empty\"]\n"
    "                flags.append(\"lazy_empty\")\n",
    "E3/E4/E5 探针段")

# ══════════════════════════════════════════════════════════════════
# 3. E5 提示词：给「空」一个正当出口
# ══════════════════════════════════════════════════════════════════
sub(
    "            \"3. 推不动就让 probes 返回空数组——宁可空，不要凑数\\n\"\n",
    "            \"3. ★ 若你判断**所有未触及项都推不动**，返回 "
    "\\\"probes\\\": []，\\n\"\n"
    "            \"   并在 no_probe_reason 里说明**为什么推不动**（指到具体"
    "哪几项）。\\n\"\n"
    "            \"   ★ 空探针配得上理由就是**合格答案**，不扣分；\\n\"\n"
    "            \"   空探针 + 空洞理由（或不写理由）会被记 lazy_empty。\\n\"\n"
    "            \"   宁可空，不要凑数——但要为『空』交代清楚。\\n\"\n",
    "E5 修行层提示词")

# ══════════════════════════════════════════════════════════════════
# 4. E5 研究层提示词同样加出口
# ══════════════════════════════════════════════════════════════════
sub(
    "        user += (\n"
    "            \"\\n\\n【本层选择】\\n\"\n"
    "            \"至少推进一件（碰一个子问题 / 新结构性 & / 提一条延迟）。\\n\"\n"
    "            \"延迟必须有回访条件；研究允许延迟，但不允许永远拖着。\\n\"\n"
    "        )\n",
    "        user += (\n"
    "            \"\\n\\n【本层选择】\\n\"\n"
    "            \"至少推进一件（碰一个子问题 / 新结构性 & / 提一条延迟）。\\n\"\n"
    "            \"延迟必须有回访条件；研究允许延迟，但不允许永远拖着。\\n\"\n"
    "            \"★ 若你判断所有未触及项都推不动：probes 可以返回 []，\\n\"\n"
    "            \"  但必须在 no_probe_reason 里写明**为什么**（指到具体哪几项）。\\n\"\n"
    "        )\n",
    "E5 研究层提示词")

out_lf = lf
assert out_lf != orig_lf, "没有任何改动"

out = out_lf.replace("\n", "\r\n")
assert "\r\r\n" not in out
SRC.write_bytes(out.encode("utf-8"))

chk = SRC.read_bytes().decode("utf-8")
assert chk.count("\r\n") == chk.count("\n")
assert "\r\r\n" not in chk

import re as _re
_TAG = _re.compile(r"\[v\d[^\]]*\]|(?<![A-Za-z0-9_\-])v\d+(?:\.\d+)*(?![A-Za-z0-9_\-])")
_s = chk.replace("\r\n", "\n")
_i = _s.index('"""')
_j = _s.index('"""', _i + 3)
_de = _s[: _j].count("\n")
_l = _s.split("\n")
_h = [k + 1 for k in range(_de + 1, len(_l))
      if _l[k].lstrip().startswith("#") and _TAG.search(_l[k])]
_t = [k + 1 for k in range(_de + 1, len(_l))
      if not _l[k].lstrip().startswith("#") and "#" in _l[k]
      and _TAG.search(_l[k].split("#", 1)[1])]
assert not _h and not _t, "本步引入了版次批注：%s %s" % (_h, _t)

print("STEP8 OK  —— %d 处替换" % len(HITS))
for _tag, _n in HITS:
    print("  · %-30s x%d" % (_tag, _n))
print("  size %d -> %d bytes" % (len(raw), len(chk.encode('utf-8'))))
