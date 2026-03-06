FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY source ./source
COPY docs ./docs

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    "pydantic[email]" \
    pydantic-settings \
    orjson \
    httpx \
    pyyaml \
    "sqlalchemy[asyncio]" \
    asyncpg \
    aiosqlite \
    alembic \
    redis \
    python-multipart \
    jinja2

CMD ["uvicorn", "source.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
