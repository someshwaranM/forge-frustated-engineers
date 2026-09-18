"""
Vigil — Chat API Routes (backend/api/routes/chat.py)

Exposes:
- POST /api/chat: Multi-turn investigative compliance chat powered by Elastic Agent Builder tools & MySQL.
- DELETE /api/chat/sessions/{session_id}: Reset conversation history for a given session.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.agents.chat_agent import get_chat_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["AI Chat"])


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="Unique session identifier for multi-turn history")
    message: str = Field(..., min_length=1, description="User investigation query or message")


class GroundedResultItem(BaseModel):
    type: str = Field(..., description="Entity type: 'call', 'finding', 'regulation', 'customer', 'product', 'transaction'")
    id: str = Field(..., description="Unique entity ID")


class ChatResponse(BaseModel):
    session_id: str
    response_text: str
    grounded_results: List[GroundedResultItem]
    tool_calls_made: List[str]
    provider_used: str


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
def post_chat_message(request: ChatRequest) -> ChatResponse:
    """
    Execute an investigative query within a multi-turn chat session.
    Invokes the AI agent with tool access to Elasticsearch (calls, regulations, findings)
    and MySQL (customer, product, transaction).
    """
    try:
        agent = get_chat_agent()
        result = agent.chat(
            session_id=request.session_id,
            user_message=request.message,
        )
        return ChatResponse(
            session_id=request.session_id,
            response_text=result["response_text"],
            grounded_results=[
                GroundedResultItem(type=g["type"], id=g["id"])
                for g in result.get("grounded_results", [])
            ],
            tool_calls_made=result.get("tool_calls_made", []),
            provider_used=result.get("provider_used", "unknown"),
        )
    except Exception as exc:
        logger.exception(f"Chat execution failed for session {request.session_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat execution failed: {str(exc)}",
        )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
def reset_session(session_id: str) -> Dict[str, Any]:
    """Reset and clear conversation history for a given session."""
    agent = get_chat_agent()
    agent.reset_session(session_id)
    return {"status": "success", "session_id": session_id, "message": "Session reset successfully"}
