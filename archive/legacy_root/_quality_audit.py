# -*- coding: utf-8 -*-
"""一次真跑的整体质量审计：从 verbose 日志 + 产物里分层取证。

用法：python _v59_quality_audit.py

分五层：
  A 成本   调用 / token / 耗时 / 预算
  B 停止   每层停止理由、是否走满、闸门统计
  C 机制   复述计数、回流注入、覆盖率双口径、不可判定轨迹、漂移标记
  D 质量   质量线索 / answered / distance / 闭环清算 / 池产出
  E 对照   与同题另两个测点横向比
"""
import os
import re
import sys

# 用法：python _quality_audit.py [日志路径]（默认 v59_default.log）
LOG = sys.argv[1] if len(sys.argv) > 1 else "v59_default.log"


def rd(p):
    return open(p, encoding="utf-8", newline="").read().replace("\r\n", "\n")


t = rd(LOG)


def g(pat, txt=None, default="?"):
    m = re.search(pat, txt if txt is not None else t)
    return m.group(1) if m else default


print("=" * 74)
print("A 成本")
print("  调用      " + g(r"llm_calls=(\d+)"))
print("  token     " + g(r"tokens=(\d+)"))
print("  耗时(s)   " + g(r"耗时 (\d+)s"))
# 预算只认 runner 打的 [BUDGET] 行；否则说"未记录"——不要拿日志里
# 别处偶然出现的 hard_max= 当数（会显示一个看似正确却是错的数）。
_bud = re.search(r"^\[BUDGET\]\s*(.+?)\s*$", t, re.M)
print("  预算      " + (_bud.group(1)[:70] if _bud else "（日志里未记录）"))

prod = g(r"\[OUTPUT\]\s*(.+?)\s*$", default="")
print("  产物      " + (prod or "（还没落盘）"))

print()
print("B 停止")
for line in t.split("\n"):
    if "⏹" in line:
        print("  " + line.strip()[:150])
print("  fix-88b 推迟 %d 次 / 放行 %d 次"
      % (t.count("推迟停止"), t.count("放行停止")))
print("  min_rounds 拦截 %d 次" % t.count("被 min_rounds"))
print("  元层闭环未清算推迟 %d 次" % t.count("元层闭环未清算"))

if not prod or not os.path.exists(prod):
    print("\n（产物还没生成，先等真跑结束）")
    raise SystemExit(0)

m = rd(prod)
rounds = re.findall(r"实际走了 (\d+) 圈", m)

print()
print("C 机制")
print("  各层实际圈数      " + str(rounds))
rep = re.findall(r"复述=(\d+)", t)
print("  复述计数（日志）  " + str(sorted(set(rep))) +
      "（全 0 = 停止理由没被假的复述计数污染）")
print("  自省回流注入      %d 次" % len(re.findall(r"自省回流. 注入", t)))
# 双口径有两个分支：可判定通道（模型自评折算/代码实算）与
# 回退分支（清晰度/结构覆盖率）。**两者都算"在"**——只认前者的写法
# 会在"全部子问题都被升级为不可判定"时假报缺失（本轮踩过）。
dual = (("模型自评折算" in m and "代码实算" in m)
        or ("清晰度" in m and "结构覆盖率" in m and "代码实算" in m))
print("  覆盖率双口径      " + ("在" if dual else "缺"))
print("  不可判定命中轨迹  " + ("在" if "不可判定覆盖轨迹" in m else "缺"))
print("  成本档位留痕      " + str(re.findall(r"\*\*成本档位\*\*：(.+)", m) or "缺"))
drift = re.findall(r"all_candidate_(?:drift|selfref)\(\d+%\)", m)
print("  漂移标记          " + str(drift or "无"))
print("  螺旋停止段        %d 层" % m.count("**螺旋停止**"))

print()
print("D 质量")
print("  质量线索          " + str([x.strip() for x in
                                  re.findall(r"\*\*质量线索\*\*：(.+)", m)]))
print("  answered          " + str(re.findall(r"answered_sub_ids：\[([^\]]*)\]", m)))
print("  answer.distance   " + str(re.findall(r"- distance：([\d.]+)", m)))
print("  综合距离          " + str(re.findall(r"\*\*综合距离\*\*：([\d.]+)", m)))
print("  闭环清算          " + str(re.findall(r"\*\*闭环清算\*\*：(.+)", m)))
print("  终局清算          " + str(re.findall(r"\*\*终局清算\*\*：(.+)", m)))
print("  产物字节          %d" % len(m.encode("utf-8")))


def pools(x):
    o, cur = {}, None
    for line in x.split("\n"):
        mm = re.match(r"### (\S+) 池", line.strip())
        if mm:
            cur = mm.group(1)
            o[cur] = {}
        elif cur:
            m2 = re.match(r"- (.+?) (\d+) 条", line.strip())
            if m2:
                o[cur][m2.group(1)] = int(m2.group(2))
    return o


print("  池产出：")
for k in ("0", "1", "both", "all"):
    pl = pools(m)
    if k in pl:
        print("    %-5s %s" % (k, pl[k]))

print()
print("E 同题三档对照")
print("  省 3/3/3(+1)       调用 125   token 548108")
print("  中 6/4/7/5(+1)     调用 220   token 1058585")
print("  默认 12/12/12(+1)  调用 %s   token %s   （本次）"
      % (g(r"llm_calls=(\d+)"), g(r"tokens=(\d+)")))
