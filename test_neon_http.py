import requests

NEON_URL = "postgresql://neondb_owner:npg_DYXMv5B0glPq@ep-blue-hall-ang445o4-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"
http_url = "https://ep-blue-hall-ang445o4-pooler.c-6.us-east-1.aws.neon.tech/sql"

headers = {
    "Neon-Connection-String": NEON_URL,
    "Content-Type": "application/json"
}

print("Testing Neon HTTP SQL API with Neon-Connection-String header...")
payload = {"query": "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"}

try:
    response = requests.post(http_url, headers=headers, json=payload, timeout=10)
    print("Status Code:", response.status_code)
    print("Response JSON:", response.json())
except Exception as e:
    print("HTTP Request failed:", e)
