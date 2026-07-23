import requests

NEON_URL = "postgresql://neondb_owner:npg_DYXMv5B0glPq@ep-blue-hall-ang445o4-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"
HTTP_URL = "https://ep-blue-hall-ang445o4-pooler.c-6.us-east-1.aws.neon.tech/sql"

headers = {
    "Neon-Connection-String": NEON_URL,
    "Content-Type": "application/json"
}

tables = [
    "categories", "category_organizations", "certificates", 
    "exam_submissions", "organizations", "platform_settings", 
    "question_papers", "questions", "user_organizations", 
    "users", "visitor_counts"
]

print("Verifying Table Row Counts in Neon DB:\n")
for t in sorted(tables):
    res = requests.post(HTTP_URL, headers=headers, json={"query": f"SELECT COUNT(*) FROM {t};"}, timeout=10)
    if res.status_code == 200:
        cnt = res.json()["rows"][0]["count"]
        print(f"  [OK] Table: {t:<25} | Rows: {cnt}")
    else:
        print(f"  [ERR] Table: {t:<25} | Error: {res.text}")
