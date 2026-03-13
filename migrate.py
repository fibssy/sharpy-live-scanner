"""
migrate.py — Runs pending SQL migrations in order.
"""

import os
import sys
import glob
import psycopg2

def get_conn():
    url = os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url)

def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.commit()

    files = sorted(glob.glob("migrations/*.sql"))
    if not files:
        print("No migration files found.")
        return

    print("Running all migrations in order...")
    for path in files:
        filename = os.path.basename(path)
        cur.execute("SELECT 1 FROM schema_migrations WHERE filename = %s", (filename,))
        if cur.fetchone():
            print(f"  Skipping {filename} (already applied)")
            continue

        print(f"  Applying {filename}...")
        with open(path, "r", encoding="utf-8") as f:
            sql = f.read()
        cur.execute(sql)
        cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (filename,))
        conn.commit()
        print(f"  Done.")

    cur.close()
    conn.close()
    print("All migrations complete.")

if __name__ == "__main__":
    main()
