"""Esquemas Pydantic compartidos."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


# --------------------------- /chat ---------------------------------- #
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    user_id: int = 1
    message: str
    history: list[ChatMessage] = Field(default_factory=list,
                                        description="Conversación previa (oldest first)")
    preset: Literal["default", "pre_sleep", "post_sleep"] = "default"
    include_context: bool = True


class ChatUsage(BaseModel):
    input_tokens: int
    output_tokens: int


class ChatResponse(BaseModel):
    text: str
    model: str
    usage: ChatUsage
    stop_reason: Optional[str]


# --------------------------- /context ------------------------------- #
class UserContext(BaseModel):
    user_id: int
    window_hours: int
    biometrics: dict
    sleep_phases: dict
    recent_alerts: list
    journal: Optional[dict]
    user: Optional[dict] = None
    now: str


# --------------------------- /health -------------------------------- #
class HealthResponse(BaseModel):
    status: str
    version: str
    db: bool
    anthropic: bool


# --------------------------- /journal ------------------------------- #
class JournalEntry(BaseModel):
    user_id: int = 1
    mood: int = Field(..., ge=1, le=10)
    stress_level: int = Field(..., ge=1, le=10)
    caffeine_after_17: bool = False
    alcohol: bool = False
    screens_min_before_bed: int = Field(0, ge=0, le=600)
    notes: Optional[str] = None
