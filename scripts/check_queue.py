"""Check persistence_queue table."""
import sqlite3
from pathlib import Path

db_path = Path(r"d:\CODE\Plotpilot\data\plotpilot.db")
conn = sqlite3.connect(str(db_path))
try:
    r = conn.execute("SELECT COUNT(*) FROM persistence_queue").fetchone()
    print(f"Queue rows: {r[0]}")

    r2 = conn.execute("SELECT MIN(id), MAX(id) FROM persistence_queue").fetchone()
    print(f"ID range: {r2[0]} - {r2[1]}")

    r3 = conn.execute("SELECT command_type, COUNT(*) as cnt FROM persistence_queue GROUP BY command_type ORDER BY cnt DESC").fetchall()
    print("By command_type:")
    for row in r3:
        print(f"  {row[0]}: {row[1]}")

    r4 = conn.execute("SELECT status, COUNT(*) as cnt FROM persistence_queue GROUP BY status ORDER BY cnt DESC").fetchall()
    print("\nBy status:")
    for row in r4:
        print(f"  {row[0]}: {row[1]}")

    # Sample
    sample = conn.execute("SELECT id, command_type, status, substr(payload, 1, 200) FROM persistence_queue WHERE status='pending' ORDER BY id DESC LIMIT 5").fetchall()
    print("\nLatest 5 pending entries:")
    for s in sample:
        print(f"  id={s[0]} type={s[1]} status={s[2]} payload={s[3][:120]}...")
finally:
    conn.close()
