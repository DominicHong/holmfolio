"""AI Agent Client for the DeepSeek chat completions API.

Default model: DeepSeek Flash (model id ``deepseek-flash``) with
``reasoning_effort`` set to ``"max"`` (the highest thinking-effort tier) so
DeepSeek runs its longest internal reasoning before answering.

The API key is read from the ``DEEPSEEK_API_KEY`` environment variable, which
is loaded from the repo-root ``.env`` file via :func:`dotenv.load_dotenv`.

Reliability features:
- A shared :class:`httpx.Client` (thread-safe, reuses the connection pool)
  instead of a fresh connection per request, which matters under high
  concurrency.
- Separate connect / read / write / pool timeouts. The read timeout defaults
  to 120 s because ``reasoning_effort=max`` can take a long time to respond.
- Automatic retries with exponential backoff + jitter for transient failures:
  network/transport errors (connect failures, read/write/connect/pool
  timeouts) and retryable HTTP statuses (408, 429, 500, 502, 503, 504).
  Non-retryable statuses (401, 403, 400, ...) fail immediately.

Currently consumed by :mod:`backend.data_source` to classify Hong Kong stocks
as red chip / A+H dual-listed for the after-tax dividend calculation. Results
are cached in ``data/hk_stock_cache.json`` so the AI is only called for symbols
that are missing from the cache.
"""

import json
import os
import random
import threading
import time

import httpx
from dotenv import load_dotenv

from backend import logger

# Load .env once at module import. Idempotent: existing env vars are not
# overridden, and a missing .env file is a no-op.
load_dotenv()

DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-flash"
DEFAULT_REASONING_EFFORT = "max"

# HTTP statuses worth retrying: rate limiting and transient server errors.
_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class AIAgentClient:
    """Minimal OpenAI-compatible chat completions client with retries.

    Importing this module is safe without an API key: the key is read lazily,
    only when an actual request is made. Use :attr:`is_configured` to check
    availability without triggering a request.

    The underlying :class:`httpx.Client` is created lazily on first request
    and shared for the lifetime of this object, so concurrent callers reuse
    the same connection pool.
    """

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str = DEEPSEEK_ENDPOINT,
        model: str = DEFAULT_MODEL,
        timeout: float = 120.0,
        connect_timeout: float = 10.0,
        write_timeout: float = 30.0,
        pool_timeout: float = 10.0,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
    ):
        self.endpoint = endpoint
        self.model = model
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.write_timeout = write_timeout
        self.pool_timeout = pool_timeout
        self.reasoning_effort = reasoning_effort
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._api_key = api_key or os.environ.get(DEEPSEEK_API_KEY_ENV)
        self._client: httpx.Client | None = None
        self._client_lock = threading.Lock()

    @property
    def is_configured(self) -> bool:
        """True when an API key is available for outgoing requests."""
        return bool(self._api_key)

    def _ensure_api_key(self) -> str:
        if not self._api_key:
            raise RuntimeError(
                f"Missing API key: set {DEEPSEEK_API_KEY_ENV} in .env"
            )
        return self._api_key

    def _http(self) -> httpx.Client:
        """Return the shared HTTP client, creating it on first use."""
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    self._client = httpx.Client(
                        timeout=httpx.Timeout(
                            connect=self.connect_timeout,
                            read=self.timeout,
                            write=self.write_timeout,
                            pool=self.pool_timeout,
                        )
                    )
        return self._client

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter for the given attempt (1-based).

        Attempt 1 -> ~1 s, attempt 2 -> ~2 s, attempt 3 -> ~4 s, plus jitter.
        """
        base = self.retry_backoff * (2 ** (attempt - 1))
        return base + random.uniform(0, base)

    def chat(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.0
    ) -> str:
        """Send a chat completion request; return the assistant message content.

        Retries transient failures (timeouts, network errors, 408/429/5xx)
        with exponential backoff + jitter up to :attr:`max_retries` times.

        Raises:
            RuntimeError: if the request fails after all retries.
            httpx.HTTPStatusError: on non-retryable HTTP statuses.
        """
        api_key = self._ensure_api_key()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "reasoning_effort": self.reasoning_effort,
        }
        logger.debug(
            f"AI request -> model={self.model}, system_len={len(system_prompt)}, "
            f"user_len={len(user_prompt)}"
        )

        last_exc: Exception | None = None
        reason = "unknown error"
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._http().post(
                    self.endpoint, headers=headers, json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code not in _RETRYABLE_STATUS_CODES:
                    raise
                reason = f"HTTP {e.response.status_code}"
                last_exc = e
            except httpx.TransportError as e:
                reason = type(e).__name__
                last_exc = e

            if attempt >= self.max_retries:
                raise RuntimeError(
                    f"AI request failed after {self.max_retries + 1} attempts "
                    f"({reason}): {last_exc}"
                ) from last_exc

            delay = self._backoff_delay(attempt + 1)
            logger.warning(
                f"AI request {reason}; retrying in {delay:.1f}s "
                f"(attempt {attempt + 1}/{self.max_retries})"
            )
            time.sleep(delay)

        raise RuntimeError(f"AI request failed: {last_exc}")  # pragma: no cover

    def chat_json(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.0
    ) -> object:
        """Like :meth:`chat`, but parse the assistant content as JSON.

        Strips ```` ```json ```` fenced blocks if present so models that wrap
        their JSON in markdown still parse cleanly.
        """
        content = self.chat(system_prompt, user_prompt, temperature=temperature)
        text = content.strip()
        if text.startswith("```"):
            inner = text.splitlines()
            if inner and inner[0].startswith("```"):
                inner = inner[1:]
            if inner and inner[-1].strip().startswith("```"):
                inner = inner[:-1]
            text = "\n".join(inner).strip()
        return json.loads(text)


# Module-level singleton. The API key is only read on the first actual request,
# so importing this module is safe with no .env present. The shared httpx
# Client is created lazily on the first request.
ai_agent_client = AIAgentClient()
