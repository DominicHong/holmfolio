"""Unit tests for backend.ai.ai_client.AIAgentClient.

No network: httpx.Client is mocked.
"""

from unittest.mock import patch, MagicMock

import httpx
import pytest

from backend.ai.ai_client import (
    AIAgentClient,
    DEEPSEEK_API_KEY_ENV,
    DEFAULT_MODEL,
    DEFAULT_REASONING_EFFORT,
    DEEPSEEK_ENDPOINT,
)


def _fake_response(content: str):
    r = MagicMock()
    r.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": content}}]
    }
    r.raise_for_status.return_value = None
    return r


def _mock_http():
    """Patch the httpx.Client constructor and return (mock_client_cls, mock_http)."""
    mock_cls = patch("backend.ai.ai_client.httpx.Client")
    mock_client_cls = mock_cls.start()
    mock_http = mock_client_cls.return_value
    return mock_cls, mock_client_cls, mock_http


def test_defaults():
    assert DEFAULT_MODEL == "deepseek-flash"
    assert DEEPSEEK_ENDPOINT == "https://api.deepseek.com/chat/completions"
    assert DEFAULT_REASONING_EFFORT == "max"


def test_is_configured_true_when_api_key_provided():
    client = AIAgentClient(api_key="test-key")
    assert client.is_configured is True


def test_is_configured_false_without_api_key(monkeypatch):
    monkeypatch.delenv(DEEPSEEK_API_KEY_ENV, raising=False)
    client = AIAgentClient()
    assert client.is_configured is False


def test_chat_returns_assistant_content():
    client = AIAgentClient(api_key="test-key")
    with patch("backend.ai.ai_client.httpx.Client") as mock_client_cls:
        mock_http = mock_client_cls.return_value
        mock_http.post.return_value = _fake_response("hello world")
        result = client.chat("sys", "usr")
    assert result == "hello world"
    args, kwargs = mock_http.post.call_args
    assert args[0] == DEEPSEEK_ENDPOINT
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    payload = kwargs["json"]
    assert payload["model"] == "deepseek-flash"
    assert payload["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]
    assert payload["reasoning_effort"] == "max"
    # Client is configured with a generous read timeout for slow reasoning
    timeout = mock_client_cls.call_args.kwargs["timeout"]
    assert timeout.read == 120.0
    assert timeout.connect == 10.0


def test_custom_timeouts_are_applied():
    client = AIAgentClient(
        api_key="test-key", timeout=300.0, connect_timeout=5.0, write_timeout=60.0
    )
    with patch("backend.ai.ai_client.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.post.return_value = _fake_response("x")
        client.chat("sys", "usr")
    timeout = mock_client_cls.call_args.kwargs["timeout"]
    assert timeout.read == 300.0
    assert timeout.connect == 5.0
    assert timeout.write == 60.0


def test_shared_http_client_is_reused():
    client = AIAgentClient(api_key="test-key")
    with patch("backend.ai.ai_client.httpx.Client") as mock_client_cls:
        mock_http = mock_client_cls.return_value
        mock_http.post.return_value = _fake_response("a")
        client.chat("sys", "usr")
        client.chat("sys", "usr")
    # Only one Client was constructed for both requests
    assert mock_client_cls.call_count == 1
    assert mock_http.post.call_count == 2


def test_reasoning_effort_is_customizable_and_sent_in_payload():
    client = AIAgentClient(api_key="test-key", reasoning_effort="low")
    assert client.reasoning_effort == "low"
    with patch("backend.ai.ai_client.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.post.return_value = _fake_response("ok")
        client.chat("sys", "usr")
    payload = mock_client_cls.return_value.post.call_args.kwargs["json"]
    assert payload["reasoning_effort"] == "low"


def test_chat_raises_without_api_key(monkeypatch):
    monkeypatch.delenv(DEEPSEEK_API_KEY_ENV, raising=False)
    client = AIAgentClient()
    with pytest.raises(RuntimeError, match=DEEPSEEK_API_KEY_ENV):
        client.chat("sys", "usr")


def test_chat_retries_on_read_timeout_then_succeeds():
    client = AIAgentClient(api_key="test-key", retry_backoff=0.01)
    with patch("backend.ai.ai_client.httpx.Client") as mock_client_cls:
        mock_http = mock_client_cls.return_value
        mock_http.post.side_effect = [
            httpx.ReadTimeout("read operation timed out"),
            _fake_response("hello after retry"),
        ]
        with patch("backend.ai.ai_client.time.sleep") as mock_sleep:
            result = client.chat("sys", "usr")
    assert result == "hello after retry"
    assert mock_http.post.call_count == 2
    mock_sleep.assert_called_once()


def test_chat_retries_on_429_then_succeeds():
    req = httpx.Request("POST", DEEPSEEK_ENDPOINT)
    client = AIAgentClient(api_key="test-key", retry_backoff=0.01)
    with patch("backend.ai.ai_client.httpx.Client") as mock_client_cls:
        mock_http = mock_client_cls.return_value
        mock_http.post.side_effect = [
            httpx.Response(429, request=req),
            _fake_response("ok after rate limit"),
        ]
        with patch("backend.ai.ai_client.time.sleep"):
            result = client.chat("sys", "usr")
    assert result == "ok after rate limit"
    assert mock_http.post.call_count == 2


def test_chat_raises_after_exhausting_retries():
    client = AIAgentClient(api_key="test-key", max_retries=2, retry_backoff=0.01)
    with patch("backend.ai.ai_client.httpx.Client") as mock_client_cls:
        mock_http = mock_client_cls.return_value
        mock_http.post.side_effect = httpx.ReadTimeout("still timing out")
        with patch("backend.ai.ai_client.time.sleep"):
            with pytest.raises(RuntimeError, match="AI request failed after 3 attempts"):
                client.chat("sys", "usr")
    assert mock_http.post.call_count == 3


def test_chat_does_not_retry_on_401():
    req = httpx.Request("POST", DEEPSEEK_ENDPOINT)
    client = AIAgentClient(api_key="test-key", max_retries=3)
    with patch("backend.ai.ai_client.httpx.Client") as mock_client_cls:
        mock_http = mock_client_cls.return_value
        mock_http.post.return_value = httpx.Response(401, request=req)
        with pytest.raises(httpx.HTTPStatusError):
            client.chat("sys", "usr")
    assert mock_http.post.call_count == 1


def test_chat_json_parses_plain_json():
    client = AIAgentClient(api_key="test-key")
    with patch("backend.ai.ai_client.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.post.return_value = _fake_response(
            '{"is_red_chip": true, "is_dual_listed": false, "a_share_symbol": null}'
        )
        result = client.chat_json("sys", "usr")
    assert result == {
        "is_red_chip": True,
        "is_dual_listed": False,
        "a_share_symbol": None,
    }


def test_chat_json_strips_markdown_fence():
    client = AIAgentClient(api_key="test-key")
    with patch("backend.ai.ai_client.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.post.return_value = _fake_response(
            '```json\n'
            '{"is_red_chip": false, "is_dual_listed": true, "a_share_symbol": "601939.SH"}\n'
            '```'
        )
        result = client.chat_json("sys", "usr")
    assert result == {
        "is_red_chip": False,
        "is_dual_listed": True,
        "a_share_symbol": "601939.SH",
    }


def test_chat_json_raises_on_invalid_json():
    client = AIAgentClient(api_key="test-key")
    with patch("backend.ai.ai_client.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.post.return_value = _fake_response("not json at all")
        with pytest.raises(ValueError):
            client.chat_json("sys", "usr")
