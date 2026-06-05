"""各入口共用的 SQLite PRAGMA，避免零散 connect 遗漏 busy_timeout/WAL 导致 database is locked。"""

import sqlite3

# 与 DatabaseConnection.get_connection 对齐；SQLite busy_handler 毫秒
# 默认 5 秒；可通过 set_busy_timeout() 在启动时从 performance.yaml 读取覆盖
BUSY_TIMEOUT_MS: int = 5000


def set_busy_timeout(ms: int) -> None:
    """启动时从配置中心调用，覆盖默认 busy_timeout。"""
    global BUSY_TIMEOUT_MS
    BUSY_TIMEOUT_MS = max(1000, min(ms, 60000))  # 钳位 1s ~ 60s


def apply_standard_pragmas(conn: sqlite3.Connection) -> None:
    """在 sqlite3.connect 之后立刻调用（单连接、连接池、短连接均需）。"""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA wal_autocheckpoint=1000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA cache_size=-32768")
