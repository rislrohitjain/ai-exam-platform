import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_workflow():
    print("Testing Registration with Name & Father's Name...")
    
    # 1. Register a new user
    username = "test_student_antigravity"
    password = "student_password_123"
    name = "John Test Doe"
    father_name = "Robert Test Doe"
    role = "candidate"
    
    reg_payload = {
        "username": username,
        "password": password,
        "role": role,
        "name": name,
        "father_name": father_name
    }
    
    response = requests.post(f"{BASE_URL}/api/auth/register", json=reg_payload)
    print("Register Response Status:", response.status_code)
    print("Register Response Body:", response.json())
    assert response.status_code == 200, "Registration failed"
    
    # 2. Login as admin to fetch users
    print("\nLogging in as Admin...")
    login_payload = {
        "username": "admin",
        "password": "admin123"
    }
    response = requests.post(f"{BASE_URL}/api/auth/login", json=login_payload)
    print("Login Status:", response.status_code)
    assert response.status_code == 200, "Admin login failed"
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Get the list of users and find our registered user
    print("\nFetching User List...")
    response = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
    print("Fetch Users Status:", response.status_code)
    users = response.json()
    
    user_record = None
    for u in users:
        if u["username"] == username:
            user_record = u
            break
            
    assert user_record is not None, "Registered user not found in admin list"
    print("Found user record in admin list:")
    print(json.dumps(user_record, indent=2))
    assert user_record["name"] == name, "Name mismatch"
    assert user_record["father_name"] == father_name, "Father name mismatch"
    
    # 4. Modify name and father's name as admin
    print("\nUpdating Name and Father's Name as Admin...")
    updated_name = "John Updated Doe"
    updated_father = "Robert Updated Doe"
    
    update_payload = {
        "roles": role,
        "name": updated_name,
        "father_name": updated_father
    }
    
    response = requests.put(
        f"{BASE_URL}/api/admin/users/{username}/role", 
        json=update_payload, 
        headers=headers
    )
    print("Update Response Status:", response.status_code)
    print("Update Response Body:", response.json())
    assert response.status_code == 200, "Admin user update failed"
    
    # 5. Verify the updates persisted
    print("\nVerifying Updated Record...")
    response = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
    users = response.json()
    
    user_record = None
    for u in users:
        if u["username"] == username:
            user_record = u
            break
            
    assert user_record is not None, "User not found after update"
    print("Updated user record in admin list:")
    print(json.dumps(user_record, indent=2))
    assert user_record["name"] == updated_name, "Updated name mismatch"
    assert user_record["father_name"] == updated_father, "Updated father name mismatch"
    
    # 6. Delete the test user to clean up
    print("\nCleaning up test user...")
    response = requests.delete(f"{BASE_URL}/api/admin/users/{username}", headers=headers)
    print("Delete Response Status:", response.status_code)
    assert response.status_code == 200, "Cleanup failed"
    
    print("\nAll API tests for registration and admin edit passed successfully!")

if __name__ == "__main__":
    test_workflow()
