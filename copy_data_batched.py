import psycopg2
import requests
import json
import sys

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

print("1. Connecting to local PostgreSQL...", flush=True)
local_conn = psycopg2.connect(LOCAL_URL)
local_cur = local_conn.cursor()

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
    "platform_settings"
]

print("2. Disabling FK constraints temporarily in Neon...", flush=True)
execute_neon("SET session_replication_role = 'replica';")

BATCH_SIZE = 30
total_copied = 0

for t in ordered_tables:
    # Fetch columns
    local_cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{t}' ORDER BY ordinal_position;")
    col_names = [c[0] for c in local_cur.fetchall()]

    # Fetch all rows
    local_cur.execute(f"SELECT * FROM {t};")
    rows = local_cur.fetchall()

    if not rows:
        print(f"Table '{t}': 0 rows.", flush=True)
        continue

    print(f"Migrating table '{t}': {len(rows)} rows...", flush=True)

    col_str = ", ".join([f'"{c}"' for c in col_names])

    # Batch rows
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i+BATCH_SIZE]
        val_tuples = []

        for row in batch:
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
                    val_str = str(val).replace("'", "''")
                    formatted_vals.append(f"'{val_str}'")
            val_tuples.append("(" + ", ".join(formatted_vals) + ")")

        batch_sql = f'INSERT INTO "{t}" ({col_str}) VALUES\n' + ",\n".join(val_tuples) + "\nON CONFLICT DO NOTHING;"
        ok, err = execute_neon(batch_sql)
        if ok:
            total_copied += len(batch)
            print(f"  [{i+len(batch)}/{len(rows)}] Inserted batch in '{t}'", flush=True)
        else:
            print(f"  ERROR in batch for '{t}': {err}", flush=True)

execute_neon("SET session_replication_role = 'origin';")

print(f"\n3. Migration finished! Total rows migrated: {total_copied}", flush=True)

local_cur.close()
local_conn.close()
