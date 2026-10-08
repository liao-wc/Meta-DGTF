# -*- coding: utf-8 -*-
"""推送前检查（往公开仓库推之前跑一次）。

存在的理由：本仓库有 `.env`（含 2 把真密钥）。一旦把密钥推上 GitHub，
即使事后删除，它仍然留在公开的提交历史里 —— 那把 key 只能作废重签。
所以「推之前扫一遍」必须是**可执行的一步**，不能靠人记得。

检查四项：
  1. `.env` 有没有被跟踪 / 被什么规则挡住；
  2. **拿 .env 里的真实值**去搜全部已跟踪文件（不是搜关键词 —— 关键词会被
     改写，真实值不会），并叠加常见密钥前缀；
  3. 体积构成（GitHub 单文件上限 100 MB、仓库建议 < 1 GB）；
  4. 提交身份与分支名。

只报「文件:行号」，**不打印密钥内容**。
"""
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
GIT = "git"

PAT = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|tvly-[A-Za-z0-9_-]{16,}"
    r"|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")


def run(*a):
    p = subprocess.run([GIT] + list(a), cwd=str(HERE), capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", "replace")


bad = 0

# ---------- 1. .env ----------
print("== 1. .env ==")
rc, _ = run("ls-files", "--error-unmatch", ".env")
if rc == 0:
    print("   ★ .env 被跟踪了 —— 必须先取消跟踪再推")
    bad += 1
else:
    rc2, out2 = run("check-ignore", "-v", ".env")
    print("   .env 未被跟踪 ✓　忽略规则：%s"
          % (out2.strip() or "(无 —— 建议补进 .gitignore)"))

# ---------- 2. 真实值扫描 ----------
print()
print("== 2. 密钥扫描（拿 .env 真实值去找）==")
secrets = {}
env = HERE / ".env"
if env.is_file():
    for ln in env.read_text(encoding="utf-8", errors="replace").split("\n"):
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if len(v) >= 12:
                secrets[k.strip()] = v
print("   待查值 %d 个：%s" % (len(secrets), ", ".join(secrets) or "无"))

_, tracked_out = run("ls-files")
tracked = [x for x in tracked_out.split("\n") if x.strip()]
hits = []
total = 0
for rel in tracked:
    fp = HERE / rel
    if not fp.is_file():
        continue
    try:
        b = fp.read_bytes()
    except OSError:
        continue
    total += len(b)
    if b"\x00" in b[:2048]:
        continue
    txt = b.decode("utf-8", "replace")
    for name, val in secrets.items():
        if val in txt:
            n = txt.count(val)
            hits.append((rel, name, n, "env 真实值"))
    for i, ln in enumerate(txt.split("\n"), 1):
        if PAT.search(ln):
            hits.append((rel, "第 %d 行" % i, 1, "疑似密钥前缀"))

_CRED = re.compile(r"(key=|token|apikey|api_key|secret|sk-|password|passwd"
                   r"|auth)=", re.I)


def classify(name, val):
    """把「检出的值」分成真凭据 / 不含凭据的地址。返回 (是否放行, 理由)。

    ★ 为什么需要这一步：只报「命中了」会变成**恒黄告警** —— 一个永远亮着
      的告警等于没有告警。这里对每个值做**确定性**判定：
      形如 URL 且不含凭据类关键词、用户名密码段、查询串的，判为地址。
    """
    v = val.strip()
    m = re.match(r"(https?)://([^/]+)(.*)$", v)
    if m:
        host = m.group(2)
        rest = m.group(3)
        why = []
        if "@" in host:
            why.append("URL 含用户名/密码段")
        if "?" in rest:
            why.append("URL 含查询串")
        if _CRED.search(v):
            why.append("URL 含凭据类关键词")
        if why:
            return False, "URL 但" + "、".join(why)
        return True, "纯服务地址（协议+主机%s，无凭据）" % (
            "，有路径" if rest.strip("/") else "")
    if len(v) < 24:
        return False, "非 URL 且过短，无法排除是凭据"
    return False, "非 URL，按凭据对待"


allow = {}
for _n, _v in list(secrets.items()):
    ok, why = classify(_n, _v)
    if ok:
        allow[_n] = why
        secrets.pop(_n)
print("   判定为「非凭据、可放行」：%s"
      % ("；".join("%s（%s）" % (k, v) for k, v in allow.items()) or "无"))
print("   仍需按凭据对待：%d 个%s"
      % (len(secrets), ("（%s）" % ", ".join(secrets)) if secrets else ""))

if hits:
    per_var = Counter(h[1] for h in hits if h[3] == "env 真实值")
    print("   命中 %d 处（扫描 %.1f MB 文本）" % (len(hits), total / 1048576))
    for name, n in per_var.most_common():
        files = [h[0] for h in hits if h[1] == name]
        tag = "（已放行：%s）" % allow[name] if name in allow else "★ 真凭据"
        print("     变量 %s：出现在 %d 个文件 %s" % (name, len(files), tag))
        for f in files[:5]:
            print("        %s" % f)
    # ★ 判红只看「**真正命中**的、且未被放行的**那个**值」——
    #   不能因为「还有几个键没被放行」就判红：那会让「0 命中的密钥」把
    #   检查永远压成黄色（恒黄告警等于没有告警）。
    real_keys = sorted(set(h[1] for h in hits if h[3] == "env 真实值")
                       - set(allow))
    prefix_hits = [h for h in hits if h[3] == "疑似密钥前缀"]
    if real_keys:
        print("   ★ 以下密钥的**真实值**出现在已跟踪文件里：%s" % real_keys)
        bad += 1
    if prefix_hits:
        print("   ★ 疑似密钥前缀命中：")
        for h in prefix_hits[:10]:
            print("       %s  %s" % (h[0], h[1]))
        bad += 1
    if not real_keys and not prefix_hits:
        print("   ✓ 命中的全部是已放行的非凭据值；无真密钥、无密钥前缀")
else:
    print("   未发现任何密钥进入版本库 ✓（扫描 %.1f MB）" % (total / 1048576))

# ---------- 3. 体积 ----------
print()
print("== 3. 体积构成 ==")
cat = Counter()
cnt = Counter()
for rel in tracked:
    fp = HERE / rel
    if not fp.is_file():
        continue
    ext = os.path.splitext(rel)[1].lower() or "(无扩展名)"
    if rel.startswith("元DGTF-V1."):
        ext = "主文件各版本"
    cat[ext] += fp.stat().st_size
    cnt[ext] += 1
for ext, s in cat.most_common(6):
    print("   %-14s %3d 个  %7.2f MB" % (ext, cnt[ext], s / 1048576))
tot = sum(cat.values())
print("   合计                  %7.2f MB" % (tot / 1048576))
big = max((fp.stat().st_size, rel) for rel in tracked
          if (fp := HERE / rel).is_file())
print("   最大单文件：%.2f MB（%s）—— GitHub 上限 100 MB"
      % (big[0] / 1048576, big[1]))
if big[0] > 100 * 1048576:
    print("   ★ 超过 100 MB，推不上去")
    bad += 1

# ---------- 4. 身份 / 分支 ----------
print()
print("== 4. 提交身份与分支 ==")
for scope in ("--global", "--local"):
    rc1, n = run("config", scope, "user.name")
    rc2, e = run("config", scope, "user.email")
    print("   %-9s %s <%s>%s" % (scope, n.strip() or "(未设)",
                                 e.strip() or "-",
                                 "" if n.strip() else "   ← 未设"))
rc3, br = run("branch", "--show-current")
print("   当前分支：%s" % (br.strip() or "(游离 HEAD)"))
rc4, rem = run("remote", "-v")
print("   远程仓库：%s" % (rem.strip() or "(未配置 —— 还没连 GitHub)"))

print()
print("=" * 60)
print("结论：%s" % ("★ 有 %d 项需要处理后再推" % bad if bad
                    else "四项检查通过，可以推送"))
sys.exit(1 if bad else 0)
