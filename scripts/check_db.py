"""Quick DB integrity check."""
import sqlite3
from pathlib import Path

db_path = Path(r"d:\CODE\Plotpilot\data\plotpilot.db")
print(f"DB exists: {db_path.exists()}")
print(f"DB size: {db_path.stat().st_size / 1024 / 1024:.1f} MB")

conn = sqlite3.connect(str(db_path))
try:
    result = conn.execute("PRAGMA integrity_check").fetchone()
    print(f"Integrity check: {result[0]}")
    
    # Check tables
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    print(f"Tables: {len(tables)}")
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM [{t[0]}]").fetchone()[0]
        print(f"  {t[0]}: {count} rows")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
