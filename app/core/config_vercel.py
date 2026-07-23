import os
from pydantic_settings import BaseSettings
from pydantic import Field

class VercelSettings(BaseSettings):
    DEBUG: bool = Field(default=False)
    # Vercel Neon DB PostgreSQL Database Details
    DATABASE_URL: str = Field(
        default="postgresql://neondb_owner:npg_DYXMv5B0glPq@ep-blue-hall-ang445o4-pooler.c-6.us-east-1.aws.neon.tech/ai-exam-platform?sslmode=require&channel_binding=require"
    )
    
    # Active LLM Settings (Ollama / OpenAI / Groq)
    DEFAULT_LLM_PROVIDER: str = Field(default="groq")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="llama3")
    OLLAMA_TEMPERATURE: float = Field(default=0.2)
    
    # OpenAI Settings
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = Field(default="gpt-4o")
    OPENAI_TEMPERATURE: float = Field(default=0.2)

    # Groq Settings
    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL: str = Field(default="llama3-8b-8192")
    GROQ_TEMPERATURE: float = Field(default=0.2)

    # OpenRouter Settings
    OPENROUTER_API_KEY: str = Field(default="")
    OPENROUTER_MODEL: str = Field(default="meta-llama/llama-3-8b-instruct:free")
    OPENROUTER_TEMPERATURE: float = Field(default=0.2)
    
    # PDF & Cryptography Configuration
    PDF_SECRET_KEY: str = Field(default="super-secret-exam-verification-key-change-this-in-production")

    class Config:
        env_file = ".env.vercel"
        env_file_encoding = "utf-8"
        extra = "ignore"

vercel_settings = VercelSettings()
