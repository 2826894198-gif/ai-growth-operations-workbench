"""SQLite demo-only schema fix for migration 0008 altered tables.

Production/Postgres uses `alembic upgrade head`; this helper only upgrades a
SQLite demo database that was created with Base.metadata.create_all before the
optimization pass columns existed.

Usage:
    cd backend && .venv/bin/python ../scripts/fix_schema_0008.py ../demo_data.db
"""

import sqlite3
import sys


def column_exists(cursor, table: str, column: str) -> bool:
    rows = cursor.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def add_column(cursor, table: str, column: str, definition: str) -> None:
    if column_exists(cursor, table, column):
        print(f"skip {table}.{column} (exists)")
        return
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    print(f"added {table}.{column}")


def main(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    add_column(cursor, "recommendations", "canonical_entity_id", "VARCHAR(36)")
    add_column(cursor, "recommendations", "case_status", "VARCHAR(32) DEFAULT 'DRAFT' NOT NULL")
    add_column(cursor, "recommendations", "simulated_impact", "JSON")
    add_column(cursor, "recommendations", "ai_explanation", "TEXT")
    add_column(cursor, "recommendations", "decision_reason", "TEXT")
    add_column(cursor, "execution_intents", "canonical_entity_id", "VARCHAR(36)")
    add_column(cursor, "execution_intents", "action_package_hash", "VARCHAR(64)")
    add_column(cursor, "execution_intents", "credential_version", "VARCHAR(64)")
    add_column(cursor, "execution_intents", "metric_snapshot_id", "VARCHAR(36)")
    add_column(cursor, "fact_ad_performance_daily", "measurement_basis", "VARCHAR(64) DEFAULT 'PLATFORM_REPORTED' NOT NULL")
    conn.commit()
    conn.close()
    print("schema fix complete")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../demo_data.db")
