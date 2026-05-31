"""Wrapper sobre la API de Anthropic."""
from __future__ import annotations

import logging
from typing import Optional

from anthropic import Anthropic

from app.config import settings
from app.services.context_loader import format_context_for_claude, load_user_context
from app.services.prompts import POST_SLEEP_PROMPT, PRE_SLEEP_PROMPT, SLEEP_COACH_SYSTEM

log = logging.getLogger("claude")


PROMPT_PRESETS = {
    "default":    SLEEP_COACH_SYSTEM,
    "pre_sleep":  SLEEP_COACH_SYSTEM + "\n\n" + PRE_SLEEP_PROMPT,
    "post_sleep": SLEEP_COACH_SYSTEM + "\n\n" + POST_SLEEP_PROMPT,
}


_client: Optional[Anthropic] = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY no configurada. Edita backend/.env."
            )
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def build_system_prompt(user_id: int, preset: str = "default", include_context: bool = True) -> str:
    """Construye el system prompt completo con contexto biométrico."""
    base = PROMPT_PRESETS.get(preset, SLEEP_COACH_SYSTEM)
    if not include_context:
        return base

    try:
        ctx = load_user_context(user_id)
        ctx_text = format_context_for_claude(ctx)
        return f"{base}\n\n{ctx_text}"
    except Exception as e:
        log.warning(f"No se pudo cargar contexto del usuario {user_id}: {e}")
        return base


def chat(
    user_id: int,
    messages: list[dict],
    preset: str = "default",
    include_context: bool = True,
) -> dict:
    """Envía la conversación a Claude y devuelve la respuesta.

    `messages` es la lista de turnos previos en formato Anthropic:
        [{"role": "user", "content": "Hola"}, ...]
    """
    client = get_client()
    system = build_system_prompt(user_id, preset, include_context)

    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=settings.claude_max_tokens,
        system=system,
        messages=messages,
    )

    assistant_text = "".join(
        block.text for block in response.content if hasattr(block, "text")
    )

    return {
        "text": assistant_text,
        "model": response.model,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
        "stop_reason": response.stop_reason,
    }
