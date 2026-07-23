import re
import requests
import json
import time

NEON_URL = "postgresql://neondb_owner:npg_DYXMv5B0glPq@ep-blue-hall-ang445o4-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"
HTTP_URL = "https://ep-blue-hall-ang445o4-pooler.c-6.us-east-1.aws.neon.tech/sql"

headers = {
    "Neon-Connection-String": NEON_URL,
    "Content-Type": "application/json"
}

def execute_sql(sql):
    payload = {"query": sql}
    try:
        res = requests.post(HTTP_URL, headers=headers, json=payload, timeout=30)
        if res.status_code == 200:
            return True, res.json()
        else:
            return False, res.text
    except Exception as e:
        return False, str(e)

print("Reading ai-exam-platform.sql...")
with open("ai-exam-platform.sql", "r", encoding="utf-8") as f:
    sql_text = f.read()

# Remove comments starting with --
lines = []
for line in sql_text.splitlines():
    stripped = line.strip()
    if stripped.startswith("--") or stripped.startswith("\\") or not stripped:
        continue
    lines.append(line)

cleaned_sql = "\n".join(lines)

# Split by semicolon (ignoring semicolons inside strings/functions if any)
# Standard pg_dump statements end with semicolon at line end
raw_statements = cleaned_sql.split(";\n")

statements = []
for stmt in raw_statements:
    s = stmt.strip()
    if s:
        if not s.endswith(";"):
            s += ";"
        statements.append(s)

print(f"Total SQL statements to execute: {len(statements)}")

success_count = 0
error_count = 0

for i, stmt in enumerate(statements):
    # Skip SET commands that aren't needed or cause issues in Neon HTTP
    if stmt.upper().startswith("SET ") or stmt.upper().startswith("SELECT PG_CATALOG"):
        continue

    ok, result = execute_sql(stmt)
    if ok:
        success_count += 1
        if i % 10 == 0 or "CREATE TABLE" in stmt.upper():
            first_line = stmt.split("\n")[0][:60]
            print(f"[{i+1}/{len(statements)}] OK: {first_line}")
    else:
        # Ignore "already exists" errors for tables/extensions if re-run
        if "already exists" in str(result):
            print(f"[{i+1}/{len(statements)}] NOTICE (Already exists): {stmt.split('\n')[0][:50]}")
            success_count += 1
        else:
            error_count += 1
            print(f"[{i+1}/{len(statements)}] ERROR: {stmt.split('\n')[0][:60]}")
            print("   Details:", result)

print(f"\nMigration completed! Success: {success_count}, Errors: {error_count}")

# Verify tables
ok, res = execute_sql("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
if ok:
    tables = [r["table_name"] for r in res.get("rows", [])]
    print(f"\nTables present in Neon DB ({len(tables)}):")
    for t in sorted(tables):
        print("  -", t)
