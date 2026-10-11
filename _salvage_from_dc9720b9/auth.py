# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 用户认证与会话（纯标准库）。

设计要点
--------
- 独立库 `dgtf_app/auth.db`：不触碰引擎与既有产物数据，出问题删库重来即可。
- 密码：`hashlib.pbkdf2_hmac`（PBKDF2-HMAC-SHA256，20 万轮）+ 每用户随机盐。
  ⚠️ 绝不存明文；校验用 `hmac.compare_digest` 做恒定时间比较，防时序侧信道。
- 会话：随机 token 存库（**存 SHA-256 摘要**，不存原文）+ HttpOnly Cookie。
  这样登出、强制下线可即时生效（纯 JWT 做不到），且库泄露也无法反推 token。
- 每日配额：按 `tasks_log` 表统计当日已发起任务数，防滥用。
- 注册开关：默认关闭；开放注册时改 `AUTH_ALLOW_REGISTER=1` 或配置项。

命令行
------
  python dgtf_app/auth.py init              # 初始化库 + 创建默认管理员
  python dgtf_app/auth.py useradd <名> [密码]  # 新增用户（不传密码则随机生成并打印）
  python dgtf_app/auth.py passwd <名> [密码]   # 改密码（同时强制该用户所有会话下线）
  python dgtf_app/auth.py userdel <名>        # 删除用户（不动其产物目录）
  python dgtf_app/auth.py list               # 列出用户
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DGTF_APP_AUTH_DB", APP_DIR / "auth.db"))

# ── 可配置项（环境变量优先，便于不改代码调整）──────────────────────
# 每日任务上限（0 表示不限制）
DAILY_TASK_LIMIT = int(os.environ.get("DGTF_APP_DAILY_LIMIT", "10"))
# 是否允许自助注册（默认关闭：成熟后再开）
ALLOW_REGISTER = os.environ.get("DGTF_APP_ALLOW_REGISTER", "0") == "1"
# 会话有效期（秒），默认 7 天
SESSION_TTL = int(os.environ.get("DGTF_APP_SESSION_TTL", str(7 * 24 * 3600)))
# 默认管理员用户名
DEFAULT_ADMIN = os.environ.get("DGTF_APP_ADMIN_USER", "admin.aL")

PBKDF2_ROUNDS = 200_000
COOKIE_NAME = "dgtf_sess"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT    NOT NULL UNIQUE,
  password_hash TEXT    NOT NULL,          -- pbkdf2$<rounds>$<salt_hex>$<hash_hex>
  role          TEXT    NOT NULL DEFAULT 'user',   -- 'admin' | 'user'
  is_active     INTEGER NOT NULL DEFAULT 1,
  created_at    REAL    NOT NULL,
  last_login_at REAL
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,             -- sha256(token)，不存原文
  user_id    INTEGER NOT NULL,
  created_at REAL    NOT NULL,
  expires_at REAL    NOT NULL,
  user_agent TEXT,
  ip         TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_exp  ON sessions(expires_at);

-- 任务发起台账：用于「每日配额」与审计
CREATE TABLE IF NOT EXISTS tasks_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL,
  task_id    TEXT    NOT NULL,
  created_at REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_log_user_time ON tasks_log(user_id, created_at);
"""


# ── 连接 ────────────────────────────────────────────────────────
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """建表（幂等）。"""
    with _connect() as conn:
        conn.executescript(_SCHEMA)


# ── 密码 ────────────────────────────────────────────────────────
def hash_password(plain: str, rounds: int = PBKDF2_ROUNDS) -> str:
    """格式：pbkdf2$<rounds>$<salt_hex>$<hash_hex>。"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, rounds)
    return f"pbkdf2${rounds}${salt.hex()}${dk.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    """恒定时间比较；格式异常一律视为不匹配（不抛异常、不泄露细节）。"""
    try:
        algo, rounds_s, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", plain.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds_s))
        return hmac.compare_digest(dk.hex(), hash_hex)   # ⚠️ 防时序攻击
    except (ValueError, AttributeError):
        return False


def gen_password(n: int = 12) -> str:
    """生成可读性尚可的随机密码（去掉易混淆字符）。"""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))


# ── 用户 ────────────────────────────────────────────────────────
def create_user(username: str, password: str, role: str = "user") -> int:
    """建用户，返回 id。用户名重复会抛 ValueError。"""
    username = (username or "").strip()
    if not username:
        raise ValueError("用户名不能为空")
    if len(username) > 40:
        raise ValueError("用户名过长")
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users(username, password_hash, role, created_at) "
                "VALUES (?,?,?,?)",
                (username, hash_password(password), role, time.time()))
            return int(cur.lastrowid)
        except sqlite3.IntegrityError as e:
            raise ValueError(f"用户名已存在：{username}") from e


def get_user_by_name(username: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?",
                           ((username or "").strip(),)).fetchone()
    return dict(row) if row else None


def get_user(uid: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    return dict(row) if row else None


def list_users() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, username, role, is_active, created_at, last_login_at "
            "FROM users ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def set_password(username: str, password: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                           (hash_password(password), username.strip()))
    return cur.rowcount > 0


def delete_user(username: str) -> bool:
    """删除用户，并连带清掉其会话与任务计数。

    ⚠️ 只删账号与会话，不动磁盘上的 outputs/<用户名>/ 产物目录——
    产物是用户的劳动成果，误删不可恢复，需要时由管理员手工处理。
    """
    u = get_user_by_name(username)
    if not u:
        return False
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (u["id"],))
        conn.execute("DELETE FROM tasks_log WHERE user_id = ?", (u["id"],))
        conn.execute("DELETE FROM users WHERE id = ?", (u["id"],))
    return True


def ensure_admin(username: str = DEFAULT_ADMIN) -> tuple[str, bool]:
    """确保管理员存在。返回 (密码, 是否新建)。新建时密码随机生成。"""
    u = get_user_by_name(username)
    if u:
        return "", False
    pwd = gen_password()
    create_user(username, pwd, role="admin")
    return pwd, True


# ── 会话 ────────────────────────────────────────────────────────
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id: int, user_agent: str = "", ip: str = "") -> str:
    """签发会话，返回 token 原文（只此一次可见；库里只存摘要）。"""
    token = secrets.token_urlsafe(32)
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions(token_hash, user_id, created_at, expires_at, "
            "user_agent, ip) VALUES (?,?,?,?,?,?)",
            (_hash_token(token), user_id, now, now + SESSION_TTL,
             (user_agent or "")[:255], (ip or "")[:64]))
        # 顺手清理该用户已过期的会话，避免表无限增长
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
    return token


def check_session(token: str) -> dict | None:
    """校验 token → 返回用户 dict；无效/过期/被禁用返回 None。"""
    if not token:
        return None
    now = time.time()
    with _connect() as conn:
        row = conn.execute(
            "SELECT s.expires_at, u.* FROM sessions s "
            "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
            (_hash_token(token),)).fetchone()
    if not row:
        return None
    if row["expires_at"] <= now:            # 过期
        return None
    if not row["is_active"]:                # 已禁用
        return None
    return dict(row)


def drop_session(token: str) -> None:
    """登出：删除该会话（即时失效）。"""
    if not token:
        return
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?",
                     (_hash_token(token),))


def drop_user_sessions(user_id: int) -> None:
    """强制下线该用户全部会话。"""
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def touch_login(user_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?",
                     (time.time(), user_id))


# ── 每日配额 ────────────────────────────────────────────────────
def _day_start(ts: float | None = None) -> float:
    """当天 0 点的时间戳（本地时区）。"""
    t = time.localtime(ts if ts is not None else time.time())
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))


def today_count(user_id: int) -> int:
    """该用户今日已发起任务数。"""
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM tasks_log WHERE user_id = ? AND created_at >= ?",
            (user_id, _day_start())).fetchone()
    return int(row["n"]) if row else 0


def quota_status(user_id: int, is_admin: bool = False) -> dict:
    """配额状态，给前端显示。管理员不受限。"""
    if is_admin:
        return {"limit": 0, "used": 0, "remaining": -1, "unlimited": True}
    limit = DAILY_TASK_LIMIT
    used = today_count(user_id)
    if limit <= 0:
        return {"limit": 0, "used": used, "remaining": -1, "unlimited": True}
    return {"limit": limit, "used": used,
            "remaining": max(0, limit - used), "unlimited": False}


def check_quota(user_id: int, is_admin: bool = False) -> tuple[bool, str]:
    """能否再开任务。返回 (允许?, 拒绝原因)。"""
    if is_admin or DAILY_TASK_LIMIT <= 0:
        return True, ""
    used = today_count(user_id)
    if used >= DAILY_TASK_LIMIT:
        return False, f"今日任务额度已用完（{used}/{DAILY_TASK_LIMIT}），请明天再试"
    return True, ""


def log_task(user_id: int, task_id: str) -> None:
    """记一笔任务（配额统计依据）。"""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO tasks_log(user_id, task_id, created_at) VALUES (?,?,?)",
            (user_id, task_id, time.time()))


# ── CLI ─────────────────────────────────────────────────────────
def _cli(argv: list[str]) -> int:
    init_db()
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0

    cmd = argv[0]
    if cmd == "init":
        pwd, created = ensure_admin()
        if created:
            print(f"✅ 已创建管理员：{DEFAULT_ADMIN}")
            print(f"   初始密码：{pwd}")
            print("   ⚠️ 请立即登录并修改密码，此密码只显示这一次。")
        else:
            print(f"ℹ️  管理员 {DEFAULT_ADMIN} 已存在，未改动。")
        print(f"   用户库：{DB_PATH}")
        print(f"   每日任务上限：{DAILY_TASK_LIMIT}   开放注册：{'是' if ALLOW_REGISTER else '否'}")
        return 0

    if cmd == "useradd":
        if len(argv) < 2:
            print("用法：python dgtf_app/auth.py useradd <用户名> [密码]")
            return 1
        name = argv[1]
        pwd = argv[2] if len(argv) > 2 else gen_password()
        try:
            create_user(name, pwd, role="user")
        except ValueError as e:
            print(f"❌ {e}")
            return 1
        print(f"✅ 已创建用户：{name}")
        print(f"   密码：{pwd}")
        return 0

    if cmd == "passwd":
        if len(argv) < 2:
            print("用法：python dgtf_app/auth.py passwd <用户名> [密码]")
            return 1
        name = argv[1]
        pwd = argv[2] if len(argv) > 2 else gen_password()
        if set_password(name, pwd):
            print(f"✅ 已重设 {name} 的密码：{pwd}")
            drop_user_sessions(get_user_by_name(name)["id"])   # 改密后旧会话全失效
            print("   已强制该用户所有会话下线。")
            return 0
        print(f"❌ 用户不存在：{name}")
        return 1

    if cmd == "userdel":
        if len(argv) < 2:
            print("用法：python dgtf_app/auth.py userdel <用户名>")
            return 1
        name = argv[1]
        if name == DEFAULT_ADMIN:
            print(f"❌ 拒绝删除默认管理员 {DEFAULT_ADMIN}。")
            return 1
        if delete_user(name):
            print(f"✅ 已删除用户：{name}（会话与任务计数已清理）")
            print(f"   产物目录 outputs/{name}/ 已保留，如需清理请手工删除。")
            return 0
        print(f"❌ 用户不存在：{name}")
        return 1

    if cmd == "list":
        users = list_users()
        if not users:
            print("（暂无用户）")
            return 0
        print(f"{'ID':<4} {'用户名':<20} {'角色':<7} {'状态':<5} 最后登录")
        for u in users:
            last = (time.strftime("%Y-%m-%d %H:%M", time.localtime(u["last_login_at"]))
                    if u["last_login_at"] else "—")
            print(f"{u['id']:<4} {u['username']:<20} {u['role']:<7} "
                  f"{'启用' if u['is_active'] else '禁用':<5} {last}")
        return 0

    print(f"未知命令：{cmd}")
    return 1


if __name__ == "__main__":
    import sys
    raise SystemExit(_cli(sys.argv[1:]))
