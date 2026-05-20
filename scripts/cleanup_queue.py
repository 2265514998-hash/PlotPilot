"""Cleanup completed persistence_queue entries and vacuum the DB."""
import sqlite3
from pathlib import Path

db_path = Path(r"d:\CODE\Plotpilot\data\plotpilot.db")
print(f"DB size before: {db_path.stat().st_size / 1024 / 1024:.1f} MB")

conn = sqlite3.connect(str(db_path))
try:
    # Delete completed entries
    r = conn.execute("DELETE FROM persistence_queue WHERE status='completed'")
    print(f"Deleted {r.rowcount} completed queue entries")

    # Delete old failed entries too
    r2 = conn.execute("DELETE FROM persistence_queue WHERE status='failed'")
    print(f"Deleted {r2.rowcount} failed queue entries")

    conn.commit()

    remaining = conn.execute("SELECT COUNT(*) FROM persistence_queue").fetchone()[0]
    print(f"Remaining queue entries: {remaining}")

    # Check pending entries
    pending = conn.execute("SELECT id, command_type, status FROM persistence_queue WHERE status='pending'").fetchall()
    print(f"Pending entries: {len(pending)}")
    for p in pending:
        print(f"  id={p[0]} type={p[1]} status={p[2]}")

finally:
    conn.close()

# Vacuum to reclaim space
print("Running VACUUM...")
conn2 = sqlite3.connect(str(db_path))
try:
    conn2.execute("VACUUM")
finally:
    conn2.close()

print(f"DB size after: {db_path.stat().st_size / 1024 / 1024:.1f} MB")
