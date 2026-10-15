# main.py
# Purpose: the FastAPI application: a health check plus the first LLM endpoint.

import logging

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.llm import LLMClient, LLMError, get_llm

logging.basicConfig(level=logging.INFO)  # show our log lines (token counts, latency) in the terminal

app = FastAPI(title=settings.app_name)

# The "system prompt" frames every answer.
SYSTEM_PROMPT = (
    "You are an assistant for clinical trial operations analysts. "
    "Answer briefly and clearly. If you are not sure, say so. "
    "You do not have access to any database yet, so never invent numbers or study data."
)


# --- Error handling ----------------------------------------------------------
# Any LLMError raised anywhere becomes a clean JSON response with the right status code.
@app.exception_handler(LLMError)
async def llm_error_handler(request, exc: LLMError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


# --- Health check ------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str
    environment: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", environment=settings.environment)


# --- LLM endpoint ------------------------------------------------------------
class AskRequest(BaseModel):
    # Validation at the door: reject empty or huge inputs BEFORE spending money on them.
    question: str = Field(min_length=3, max_length=2000)


class AskResponse(BaseModel):
    answer: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


@app.post("/llm/ask", response_model=AskResponse)
async def ask(body: AskRequest, llm: LLMClient = Depends(get_llm)) -> AskResponse:
    # Depends(get_llm) hands us the client; tests replace it with a fake.
    result = await llm.complete(system=SYSTEM_PROMPT, user=body.question)
    return AskResponse(
        answer=result.text,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )