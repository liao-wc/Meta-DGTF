# -*- coding: utf-8 -*-
"""[v1.21.73 外部锚点对照跑臂] 同源两臂，只差 external_anchor.enabled。

为什么另写一个：`_arm_v72.py` 认得 cost_profile / mode / re_eval_every_n，
不认 `external_anchor`。而「同题、同配置、只差锚点开关」正是本轮要对照的
那一件事。本跑臂**不改引擎任何逻辑**，只在 load_config 之后覆盖 cfg 再 run。

用法：
  python _arm_v73.py <tag> <profile> <mode> "<rounds>" "<question>"

环境变量：
  V73_ANCHOR=<path>   给路径 → external_anchor.enabled=True（ON 臂）
                      不给   → 保持 yaml/默认（OFF 臂）

产出：
  v73arm_<tag>.log         完整 verbose 日志 + 结尾汇总
  v73arm_<tag>.full.json   packed 全量侧车（离线分析用）
  outputs/<时间>_<题目前缀>.md

★ 判据预注册在 `_anchor_prereg.json`，跑之前就写死了，跑完不许改。
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_dotenv(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_module():
    spec = importlib.util.spec_from_file_location(
        "dgtf73arm", HERE / "元DGTF-V1.21.73.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf73arm"] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    if len(sys.argv) < 6:
        print(__doc__)
        return 2
    tag, profile, mode, rounds = (sys.argv[1], sys.argv[2], sys.argv[3],
                                  sys.argv[4])
    question = " ".join(sys.argv[5:])
    load_dotenv(HERE / ".env")
    mod = load_module()
    cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))

    notes = []
    cfg["cost_profile"] = profile
    notes.append(f"cost_profile={profile}")

    anchor_path = os.environ.get("V73_ANCHOR", "").strip()
    if anchor_path:
        cfg["external_anchor"] = {
            "enabled": True, "path": anchor_path,
            "max_items": int(os.environ.get("V73_MAX_ITEMS", "12")),
            "crosscheck": True,
        }
        notes.append(f"锚点ON={anchor_path}")
    else:
        cfg["external_anchor"] = {"enabled": False, "path": "",
                                  "max_items": 12, "crosscheck": True}
        notes.append("锚点OFF")

    rmap = {}
    for part in rounds.split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            rmap[k.strip()] = int(v.strip())

    t0 = time.time()
    buf = io.StringIO()
    err = None
    res = None
    meta = None
    with contextlib.redirect_stdout(buf):
        try:
            print(f"🧪 跑臂 {tag}：{' | '.join(notes)} | mode={mode} "
                  f"| rounds={rounds}")
            print(f"题目：{question}")
            meta = mod.MetaDGTF(cfg)
            res = meta.run(question, route=list(rmap.keys()) or ["0", "1"],
                           rounds=rmap, parallel_mode=mode)
        except Exception:
            import traceback
            err = traceback.format_exc()
    dt = time.time() - t0
    log = buf.getvalue().replace("\r\n", "\n")

    tail = ["", "=" * 60,
            f"arm={tag} {' | '.join(notes)} mode={mode} rounds={rounds}",
            f"served_by={sorted(meta.llm.SERVED_SEEN) if meta else '?'}",
            f"耗时 {dt:.0f}s = {dt / 60:.1f}min"]
    if res is not None:
        dec = res.get("decidability") or {}
        ea = res.get("external_anchor")
        tail += [
            f"llm_calls={res['llm_calls']} tokens={res['llm_tokens']}",
            f"dispatch.ran={res['dispatch'].get('ran')}",
            f"layer_contribution={json.dumps(res.get('layer_contribution'), ensure_ascii=False)}",
            f"decidability={dec.get('decidability')} _source={dec.get('_source')} "
            f"_divergent={dec.get('_divergent')} _pool={dec.get('_pool_status')} "
            f"_ext={dec.get('_ext_status')}",
            f"anchor_refs(外判引用)={dec.get('anchor_refs')} "
            f"_anchors_given={dec.get('_anchors_given')}",
        ]
        if ea is None:
            tail.append("external_anchor=无键（OFF 臂，与 v1.21.72 同构）")
        else:
            sm = ea.get("summary") or {}
            tail += [
                f"external_anchor: anchors={ea.get('anchors')} "
                f"claims={sm.get('claims')} supported={sm.get('supported')} "
                f"conflicted={sm.get('conflicted')} unmatched={sm.get('unmatched')} "
                f"anchor_used={sm.get('anchor_used')}",
                f"  source_file={ea.get('source_file')} "
                f"retrieved_at={ea.get('retrieved_at')}",
                f"  error={ea.get('error') or '（无）'}",
            ]
        try:
            p = mod.save_result(res, str(HERE / "outputs"))
            tail.append(f"产物={p}")
        except Exception:
            import traceback as _tb
            tail.append("产物落盘异常：\n" + _tb.format_exc())
        try:
            fp = HERE / f"v73arm_{tag}.full.json"
            fp.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                          encoding="utf-8")
            tail.append(f"侧车={fp.name}")
        except Exception as exc:
            tail.append(f"侧车落盘失败：{type(exc).__name__} {exc}")
    if err:
        tail.append("异常：\n" + err)
    tail.append("=" * 60)
    (HERE / f"v73arm_{tag}.log").write_text(log + "\n".join(tail) + "\n",
                                            encoding="utf-8")
    print(f"[{tag}] {'OK' if res else 'FAIL'}  {dt / 60:.1f}min  "
          f"calls={res['llm_calls'] if res else '-'}  "
          f"tokens={res['llm_tokens'] if res else '-'}")
    return 0 if res else 1


if __name__ == "__main__":
    sys.exit(main())
