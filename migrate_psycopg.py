import psycopg2
import sys

LOCAL_URL = "postgresql://postgres:Admin%40123@localhost:5432/ai-exam-platform"
NEON_URL = "postgresql://neondb_owner:npg_DYXMv5B0glPq@ep-blue-hall-ang445o4.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"

print("1. Reading SQL dump file...")
with open("ai-exam-platform.sql", "r", encoding="utf-8") as f:
    sql_content = f.read()

print("2. Connecting to Neon PostgreSQL database...")
try:
    conn = psycopg2.connect(NEON_URL)
    conn.autocommit = True
    cur = conn.cursor()
    print("Connected successfully!")

    print("3. Executing SQL dump on Neon...")
    cur.execute(sql_content)
    print("SQL execution complete!")

    # Verify tables
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    tables = cur.fetchall()
    print(f"4. Successfully migrated {len(tables)} tables to Neon DB:")
    for t in tables:
        print(f"   - {t[0]}")

    cur.close()
    conn.close()
except Exception as e:
    print("Error during migration:", e)
    sys.exit(1)
