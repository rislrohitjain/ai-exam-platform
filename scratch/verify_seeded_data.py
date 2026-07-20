import os
import sys

# Add project root to python path to import models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import SessionLocal, engine
from app.models.db_models import User, Category, QuestionPaper, Question, ExamSubmission, Certificate, Organization, PlatformSettings

def run_verification():
    print("=" * 60)
    print("DATABASE SEED VERIFICATION RESULTS")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Check connection URL
        print(f"Connected to Database URL: {engine.url}")
        
        # 1. Organizations Count
        orgs_count = db.query(Organization).count()
        print(f"Organizations Count: {orgs_count}")
        print("Sample Organizations:")
        for org in db.query(Organization).limit(5).all():
            print(f" - [{org.type.upper()}] {org.name}")
        print("-" * 40)
        
        # 2. Users Count
        users_count = db.query(User).count()
        students_count = db.query(User).filter(User.roles.like("%candidate%")).count()
        instructors_count = db.query(User).filter(User.roles.like("%instructor%")).count()
        admins_count = db.query(User).filter(User.roles.like("%admin%")).count()
        print(f"Total Users: {users_count}")
        print(f" - Students (candidates): {students_count}")
        print(f" - Instructors: {instructors_count}")
        print(f" - Admins: {admins_count}")
        
        print("Sample Students:")
        for user in db.query(User).filter(User.roles.like("%candidate%")).limit(5).all():
            # Get associated organization names
            org_names = ", ".join([org.name for org in user.organizations])
            print(f" - Username: {user.username} | Orgs: {org_names}")
        print("-" * 40)
        
        # 3. Categories Count
        categories_count = db.query(Category).count()
        print(f"Categories Count: {categories_count}")
        print("Sample Categories:")
        for cat in db.query(Category).limit(5).all():
            print(f" - {cat.name}")
        print("-" * 40)
        
        # 4. Question Papers & Questions Count
        papers_count = db.query(QuestionPaper).count()
        questions_count = db.query(Question).count()
        objective_count = db.query(Question).filter(Question.type == "objective").count()
        subjective_count = db.query(Question).filter(Question.type == "subjective").count()
        print(f"Question Papers Count: {papers_count}")
        print(f"Total Questions: {questions_count} ({objective_count} MCQs, {subjective_count} Subjectives)")
        print("Sample Question Papers:")
        for paper in db.query(QuestionPaper).limit(5).all():
            print(f" - [{paper.code}] {paper.title} | Marks: {paper.total_marks}")
        print("-" * 40)
        
        # 5. Exam Submissions Count
        submissions_count = db.query(ExamSubmission).count()
        evaluated_count = db.query(ExamSubmission).filter(ExamSubmission.status == "evaluated").count()
        pending_count = db.query(ExamSubmission).filter(ExamSubmission.status == "pending").count()
        print(f"Exam Submissions Count: {submissions_count}")
        print(f" - Evaluated: {evaluated_count}")
        print(f" - Pending Evaluation: {pending_count}")
        
        # Check grade distribution
        from sqlalchemy import func
        grade_stats = db.query(ExamSubmission.final_grade, func.count(ExamSubmission.id)).group_by(ExamSubmission.final_grade).all()
        print("Grade Distribution:")
        for grade, count in grade_stats:
            print(f" - Grade {grade}: {count}")
        print("-" * 40)
        
        # 6. Certificates Count
        certs_count = db.query(Certificate).count()
        print(f"Certificates Issued: {certs_count}")
        print("Sample Certificates:")
        for cert in db.query(Certificate).limit(5).all():
            print(f" - ID: {cert.id} | Student: {cert.student_id} | Paper ID: {cert.paper_id}")
        print("-" * 40)
        
        # 7. Platform Settings Settings
        platform_settings = db.query(PlatformSettings).first()
        if platform_settings:
            print("Platform Settings (AI Configs):")
            print(f" - Active Provider: {platform_settings.active_provider}")
            print(f" - Ollama URL: {platform_settings.ollama_base_url} | Model: {platform_settings.ollama_model}")
            print(f" - OpenAI Model: {platform_settings.openai_model}")
            print(f" - Groq Model: {platform_settings.groq_model}")
        else:
            print("Platform Settings (AI Configs): NOT FOUND")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error during verification: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_verification()
