from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import datetime
import uuid
from app.core.database import Base

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    type = Column(String(100), default="institute", nullable=False)  # "college", "school", "coaching", "institute", "other"
    description = Column(Text, nullable=True)

    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    papers = relationship("QuestionPaper", back_populates="organization", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="organization", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    plain_password = Column(String(255), nullable=True)
    roles = Column(String(255), default="candidate", nullable=False)  # comma-separated, e.g. "admin,instructor,candidate"
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="users")

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)

    # Relationships
    parent = relationship("Category", remote_side=[id], backref="children_list")
    papers = relationship("QuestionPaper", back_populates="category", cascade="all, delete-orphan")
    organization = relationship("Organization", back_populates="categories")

    @property
    def children(self):
        return self.children_list

class QuestionPaper(Base):
    __tablename__ = "question_papers"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    total_marks = Column(Float, default=0.0)
    grade_thresholds = Column(JSON, nullable=False, default=dict)  # {"A": 80.0, "B": 60.0, "C": 50.0}
    description = Column(Text, nullable=True)

    # Relationships
    category = relationship("Category", back_populates="papers")
    questions = relationship("Question", back_populates="paper", cascade="all, delete-orphan")
    submissions = relationship("ExamSubmission", back_populates="paper", cascade="all, delete-orphan")
    certificates = relationship("Certificate", back_populates="paper", cascade="all, delete-orphan")
    organization = relationship("Organization", back_populates="papers")

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("question_papers.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)  # "objective" or "subjective"
    content = Column(Text, nullable=False)
    answer_key = Column(Text, nullable=False)
    marks = Column(Float, nullable=False, default=1.0)
    context_vector = Column(Vector(1536), nullable=True)
    option_a = Column(Text, nullable=True)
    option_b = Column(Text, nullable=True)
    option_c = Column(Text, nullable=True)
    option_d = Column(Text, nullable=True)

    # Relationships
    paper = relationship("QuestionPaper", back_populates="questions")

class ExamSubmission(Base):
    __tablename__ = "exam_submissions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(100), index=True, nullable=False)
    paper_id = Column(Integer, ForeignKey("question_papers.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="pending")  # "pending", "evaluated", "failed"
    responses = Column(JSON, nullable=False)
    evaluated_responses = Column(JSON, nullable=True)
    overall_score = Column(Float, nullable=True)
    percentage = Column(Float, nullable=True)
    final_grade = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    paper = relationship("QuestionPaper", back_populates="submissions")

class PlatformSettings(Base):
    __tablename__ = "platform_settings"

    id = Column(Integer, primary_key=True, default=1)
    active_provider = Column(String(50), default="ollama", nullable=False)
    ollama_base_url = Column(String(255), default="http://localhost:11434")
    ollama_model = Column(String(100), default="llama3")
    ollama_temperature = Column(Float, default=0.2)
    openai_api_key = Column(String(255), default="")
    openai_model = Column(String(100), default="gpt-4o")
    openai_temperature = Column(Float, default=0.2)

class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(String(100), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(100), index=True, nullable=False)
    paper_id = Column(Integer, ForeignKey("question_papers.id", ondelete="CASCADE"), nullable=False)
    issue_date = Column(DateTime, default=datetime.datetime.utcnow)
    digital_signature = Column(String(255), nullable=False)

    # Relationships
    paper = relationship("QuestionPaper", back_populates="certificates")
