import os
import subprocess
import sys

NEON_URL = "postgresql://neondb_owner:npg_DYXMv5B0glPq@ep-blue-hall-ang445o4.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"
SQL_FILE = "ai-exam-platform.sql"

print(f"Connecting to Neon and restoring {SQL_FILE}...")
env = os.environ.copy()

cmd = ["psql", NEON_URL, "-f", SQL_FILE]
result = subprocess.run(cmd, capture_output=True, text=True, env=env)

if result.returncode == 0:
    print("Success! SQL file imported successfully.")
else:
    print(f"Return code: {result.returncode}")
    print("STDOUT sample:", result.stdout[-500:])
    print("STDERR sample:", result.stderr[-500:])

# Let's verify tables
cmd_check = ["psql", NEON_URL, "-c", "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"]
res_check = subprocess.run(cmd_check, capture_output=True, text=True)
print("\nTables in Neon DB:")
print(res_check.stdout)
