# -*- coding: utf-8 -*-
"""把「git 说中文」固化到用户环境：LANG 变量 + git 编码配置 + Git Bash 界面语言。

三步，都不需要管理员（全部写在当前用户下）：
  1. HKCU\\Environment 新增 LANG=zh_CN.UTF-8，并广播 WM_SETTINGCHANGE
     让**新开的**终端立刻看到（已开着的窗口不会自动更新）。
  2. git 全局配置四项编码相关键（中文文件名 / 提交信息 / 日志输出）。
  3. Git Bash（mintty）界面语言设为中文 —— 写 ~/.minttyrc。
"""
import ctypes
import subprocess
import winreg
from ctypes import wintypes
from pathlib import Path

GIT = r"C:\Program Files\Git\cmd\git.exe"
LANG_VALUE = "zh_CN.UTF-8"
MINTTY = Path(r"C:\Users\18432\.minttyrc")


def reg_get(name):
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
        return winreg.QueryValueEx(k, name)[0]
    except Exception:
        return None


print("== 1. 用户环境变量 LANG ==")
before = reg_get("LANG")
print("   改前：%r" % before)
k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                   winreg.KEY_SET_VALUE)
winreg.SetValueEx(k, "LANG", 0, winreg.REG_SZ, LANG_VALUE)
winreg.CloseKey(k)
print("   改后：%r" % reg_get("LANG"))

# 广播，让新开的进程拿到新环境
HWND_BROADCAST = 0xFFFF
WM_SETTINGCHANGE = 0x001A
SMTO_ABORTIFHUNG = 0x0002
res = wintypes.DWORD()
ctypes.windll.user32.SendMessageTimeoutW(
    HWND_BROADCAST, WM_SETTINGCHANGE, 0,
    ctypes.c_wchar_p("Environment"), SMTO_ABORTIFHUNG, 5000,
    ctypes.byref(res))
print("   已广播 WM_SETTINGCHANGE（已开着的终端需自己重开）")

print()
print("== 2. git 全局编码配置 ==")
for key, val in (
    ("core.quotepath", "false"),          # 中文文件名不再被转义成 \344\270...
    ("gui.encoding", "utf-8"),
    ("i18n.commitencoding", "utf-8"),
    ("i18n.logoutputencoding", "utf-8"),
):
    p = subprocess.run([GIT, "config", "--global", key, val],
                       capture_output=True, text=True)
    got = subprocess.run([GIT, "config", "--global", "--get", key],
                         capture_output=True, text=True).stdout.strip()
    print("   %-24s = %-8s %s" % (key, got, "✓" if got == val else "★ 失败"))

print()
print("== 3. Git Bash（mintty）界面语言 ==")
line = "Language=zh_CN"
if MINTTY.is_file():
    txt = MINTTY.read_text(encoding="utf-8", errors="replace")
    if line in txt:
        print("   %s 已含 %s" % (MINTTY.name, line))
    else:
        if not txt.endswith("\n"):
            txt += "\n"
        MINTTY.write_text(txt + line + "\n", encoding="utf-8")
        print("   已追加 %s 到 %s" % (line, MINTTY))
else:
    MINTTY.write_text(line + "\nCharset=UTF-8\n", encoding="utf-8")
    print("   已创建 %s" % MINTTY)
print("   内容：%r" % MINTTY.read_text(encoding="utf-8").strip()[:80])
