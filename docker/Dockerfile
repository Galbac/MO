FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update     && apt-get install -y --no-install-recommends build-essential libpq-dev curl     && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY source ./source
COPY docs ./docs

RUN pip install --no-cache-dir     fastapi     uvicorn     "pydantic[email]"     pydantic-settings     orjson     httpx     pyyaml     "sqlalchemy[asyncio]"     asyncpg     aiosqlite     alembic     redis     python-multipart     jinja2
RUN pip install --no-cache-dir watchfiles

RUN useradd -r -m appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "source.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
