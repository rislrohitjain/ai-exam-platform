import json
import uuid
import logging
from typing import TypedDict, List, Dict, Any
from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.models.db_models import ExamSubmission, QuestionPaper, Question, Certificate
from app.services.llm_factory import get_chat_model, generate_embedding
from app.services.pdf_service import generate_signature

logger = logging.getLogger("langgraph_agent")

class EvaluationState(TypedDict):
    db: Session
    submission_id: int
    paper_id: int
    student_id: str
    responses: List[Dict[str, Any]]          # [{"question_id": 1, "answer": "text"}]
    questions: List[Dict[str, Any]]          # Database questions models representation
    evaluated_responses: List[Dict[str, Any]]  # Output list of evaluations
    total_score: float
    max_score: float
    percentage: float
    final_grade: str

# Node 1: Objective Evaluation
def evaluate_objective_node(state: EvaluationState) -> EvaluationState:
    logger.info("Running Objective Evaluation Node")
    evaluated = list(state.get("evaluated_responses", []))
    responses_dict = {r["question_id"]: r["answer"] for r in state["responses"]}
    
    for q in state["questions"]:
        if q["type"] == "objective":
            q_id = q["id"]
            student_ans = str(responses_dict.get(q_id, "")).strip().lower()
            correct_ans = str(q["answer_key"]).strip().lower()
            
            # Case insensitive exact match check
            if student_ans == correct_ans:
                score = float(q["marks"])
                rationale = "Deterministic match: Student answer matched correct answer key perfectly."
                similarity = 1.0
            else:
                score = 0.0
                rationale = f"Deterministic mismatch: Student answer '{student_ans}' did not match correct key '{correct_ans}'."
                similarity = 0.0
                
            evaluated.append({
                "question_id": q_id,
                "score": score,
                "max_marks": float(q["marks"]),
                "rationale": rationale,
                "semantic_similarity": similarity
            })
            
    state["evaluated_responses"] = evaluated
    return state

# Node 2: Subjective Evaluation
def evaluate_subjective_node(state: EvaluationState) -> EvaluationState:
    logger.info("Running Subjective Evaluation Node")
    db = state["db"]
    evaluated = list(state.get("evaluated_responses", []))
    responses_dict = {r["question_id"]: r["answer"] for r in state["responses"]}
    
    # Load LLM
    try:
        llm = get_chat_model(db)
    except Exception as e:
        logger.error(f"Failed to load LLM from factory: {e}. Fallback to simulated subjective evaluator.")
        llm = None

    for q in state["questions"]:
        if q["type"] == "subjective":
            q_id = q["id"]
            student_ans = str(responses_dict.get(q_id, "")).strip()
            correct_ans = str(q["answer_key"]).strip()
            max_m = float(q["marks"])
            
            # Step 1: Semantic Cosine Similarity via pgvector
            semantic_score = 0.0
            if student_ans:
                try:
                    student_vector = db.query(Question).filter(Question.id == q_id).first() # Dummy to verify connection
                    # Generate embedding for student answer
                    ans_embedding = db.execute(
                        db.query(Question.context_vector).filter(Question.id == q_id).statement
                    ).scalar()
                    
                    if ans_embedding is not None:
                        # Fetch cosine similarity using native pgvector operators
                        student_emb = generate_embedding(db, student_ans)
                        # SQLAlchemy pgvector distance call: 1 - cosine_distance
                        sim = db.query(
                            (1 - Question.context_vector.cosine_distance(student_emb)).label("similarity")
                        ).filter(Question.id == q_id).scalar()
                        
                        if sim is not None:
                            semantic_score = max(0.0, min(1.0, float(sim)))
                except Exception as e:
                    logger.warning(f"pgvector similarity query failed: {e}. Falling back to default embedding calculation.")
                    # Fallback string edit distance or dummy similarity metric
                    import difflib
                    semantic_score = difflib.SequenceMatcher(None, student_ans.lower(), correct_ans.lower()).ratio()

            # Step 2: LLM evaluation with prompt instructions
            if llm and student_ans:
                prompt_template = ChatPromptTemplate.from_messages([
                    ("system", (
                        "You are an expert AI professor. Evaluate the student's subjective answer based on the marking rubric and context.\n"
                        "You must respond ONLY with a valid JSON object. Do not include markdown codeblocks, prefix or suffix text.\n"
                        "JSON schema:\n"
                        "{{\n"
                        "  \"score\": float, // evaluated score between 0.0 and {max_marks}\n"
                        "  \"rationale\": string // detailed explainability of why the score was given\n"
                        "  \"semantic_similarity\": float // score between 0.0 and 1.0 indicating semantic equivalence to reference key\n"
                        "}}\n"
                    )),
                    ("human", (
                        "Question: {question}\n"
                        "Expected Answer Rubric: {rubric}\n"
                        "Student Submission: {submission}\n"
                        "Pre-computed pgvector Semantic Score: {semantic_similarity:.4f}\n"
                        "Maximum Allowed Marks: {max_marks}\n"
                        "Evaluate strictly and output JSON:"
                    ))
                ])
                
                chain = prompt_template | llm
                
                try:
                    response = chain.invoke({
                        "question": q["content"],
                        "rubric": correct_ans,
                        "submission": student_ans,
                        "semantic_similarity": semantic_score,
                        "max_marks": max_m
                    })
                    
                    # Parse output safely
                    resp_content = response.content.strip()
                    # Strip standard markdown json blocks if returned by LLM
                    if resp_content.startswith("```json"):
                        resp_content = resp_content[7:]
                    if resp_content.endswith("```"):
                        resp_content = resp_content[:-3]
                    resp_content = resp_content.strip()
                    
                    parsed = json.loads(resp_content)
                    score = min(max_m, max(0.0, float(parsed.get("score", 0.0))))
                    rationale = parsed.get("rationale", "Graded by LLM.")
                    similarity = min(1.0, max(0.0, float(parsed.get("semantic_similarity", semantic_score))))
                except Exception as e:
                    logger.error(f"LLM parsing failed: {e}. Falling back to default grading logic.")
                    # Safe fallback grading based on semantic score
                    score = float(round(semantic_score * max_m, 1))
                    rationale = f"LLM parsing error. Automatically graded based on pgvector context similarity of {semantic_score:.2%}."
                    similarity = semantic_score
            else:
                # Local baseline rule for grading if LLM is offline / submission is empty
                if not student_ans:
                    score = 0.0
                    rationale = "Submission was empty. Question received no marks."
                    similarity = 0.0
                else:
                    score = float(round(semantic_score * max_m, 1))
                    rationale = f"Ollama/OpenAI service offline. Graded using local text matching score of {semantic_score:.2%}."
                    similarity = semantic_score

            evaluated.append({
                "question_id": q_id,
                "score": score,
                "max_marks": max_m,
                "rationale": rationale,
                "semantic_similarity": similarity
            })

    state["evaluated_responses"] = evaluated
    return state

# Node 3: Grading & Result Aggregation
def aggregate_grading_node(state: EvaluationState) -> EvaluationState:
    logger.info("Running Aggregate Grading Node")
    db = state["db"]
    evaluated = state["evaluated_responses"]
    
    total_score = sum(ev["score"] for ev in evaluated)
    max_score = sum(ev["max_marks"] for ev in evaluated)
    
    percentage = (total_score / max_score * 100.0) if max_score > 0 else 0.0
    
    # Load Paper to check Grade Thresholds
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == state["paper_id"]).first()
    thresholds = paper.grade_thresholds if (paper and paper.grade_thresholds) else {"A": 80.0, "B": 60.0, "C": 50.0}
    
    # Determine grade
    final_grade = "F"
    sorted_thresholds = sorted(thresholds.items(), key=lambda x: x[1], reverse=True)
    for gr, th in sorted_thresholds:
        if percentage >= float(th):
            final_grade = gr
            break

    # Save to state
    state["total_score"] = total_score
    state["max_score"] = max_score
    state["percentage"] = percentage
    state["final_grade"] = final_grade
    
    # Write back results to Postgres DB
    submission = db.query(ExamSubmission).filter(ExamSubmission.id == state["submission_id"]).first()
    if submission:
        submission.status = "evaluated"
        submission.overall_score = total_score
        submission.percentage = percentage
        submission.final_grade = final_grade
        submission.evaluated_responses = evaluated
        db.commit()
        logger.info(f"Updated ExamSubmission {state['submission_id']} with grade {final_grade}")
        
        # Issue Certificate if student passed (percentage >= 50)
        if percentage >= 50.0:
            cert = db.query(Certificate).filter(
                Certificate.student_id == submission.student_id,
                Certificate.paper_id == submission.paper_id
            ).first()
            
            if not cert:
                cert_id = str(uuid.uuid4())
                signature = generate_signature(submission.student_id, submission.paper_id, cert_id)
                new_cert = Certificate(
                    id=cert_id,
                    student_id=submission.student_id,
                    paper_id=submission.paper_id,
                    digital_signature=signature
                )
                db.add(new_cert)
                db.commit()
                logger.info(f"Automatically issued Certificate {cert_id} for student {submission.student_id}")
                
    return state

# Define StateGraph lazily to avoid crashing at import time on serverless (Vercel)
_compiled_app = None

def get_app():
    """Returns the compiled LangGraph evaluation workflow, building it on first call."""
    global _compiled_app
    if _compiled_app is None:
        workflow = StateGraph(EvaluationState)
        workflow.add_node("evaluate_objective", evaluate_objective_node)
        workflow.add_node("evaluate_subjective", evaluate_subjective_node)
        workflow.add_node("aggregate_grading", aggregate_grading_node)
        workflow.set_entry_point("evaluate_objective")
        workflow.add_edge("evaluate_objective", "evaluate_subjective")
        workflow.add_edge("evaluate_subjective", "aggregate_grading")
        workflow.add_edge("aggregate_grading", END)
        _compiled_app = workflow.compile()
    return _compiled_app
