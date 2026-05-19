FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
ENV UV_HTTP_TIMEOUT=120
RUN uv sync --frozen --no-dev

COPY . .

ENV PYTHONPATH=/app

CMD ["uv", "run", "python", "-m", "services.vacancy_ml_service.main"]
