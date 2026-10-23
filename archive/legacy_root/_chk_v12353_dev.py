# -*- coding: utf-8 -*-
"""v1.23.53 开发期构造性验证：记忆库目录**一处解析**。

判据：
  A 真入口（载入）：`playbook.dir=tmp1`，tmp1 里种一份 bandit.json
    ⇒ `MetaDGTF(cfg)._bandit.n` 必须读到那份（证明载入真的走了 tmp1）
  B 落盘：同一 cfg ⇒ `_save_bandit` 落到 tmp1
  C 旧版对照：同 cfg 跑 v1.23.52 ⇒ 落到**旧回落点**（`eml_dir()`），不是 tmp1
    ★ 为不碰生产 `dgtf_memory/`：把两版的 `eml_dir` 都临时指到 tmp_repo
  D 显式 `auto.bandit.dir` 仍优先（显式赢了才用显式的）
  E 默认（`playbook.dir` 空）⇒ 落到 `eml_dir()`（与旧版逐字相同）
  F 生产库护栏：全程 `dgtf_memory/bandit.json` 字节不变
"""
import importlib.util
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO_BANDIT = HERE / "dgtf_memory" / "bandit.json"
bad, ok = [], []


def ck(cond, msg):
    (ok if cond else bad).append(msg)
    print(("  [OK]   " if cond else "  [BAD]  ") + msg)
    return bool(cond)


def load(py):
    spec = importlib.util.spec_from_file_location("e53_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def cfg_of(mod, pdir="", bdir=""):
    c = mod.load_config(str(HERE / "__nonexistent__.yaml"))
    c["api"]["key"] = "sk-smoke-test-key"
    c["output"]["verbose"] = False
    c.setdefault("playbook", {})["mode"] = "shadow"
    c["playbook"]["dir"] = str(pdir)
    c.setdefault("auto", {}).setdefault("bandit", {})
    c["auto"]["bandit"]["enabled"] = True
    c["auto"]["bandit"]["dir"] = str(bdir)
    c["all_on"] = False
    return c


def seed(mod, d, n0=9):
    d.mkdir(parents=True, exist_ok=True)
    k = len(mod._BANDIT_ARMS)
    (d / mod._BANDIT_FILE).write_text(json.dumps(
        {"t": 123, "n": [n0] + [0] * (k - 1),
         "mean": [0.5] * k, "cost": [100.0] * k}), encoding="utf-8")


_before = REPO_BANDIT.read_bytes() if REPO_BANDIT.is_file() else None

new = load(HERE / "元DGTF-V1.23.53.py")
old = load(HERE / "元DGTF-V1.23.52.py")
# ★ 两版的 eml_dir 都指到临时"假仓库"，免得测试碰真库
_repo_fake = pathlib.Path(tempfile.mkdtemp(prefix="v53repo_"))
new.eml_dir = lambda base=None: _repo_fake
old.eml_dir = lambda base=None: _repo_fake

print("=" * 62)
print("【A】真入口：playbook.dir=tmp1 ⇒ 载入读到 tmp1 里那份")
tmp1 = pathlib.Path(tempfile.mkdtemp(prefix="v53A_"))
seed(new, tmp1, n0=9)
m1 = new.MetaDGTF(cfg_of(new, pdir=tmp1))
ck(m1._bandit is not None, "bandit 已载入")
ck(int(m1._bandit.n[0]) == 9, "读到了 tmp1 的那份（n[0]=%r，期望 9）"
   % (int(m1._bandit.n[0]) if m1._bandit else None,))
ck((tmp1 / new._BANDIT_FILE).is_file(), "tmp1 里确有 bandit.json")

print("\n【B】落盘：同一 cfg ⇒ 写到 tmp1")
bb = new._load_bandit(m1._bandit_cfg, new.eml_store_dir(m1.config))
bb.n[1] = 7
ck(new._save_bandit(bb, m1._bandit_cfg, new.eml_store_dir(m1.config)) is True,
   "_save_bandit 返回 True")
_after = json.loads((tmp1 / new._BANDIT_FILE).read_text(encoding="utf-8"))
ck(int(_after["n"][1]) == 7, "落盘进了 tmp1（n[1]=%r）" % (_after["n"][1],))
ck(not (_repo_fake / new._BANDIT_FILE).is_file(),
   "假仓库里没被写（旧行为会写这儿）")

print("\n【C】旧版对照：同 cfg ⇒ 落到 eml_dir()，不是 tmp1")
tmp3 = pathlib.Path(tempfile.mkdtemp(prefix="v53C_"))
seed(old, tmp3, n0=3)
m3 = old.MetaDGTF(cfg_of(old, pdir=tmp3))
ck(int(m3._bandit.n[0]) == 0,
   "旧版**没**读 tmp3（n[0]=%r，说明它看的是 eml_dir()）"
   % (int(m3._bandit.n[0]) if m3._bandit else None,))
bb3 = old._load_bandit(m3._bandit_cfg)
bb3.n[1] = 5
old._save_bandit(bb3, m3._bandit_cfg)
ck((_repo_fake / old._BANDIT_FILE).is_file(), "旧版把 bandit 写到了 eml_dir()（露馅）")
ck(not (tmp3 / old._BANDIT_FILE).is_file() or
   json.loads((tmp3 / old._BANDIT_FILE).read_text(encoding="utf-8"))["n"][1] != 5,
   "旧版没往 tmp3 写（n[1] 未被改成 5）")

print("\n【D】显式 auto.bandit.dir 仍优先")
tmp4 = pathlib.Path(tempfile.mkdtemp(prefix="v53D_"))
tmp4b = pathlib.Path(tempfile.mkdtemp(prefix="v53D2_"))
seed(new, tmp4b, n0=4)
m4 = new.MetaDGTF(cfg_of(new, pdir=tmp4, bdir=tmp4b))
ck(int(m4._bandit.n[0]) == 4, "显式 dir 赢了 playbook.dir（n[0]=%r）"
   % (int(m4._bandit.n[0]) if m4._bandit else None,))

print("\n【E】默认（playbook.dir 空）⇒ 回落 eml_dir()（与旧版相同）")
ck(str(new.eml_store_dir(cfg_of(new, pdir=""))) == str(_repo_fake),
   "空 playbook.dir ⇒ eml_dir()")
ck(str(new.eml_store_dir(cfg_of(new, pdir=tmp1))) == str(tmp1),
   "有 playbook.dir ⇒ 跟着它")

print("\n【F】生产库护栏")
_after_repo = REPO_BANDIT.read_bytes() if REPO_BANDIT.is_file() else None
ck(_before == _after_repo, "dgtf_memory/bandit.json 全程字节未变")

print("\n" + "=" * 62)
print("通过 %d / 判红 %d" % (len(ok), len(bad)))
for b in bad:
    print("  ! " + b)
sys.exit(1 if bad else 0)
