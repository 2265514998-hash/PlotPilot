"""一次性清理 persistence_queue 中的历史 CREATE TABLE 任务。"""
from infrastructure.persistence.database.connection import get_connection_pool
from application.engine.services.persistence_queue_v2 import initialize_persistent_queue_v2

if __name__ == "__main__":
    pq = initialize_persistent_queue_v2(get_connection_pool())
    with pq._db_pool.get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c FROM persistence_queue
            WHERE command_type='execute_sql' AND status IN ('pending','processing')
            AND payload LIKE '%CREATE TABLE IF NOT EXISTS worldbuilding%'
            """
        ).fetchone()
        print("清理前 pending worldbuilding DDL:", row["c"])
