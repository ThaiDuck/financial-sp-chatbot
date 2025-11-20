import logging
import os
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List

logger = logging.getLogger(__name__)

# ✅ CRITICAL FIX: Use MULTILINGUAL model (supports Vietnamese!)
# Old: "sentence-transformers/all-MiniLM-L6-v2" (English-only)
# New: "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" (100+ languages)
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_DIMENSION = 384

# ✅ FIX: Global model instance (load once on module import)
_model = None

def get_embedding_model():
    """Load embedding model once and cache it"""
    global _model
    
    if _model is None:
        try:
            logger.info(f"Loading MULTILINGUAL embedding model: {EMBEDDING_MODEL}...")
            
            # ✅ FIX: Force CPU device and avoid meta tensor issues
            _model = SentenceTransformer(
                EMBEDDING_MODEL,
                device='cpu',  # Force CPU
                cache_folder=None  # Use default cache
            )
            
            # ✅ FIX: Ensure model is fully loaded
            _model.eval()
            
            logger.info("✅ Multilingual embedding model loaded successfully")
            logger.info("   Supports: Vietnamese, English, Chinese, and 100+ languages")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            # Return a dummy fallback
            _model = None
    
    return _model

def _normalize_text(text: str, language: str = None) -> str:
    """
    ✅ CRITICAL: Normalize text for better embedding quality
    
    This is KEY to making Vietnamese search work!
    """
    import unicodedata
    import re
    
    # ✅ Step 1: Unicode normalization (critical for Vietnamese)
    # NFC = Canonical Decomposition, followed by Canonical Composition
    text = unicodedata.normalize('NFC', text)
    
    # ✅ Step 2: Remove excessive whitespace
    text = " ".join(text.split())
    
    # ✅ Step 3: Lowercase (but preserve Vietnamese characters)
    text = text.lower()
    
    # ✅ Step 4: Remove special characters but keep Vietnamese diacritics
    # Keep: letters (including Vietnamese), digits, spaces, basic punctuation
    text = re.sub(r'[^\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ.,!?-]', ' ', text)
    
    # ✅ Step 5: Remove excessive punctuation
    text = re.sub(r'[.,!?-]{2,}', '.', text)
    
    # ✅ Step 6: Remove digits if not part of important context
    # Keep years (4 digits), but remove random numbers
    text = re.sub(r'\b\d{1,3}\b', '', text)  # Remove 1-3 digit numbers
    
    # ✅ Step 7: Final cleanup
    text = " ".join(text.split())
    
    return text.strip()

async def create_embedding(text: str):
    """
    ✅ CRITICAL FIX: Better preprocessing + multilingual support
    """
    try:
        text = text.strip()
        
        if not text:
            logger.warning("Empty text provided for embedding")
            return [0.0] * VECTOR_DIMENSION
        
        # ✅ CRITICAL: Detect language
        vietnamese_chars = 'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ'
        is_vietnamese = any(char in text.lower() for char in vietnamese_chars)
        
        language = "vietnamese" if is_vietnamese else "english"
        
        # ✅ CRITICAL: Normalize text BEFORE embedding
        normalized_text = _normalize_text(text, language)
        
        logger.info(f"📝 Embedding {language} text: '{normalized_text[:100]}'")
        
        # ✅ For long text, use smart truncation
        if len(normalized_text) > 5000:
            # Keep first 3000 chars + last 1000 chars
            normalized_text = normalized_text[:3000] + " ... " + normalized_text[-1000:]
            logger.info(f"   Truncated to 4000 chars (kept beginning + end)")
        
        model = get_embedding_model()
        
        if model is None:
            logger.error("Embedding model not available")
            return [0.0] * VECTOR_DIMENSION
        
        # ✅ Generate embedding
        try:
            embedding = model.encode(
                normalized_text,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,  # ✅ Critical for cosine similarity
                batch_size=1
            )
            
            # ✅ Validate embedding
            magnitude = np.linalg.norm(embedding)
            if magnitude < 0.9 or magnitude > 1.1:
                logger.warning(f"⚠️ Unusual embedding magnitude: {magnitude:.3f}")
            
            if np.max(np.abs(embedding)) < 0.01:
                logger.error("❌ Near-zero embedding!")
                return [0.0] * VECTOR_DIMENSION
            
            logger.info(f"✅ Generated {language} embedding (magnitude: {magnitude:.3f})")
            
            return embedding.tolist()
            
        except Exception as encode_error:
            logger.error(f"❌ Encoding failed: {encode_error}")
            
            # Retry with ultra-short text
            try:
                short_text = normalized_text[:200]
                logger.info(f"Retrying with short text: '{short_text}'")
                
                embedding = model.encode(
                    short_text,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    batch_size=1
                )
                return embedding.tolist()
            except:
                logger.error("❌ Retry failed")
                return [0.0] * VECTOR_DIMENSION
        
    except Exception as e:
        logger.error(f"❌ Error creating embedding: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return [0.0] * VECTOR_DIMENSION

async def similarity_search(query_embedding, embeddings, top_k=5):
    """Find the most similar embeddings using cosine similarity"""
    try:
        # Convert to numpy arrays for efficient computation
        query_emb = np.array(query_embedding)
        emb_array = np.array(embeddings)
        
        # Compute cosine similarity
        dot_product = np.dot(emb_array, query_emb)
        norm_query = np.linalg.norm(query_emb)
        norm_docs = np.linalg.norm(emb_array, axis=1)
        
        # Avoid division by zero
        cosine_sim = dot_product / (norm_query * norm_docs + 1e-8)
        
        # Get indices of top k most similar embeddings
        top_indices = np.argsort(cosine_sim)[-top_k:][::-1]
        
        return top_indices.tolist()
    except Exception as e:
        logger.error(f"Similarity search error: {e}")
        return []
