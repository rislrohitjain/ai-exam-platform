import os
import sys
import datetime
import uuid
import json
import hashlib
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add project root to python path to import models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.db_models import Base, User, Category, QuestionPaper, Question, ExamSubmission, Certificate, Organization
from app.api.auth import hash_password
from app.services.pdf_service import generate_signature
from app.services.llm_factory import generate_embedding

# Step 1: Connect to default 'postgres' database to create the new target database
pg_default_url = "postgresql://postgres:Admin%40123@localhost:5432/postgres"
engine_default = create_engine(pg_default_url)

print("Connecting to PostgreSQL to check database status...")
try:
    with engine_default.connect() as conn:
        # Autocommit is required to run CREATE DATABASE statements in Postgres
        conn.execution_options(isolation_level="AUTOCOMMIT")
        
        # Check if database already exists
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'ai-exam-platform'")
        ).scalar()
        
        if not exists:
            print("Creating PostgreSQL database 'ai-exam-platform'...")
            conn.execute(text('CREATE DATABASE "ai-exam-platform";'))
            print("Database 'ai-exam-platform' created successfully.")
        else:
            print("Database 'ai-exam-platform' already exists.")
except Exception as db_err:
    print(f"Error creating database: {db_err}")
    sys.exit(1)

# Step 2: Connect to the new 'ai-exam-platform' database
target_db_url = "postgresql://postgres:Admin%40123@localhost:5432/ai-exam-platform"
engine = create_engine(target_db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

print("Initializing table schemas...")
# Check pgvector support to map Vector column correctly
HAS_PGVECTOR = False
try:
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 1 FROM pg_type WHERE typname = 'vector'")).scalar()
        if not res:
            try:
                with engine.begin() as trans:
                    trans.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                res = conn.execute(text("SELECT 1 FROM pg_type WHERE typname = 'vector'")).scalar()
            except Exception:
                pass
        HAS_PGVECTOR = bool(res)
except Exception:
    pass

# We dynamically import the compiler fallback if needed
from app.core import database
database.HAS_PGVECTOR = HAS_PGVECTOR
print(f"pgvector status: {'Supported' if HAS_PGVECTOR else 'Unsupported (falling back to TEXT)'}")

# Drop and recreate schemas to start clean
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("Database schemas initialized.")

db = SessionLocal()

try:
    print("Seeding Organizations...")
    orgs = [
        Organization(name="MIT University", type="college", description="Massachusetts Institute of Technology"),
        Organization(name="Stanford High School", type="school", description="Stanford Preparatory High School"),
        Organization(name="Apex Coaching Classes", type="coaching", description="Apex Professional Engineering Coaching")
    ]
    db.add_all(orgs)
    db.commit()
    
    # Reload from DB to get generated IDs
    org_mit = db.query(Organization).filter(Organization.name == "MIT University").first()
    org_stanford = db.query(Organization).filter(Organization.name == "Stanford High School").first()
    org_apex = db.query(Organization).filter(Organization.name == "Apex Coaching Classes").first()

    print("Seeding Users...")
    users = [
        # Admins get admin, instructor, and candidate roles by default
        User(username="admin", hashed_password=hash_password("admin123"), plain_password="admin123", roles="admin,instructor,candidate", organization_id=None),
        
        # Mapped Student Candidates
        User(username="rohan_gupta", hashed_password=hash_password("student123"), plain_password="student123", roles="candidate", organization_id=org_mit.id),
        User(username="aarav_sharma", hashed_password=hash_password("alex123"), plain_password="alex123", roles="candidate", organization_id=org_mit.id),
        User(username="diya_patel", hashed_password=hash_password("sarah123"), plain_password="sarah123", roles="candidate", organization_id=org_stanford.id),
        User(username="isha_iyer", hashed_password=hash_password("emily123"), plain_password="emily123", roles="candidate", organization_id=org_apex.id),
        User(username="kabir_singh", hashed_password=hash_password("david123"), plain_password="david123", roles="candidate", organization_id=org_mit.id),
        
        # Mapped Instructors
        User(username="instructor_mit", hashed_password=hash_password("mit123"), plain_password="mit123", roles="instructor", organization_id=org_mit.id),
        User(username="instructor_stanford", hashed_password=hash_password("stanford123"), plain_password="stanford123", roles="instructor", organization_id=org_stanford.id),
        User(username="instructor_apex", hashed_password=hash_password("apex123"), plain_password="apex123", roles="instructor", organization_id=org_apex.id)
    ]
    db.add_all(users)
    db.commit()

    print("Seeding Categories (10 items)...")
    categories_dict = {}
    categories_data = [
        ("Software Engineering", org_stanford.id),
        ("Artificial Intelligence", org_apex.id),
        ("Web Development", org_mit.id),
        ("Database Systems", org_mit.id),
        ("Computer Networks", None), # Global
        ("Cybersecurity", None), # Global
        ("Cloud Computing", org_mit.id),
        ("Data Science", org_apex.id),
        ("Operating Systems", org_stanford.id),
        ("Mobile Development", org_mit.id)
    ]
    for name, org_id in categories_data:
        cat = Category(name=name, parent_id=None, organization_id=org_id)
        db.add(cat)
        db.commit()
        categories_dict[name] = cat.id

    print("Seeding Exam Papers (10 items)...")
    papers_data = [
        {
            "code": "SE-2026-M-001",
            "title": "Software Architecture Principles",
            "cat_name": "Software Engineering",
            "org_id": org_stanford.id,
            "desc": "Covers Monolith vs Microservices, REST API design, design patterns, and clean architecture.",
            "thresholds": {"A": 80.0, "B": 60.0, "C": 50.0}
        },
        {
            "code": "AI-2026-M-001",
            "title": "Neural Networks & Gradients",
            "cat_name": "Artificial Intelligence",
            "org_id": org_apex.id,
            "desc": "Covers perceptrons, backpropagation, activation functions, and optimization algorithms.",
            "thresholds": {"A": 85.0, "B": 70.0, "C": 55.0}
        },
        {
            "code": "WD-2026-M-001",
            "title": "Advanced Web Architectures",
            "cat_name": "Web Development",
            "org_id": org_mit.id,
            "desc": "React rendering patterns, Virtual DOM operations, HTTP caching, and WebSocket protocols.",
            "thresholds": {"A": 80.0, "B": 65.0, "C": 50.0}
        },
        {
            "code": "DB-2026-M-001",
            "title": "Relational Database Design",
            "cat_name": "Database Systems",
            "org_id": org_mit.id,
            "desc": "Index strategies, ACID transactions, database normalization rules, and query optimization.",
            "thresholds": {"A": 75.0, "B": 60.0, "C": 50.0}
        },
        {
            "code": "NW-2026-M-001",
            "title": "TCP/IP Protocols & Routing",
            "cat_name": "Computer Networks",
            "org_id": None, # Global
            "desc": "CIDR subnetting, OSI model layers, TCP three-way handshake, DNS propagation.",
            "thresholds": {"A": 80.0, "B": 70.0, "C": 50.0}
        },
        {
            "code": "SY-2026-M-001",
            "title": "Penetration Testing Basics",
            "cat_name": "Cybersecurity",
            "org_id": None, # Global
            "desc": "SQL injections, Cross-Site Scripting (XSS), network sniffing, and asymmetric encryption.",
            "thresholds": {"A": 85.0, "B": 70.0, "C": 60.0}
        },
        {
            "code": "CC-2026-M-001",
            "title": "AWS Cloud Engineering",
            "cat_name": "Cloud Computing",
            "org_id": org_mit.id,
            "desc": "IAM roles, VPC subnet routing, EC2 autoscaling, and serverless architectures.",
            "thresholds": {"A": 80.0, "B": 60.0, "C": 50.0}
        },
        {
            "code": "DS-2026-M-001",
            "title": "Machine Learning & Regression",
            "cat_name": "Data Science",
            "org_id": org_apex.id,
            "desc": "Supervised learning algorithms, regression models, over-fitting, bias-variance trade-off.",
            "thresholds": {"A": 80.0, "B": 65.0, "C": 50.0}
        },
        {
            "code": "OS-2026-M-001",
            "title": "Linux Kernel Concepts",
            "cat_name": "Operating Systems",
            "org_id": org_stanford.id,
            "desc": "Process scheduling, virtual memory management, system calls, and file system layouts.",
            "thresholds": {"A": 75.0, "B": 60.0, "C": 50.0}
        },
        {
            "code": "MD-2026-M-001",
            "title": "Mobile App Architecture",
            "cat_name": "Mobile Development",
            "org_id": org_mit.id,
            "desc": "Model-View-ViewModel (MVVM), native memory management, and asynchronous network tasks.",
            "thresholds": {"A": 80.0, "B": 65.0, "C": 50.0}
        }
    ]

    papers_dict = {}
    for p in papers_data:
        paper = QuestionPaper(
            code=p["code"],
            title=p["title"],
            category_id=categories_dict[p["cat_name"]],
            organization_id=p["org_id"],
            total_marks=0.0, # Will update dynamically as questions are added
            grade_thresholds=p["thresholds"],
            description=p["desc"]
        )
        db.add(paper)
        db.commit()
        papers_dict[p["title"]] = paper.id

    print("Seeding Questions for each Exam Paper...")
    
    # 1. Software Architecture Questions
    se_paper_id = papers_dict["Software Architecture Principles"]
    se_questions = [
        Question(
            paper_id=se_paper_id,
            type="objective",
            content="Which HTTP method is idempotent and primarily used to completely replace an existing resource on a web server?\nA) POST\nB) PUT\nC) PATCH\nD) DELETE",
            answer_key="B",
            marks=2.0
        ),
        Question(
            paper_id=se_paper_id,
            type="subjective",
            content="Explain the primary differences between Monolithic Architecture and Microservices Architecture, highlighting trade-offs regarding deployments and data storage.",
            answer_key="Monolith stores all data in a single shared database and runs as one deployment package. Microservices decouple components into separate services, each with its own database (database-per-service pattern), deployed independently. Trade-offs: Microservices add network complexity, data consistency challenges (eventual consistency), but scale independently and reduce deployment blast radiuses.",
            marks=8.0
        )
    ]
    
    # 2. Neural Networks Questions
    ai_paper_id = papers_dict["Neural Networks & Gradients"]
    ai_questions = [
        Question(
            paper_id=ai_paper_id,
            type="objective",
            content="What activation function outputs values in the range [-1, 1]?\nA) Sigmoid\nB) ReLU\nC) Tanh\nD) Leaky ReLU",
            answer_key="C",
            marks=2.0
        ),
        Question(
            paper_id=ai_paper_id,
            type="subjective",
            content="Describe the vanishing gradient problem in deep neural networks and explain how activation functions like ReLU mitigate it.",
            answer_key="Vanishing gradient occurs when backpropagating gradients through many layers using activation functions like Sigmoid, where derivatives are small (max 0.25). Multiplying these small derivatives recursively makes gradients decay exponentially to zero, freezing weights. ReLU mitigates this because its derivative is constant 1.0 for all positive inputs, preventing gradient decay during backpropagation.",
            marks=8.0
        )
    ]

    # 3. Web Development Questions
    wd_paper_id = papers_dict["Advanced Web Architectures"]
    wd_questions = [
        Question(
            paper_id=wd_paper_id,
            type="objective",
            content="Which React hook is designed to cache the result of an expensive calculation between re-renders?\nA) useEffect\nB) useCallback\nC) useMemo\nD) useRef",
            answer_key="C",
            marks=2.0
        ),
        Question(
            paper_id=wd_paper_id,
            type="subjective",
            content="Explain the concept of Virtual DOM reconciliation in modern frontend frameworks and how 'keys' help optimize this process.",
            answer_key="Virtual DOM reconciliation is the algorithm used to diff a new virtual tree with the previous one. Instead of re-rendering the actual DOM tree, the framework calculates the minimal set of DOM nodes that changed and updates only those. Keys provide stable identifiers for list items, allowing the diffing algorithm to instantly identify elements that were moved, added, or deleted, rather than re-creating them.",
            marks=8.0
        )
    ]

    # Add questions for the other papers to ensure they are fully populated
    other_papers = [
        ("Relational Database Design", "What normal form requires removing transitive functional dependencies?\nA) 1NF\nB) 2NF\nC) 3NF\nD) BCNF", "C", "Explain the difference between clustered and non-clustered indexes in SQL databases.", "Clustered indexes physically reorder rows in the table on disk to match the index key (one per table). Non-clustered indexes maintain a separate index tree structure containing key values and row pointers pointing to actual rows on disk (multiple per table)."),
        ("TCP/IP Protocols & Routing", "Which layer of the OSI model is responsible for routing IP packets across networks?\nA) Data Link\nB) Network\nC) Transport\nD) Session", "B", "Explain the steps involved in a TCP three-way handshake connection establishment.", "1. Client sends a SYN (Synchronize) packet to the server to initiate connection. 2. Server replies with a SYN-ACK packet, acknowledging client and synchronizing its own sequence. 3. Client replies with an ACK packet to finalize connection establishment, moving both sockets to ESTABLISHED state."),
        ("Penetration Testing Basics", "Which of the following describes cross-site scripting (XSS)?\nA) Executing arbitrary SQL queries\nB) Injecting malicious scripts into web pages viewed by other users\nC) Brute forcing login passwords\nD) Spoofing IP addresses", "B", "Explain asymmetric cryptography and how public and private keys verify digital certificates.", "Asymmetric cryptography uses mathematically linked key pairs: a public key to encrypt/verify and a private key to decrypt/sign. A certificate authority signs a digital certificate using its private key. Receivers verify the authority signature using the authority's publicly available public key, proving the certificate was authentic and untampered."),
        ("AWS Cloud Engineering", "Which AWS service provides resizable virtual machine computation instances?\nA) S3\nB) RDS\nC) EC2\nD) Lambda", "C", "Explain the role of IAM policies, roles, and users in AWS security administration.", "IAM Users represent individuals/services needing access. IAM Groups collect users for easier administration. IAM Policies are JSON documents defining explicit permissions. IAM Roles are identity profiles without credentials that users or compute resources (like EC2) can temporarily assume to perform authorized API calls."),
        ("Machine Learning & Regression", "Which algorithm is highly sensitive to outliers and seeks a hyperplane to maximize classes separation?\nA) Decision Trees\nB) Support Vector Machines\nC) K-Nearest Neighbors\nD) Naive Bayes", "B", "Explain the bias-variance trade-off in machine learning generalization.", "Bias represents errors from simplistic assumptions (underfitting, model doesn't learn features). Variance represents errors from extreme sensitivity to training set noise (overfitting, model learns noise instead of generalized rule). The trade-off requires balancing model capacity to minimize both source errors for generalized test accuracy."),
        ("Linux Kernel Concepts", "Which system call is used to create a new process by duplicating the calling process?\nA) execve\nB) fork\nC) wait\nD) exit", "B", "Describe virtual memory paging and how Page Fault exceptions are handled by the OS kernel.", "Virtual memory splits program address space into virtual pages. The MMU maps virtual pages to physical frame tables. A Page Fault occurs when a page requested is not mapped in physical memory. The kernel halts execution, locates the missing page on disk (swap), loads it into a physical memory frame, updates page tables, and resumes instruction execution."),
        ("Mobile App Architecture", "Which design pattern separates UI controllers, data structures, and state binder engines?\nA) MVC\nB) MVP\nC) MVVM\nD) Singleton", "C", "Explain Model-View-ViewModel (MVVM) architecture and how data binding benefits mobile UI threads.", "MVVM separates the View (UI) from the Model (Data). The ViewModel exposes state properties representing UI logic. Data binding automatically synchronizes states between the View and ViewModel without manual event handlers. This reduces boilerplate controllers, allows independent unit testing of logic, and isolates UI rendering updates on main threads.")
    ]

    all_q_objs = []
    # Add SE, AI, and WD questions first
    all_q_objs.extend(se_questions)
    all_q_objs.extend(ai_questions)
    all_q_objs.extend(wd_questions)

    # Add other papers' questions
    for paper_title, obj_q, obj_key, subj_q, subj_key in other_papers:
        pid = papers_dict[paper_title]
        all_q_objs.append(Question(
            paper_id=pid,
            type="objective",
            content=obj_q,
            answer_key=obj_key,
            marks=2.0
        ))
        all_q_objs.append(Question(
            paper_id=pid,
            type="subjective",
            content=subj_q,
            answer_key=subj_key,
            marks=8.0
        ))

    db.add_all(all_q_objs)
    db.commit()

    # Pre-generate embeddings for subjective questions if Ollama/OpenAI is configured
    print("Generating vector embeddings for subjective answers...")
    import asyncio
    for q in all_q_objs:
        if q.type == "subjective":
            try:
                context_text = f"{q.content} {q.answer_key}"
                emb = asyncio.run(generate_embedding(db, context_text))
                q.context_vector = emb
                db.commit()
            except Exception as emb_err:
                print(f"Skipped embedding generation for Question ID {q.id} (LLM offline).")

    # Update total marks for all papers
    for paper in db.query(QuestionPaper).all():
        total = sum(q.marks for q in paper.questions)
        paper.total_marks = total
        db.commit()

    print("Seeding Submissions, Grading evaluations, and Certificates...")
    
    # Sub 1: Aarav Sharma (Passed WD)
    wd_p = db.query(QuestionPaper).filter(QuestionPaper.code == "WD-2026-M-001").first()
    wd_questions_list = db.query(Question).filter(Question.paper_id == wd_p.id).all()
    sub_1 = ExamSubmission(
        student_id="aarav_sharma",
        paper_id=wd_p.id,
        status="evaluated",
        responses=[
            {"question_id": wd_questions_list[0].id, "answer": "C"}, # MCQ Correct
            {"question_id": wd_questions_list[1].id, "answer": "Virtual DOM reconciliation performs a comparative analysis between the new virtual tree representation and the previous tree layout. It calculates changes and patches the real DOM where needed. Keys help identify changes in elements uniquely to optimize rendering performance."} # Subjective - High quality
        ],
        evaluated_responses=[
            {
                "question_id": wd_questions_list[0].id,
                "score": 2.0,
                "max_marks": 2.0,
                "rationale": "Deterministic match: Student answer matched correct answer key perfectly.",
                "semantic_similarity": 1.0
            },
            {
                "question_id": wd_questions_list[1].id,
                "score": 7.0,
                "max_marks": 8.0,
                "rationale": "High quality answer. Correctly describes Virtual DOM diffing, patching, and the use of keys to uniquely identify moved or deleted list items.",
                "semantic_similarity": 0.88
            }
        ],
        overall_score=9.0,
        percentage=90.0,
        final_grade="A"
    )
    db.add(sub_1)
    db.commit()

    # Create certificate for sub_1
    cert_1_id = str(uuid.uuid4())
    sig_1 = generate_signature("aarav_sharma", wd_p.id, cert_1_id)
    cert_1 = Certificate(
        id=cert_1_id,
        student_id="aarav_sharma",
        paper_id=wd_p.id,
        issue_date=datetime.datetime.utcnow() - datetime.timedelta(days=2),
        digital_signature=sig_1
    )
    db.add(cert_1)
    db.commit()

    # Sub 2: Diya Patel (Passed SE)
    se_p = db.query(QuestionPaper).filter(QuestionPaper.code == "SE-2026-M-001").first()
    se_questions_list = db.query(Question).filter(Question.paper_id == se_p.id).all()
    sub_2 = ExamSubmission(
        student_id="diya_patel",
        paper_id=se_p.id,
        status="evaluated",
        responses=[
            {"question_id": se_questions_list[0].id, "answer": "B"}, # MCQ Correct
            {"question_id": se_questions_list[1].id, "answer": "Monolith runs as a single process with a shared database, which is simple but hard to scale. Microservices split parts into individual processes with their own databases, reducing blast radius."} # Subjective - OK
        ],
        evaluated_responses=[
            {
                "question_id": se_questions_list[0].id,
                "score": 2.0,
                "max_marks": 2.0,
                "rationale": "Deterministic match: Student answer matched correct answer key.",
                "semantic_similarity": 1.0
            },
            {
                "question_id": se_questions_list[1].id,
                "score": 6.0,
                "max_marks": 8.0,
                "rationale": "Mentions process separation and independent database schemas. Misses deployment trade-offs and network latency context.",
                "semantic_similarity": 0.75
            }
        ],
        overall_score=8.0,
        percentage=80.0,
        final_grade="B"
    )
    db.add(sub_2)
    db.commit()

    cert_2_id = str(uuid.uuid4())
    sig_2 = generate_signature("diya_patel", se_p.id, cert_2_id)
    cert_2 = Certificate(
        id=cert_2_id,
        student_id="diya_patel",
        paper_id=se_p.id,
        issue_date=datetime.datetime.utcnow() - datetime.timedelta(days=1),
        digital_signature=sig_2
    )
    db.add(cert_2)
    db.commit()

    # Sub 3: Isha Iyer (Failed AI)
    ai_p = db.query(QuestionPaper).filter(QuestionPaper.code == "AI-2026-M-001").first()
    ai_questions_list = db.query(Question).filter(Question.paper_id == ai_p.id).all()
    sub_3 = ExamSubmission(
        student_id="isha_iyer",
        paper_id=ai_p.id,
        status="evaluated",
        responses=[
            {"question_id": ai_questions_list[0].id, "answer": "A"}, # MCQ Incorrect (Sigmoid)
            {"question_id": ai_questions_list[1].id, "answer": "Vanishing gradients means gradients get very large during training."} # Subjective - Completely wrong
        ],
        evaluated_responses=[
            {
                "question_id": ai_questions_list[0].id,
                "score": 0.0,
                "max_marks": 2.0,
                "rationale": "Deterministic mismatch: Student answer 'A' did not match correct key 'C'.",
                "semantic_similarity": 0.0
            },
            {
                "question_id": ai_questions_list[1].id,
                "score": 1.0,
                "max_marks": 8.0,
                "rationale": "Inaccurate description. Gradients shrink to zero in vanishing gradient problems, they do not get very large (that is exploding gradients).",
                "semantic_similarity": 0.15
            }
        ],
        overall_score=1.0,
        percentage=10.0,
        final_grade="F"
    )
    db.add(sub_3)
    db.commit()

    # Sub 4: Rohan Gupta (Pending)
    sub_4 = ExamSubmission(
        student_id="rohan_gupta",
        paper_id=wd_p.id,
        status="pending",
        responses=[
            {"question_id": wd_questions_list[0].id, "answer": "C"},
            {"question_id": wd_questions_list[1].id, "answer": "Virtual DOM reconciliation compares program trees. Keys speed it up."}
        ],
        created_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
    )
    db.add(sub_4)
    db.commit()

    print("Database seeding completed successfully.")

except Exception as seed_err:
    print(f"Error seeding database: {seed_err}")
    db.rollback()
    sys.exit(1)
finally:
    db.close()
