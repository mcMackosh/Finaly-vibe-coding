# FinAlly Backend

Market data layer (simulator + SSE stream) for the FinAlly trading workstation. See
`planning/PLAN.md` and `planning/MARKET_DATA_DESIGN.md` for the full design.

## Run

```bash
uv sync

# HTTP API + SSE stream (the data source for charts)
uv run uvicorn app.main:app --reload
# then: curl http://localhost:8000/api/health
#       curl -N http://localhost:8000/api/stream/prices

# terminal-only demo of the same price stream
uv run python -m app.console
```

## Test

```bash
uv run pytest
```
