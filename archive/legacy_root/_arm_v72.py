# -*- coding: utf-8 -*-
"""[成本对照跑臂] 单次真跑，可按臂覆盖 cost_profile / parallel_mode / 圈数 / 低频项。

为什么另写一个：`_run_v60.py` / `_run_v72.py` 只认 `--route` 与 `rounds`，
不认 `cost_profile` 覆盖，也没有 `re_eval_every_n` 的旋钮 —— 而
「同题不同档 / 同题不同模式 / 同题不同低频频率」正是要对照的三件事。
本跑臂**不改引擎任何逻辑**，只在 load_config 之后覆盖 cfg 再 run。

用法：
  python _arm_v72.py <tag> <profile> <mode> "<rounds>" "<question>"
例：
  python _arm_v72.py cmp_bal_serial balanced serial "0:3,1:3,both:3,all:3" "……"

可选环境变量：
  V72_RE_EVAL=<int>   覆盖 spiral.re_eval_every_n（链接推荐旋钮）

产出：
  v72arm_<tag>.log         完整 verbose 日志 + 结尾汇总
  outputs/<时间>_<题目前缀>.md   产物
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
sys.path.insert(0, str(HERE))


def load_dotenv(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_module():
    spec = importlib.util.spec_from_file_location(
        "dgtf72arm", HERE / "元DGTF-V1.21.72.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf72arm"] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    if len(sys.argv) < 6:
        print(__doc__)
        return 2
    tag, profile, mode, rounds, question = (
        sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4],
        " ".join(sys.argv[5:]))
    load_dotenv(HERE / ".env")
    mod = load_module()
    cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))

    notes = []
    cfg["cost_profile"] = profile
    notes.append(f"cost_profile={profile}")
    if os.environ.get("V72_RE_EVAL"):
        _rv = int(os.environ["V72_RE_EVAL"])
        cfg.setdefault("spiral", {})["re_eval_every_n"] = _rv
        notes.append(f"re_eval_every_n={_rv}")

    t0 = time.time()
    buf = io.StringIO()
    err = None
    res = None
    meta = None
    with contextlib.redirect_stdout(buf):
        try:
            print(f"🧪 跑臂 {tag}：{' | '.join(notes)} | mode={mode} "
                  f"| rounds={rounds}")
            meta = mod.MetaDGTF(cfg)
            res = meta.run(question, route=["0", "1", "both", "all"],
                           rounds=rounds, parallel_mode=mode)
        except Exception:
            import traceback
            err = traceback.format_exc()
    dt = time.time() - t0
    log = buf.getvalue().replace("\r\n", "\n")

    tail = ["", "=" * 60,
            f"arm={tag} profile={profile} mode={mode} rounds={rounds}",
            f"served_by={sorted(meta.llm.SERVED_SEEN) if meta else '?'}",
            f"耗时 {dt:.0f}s = {dt/60:.1f}min"]
    if res is not None:
        tail += [
            f"llm_calls={res['llm_calls']} tokens={res['llm_tokens']}",
            f"dispatch.ran={res['dispatch'].get('ran')}",
            f"dispatch.missing={res['dispatch'].get('missing')}",
            f"layer_contribution={json.dumps(res.get('layer_contribution'),
                                             ensure_ascii=False)}",
        ]
        try:
            p = mod.save_result(res, str(HERE / "outputs"))
            tail.append(f"产物={p}")
        except Exception:
            import traceback as _tb
            tail.append("产物落盘异常：\n" + _tb.format_exc())
    if err:
        tail.append("异常：\n" + err)
    tail.append("=" * 60)
    (HERE / f"v72arm_{tag}.log").write_text(
        log + "\n".join(tail) + "\n", encoding="utf-8")
    print(f"[{tag}] {'OK' if res else 'FAIL'}  {dt/60:.1f}min  "
          f"calls={res['llm_calls'] if res else '-'}  "
          f"tokens={res['llm_tokens'] if res else '-'}")
    return 0 if res else 1


if __name__ == "__main__":
    sys.exit(main())
