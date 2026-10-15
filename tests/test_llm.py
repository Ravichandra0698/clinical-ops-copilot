# test_llm.py
# Purpose: prove the endpoint works WITHOUT calling the real (paid) LLM.
# We swap the real client for fakes using FastAPI's dependency_overrides.
# Run from the project root with:  python -m pytest -q

import pytest
from fastapi.testclient import TestClient

from app.llm import LLMError, LLMResult, get_llm
from app.main import app

client = TestClient(app)


class FakeLLM:
    """Pretends to be the model and always answers instantly."""

    async def complete(self, system, user, max_tokens=None):
        return LLMResult(text=f"echo: {user}", model="fake-model",
                         input_tokens=5, output_tokens=3, latency_ms=1)


class BusyLLM:
    """Pretends the provider is rate-limiting us."""

    async def complete(self, system, user, max_tokens=None):
        raise LLMError("The model is busy, please try again shortly", 429)


@pytest.fixture(autouse=True)
def clean_overrides():
    yield                              # run the test first...
    app.dependency_overrides.clear()   # ...then always remove any fakes


def test_ask_returns_answer_and_usage():
    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    r = client.post("/llm/ask", json={"question": "What is dropout rate?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "echo: What is dropout rate?"
    assert body["input_tokens"] == 5 and body["output_tokens"] == 3


def test_too_short_question_is_rejected_before_calling_the_model():
    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    r = client.post("/llm/ask", json={"question": "hi"})
    assert r.status_code == 422        # FastAPI's "validation failed" status


def test_provider_rate_limit_becomes_a_clean_429():
    app.dependency_overrides[get_llm] = lambda: BusyLLM()
    r = client.post("/llm/ask", json={"question": "What is dropout rate?"})
    assert r.status_code == 429
    assert "busy" in r.json()["detail"]