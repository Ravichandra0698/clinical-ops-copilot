# Clinical Ops Copilot

A **synthetic** pharma clinical-trial operations project, built step by step as AI-engineering. It grows from a FastAPI skeleton into an agentic AI copilot.

> **All data is fabricated.** No real subjects, sites, studies, or company data are used, and no real company's systems are represented. The data-quality problems and the two outlier sites were planted on purpose by the data generator.

## What it does so far

| Area | What exists |
|---|---|
| API | FastAPI app with `/health` and an LLM endpoint `POST /llm/ask` |
| LLM layer | Provider wrapper with a free local open-source model (Ollama) by default and an optional paid cloud client; timeouts, error translation, token and latency logging, and a swappable client |
| Database | PostgreSQL 16 in Docker, five tables, about 1.4M rows, foreign keys, an index experiment |
| Data quality | SQL validation queries and a `visits_clean` view (duplicates and impossible dates excluded) |
| Analytics | Pandas reproduction of the validation findings and a chart of outlier sites |
| ML | Dropout prediction (honest negative result: no better than a baseline) and site risk scoring (robust z-score and Isolation Forest) |
| Tests | Five tests using fake LLM clients and a fake Ollama server, so no model or paid API is needed |

## Findings on the synthetic data

- 5,264 duplicate visits, 5,259 visits dated before consent, about 1% missing ages, 3.4% missed visits.
- `visits_clean` returns 1,047,619 of 1,058,106 rows; the removed rows reconcile exactly with duplicates plus impossible dates.
- Indexing a subject lookup took a query from about 578 ms to about 0.19 ms (cold-cache first run).
- Two planted sites (SITE0034, SITE0412) stand out on dropout, visit lateness, and adverse-event reporting lag; both anomaly methods rank them first and second.
- Subject-level dropout models scored about 0.50 AUC, so they were not shipped. The signal in this dataset lives at the site level.

## Project structure

```
app/          FastAPI app (main.py, config.py, llm.py)
analytics/    Database connection, Pandas analysis, ML scripts
sql/          Schema, load, constraints, validation, clean view
scripts/      Synthetic data generator
tests/        Endpoint tests with a fake LLM
charts/       Generated charts
```

## Setup (Windows, PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**1. Generate the synthetic data** (seeded, so the output is reproducible)

```powershell
python scripts/generate_pharma_data.py --out data/pharma_dataset
```

**2. Start PostgreSQL and load the data** (Docker Desktop must be running; one line, from the project root)

```powershell
docker run -d --name trials-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=trials -p 5433:5432 -v trials_pgdata:/var/lib/postgresql/data -v "${PWD}/data:/data" -v "${PWD}/sql:/sql" postgres:16
docker exec -i trials-db psql -U postgres -d trials -f /sql/01_schema.sql
docker exec -i trials-db psql -U postgres -d trials -f /sql/02_load.sql
docker exec -i trials-db psql -U postgres -d trials -f /sql/03_constraints.sql
docker exec -i trials-db psql -U postgres -d trials -f /sql/07_clean_view.sql
```

**3. Analytics and ML**

```powershell
python -m analytics.reproduce_findings
python -m analytics.dropout_model
python -m analytics.site_risk
```

**4. API with a free local LLM** (install [Ollama](https://ollama.com/download) first, then pull a small model)

```powershell
ollama pull llama3.2:3b
```

Create a `.env` file in the project root (it is git-ignored):

```
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
```

Then run the tests and the server:

```powershell
python -m pytest -q
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` and try `POST /llm/ask`. The first call is slow while the model loads. To use the paid Anthropic API instead, set `LLM_PROVIDER=anthropic`, add `ANTHROPIC_API_KEY=...` to `.env`, and run `pip install anthropic`.

## Roadmap

Days 1 to 6 are built (environment, PostgreSQL, validation, analytics, ML, LLM API). Next: prompt engineering and structured outputs, RAG, vector search, a SQL agent, orchestration, MCP, React, then GCP deployment, testing and evaluation, security, monitoring, and a full-system review.