FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY backend/pyproject.toml ./pyproject.toml
RUN mkdir -p app \
    && touch app/__init__.py \
    && pip install --upgrade pip \
    && pip install -e ".[google]"

COPY --chown=app:app backend/app ./app
COPY --chown=app:app backend/migrations ./migrations
COPY --chown=app:app backend/alembic.ini ./alembic.ini
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app config ./config
COPY --chown=app:app fixtures ./fixtures
COPY --chown=app:app evals ./evals

RUN mkdir -p /app/artifacts && chown app:app /app/artifacts

USER app

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
