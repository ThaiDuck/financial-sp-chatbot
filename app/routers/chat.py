import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database.connection import get_session
from ..chains.chat_chain import create_chat_chain, process_user_query

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={404: {"description": "Not found"}},
)

# ✅ NEW: In-memory session storage (simple approach)
# For production: use Redis or database
_chat_sessions = {}

class Message(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  

class ChatResponse(BaseModel):
    response: str
    session_id: str  # ✅ NEW: Return session ID
    sources: list = []

@router.post("/message")
async def chat(request: ChatRequest, session: Session = Depends(get_session)):
    """✅ OPTIMIZED: Minimal history"""
    try:
        session_id = request.session_id or f"session_{len(_chat_sessions)}"
        
        if session_id not in _chat_sessions:
            _chat_sessions[session_id] = []
        
        history = _chat_sessions[session_id]
        
        history.append({
            "role": "user",
            "content": request.message
        })
        
        # ✅ REDUCED: Keep only 4 messages (2 turns) instead of 10
        if len(history) > 4:
            history = history[-4:]
            _chat_sessions[session_id] = history
        
        # ✅ REDUCED: Pass only last 2 messages (1 turn)
        chain_dict = create_chat_chain(session)
        
        response = await process_user_query(
            chain_dict, 
            request.message,
            conversation_history=history[-2:] 
        )
        
        history.append({
            "role": "assistant",
            "content": response
        })
        
        return ChatResponse(
            response=response,
            session_id=session_id
        )
        
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        return ChatResponse(
            response=f"Error: {str(e)}",
            session_id=request.session_id or "error"
        )

@router.post("/clear")
async def clear_session(session_id: str):
    """Clear conversation history for a session"""
    try:
        if session_id in _chat_sessions:
            del _chat_sessions[session_id]
            logger.info(f"Cleared session: {session_id}")
            return {"success": True, "message": "Session cleared"}
        else:
            return {"success": False, "message": "Session not found"}
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        return {"success": False, "error": str(e)}

@router.get("/history/{session_id}")
async def get_history(session_id: str):
    """Get conversation history for a session"""
    try:
        if session_id in _chat_sessions:
            return {
                "success": True,
                "session_id": session_id,
                "history": _chat_sessions[session_id]
            }
        else:
            return {
                "success": False,
                "message": "Session not found"
            }
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return {"success": False, "error": str(e)}
