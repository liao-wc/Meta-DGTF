# -*- coding: utf-8 -*-
"""适配层判据（零 API、零 GPU、不需要 8772/8773 在线）。

被 `scripts/local_model/openai_shim.py` 服务的三种失败形态都要被钉住：
  · 分流错（把 self_check 的 prompt 派给 route 适配器 ⇒ 输出更差且难查）
  · 消息摊平丢内容（content 是数组时静默变空串 ⇒ 引擎拿到空回复）
  · 上游挂了却回 200 空内容（引擎会当成「模型没话说」，不触发它的失败留痕）

判据用**进程内起服务**（假上游 + 真 shim Handler），不依赖外部端口占用。
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import openai_shim as S  # noqa: E402

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


# ── 假上游：/generate 返回固定结构 ──────────────────────────
class _Up(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    reply = {"ok": True, "text": "上游原文", "prompt_tokens": 11,
             "gen_tokens": 7, "confidence": 0.8, "cached": False, "ms": 1.0}
    seen_stage = []
    seen_max_new = []
    seen_reppen = []
    fail = False

    def log_message(self, *a):
        return

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n).decode("utf-8"))
        type(self).seen_stage.append(body.get("stage"))
        type(self).seen_max_new.append(body.get("max_new_tokens"))
        type(self).seen_reppen.append(body.get("repetition_penalty"))
        if type(self).fail:
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        raw = json.dumps(type(self).reply, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _serve(handler, port):
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _post(port, body, timeout=10):
    req = urllib.request.Request(
        "http://127.0.0.1:%d/v1/chat/completions" % port,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def main() -> int:
    # ── S1 stage 分流 ────────────────────────────────────
    ck("S1a model 冒号后缀优先", S.pick_stage("local:dual_judge", "自省", "") == "dual_judge",
       S.pick_stage("local:dual_judge", "自省", ""))
    ck("S1b 无后缀按「自省」命中 self_check",
       S.pick_stage("local", "请做自省，看是否有复述", "") == "self_check")
    ck("S1c 无后缀按「双判」命中 dual_judge",
       S.pick_stage("local", "你是双判器", "") == "dual_judge")
    ck("S1d 无特征兜底 self_check",
       S.pick_stage("", "随便一段话", "") == "self_check")
    ck("S1e 冒号后为空 ⇒ 不算指定", S.pick_stage("local:", "自省", "") == "self_check",
       S.pick_stage("local:", "自省", ""))

    # ── S1f [V2.2.13] 显式 stage 通道（引擎经 extra_body 摊到请求顶层）──
    #   背景：此前引擎请求不带 stage、文本也不含关键词 ⇒ 兜底 self_check
    #   ⇒ 主生成/清单/重锚定全被路由到**自省 LoRA** + 64 token（题不对文）。
    ck("S1f 显式 stage 优先于一切（expand_pair_merged 原样通过）",
       S.pick_stage("local", "随便一段话", "x", explicit="expand_pair_merged")
       == "expand_pair_merged")
    ck("S1f2 显式 stage 覆盖 model 冒号后缀",
       S.pick_stage("local:dual_judge", "x", "y", explicit="route") == "route")
    ck("S1f3 显式 stage 覆盖文本关键词",
       S.pick_stage("local", "请做自省", "", explicit="manifest") == "manifest")
    ck("S1f4 清洗：大小写归一、非法字符剔除（防注入）",
       S.pick_stage("local", "x", "y", explicit="Expand-Pair MERGED!")
       == "expandpairmerged")
    ck("S1f5 全非法/空白 explicit ⇒ 不采用（回落老规则）",
       S.pick_stage("local", "请做自省", "", explicit="  ") == "self_check")
    ck("S1f6 空 explicit ⇒ 老行为不变（回归保护）",
       S.pick_stage("local:dual_judge", "自省", "") == "dual_judge")
    ck("S1f7 恶意串清洗后只留安全字符",
       S.pick_stage("local", "x", "y", explicit="bad/stage;rm -rf")
       == "badstagermrf")

    # ── S1g [V2.2.13b] 诚实的 finish_reason（纯函数）─────────
    #   此前硬编码 "stop"：本地被 max_new 掐断也报「正常结束」⇒
    #   引擎续跑机制（last_finish=="length"）在本地链路是死的。
    ck("S1g 撞到上限 ⇒ length",
       S.finish_reason_for(224, 224) == "length")
    ck("S1g2 未到上限 ⇒ stop（自然 EOS 不装截断）",
       S.finish_reason_for(27, 224) == "stop")
    ck("S1g3 解析失败 ⇒ stop（不假装截断）",
       S.finish_reason_for("x", 224) == "stop")
    ck("S1g4 上限 ≤ 0 ⇒ stop（不假装截断）",
       S.finish_reason_for(10, 0) == "stop")

    # ── S1i [V2.2.13b] sanitize_stage 单一定义（防两处分叉）──
    #   shim 与 service 各自维护合法字符集 ⇒ 「shim 放行、service 400」。
    import dgtf_local_llm.gates as _gates  # noqa: E402
    ck("S1i sanitize_stage 与 gates 同一函数（不是复制）",
       S._sanitize_stage is _gates.sanitize_stage)

    # ── S2 messages 摊平 ────────────────────────────────
    sp, us = S.flatten_messages([
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "U1"},
        {"role": "user", "content": "U2"},
    ])
    ck("S2a system 取出", sp == "SYS", sp)
    ck("S2b 多条 user 按序拼接（不丢）", us == "U1\n\nU2", us)

    sp2, us2 = S.flatten_messages([{"role": "user", "content": [
        {"type": "text", "text": "甲"},
        {"type": "image_url", "image_url": {"url": "x"}},
        {"type": "text", "text": "乙"}]}])
    ck("S2c 数组 content 只取 text 段（不变成空串）",
       us2 == "甲\n乙", repr(us2))
    ck("S2d 数组 content 无 system 时 system 为空", sp2 == "", repr(sp2))

    # ── S3 真转发（进程内假上游 + 真 Handler）────────────
    up = _serve(_Up, 18774)
    S.UPSTREAM = "http://127.0.0.1:18774"
    shim = _serve(S.Handler, 18773)
    try:
        _Up.seen_stage.clear()
        code, obj = _post(18773, {
            "model": "local:route",
            "messages": [{"role": "system", "content": "sys"},
                         {"role": "user", "content": "usr"}],
            "max_tokens": 50, "temperature": 0})
        ck("S3a 返回 200", code == 200, code)
        ck("S3b OpenAI 形状完整（choices/message/content）",
           obj.get("choices", [{}])[0].get("message", {}).get("content") == "上游原文",
           obj.get("choices"))
        ck("S3c usage 三项齐全且总数=和",
           obj.get("usage", {}).get("total_tokens")
           == obj["usage"]["prompt_tokens"] + obj["usage"]["completion_tokens"],
           obj.get("usage"))
        ck("S3d stage 被正确转发给上游", _Up.seen_stage == ["route"],
           _Up.seen_stage)
        ck("S3e model 原样回显（不制造假「别名漂移」告警）",
           obj.get("model") == "local:route", obj.get("model"))
        ck("S3f 留痕字段带出（stage/confidence）",
           (obj.get("dgtf_local") or {}).get("stage") == "route",
           obj.get("dgtf_local"))

        # ★ max_tokens 压缩：引擎 thinking 档会抬到 32000，不能原样等。
        #   【判据随实现更新】旧版夹到 2048；现在按 **stage 训练长度**压
        #   （实测同 prompt：2048 ⇒ 110s 超时 / 64 ⇒ 11s）。
        #   ★ 这里用**硬等式登记**新值，不是放宽成 `< 32000` —— 放宽后
        #     「压成一坨」和「没压」都过得去，判据就没牙了。
        _Up.seen_max_new.clear()
        _post(18773, {"model": "local", "messages": [{"role": "user", "content": "x"}],
                      "max_tokens": 32000})
        ck("S3g 超大 max_tokens 被压到该 stage 的训练长度（不白等超时）",
           _Up.seen_max_new == [64], _Up.seen_max_new)

        # ★ 负对照：不是「全部压成一个数」—— 换 stage 上限必须跟着变。
        _Up.seen_max_new.clear()
        _post(18773, {"model": "local:dual_judge",
                      "messages": [{"role": "user", "content": "x"}],
                      "max_tokens": 32000})
        ck("S3h 换 stage 后上限随之变化（不是写死一个全局常数）",
           _Up.seen_max_new == [224], _Up.seen_max_new)

        # ── S3i [V2.2.13b] finish_reason 端到端（假上游报 gen_tokens）──
        _saved_reply = dict(_Up.reply)
        try:
            # route 上限 96：上游报 gen_tokens=96（撞顶）⇒ length + truncated
            _Up.reply = {**_saved_reply, "gen_tokens": 96}
            code3, obj3 = _post(18773, {
                "model": "local:route", "max_tokens": 600,
                "messages": [{"role": "user", "content": "u"}]})
            ck("S3i 撞上限 ⇒ finish_reason=length（端到端）",
               obj3["choices"][0]["finish_reason"] == "length",
               obj3["choices"][0].get("finish_reason"))
            ck("S3i2 留痕字段 truncated=true",
               obj3.get("dgtf_local", {}).get("truncated") is True,
               obj3.get("dgtf_local"))
            # 上游报 gen_tokens=27（自然 EOS）⇒ stop
            _Up.reply = {**_saved_reply, "gen_tokens": 27}
            code4, obj4 = _post(18773, {
                "model": "local:route", "max_tokens": 600,
                "messages": [{"role": "user", "content": "u"}]})
            ck("S3i3 自然结束 ⇒ finish_reason=stop（不装截断）",
               obj4["choices"][0]["finish_reason"] == "stop",
               obj4["choices"][0].get("finish_reason"))
        finally:
            _Up.reply = _saved_reply

        # ── S5 [V2.2.14] base-model stage 自动带重复惩罚 ──
        #   0.5B 底座在结构化 JSON 任务上确定性复读 ⇒ 撞上限 ⇒ JSON 截断。
        #   LoRA stage 不带（训练分布内不复读；多走 temp=0 graph 快路径）。
        from dgtf_local_llm.gates import BASE_STAGE_REP_PEN  # noqa: E402
        _Up.seen_reppen.clear()
        _post(18773, {"model": "local",
                      "messages": [{"role": "user", "content": "u"}],
                      "stage": "re_anchor", "max_tokens": 500})
        _post(18773, {"model": "local",
                      "messages": [{"role": "user", "content": "u"}],
                      "stage": "self_check", "max_tokens": 500})
        ck("S5a base-model stage 带默认重复惩罚（治复读）",
           _Up.seen_reppen[0] == BASE_STAGE_REP_PEN, _Up.seen_reppen)
        ck("S5b LoRA stage 不带惩罚（不改适配器行为）",
           _Up.seen_reppen[1] == 0.0, _Up.seen_reppen)

        # ── S4 上游坏掉 ⇒ 必须显式失败，不能 200 空内容 ──
        _Up.fail = True
        code2, obj2 = _post(18773, {"model": "local",
                                    "messages": [{"role": "user", "content": "x"}]})
        ck("S4a 上游 5xx ⇒ shim 回 503（不是 200 空内容）", code2 == 503, code2)
        ck("S4b 失败原因写进 body（可诊断）",
           "upstream" in json.dumps(obj2, ensure_ascii=False),
           obj2)
    finally:
        shim.shutdown()
        up.shutdown()
        S.UPSTREAM = "http://127.0.0.1:8772"

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    for f in F:
        print("  - " + f)
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
