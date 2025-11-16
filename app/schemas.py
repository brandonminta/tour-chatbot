"""Pydantic schemas for the chatbot endpoints."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="Texto ingresado por el usuario")
    conversation_id: Optional[str] = Field(
        default=None, description="Identificador de la sesión del chat"
    )


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    stage: str
    registration_completed: bool = False
    wait_listed: bool = False
    suggested_tours: List[str] = Field(default_factory=list)


class InitChatResponse(BaseModel):
    conversation_id: str
    reply: str
    stage: str
    suggested_tours: List[str] = Field(default_factory=list)
