import os
import sys
import datetime
import uuid
import random
from sqlalchemy import text

# Add project root to python path to import models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import Base, engine, SessionLocal
from app.models.db_models import User, Category, QuestionPaper, Question, ExamSubmission, Certificate, Organization
from app.api.auth import hash_password
from app.services.pdf_service import generate_signature
from app.services.llm_factory import get_settings

# Re-create database schemas to start fresh
print("Wiping and re-creating database schemas...")
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("Database schemas created.")

db = SessionLocal()

# Common First Names & Jaipur/Rajasthan Surnames
first_names = [
    "Aarav", "Ananya", "Rahul", "Priya", "Amit", "Neha", "Rohit", "Siddharth", "Kavita", "Aditya",
    "Pooja", "Vikram", "Deepa", "Sanjay", "Anjali", "Arjun", "Ritu", "Manish", "Shreya", "Vijay",
    "Abhishek", "Divya", "Karan", "Kiran", "Nikhil", "Nisha", "Pranav", "Prerna", "Rajesh", "Riya",
    "Sandeep", "Sneha", "Tushar", "Vasudha", "Varun", "Yash", "Tanvi", "Rohan", "Meera", "Sameer",
    "Lokesh", "Deepak", "Surendra", "Yogesh", "Swati", "Jyoti", "Priyanka", "Saurabh", "Hemant", "Harish",
    "Chandra", "Bhupendra", "Devendra", "Jitendra", "Kapil", "Rajendra", "Rakesh", "Ayush", "Anuj", "Hemendra"
]

last_names = [
    "Sharma", "Verma", "Gupta", "Singh", "Meena", "Choudhary", "Jangid", "Saini", "Shekhawat", "Rathore",
    "Agarwal", "Jain", "Vijay", "Mathur", "Khandelwal", "Yadav", "Soni", "Mishra", "Pandey", "Saxena"
]

def generate_indian_names(count=100):
    generated = set()
    random.seed(42)  # For reproducibility
    while len(generated) < count:
        first = random.choice(first_names)
        last = random.choice(last_names)
        username = f"{first.lower()}_{last.lower()}"
        if username not in generated:
            generated.add(username)
    return sorted(list(generated))

try:
    # Seed default platform settings
    print("Initializing platform configurations (AI Configs)...")
    get_settings(db)

    print("Seeding 15 Real-world Jaipur Colleges (Organizations)...")
    colleges_list = [
        ("Malaviya National Institute of Technology Jaipur", "MNIT"),
        ("Manipal University Jaipur", "MUJ"),
        ("LNM Institute of Information Technology", "LNMIIT"),
        ("University of Rajasthan", "RU"),
        ("Jaipur National University", "JNU"),
        ("JECRC University", "JECRC"),
        ("Swami Keshvanand Institute of Technology", "SKIT"),
        ("Poornima University", "PU"),
        ("Arya College of Engineering & IT", "ARYA"),
        ("NIMS University Jaipur", "NIMS"),
        ("Biyani Group of Colleges", "BIYANI"),
        ("St. Wilfred's College", "WILFRED"),
        ("S.S. Jain Subodh PG College", "SUBODH"),
        ("University Maharani College", "MAHARANI"),
        ("University Maharaja College", "MAHARAJA")
    ]
    
    org_objs = []
    for name, code in colleges_list:
        org = Organization(name=name, type="college", description=f"Prestigious institute of higher education in Jaipur: {name} ({code})")
        db.add(org)
        org_objs.append(org)
    db.commit()
    
    # Reload organizations to get IDs
    orgs = db.query(Organization).all()
    print(f"Seeded {len(orgs)} colleges.")

    print("Seeding 100 Indian Student Candidates based in Jaipur...")
    usernames = generate_indian_names(100)
    student_users = []
    
    random.seed(12345) # For reproducible allocations
    for i, uname in enumerate(usernames):
        # Reconstruct name components from username
        parts = uname.split("_")
        first = parts[0].capitalize()
        last = parts[1].capitalize()
        full_name = f"{first} {last}"
        
        # Pick a father's name with the same last name but a different first name
        father_first = random.choice([fn for fn in first_names if fn.lower() != first.lower()])
        father_name = f"{father_first} {last}"

        # Configure multiple organizations (tenancy)
        if i < 5:
            student_orgs = orgs
        else:
            student_orgs = random.sample(orgs, random.randint(1, 4))
            
        primary_org_id = student_orgs[0].id
        user = User(
            username=uname,
            name=full_name,
            father_name=father_name,
            hashed_password=hash_password("student123"),
            plain_password="student123",
            roles="candidate",
            organization_id=primary_org_id,
            organizations=student_orgs
        )
        db.add(user)
        student_users.append(user)
    
    print("Seeding 5 Jaipur Instructor Users (with multiple organization tenancies)...")
    for j in range(1, 6):
        instr_orgs = random.sample(orgs, random.randint(2, 5))
        
        # Generate instructor names
        first = random.choice(first_names)
        last = random.choice(last_names)
        full_name = f"{first} {last}"
        father_first = random.choice([fn for fn in first_names if fn.lower() != first.lower()])
        father_name = f"{father_first} {last}"

        instructor = User(
            username=f"instructor_{j}",
            name=full_name,
            father_name=father_name,
            hashed_password=hash_password("instructor123"),
            plain_password="instructor123",
            roles="instructor",
            organization_id=instr_orgs[0].id,
            organizations=instr_orgs
        )
        db.add(instructor)

    # Seed 1 admin user
    admin_user = User(
        username="admin",
        name="Rajesh Verma (Admin)",
        father_name="Omprakash Verma",
        hashed_password=hash_password("admin123"),
        plain_password="admin123",
        roles="admin,instructor,candidate",
        organization_id=None,
        organizations=[]
    )
    db.add(admin_user)
    db.commit()
    print("Seeded 100 students, 5 instructors, and 1 admin.")

    print("Seeding 15 Categories & Question Papers...")
    topics = [
        ("Data Structures & Algorithms", "DSA-2026-M", "Fundamental and advanced algorithms, complexity analysis, and linear/non-linear structures."),
        ("Advanced Operating Systems", "OS-2026-M", "Process scheduling, thread concurrency, virtual memory mapping, and file system page caches."),
        ("Compiler Design Foundations", "CD-2026-M", "Lexical parsing, syntax analysis trees, intermediate code generation, and optimization phases."),
        ("Computer Networks & Security", "NET-2026-M", "TCP/IP protocol suites, CIDR subnet routing, TLS handshakes, and cryptographic verification."),
        ("Database Management Systems", "DBMS-2026-M", "Relational algebra, normal forms, B-tree indexes, transactions ACID, and query planning."),
        ("Object Oriented Programming", "OOP-2026-M", "Encapsulation, inheritance structures, polymorphism interfaces, and design patterns."),
        ("Theory of Computation", "TOC-2026-M", "Finite automata, regular expressions, context-free grammars, and Turing machine decidability."),
        ("Software Engineering Methodologies", "SE-2026-M", "Agile sprints, software architecture patterns, CI/CD pipelines, and automated testing."),
        ("Artificial Intelligence & ML", "AI-2026-M", "Supervised/unsupervised models, activation functions, backpropagation, and loss optimizers."),
        ("Cloud Computing Architectures", "CLOUD-2026-M", "Virtualization, IAM security policies, autoscaling groups, and serverless compute functions."),
        ("Discrete Mathematics", "DM-2026-M", "Propositional logic, set theory, graph colorings, combinatorics, and recurrence relations."),
        ("Digital Logic & Design", "DLD-2026-M", "Boolean minimization, K-maps, combinational multiplexers, sequential flip-flops, and counters."),
        ("Microprocessors & Interfaces", "MP-2026-M", "Assembly registers, memory segment offsets, interrupts vector tables, and DMA controllers."),
        ("Web Technology & Standards", "WEB-2026-M", "HTTP protocol details, DOM painting pipelines, React hooks state, and asynchronous networking."),
        ("Data Science & Analytics", "DS-2026-M", "Exploratory data analysis, Pandas operations, feature scaling, and statistics distribution.")
    ]

    papers = []
    all_questions = []

    # Question template helpers
    mcq_details = [
        ("What is the primary advantage of {concept}?", "Increases raw efficiency", "Reduces execution complexity", "Simplifies implementation layout", "Enhances modular reusability", "B"),
        ("Which of the following best describes the core operation of {concept}?", "Executes queries concurrently", "Performs linear operations", "Decouples state from data structures", "Minimizes structural overhead", "C"),
        ("In {concept}, which error is most commonly encountered during runtime?", "Stack Overflow exception", "Null Pointer reference", "OutOfMemory allocation error", "Type Mismatch conversion", "A"),
        ("What is the average case complexity of {concept} operations?", "O(1) constant time", "O(log n) logarithmic time", "O(n) linear complexity", "O(n log n) linearithmic time", "B"),
        ("Which design pattern is best suited to manage {concept} instantiations?", "Singleton pattern", "Factory method pattern", "Observer broadcast pattern", "Decorator runtime wrapper", "D"),
        ("Under which condition does {concept} fail to compile or execute?", "Circular dependencies exist", "Null values are passed", "Index exceeds boundary limits", "Class path is undefined", "A"),
        ("What is the optimal size constraint for {concept} allocations?", "Bounded by thread stack size", "Dynamic and auto-expanding", "Fixed at compilation time", "Determined by heap capacity", "B"),
        ("Which mechanism does {concept} utilize to maintain thread safety?", "Mutex lock synchronization", "Optimistic concurrency versioning", "Double-checked volatile locks", "ThreadLocal memory isolation", "C"),
        ("What is the primary difference between {concept} and standard implementations?", "Reduced code boilerplate", "Garbage collection priority", "Asynchronous thread execution", "Lower architectural complexity", "A"),
        ("Which test suite is recommended to validate {concept} operations?", "Unit tests with mock data", "Integration end-to-end runs", "Load testing concurrency suites", "Regression regression checks", "A")
    ]

    subj_details = [
        ("Explain the role and functionality of {concept} in modern software systems. Discuss its architectural benefits and potential scaling bottlenecks.", 
         "{concept} acts as a core operational layer that decouples modules and manages state efficiently. Benefits: scalability, loose coupling. Bottlenecks: network overhead and serialization latency."),
        
        ("Describe the design trade-offs associated with utilizing {concept}. Provide a sample scenario where it outperforms standard approaches.", 
         "Trade-offs include higher initialization memory vs faster runtime lookup. Outperforms standard models when read-heavy operations are performed under high concurrent load."),
         
        ("Detail the security implications of implementing {concept} across public networks. What mitigation strategies should be applied?", 
         "Implications include potential injection attacks and data leakage. Mitigations: implement strict input validation, enable TLS encryption, and apply least-privilege access rules."),
         
        ("Explain the difference between synchronous and asynchronous operations of {concept}. Which model is preferred for real-time applications?", 
         "Synchronous blocks execution until task completion, while asynchronous returns immediate control using callbacks or event loops. Asynchronous is preferred for real-time systems to maintain responsiveness."),
         
        ("Discuss how {concept} integrates with containerized environments (e.g. Docker, Kubernetes). What health metrics should be monitored?", 
         "Integrates via environmental config injection and stateless routing. Key metrics: memory consumption bounds, transaction-per-second throughput, and active socket connection pools.")
    ]

    for idx, (subject, code_prefix, desc) in enumerate(topics):
        # Create category with multiple organizations
        cat_orgs = [orgs[idx]] + random.sample([o for o in orgs if o.id != orgs[idx].id], random.randint(1, 4))
        cat = Category(
            name=subject, 
            parent_id=None, 
            organization_id=orgs[idx].id,
            organizations=cat_orgs
        )
        db.add(cat)
        db.commit()
        db.refresh(cat)
        
        # Create paper (1 per college)
        paper = QuestionPaper(
            code=f"{code_prefix}-001",
            title=f"Advanced {subject}",
            category_id=cat.id,
            organization_id=orgs[idx].id,
            total_marks=0.0,
            grade_thresholds={"A": 80.0, "B": 60.0, "C": 50.0},
            description=desc
        )
        db.add(paper)
        db.commit()
        db.refresh(paper)
        papers.append(paper)
        
        # Concepts specific to this subject to fill templates
        concepts = [f"{subject} Concept {j}" for j in range(15)]
        
        # Add 10 MCQs
        for k in range(10):
            concept = concepts[k]
            q_text_template, opt_a, opt_b, opt_c, opt_d, ans_key = mcq_details[k]
            content = f"{q_text_template.format(concept=concept)}\nA) {opt_a}\nB) {opt_b}\nC) {opt_c}\nD) {opt_d}"
            
            q = Question(
                paper_id=paper.id,
                type="objective",
                content=content,
                answer_key=ans_key,
                marks=2.0,
                option_a=opt_a,
                option_b=opt_b,
                option_c=opt_c,
                option_d=opt_d
            )
            db.add(q)
            all_questions.append(q)
            
        # Add 5 Subjectives
        for k in range(5):
            concept = concepts[10 + k]
            q_text_template, ans_rubric = subj_details[k]
            content = q_text_template.format(concept=concept)
            answer_key = ans_rubric.format(concept=concept)
            
            q = Question(
                paper_id=paper.id,
                type="subjective",
                content=content,
                answer_key=answer_key,
                marks=8.0
            )
            db.add(q)
            all_questions.append(q)
            
        db.commit()
        
    # Reload papers with total marks updated
    for paper in db.query(QuestionPaper).all():
        total = sum(q.marks for q in paper.questions)
        paper.total_marks = total
        db.commit()
        
    print(f"Seeded 15 papers with 15 questions each (Total {len(all_questions)} questions).")

    print("Seeding 160 Submissions and Certificates (mix of evaluated and pending)...")
    
    # We will generate 160 submissions
    random.seed(101)
    
    grades_count = {"A": 0, "B": 0, "C": 0, "F": 0}
    submissions_seeded = 0
    pending_seeded = 0
    
    for s_idx in range(160):
        # Pick student
        student = student_users[s_idx % len(student_users)]
        # Pick paper that student has access to
        student_org_ids = [o.id for o in student.organizations]
        accessible_papers = [p for p in papers if p.organization_id in student_org_ids]
        
        if not accessible_papers:
            accessible_papers = papers # Fallback
            
        paper = random.choice(accessible_papers)
        
        # Get questions for this paper
        paper_qs = db.query(Question).filter(Question.paper_id == paper.id).all()
        mcq_qs = [q for q in paper_qs if q.type == "objective"]
        subj_qs = [q for q in paper_qs if q.type == "subjective"]
        
        # Grade intent: we want a natural spread (A, B, C, F)
        grade_intent = ["A", "B", "C", "F"][s_idx % 4]
        
        responses = []
        evaluated_responses = []
        total_obtained = 0.0
        
        # Grade MCQs (10 questions, 2 marks each)
        for idx_mcq, mq in enumerate(mcq_qs):
            correct = False
            if grade_intent == "A":
                correct = (random.random() < 0.9)  # 90% correct
            elif grade_intent == "B":
                correct = (random.random() < 0.7)  # 70% correct
            elif grade_intent == "C":
                correct = (random.random() < 0.55) # 55% correct
            else:
                correct = (random.random() < 0.3)  # 30% correct
                
            student_ans = mq.answer_key if correct else random.choice([x for x in ["A", "B", "C", "D"] if x != mq.answer_key])
            responses.append({"question_id": mq.id, "answer": student_ans})
            
            score = 2.0 if student_ans == mq.answer_key else 0.0
            total_obtained += score
            
            evaluated_responses.append({
                "question_id": mq.id,
                "score": score,
                "max_marks": 2.0,
                "rationale": "Deterministic match: Student answer matched correct answer key." if score > 0 else f"Deterministic mismatch: Student selected '{student_ans}', correct is '{mq.answer_key}'.",
                "semantic_similarity": 1.0 if score > 0 else 0.0
            })
            
        # Grade Subjectives (5 questions, 8 marks each)
        for idx_sub, sq in enumerate(subj_qs):
            if grade_intent == "A":
                student_text = sq.answer_key + " It operates synchronously and provides immediate scaling results under concurrent load, which reduces operational overhead."
                score = random.choice([7.0, 8.0])
                sim = random.uniform(0.85, 0.95)
                rationale = "Excellent answer. Correctly describes operational mechanisms, decoupling behavior, and scaling trade-offs."
            elif grade_intent == "B":
                student_text = sq.answer_key.replace("scalability, loose coupling", "good layout and structure")
                score = random.choice([5.0, 6.0])
                sim = random.uniform(0.65, 0.80)
                rationale = "Good explanation. Mentions decoupling and state management. Missing detailed latency trade-offs."
            elif grade_intent == "C":
                student_text = "It manages state efficiently. It is used to scale systems but has network issues."
                score = random.choice([4.0, 4.5])
                sim = random.uniform(0.50, 0.60)
                rationale = "Passable answer. Conceptually correct but lacks architectural details and operational mechanism analysis."
            else:
                student_text = "I do not know the exact mechanism of this concept, but it is useful for programming."
                score = random.choice([0.0, 1.0, 2.0])
                sim = random.uniform(0.10, 0.30)
                rationale = "Incomplete/incorrect answer. Fails to describe operational mechanism, benefits, or scaling limitations."
                
            responses.append({"question_id": sq.id, "answer": student_text})
            total_obtained += score
            
            evaluated_responses.append({
                "question_id": sq.id,
                "score": score,
                "max_marks": 8.0,
                "rationale": rationale,
                "semantic_similarity": sim
            })
            
        percentage = (total_obtained / paper.total_marks) * 100
        
        final_grade = "F"
        if percentage >= 80.0:
            final_grade = "A"
        elif percentage >= 60.0:
            final_grade = "B"
        elif percentage >= 50.0:
            final_grade = "C"
            
        # Determine if this submission is pending grading (1 in 8 is pending)
        is_pending = (s_idx % 8 == 0)
        
        if is_pending:
            sub = ExamSubmission(
                student_id=student.username,
                paper_id=paper.id,
                status="pending",
                responses=responses,
                evaluated_responses=None,
                overall_score=None,
                percentage=None,
                final_grade=None,
                created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=random.randint(1, 23))
            )
            db.add(sub)
            db.commit()
            db.refresh(sub)
            pending_seeded += 1
        else:
            grades_count[final_grade] += 1
            sub = ExamSubmission(
                student_id=student.username,
                paper_id=paper.id,
                status="evaluated",
                responses=responses,
                evaluated_responses=evaluated_responses,
                overall_score=total_obtained,
                percentage=percentage,
                final_grade=final_grade,
                created_at=datetime.datetime.utcnow() - datetime.timedelta(days=random.randint(1, 10))
            )
            db.add(sub)
            db.commit()
            db.refresh(sub)
            submissions_seeded += 1
            
            # If passed (A, B, C), seed a certificate
            if final_grade in ["A", "B", "C"]:
                cert_id = str(uuid.uuid4())
                sig = generate_signature(student.username, paper.id, cert_id)
                cert = Certificate(
                    id=cert_id,
                    student_id=student.username,
                    paper_id=paper.id,
                    issue_date=sub.created_at + datetime.timedelta(hours=2),
                    digital_signature=sig
                )
                db.add(cert)
                db.commit()

    print(f"Seeded {submissions_seeded} evaluated submissions.")
    print(f"Seeded {pending_seeded} pending submissions.")
    print(f"Grade distribution (evaluated): {grades_count}")
    print("Database seeding completed successfully with Jaipur locations and names!")

except Exception as seed_err:
    print(f"Error seeding database: {seed_err}")
    db.rollback()
    sys.exit(1)
finally:
    db.close()
