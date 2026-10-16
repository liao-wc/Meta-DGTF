def check_v12349_run_ckpt():
    """[v1.23.49] 修「run() 只在返回后写盘 ⇒ 中断全丢」：跑中快照 + 孤儿回收。

    ★ 判据：① 写-读回环（含 View 的 `to_dict` 形状）；② **原子**（不留 `.tmp` 残骸）；
      ③ 孤儿回收：过期的 `running` ⇒ `interrupted` + why；④ **负对照**：还没过期
        的 ⇒ 不动；⑤ 幂等（第二次不再改）；⑥ `interval<=0` / 无 run_id ⇒ 不起线程；
      ⑦ 配置键 + 接线在源码，且**默认 False**（零行为差）。
    """
    import tempfile
    import time as _t
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for tok in ("def write_run_ckpt(run_id: str", "def start_run_ckpt(engine",
                "def stop_run_ckpt(stop_evt, engine=None",
                "def recover_orphan_runs(base=None",
                '"live_checkpoint": False,', "start_run_ckpt(self, _ck_rid, _ck_iv)"):
        if tok not in src:
            bad.append("[CK] 源码缺：%s" % tok)

    _base = Path(tempfile.mkdtemp(prefix="ckpt_"))
    W = mod.write_run_ckpt
    # ① 写-读回环
    _p = W("T1", {"id": "T1", "status": "running", "n_views": 2,
                  "views": {"0": {"anchor": "甲"}}}, base=_base)
    if not _p.exists():
        bad.append("[CK] 写完文件不在")
    else:
        _d = json.loads(_p.read_text(encoding="utf-8"))
        if _d.get("n_views") != 2 or (_d.get("views") or {}).get("0", {}).get("anchor") != "甲":
            bad.append("[CK] 回环内容不对：%r" % (_d,))
    # ② 原子：不留 .tmp 残骸
    if list(_base.glob("*.tmp")):
        bad.append("[CK] 留下 .tmp 残骸（非原子写）")
    # ③ 孤儿回收（伪造一个很旧的 running）
    _old = {"id": "T2", "status": "running", "t": _t.time() - 100000.0,
            "views": {"0": {"x": 1}}}
    W("T2", _old, base=_base)
    _r1 = mod.recover_orphan_runs(base=_base, stale_sec=900.0)
    _ids = [x.get("id") for x in _r1]
    if "T2" not in _ids:
        bad.append("[CK] 过期 running 没被回填：%r" % (_r1,))
    _d2 = json.loads((_base / "T2.json").read_text(encoding="utf-8"))
    if _d2.get("status") != "interrupted" or not _d2.get("interrupted_why"):
        bad.append("[CK] 回填形状不对：%r" % (_d2.get("status"),))
    if not _d2.get("views", {}).get("0"):
        bad.append("[CK] 回填把 views 弄丢了（内容没留下）")
    # ⑤ 幂等
    _r2 = mod.recover_orphan_runs(base=_base, stale_sec=900.0)
    if any(x.get("id") == "T2" for x in _r2):
        bad.append("[CK] 不幂等：第二次又改了一次")
    # ④ 负对照：新鲜的 running 不动
    W("T3", {"id": "T3", "status": "running", "t": _t.time()}, base=_base)
    _r3 = mod.recover_orphan_runs(base=_base, stale_sec=900.0)
    if any(x.get("id") == "T3" for x in _r3):
        bad.append("[CK-负对照] 还没过期就被判孤儿")
    _d3 = json.loads((_base / "T3.json").read_text(encoding="utf-8"))
    if _d3.get("status") != "running":
        bad.append("[CK-负对照] 新鲜的 running 被改了状态")
    # ⑥ interval<=0 / 无 id ⇒ 不起
    if mod.start_run_ckpt(object(), "", 30.0) is not None:
        bad.append("[CK] 无 run_id 竟起了线程")
    if mod.start_run_ckpt(object(), "T9", 0) is not None:
        bad.append("[CK] interval<=0 竟起了线程")
    # 起-停闭环（真线程）
    class _E:
        _results = {"0": None}
        _question = "q"
        _route = ["0"]
    _ev = mod.start_run_ckpt(_E(), "T4", 0.05)
    if _ev is None:
        bad.append("[CK] 正常参数竟没起线程")
    else:
        _t.sleep(0.2)
        mod.stop_run_ckpt(_ev, _E(), "T4", "done")
        _d4 = json.loads((_base / "T4.json").read_text(encoding="utf-8"))
        if _d4.get("status") != "done":
            bad.append("[CK] 停的时候没落最后一份 done：%r" % (_d4.get("status"),))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.49 跑中快照（回环 · 原子无残骸 · 过期⇒interrupted+why · "
          "新鲜不动 · 幂等 · 不起线程的两种情形 · 起停闭环落 done）全过")
    return True
