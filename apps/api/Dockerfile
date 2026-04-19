# Local / CI: build from ``apps/api`` (``docker build -f Dockerfile .``).
# Railway from monorepo root uses repo-root ``Dockerfile.api`` + ``railway.json``.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml .
COPY src ./src
COPY docker-entrypoint.sh /docker-entrypoint.sh

RUN chmod +x /docker-entrypoint.sh \
    && pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir .

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
