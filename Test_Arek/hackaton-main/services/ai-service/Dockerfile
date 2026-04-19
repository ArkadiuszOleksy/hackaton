FROM python:3.12-slim AS base
RUN pip install uv --no-cache-dir

FROM base AS deps
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-cache 2>/dev/null || uv sync --no-dev --no-cache

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=deps /app/.venv /app/.venv
COPY app/ app/
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8002
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8002/health').raise_for_status()"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]
