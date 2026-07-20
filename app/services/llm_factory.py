from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_ollama import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from app.models.db_models import PlatformSettings
from app.core.config import settings
import logging

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
                openai_temperature=settings.OPENAI_TEMPERATURE
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
            openai_temperature=settings.OPENAI_TEMPERATURE
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
    
    # Default fallback to Ollama
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
                
    # Fallback to Ollama Embeddings
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
