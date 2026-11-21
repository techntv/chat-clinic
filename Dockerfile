FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
# Dev deps are included so `docker compose run --rm web pytest` works on the VPS too.
RUN uv sync --frozen --no-install-project

COPY . .

EXPOSE 8000
CMD ["sh", "scripts/start_web.sh"]
