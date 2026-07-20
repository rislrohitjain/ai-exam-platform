from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.models.db_models import PlatformSettings
from app.core.config import settings
import os
import logging

# Ollama is only available in local/self-hosted environments
IS_SERVERLESS = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

logger = logging.getLogger("llm_factory")

def get_settings(db: Session) -> PlatformSettings:
    """
    Retrieves the platform settings from the database.
    If none exist, creates a default settings record based on environment variables.
    """
    try:
        db_settings = db.query(PlatformSettings).first()
        if not db_settings:
            db_settings = PlatformSettings(
                active_provider=settings.DEFAULT_LLM_PROVIDER,
                ollama_base_url=settings.OLLAMA_BASE_URL,
                ollama_model=settings.OLLAMA_MODEL,
                ollama_temperature=settings.OLLAMA_TEMPERATURE,
                openai_api_key=settings.OPENAI_API_KEY,
                openai_model=settings.OPENAI_MODEL,
                openai_temperature=settings.OPENAI_TEMPERATURE,
                groq_api_key=settings.GROQ_API_KEY,
                groq_model=settings.GROQ_MODEL,
                groq_temperature=settings.GROQ_TEMPERATURE,
                openrouter_api_key=settings.OPENROUTER_API_KEY,
                openrouter_model=settings.OPENROUTER_MODEL,
                openrouter_temperature=settings.OPENROUTER_TEMPERATURE
            )
            db.add(db_settings)
            db.commit()
            db.refresh(db_settings)
            logger.info("Created default platform settings in database.")
        return db_settings
    except Exception as e:
        logger.warning(f"Database error reading platform settings: {e}. Falling back to default configuration.")
        # Return a transient instance of PlatformSettings that is not attached to DB
        return PlatformSettings(
            active_provider=settings.DEFAULT_LLM_PROVIDER,
            ollama_base_url=settings.OLLAMA_BASE_URL,
            ollama_model=settings.OLLAMA_MODEL,
            ollama_temperature=settings.OLLAMA_TEMPERATURE,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_model=settings.OPENAI_MODEL,
            openai_temperature=settings.OPENAI_TEMPERATURE,
            groq_api_key=settings.GROQ_API_KEY,
            groq_model=settings.GROQ_MODEL,
            groq_temperature=settings.GROQ_TEMPERATURE,
            openrouter_api_key=settings.OPENROUTER_API_KEY,
            openrouter_model=settings.OPENROUTER_MODEL,
            openrouter_temperature=settings.OPENROUTER_TEMPERATURE
        )

def get_chat_model(db: Session):
    """
    Returns the active Chat Model configured in the database.
    """
    db_settings = get_settings(db)
    
    if db_settings.active_provider == "openai":
        if not db_settings.openai_api_key:
            logger.warning("OpenAI API key is missing. Using Ollama fallback.")
        else:
            try:
                return ChatOpenAI(
                    api_key=db_settings.openai_api_key,
                    model=db_settings.openai_model,
                    temperature=db_settings.openai_temperature
                )
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI chat model: {e}")
                
    elif db_settings.active_provider == "groq":
        if not db_settings.groq_api_key:
            logger.warning("Groq API key is missing. Using Ollama fallback.")
        else:
            try:
                return ChatOpenAI(
                    api_key=db_settings.groq_api_key,
                    base_url="https://api.groq.com/openai/v1",
                    model=db_settings.groq_model or "llama3-8b-8192",
                    temperature=db_settings.groq_temperature
                )
            except Exception as e:
                logger.error(f"Failed to initialize Groq chat model: {e}")
                
    elif db_settings.active_provider == "openrouter":
        if not db_settings.openrouter_api_key:
            logger.warning("OpenRouter API key is missing. Using Ollama fallback.")
        else:
            try:
                return ChatOpenAI(
                    api_key=db_settings.openrouter_api_key,
                    base_url="https://openrouter.ai/api/v1",
                    model=db_settings.openrouter_model or "meta-llama/llama-3-8b-instruct:free",
                    temperature=db_settings.openrouter_temperature
                )
            except Exception as e:
                logger.error(f"Failed to initialize OpenRouter chat model: {e}")
    
    # Ollama fallback — only available in local environments
    if IS_SERVERLESS:
        raise ValueError(
            "No valid LLM provider configured. "
            "Set GROQ_API_KEY (or OPENAI_API_KEY) in Vercel Environment Variables."
        )
    from langchain_ollama import ChatOllama
    return ChatOllama(
        base_url=db_settings.ollama_base_url,
        model=db_settings.ollama_model,
        temperature=db_settings.ollama_temperature
    )

def get_embeddings_model(db: Session):
    """
    Returns the active Embeddings Model configured in the database.
    """
    db_settings = get_settings(db)
    
    if db_settings.active_provider == "openai":
        if db_settings.openai_api_key:
            try:
                return OpenAIEmbeddings(
                    api_key=db_settings.openai_api_key,
                    model="text-embedding-3-small"
                )
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI embeddings: {e}")
                
    # Ollama Embeddings fallback — only in local environments
    if IS_SERVERLESS:
        logger.warning("No embeddings provider configured for serverless. Returning dummy vectors.")
        return None
    from langchain_community.embeddings import OllamaEmbeddings
    return OllamaEmbeddings(
        base_url=db_settings.ollama_base_url,
        model="nomic-embed-text"
    )

async def generate_embedding(db: Session, text: str) -> list[float]:
    """
    Generates a 1536-dimensional vector embedding for a given text.
    Includes a fallback dummy vector generator if the embedding service fails.
    """
    if not text:
        return [0.0] * 1536
        
    try:
        embedder = get_embeddings_model(db)
        # LangChain embeddings uses embed_query
        vector = embedder.embed_query(text)
        
        # Adjust dimensions to exactly 1536 to fit pgvector schema
        if len(vector) < 1536:
            # Pad with zeros if size is smaller (e.g. nomic-embed is 768)
            vector = vector + [0.0] * (1536 - len(vector))
        elif len(vector) > 1536:
            # Truncate if larger
            vector = vector[:1536]
            
        return vector
    except Exception as e:
        logger.warning(f"Embedding service failed ({e}). Returning fallback dummy vector.")
        # Return deterministic hash-based dummy vector for offline usage
        import hashlib
        h = hashlib.sha256(text.encode('utf-8')).digest()
        dummy = []
        for i in range(1536):
            # Generate deterministic floats between -1.0 and 1.0
            byte_idx = (i * 2) % len(h)
            val = (h[byte_idx] - 128) / 128.0
            dummy.append(val)
        return dummy
