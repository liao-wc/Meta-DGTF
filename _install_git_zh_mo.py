# -*- coding: utf-8 -*-
"""把 git.mo 装进系统 Git 安装目录（需要一次管理员授权 / UAC 弹窗）。

为什么必须提权：C:\\Program Files\\Git 的 ACL 只允许管理员写入
（实测 `touch` 返回 Permission denied）。这是操作系统的权限边界，
不是沙箱策略，无法绕过。

做法：用 ShellExecuteExW + "runas" 触发 UAC（屏幕上会弹一次确认框），
把 mkdir + copy 交给提权后的 cmd 执行，然后等它结束、核对落盘结果。
"""
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

SRC = Path(r"C:\Users\18432\Desktop\元DGTF-多模并行架构\git-zh_CN.mo")
DST_DIR = Path(r"C:\Program Files\Git\mingw64\share\locale\zh_CN\LC_MESSAGES")
DST = DST_DIR / "git.mo"


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


SEE_MASK_NOCLOSEPROCESS = 0x00000040
SW_HIDE = 0

shell32 = ctypes.windll.shell32
kernel32 = ctypes.windll.kernel32

if DST.is_file() and DST.stat().st_size == SRC.stat().st_size:
    print("目标已存在且大小一致，跳过：%s" % DST)
    sys.exit(0)

cmd = 'cmd.exe'
params = '/c mkdir "%s" & copy /Y "%s" "%s"' % (DST_DIR, SRC, DST)

info = SHELLEXECUTEINFOW()
info.cbSize = ctypes.sizeof(info)
info.fMask = SEE_MASK_NOCLOSEPROCESS
info.lpVerb = "runas"
info.lpFile = cmd
info.lpParameters = params
info.lpDirectory = None
info.nShow = SW_HIDE

print("正在请求管理员权限（屏幕上会弹出 UAC 确认框，请点『是』）…")
ok = shell32.ShellExecuteExW(ctypes.byref(info))
if not ok:
    err = ctypes.get_last_error()
    print("★ 提权失败 / 被取消，错误码 %d（1223 = 用户点了『否』）" % err)
    sys.exit(1)

h = info.hProcess
if h:
    kernel32.WaitForSingleObject(h, 60000)
    code = wintypes.DWORD()
    kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    kernel32.CloseHandle(h)
    print("提权进程退出码 %d" % code.value)

time.sleep(0.5)
if DST.is_file():
    print("✓ 已落盘：%s（%d 字节）" % (DST, DST.stat().st_size))
    sys.exit(0)
print("★ 文件仍不在位：%s" % DST)
sys.exit(1)
