"""AI agent clients used by the backend (e.g. DeepSeek chat completions)."""

from backend.ai.ai_client import (
    AIAgentClient,
    ai_agent_client,
    DEEPSEEK_API_KEY_ENV,
    DEEPSEEK_ENDPOINT,
    DEFAULT_MODEL,
    DEFAULT_REASONING_EFFORT,
)

__all__ = [
    "AIAgentClient",
    "ai_agent_client",
    "DEEPSEEK_API_KEY_ENV",
    "DEEPSEEK_ENDPOINT",
    "DEFAULT_MODEL",
    "DEFAULT_REASONING_EFFORT",
]
