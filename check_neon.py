import psycopg2
import sys

NEON_URL_443 = "postgresql://neondb_owner:npg_DYXMv5B0glPq@ep-blue-hall-ang445o4-pooler.c-6.us-east-1.aws.neon.tech:443/neondb?sslmode=require"

print("Connecting to Neon over port 443...", flush=True)
try:
    conn = psycopg2.connect(NEON_URL_443, connect_timeout=10)
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    tables = cur.fetchall()
    print(f"SUCCESS on port 443! Found {len(tables)} tables:", flush=True)
    for t in tables:
        print(" -", t[0], flush=True)
    cur.close()
    conn.close()
except Exception as e:
    print("ERROR on port 443:", e, flush=True)
    sys.exit(1)
