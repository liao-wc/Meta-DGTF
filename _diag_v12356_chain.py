# -*- coding: utf-8 -*-
"""逐个跑变异体链上的检查，定位是哪一条在 v1.23.56 上不绿。

★ 变异体 harness 只打 `out[-1200:]`（日志尾巴），看不到是哪条判据红 ⇒ 单独定位。
"""
import sys

sys.path.insert(0, ".")
import smoke_test as st  # noqa: E402

CHECKS = [
    "check_v12332_discipline", "check_v12333_autotune", "check_v12334_prompt",
    "check_v12336_allweb", "check_v12336_readings", "check_v12336_tick",
    "check_v12336_eml", "check_v12336_webneed", "check_v12337_roundtick",
    "check_v12340_backfeed_stage", "check_v12340_relax_force",
    "check_v12341_goal_fresh", "check_v12341_excavate_dir",
    "check_v12341_attribution", "check_v12342_ctx_shape",
    "check_v12343_gain_stop", "check_v12344_eml_adaptive",
    "check_v12345_output_rep", "check_v12346_duty_span",
    "check_v12347_gain_suggest", "check_v12348_eml_semantic",
    "check_v12349_run_ckpt", "check_v12350_resume",
    "check_v12351_eml_once_per_run", "check_v12352_paused_no_eml",
    "check_v12353_eml_dir_single", "check_v12354_parallel_wall_clock",
    "check_v12355_paused_gap", "check_v12356_ckpt_cumulative",
    "check_v12339_ondemand", "check_v12338_relax_targets",
    "check_v12338_backfeed",
]

print("SRC =", st.SRC.name)
for name in CHECKS:
    fn = getattr(st, name, None)
    if fn is None:
        print("%-32s 缺失" % name)
        continue
    try:
        ok = fn()
    except Exception as e:  # noqa: BLE001
        print("%-32s 抛错 %r" % (name, e))
        continue
    if not ok:
        print("%-32s ✗ 判红" % name)
