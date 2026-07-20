from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import io
import logging
import jwt
import datetime
from app.core.config import settings

SECRET_KEY = settings.PDF_SECRET_KEY
ALGORITHM = "HS256"

def create_download_token(submission_id: int, doc_type: str) -> str:
    """
    Creates a secure, signed JWT token for downloading PDFs without exposing raw database IDs in URLs.
    """
    payload = {
        "sub_id": submission_id,
        "type": doc_type,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

from app.core.database import get_db, SessionLocal
from app.models.db_models import ExamSubmission, QuestionPaper, Question, Certificate, User
from app.services.langgraph_agent import app as langgraph_workflow
from app.services.pdf_service import generate_marksheet_pdf, generate_certificate_pdf

from app.api.auth import require_candidate, get_current_user

logger = logging.getLogger("evaluation_api")
router = APIRouter(prefix="/api/evaluation", tags=["Evaluation API"], dependencies=[Depends(require_candidate)])

# --- Pydantic Schemas ---
class StudentResponse(BaseModel):
    question_id: int
    answer: str

class ExamSubmissionRequest(BaseModel):
    student_id: str = Field(..., max_length=100)
    paper_id: int
    responses: List[StudentResponse]

# --- Background Task Runner ---
def run_evaluation_agent(submission_id: int):
    """
    Background worker that runs the LangGraph evaluation agent.
    """
    logger.info(f"Starting background evaluation for submission {submission_id}")
    db = SessionLocal()
    try:
        submission = db.query(ExamSubmission).filter(ExamSubmission.id == submission_id).first()
        if not submission:
            logger.error(f"Submission {submission_id} not found in database.")
            return

        paper = db.query(QuestionPaper).filter(QuestionPaper.id == submission.paper_id).first()
        if not paper:
            logger.error(f"Paper {submission.paper_id} not found for submission.")
            submission.status = "failed"
            db.commit()
            return

        # Prepare state variables
        questions_db = db.query(Question).filter(Question.paper_id == paper.id).all()
        questions = [{
            "id": q.id,
            "type": q.type,
            "content": q.content,
            "answer_key": q.answer_key,
            "marks": q.marks
        } for q in questions_db]

        # Construct initial state
        initial_state = {
            "db": db,
            "submission_id": submission.id,
            "paper_id": paper.id,
            "student_id": submission.student_id,
            "responses": submission.responses,
            "questions": questions,
            "evaluated_responses": [],
            "total_score": 0.0,
            "max_score": 0.0,
            "percentage": 0.0,
            "final_grade": "F"
        }

        # Run LangGraph Agent
        langgraph_workflow.invoke(initial_state)
        logger.info(f"Background evaluation completed successfully for submission {submission_id}")
    except Exception as e:
        logger.error(f"Error executing LangGraph workflow for submission {submission_id}: {e}")
        try:
            sub = db.query(ExamSubmission).filter(ExamSubmission.id == submission_id).first()
            if sub:
                sub.status = "failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()

# --- Evaluation API Router Endpoints ---

@router.post("/submit", response_model=Dict[str, Any], status_code=status.HTTP_202_ACCEPTED)
def submit_exam(
    payload: ExamSubmissionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Submits an exam for evaluation. Runs LangGraph evaluation in the background.
    """
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == payload.paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Question paper not found")

    # Duplicate attempt protection
    existing_sub = db.query(ExamSubmission).filter(
        ExamSubmission.student_id == payload.student_id,
        ExamSubmission.paper_id == payload.paper_id
    ).first()
    if existing_sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already submitted an assessment for this exam paper. Only one attempt is allowed."
        )

    # Create submission record
    responses_list = [{"question_id": r.question_id, "answer": r.answer} for r in payload.responses]
    submission = ExamSubmission(
        student_id=payload.student_id,
        paper_id=payload.paper_id,
        status="pending",
        responses=responses_list
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # Broadcast live activity via WebSocket to listening administrators
    import asyncio
    from app.api.ws import manager
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.send_activity(payload.student_id, "candidate", "Submitted Exam", f"Paper: {paper.title} (Code: {paper.code})"))
        else:
            loop.run_until_complete(manager.send_activity(payload.student_id, "candidate", "Submitted Exam", f"Paper: {paper.title} (Code: {paper.code})"))
    except Exception:
        pass

    # Dispatch agent evaluation background worker
    background_tasks.add_task(run_evaluation_agent, submission.id)

    return {
        "message": "Exam submission accepted. Evaluation started in background.",
        "submission_id": submission.id,
        "status": submission.status
    }

@router.get("/submissions/{submission_id}", response_model=Dict[str, Any])
def get_submission_status(submission_id: int, db: Session = Depends(get_db)):
    """
    Retrieves the status and scoring breakdown of an exam submission.
    """
    sub = db.query(ExamSubmission).filter(ExamSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    return {
        "submission_id": sub.id,
        "student_id": sub.student_id,
        "paper_id": sub.paper_id,
        "paper_title": sub.paper.title if sub.paper else "N/A",
        "status": sub.status,
        "overall_score": sub.overall_score,
        "percentage": sub.percentage,
        "final_grade": sub.final_grade,
        "created_at": sub.created_at.strftime("%Y-%m-%d %H:%M:%S") if sub.created_at else None,
        "evaluated_responses": sub.evaluated_responses
    }

# New router for public doc downloads via secure single-use tokens (allows direct browser links)
download_router = APIRouter(prefix="/api/evaluation/download", tags=["Document Downloads"])

@download_router.get("/marksheet")
def download_marksheet(token: str, db: Session = Depends(get_db)):
    """
    Securely downloads a marksheet PDF using an encrypted/signed token.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        submission_id = payload.get("sub_id")
        doc_type = payload.get("type")
        if not submission_id or doc_type != "marksheet":
            raise HTTPException(status_code=403, detail="Invalid token payload")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="Download token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=403, detail="Invalid download token")

    sub = db.query(ExamSubmission).filter(ExamSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.status != "evaluated":
        raise HTTPException(status_code=400, detail="Submission has not been evaluated yet")

    paper = sub.paper
    questions = db.query(Question).filter(Question.paper_id == paper.id).all()
    
    student_user = db.query(User).filter(User.username == sub.student_id).first()
    student_name = student_user.name if student_user else sub.student_id
    father_name = student_user.father_name if student_user else "N/A"
    
    pdf_bytes = generate_marksheet_pdf(sub, paper, questions, student_name, father_name)
    filename = f"marksheet_{sub.student_id}_{paper.code}.pdf"
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@download_router.get("/certificate")
def download_certificate(token: str, db: Session = Depends(get_db)):
    """
    Securely downloads a digitally signed certificate PDF using an encrypted/signed token.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        submission_id = payload.get("sub_id")
        doc_type = payload.get("type")
        if not submission_id or doc_type != "certificate":
            raise HTTPException(status_code=403, detail="Invalid token payload")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="Download token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=403, detail="Invalid download token")

    sub = db.query(ExamSubmission).filter(ExamSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.status != "evaluated":
        raise HTTPException(status_code=400, detail="Submission has not been evaluated yet")

    cert = db.query(Certificate).filter(
        Certificate.student_id == sub.student_id,
        Certificate.paper_id == sub.paper_id
    ).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate details not found")

    student_user = db.query(User).filter(User.username == sub.student_id).first()
    student_name = student_user.name if student_user else sub.student_id
    father_name = student_user.father_name if student_user else "N/A"

    pdf_bytes = generate_certificate_pdf(
        certificate=cert,
        student_name=student_name,
        paper_title=sub.paper.title,
        grade=sub.final_grade,
        father_name=father_name
    )
    filename = f"certificate_{sub.student_id}_{sub.paper.code}.pdf"
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/submissions/{submission_id}/explain/{question_id}", response_model=Dict[str, Any])
def explain_grading_rationale(submission_id: int, question_id: int, db: Session = Depends(get_db)):
    """
    Interactive 'Why Best' feature explaining LLM rationale and semantic similarity metrics.
    """
    sub = db.query(ExamSubmission).filter(ExamSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    if sub.status != "evaluated":
        raise HTTPException(status_code=400, detail="Submission is not evaluated yet.")

    # Find the specific question evaluation in the JSON breakdown
    evals = sub.evaluated_responses or []
    question_eval = next((ev for ev in evals if ev.get("question_id") == question_id), None)

    if not question_eval:
        raise HTTPException(status_code=404, detail="Question evaluation details not found in this submission.")

    q = db.query(Question).filter(Question.id == question_id).first()
    
    # Format explainability breakdown
    return {
        "question_id": question_id,
        "question_content": q.content if q else "N/A",
        "student_response": next((r["answer"] for r in sub.responses if r["question_id"] == question_id), "N/A"),
        "expected_answer_rubric": q.answer_key if q else "N/A",
        "obtained_score": question_eval.get("score"),
        "max_marks": question_eval.get("max_marks"),
        "semantic_similarity_score": question_eval.get("semantic_similarity"),
        "grading_rationale": question_eval.get("rationale")
    }

@router.get("/submissions", response_model=List[Dict[str, Any]])
def list_submissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists exam submissions scoped by user permissions and organization tenancy.
    """
    allowed_roles = current_user.roles.split(",")
    if "admin" in allowed_roles:
        subs = db.query(ExamSubmission).all()
    elif "instructor" in allowed_roles:
        # Instructors see all submissions of papers created under their organizations
        user_org_ids = [org.id for org in current_user.organizations]
        subs = db.query(ExamSubmission).join(QuestionPaper).filter(
            QuestionPaper.organization_id.in_(user_org_ids)
        ).all()
    else:
        # Candidates see only their own submissions
        subs = db.query(ExamSubmission).filter(ExamSubmission.student_id == current_user.username).all()
        
    result = []
    for s in subs:
        total_marks = sum(q.marks for q in s.paper.questions) if s.paper else 0.0
        
        # Generate secure tokens for download links
        marksheet_token = create_download_token(s.id, "marksheet") if s.status == "evaluated" else None
        certificate_token = create_download_token(s.id, "certificate") if (s.status == "evaluated" and s.percentage >= 50.0) else None
        
        result.append({
            "submission_id": s.id,
            "student_id": s.student_id,
            "paper_id": s.paper_id,
            "paper_code": s.paper.code if s.paper else "N/A",
            "paper_title": s.paper.title if s.paper else "N/A",
            "status": s.status,
            "overall_score": s.overall_score or 0.0,
            "max_score": total_marks,
            "percentage": s.percentage or 0.0,
            "final_grade": s.final_grade or "N/A",
            "marksheet_token": marksheet_token,
            "certificate_token": certificate_token
        })
    return result
