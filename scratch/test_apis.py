import requests
import time

BASE_URL = "http://localhost:8000"

def test_workflow():
    print("--- Starting End-to-End API Integration Test ---")
    
    # 1. Register a test admin and candidate (or use seeded admin/student)
    session = requests.Session()
    
    # Seeded accounts: admin/admin123 and student/student123
    print("Logging in as admin...")
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if login_resp.status_code != 200:
        print(f"Admin login failed: {login_resp.text}")
        return
    
    admin_token = login_resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("Admin login successful.")

    # 2. Create a Category
    print("Creating category...")
    cat_resp = session.post(f"{BASE_URL}/api/admin/categories", json={
        "name": "Computer Science",
        "parent_id": None
    }, headers=admin_headers)
    if cat_resp.status_code not in (200, 201):
        print(f"Category creation failed: {cat_resp.text}")
        return
    cat_id = cat_resp.json()["category_id"]
    print(f"Category 'Computer Science' created with ID: {cat_id}")

    # 3. Create a Question Paper
    print("Creating question paper...")
    paper_resp = session.post(f"{BASE_URL}/api/admin/papers", json={
        "code": "CS-101",
        "title": "Introduction to Computer Science",
        "category_id": cat_id,
        "grade_thresholds": {"A++": 90.0, "A": 80.0, "B": 70.0, "C": 50.0},
        "description": "Basics of CS including programming and systems."
    }, headers=admin_headers)
    if paper_resp.status_code not in (200, 201):
        print(f"Question paper creation failed: {paper_resp.text}")
        return
    paper_id = paper_resp.json()["paper_id"]
    print(f"Question paper created with ID: {paper_id}")

    # 4. Add Questions
    # Objective Question
    print("Adding objective question...")
    q1_resp = session.post(f"{BASE_URL}/api/admin/papers/{paper_id}/questions", json={
        "type": "objective",
        "content": "What is the time complexity of binary search?",
        "answer_key": "O(log n)",
        "marks": 5.0,
        "option_a": "O(n)",
        "option_b": "O(log n)",
        "option_c": "O(n log n)",
        "option_d": "O(1)"
    }, headers=admin_headers)
    if q1_resp.status_code not in (200, 201):
        print(f"Objective question creation failed: {q1_resp.text}")
        return
    q1_id = q1_resp.json()["question_id"]
    print(f"Objective question added with ID: {q1_id}")

    # Subjective Question
    print("Adding subjective question...")
    q2_resp = session.post(f"{BASE_URL}/api/admin/papers/{paper_id}/questions", json={
        "type": "subjective",
        "content": "Explain what a virtual memory is and why it is useful.",
        "answer_key": "Virtual memory is a memory management capability of an OS that uses hardware and software to allow a computer to compensate for physical memory shortages, temporarily transferring data from random access memory (RAM) to disk storage.",
        "marks": 10.0
    }, headers=admin_headers)
    if q2_resp.status_code not in (200, 201):
        print(f"Subjective question creation failed: {q2_resp.text}")
        return
    q2_id = q2_resp.json()["question_id"]
    print(f"Subjective question added with ID: {q2_id}")

    # 5. Login as student
    print("Logging in as student...")
    login_student_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "username": "student",
        "password": "student123"
    })
    if login_student_resp.status_code != 200:
        print(f"Student login failed: {login_student_resp.text}")
        return
    student_token = login_student_resp.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}
    print("Student login successful.")

    # 6. Submit Exam Response
    print("Submitting student responses...")
    submit_resp = session.post(f"{BASE_URL}/api/evaluation/submit", json={
        "student_id": "student",
        "paper_id": paper_id,
        "responses": [
            {"question_id": q1_id, "answer": "O(log n)"},
            {"question_id": q2_id, "answer": "Virtual memory is a technique that uses hard drive space as temporary RAM to handle memory shortage."}
        ]
    }, headers=student_headers)
    if submit_resp.status_code not in (200, 202):
        print(f"Exam submission failed: {submit_resp.text}")
        return
    submission_id = submit_resp.json()["submission_id"]
    print(f"Exam submitted successfully. Submission ID: {submission_id}")

    # 7. Check status of evaluation (it runs in background, so poll a few times)
    print("Polling evaluation status...")
    for _ in range(10):
        status_resp = session.get(f"{BASE_URL}/api/evaluation/submissions/{submission_id}", headers=student_headers)
        if status_resp.status_code != 200:
            print(f"Error checking submission status: {status_resp.text}")
            break
        data = status_resp.json()
        status = data.get("status")
        print(f"Current status: {status}")
        if status in ("evaluated", "failed"):
            print("Evaluation finished!")
            print(f"Submission details: {data}")
            break
        time.sleep(2)
    else:
        print("Polling timed out. Evaluation still pending or stuck.")

if __name__ == "__main__":
    test_workflow()
