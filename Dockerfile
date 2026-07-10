# syntax=docker/dockerfile:1

# Stage 1 — build the Next.js static export
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2 — Python app runtime (FastAPI serves API + static frontend)
FROM python:3.12-slim
WORKDIR /app/backend

# uv for reproducible dependency installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies first for better layer caching
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy backend source and the built frontend
COPY backend/ ./
COPY --from=frontend /app/frontend/out /app/frontend/out

# Runtime SQLite location (bind-mounted at run time)
RUN mkdir -p /app/db

ENV PATH="/app/backend/.venv/bin:$PATH"
ENV PYTHONPATH=/app/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
