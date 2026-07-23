import psycopg2
import requests
import json

LOCAL_URL = "postgresql://postgres:Admin%40123@localhost:5432/ai-exam-platform"
NEON_URL = "postgresql://neondb_owner:npg_DYXMv5B0glPq@ep-blue-hall-ang445o4-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"
HTTP_URL = "https://ep-blue-hall-ang445o4-pooler.c-6.us-east-1.aws.neon.tech/sql"

headers = {
    "Neon-Connection-String": NEON_URL,
    "Content-Type": "application/json"
}

def execute_neon(sql):
    payload = {"query": sql}
    try:
        res = requests.post(HTTP_URL, headers=headers, json=payload, timeout=30)
        if res.status_code == 200:
            return True, res.json()
        else:
            return False, res.text
    except Exception as e:
        return False, str(e)

print("Connecting to local PostgreSQL database...")
local_conn = psycopg2.connect(LOCAL_URL)
local_cur = local_conn.cursor()

# Get all tables in public schema
local_cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
tables = [r[0] for r in local_cur.fetchall()]

print(f"Found {len(tables)} tables in local database: {tables}")

# Order tables to satisfy foreign key dependencies
ordered_tables = [
    "organizations",
    "users",
    "categories",
    "category_organizations",
    "user_organizations",
    "question_papers",
    "questions",
    "exam_submissions",
    "certificates",
    "platform_settings",
    "visitor_counts"
]

# Disable foreign keys temporarily during insert
execute_neon("SET session_replication_role = 'replica';")

total_inserted = 0

for t in ordered_tables:
    if t not in tables:
        continue

    # Fetch columns
    local_cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{t}' ORDER BY ordinal_position;")
    cols_info = local_cur.fetchall()
    col_names = [c[0] for c in cols_info]

    # Fetch rows
    local_cur.execute(f"SELECT * FROM {t};")
    rows = local_cur.fetchall()

    if not rows:
        print(f"Table '{t}': 0 rows to copy.")
        continue

    print(f"Copying {len(rows)} rows to table '{t}' in Neon...")

    # Build INSERT queries
    for row in rows:
        formatted_vals = []
        for val in row:
            if val is None:
                formatted_vals.append("NULL")
            elif isinstance(val, bool):
                formatted_vals.append("TRUE" if val else "FALSE")
            elif isinstance(val, (int, float)):
                formatted_vals.append(str(val))
            elif isinstance(val, (dict, list)):
                formatted_vals.append("'" + json.dumps(val).replace("'", "''") + "'")
            else:
                # String / text / timestamp / vector
                val_str = str(val).replace("'", "''")
                formatted_vals.append(f"'{val_str}'")

        col_str = ", ".join([f'"{c}"' for c in col_names])
        val_str = ", ".join(formatted_vals)
        insert_sql = f'INSERT INTO "{t}" ({col_str}) VALUES ({val_str}) ON CONFLICT DO NOTHING;'

        ok, err = execute_neon(insert_sql)
        if ok:
            total_inserted += 1
        else:
            print(f"  Failed insert in {t}: {err}")

execute_neon("SET session_replication_role = 'origin';")

print(f"\nData copying completed! Total rows inserted across tables: {total_inserted}")

local_cur.close()
local_conn.close()
