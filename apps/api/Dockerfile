# Local / CI: build from ``apps/api`` (``docker build -f Dockerfile .``).
# Railway from monorepo root uses repo-root ``Dockerfile.api`` + ``railway.json``.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml .
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir .

EXPOSE 8000

# Railway sets ``PORT`` at runtime
CMD ["sh", "-c", "exec python -m uvicorn battlescope_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
