import psycopg2

LOCAL_URL = "postgresql://postgres:Admin%40123@localhost:5432/ai-exam-platform"

try:
    conn = psycopg2.connect(LOCAL_URL)
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    tables = [r[0] for r in cur.fetchall()]
    print("Local database tables & row counts:")
    for t in sorted(tables):
        cur.execute(f"SELECT COUNT(*) FROM {t};")
        cnt = cur.fetchone()[0]
        print(f" - {t:<25} : {cnt} rows")
    cur.close()
    conn.close()
except Exception as e:
    print("Error:", e)
