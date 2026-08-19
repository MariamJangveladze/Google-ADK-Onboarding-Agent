FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.8.11 /uv /uvx /bin/
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --extra integrations || uv sync --no-dev --extra integrations

COPY src ./src
COPY data ./data
COPY migrations ./migrations

USER 65532:65532
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "onboarding_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
