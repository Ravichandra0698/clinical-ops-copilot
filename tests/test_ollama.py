# test_ollama.py
# Purpose: test the Ollama client WITHOUT Ollama running.
# httpx.MockTransport plays the role of the Ollama server and returns canned replies.
# Run from the project root with:  python -m pytest -q

import asyncio

import httpx

from app.llm import LLMError, OllamaLLM


def test_ollama_reply_is_parsed_into_an_llm_result():
    def fake_server(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"  # we called the right endpoint
        return httpx.Response(200, json={
            "model": "llama3.2:3b",
            "message": {"role": "assistant", "content": "A screen failure is..."},
            "prompt_eval_count": 40,
            "eval_count": 25,
        })

    llm = OllamaLLM(transport=httpx.MockTransport(fake_server))
    result = asyncio.run(llm.complete(system="be brief", user="What is a screen failure?"))
    assert result.text == "A screen failure is..."
    assert result.input_tokens == 40 and result.output_tokens == 25


def test_connection_refused_becomes_a_clear_503():
    def server_down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    llm = OllamaLLM(transport=httpx.MockTransport(server_down))
    try:
        asyncio.run(llm.complete(system="x", user="hello there"))
        assert False, "expected an LLMError"
    except LLMError as exc:
        assert exc.status_code == 503
        assert "not running" in str(exc)