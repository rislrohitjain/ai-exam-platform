"""
One-time SQLite migration script.
Renames the old 'role' column to 'roles' in the users table,
and re-seeds default accounts if the table is empty after migration.
"""
import sqlite3
import hashlib

DB_PATH = "ai_exam_db.db"
SALT = "ai_exam_platform_salt_2026"

def hash_password(password: str) -> str:
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        SALT.encode('utf-8'),
        100000
    )
    return pw_hash.hex()

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Check current columns
cur.execute("PRAGMA table_info(users)")
cols = [row[1] for row in cur.fetchall()]
print("Current users columns:", cols)

if "roles" not in cols:
    if "role" in cols:
        print("Renaming column 'role' -> 'roles' ...")
        cur.execute("ALTER TABLE users RENAME COLUMN role TO roles")
        conn.commit()
        print("Done.")
    else:
        print("Neither 'role' nor 'roles' found — adding 'roles' column ...")
        cur.execute("ALTER TABLE users ADD COLUMN roles TEXT NOT NULL DEFAULT 'candidate'")
        conn.commit()
        print("Done.")
else:
    print("Column 'roles' already exists — no migration needed.")

# Verify final schema
cur.execute("PRAGMA table_info(users)")
cols_after = [row[1] for row in cur.fetchall()]
print("Final users columns:", cols_after)

# Show current users
cur.execute("SELECT id, username, roles FROM users")
rows = cur.fetchall()
print(f"\nExisting users ({len(rows)} total):")
for r in rows:
    print(f"  id={r[0]}  username={r[1]}  roles={r[2]}")

# Re-seed if empty
if len(rows) == 0:
    print("\nNo users found — seeding defaults ...")
    cur.execute(
        "INSERT INTO users (username, hashed_password, roles) VALUES (?, ?, ?)",
        ("admin", hash_password("admin123"), "admin,instructor,candidate")
    )
    cur.execute(
        "INSERT INTO users (username, hashed_password, roles) VALUES (?, ?, ?)",
        ("student", hash_password("student123"), "candidate")
    )
    conn.commit()
    print("Seeded admin (admin123) and student (student123).")

conn.close()
print("\nMigration complete.")
