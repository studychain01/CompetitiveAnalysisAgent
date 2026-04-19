#!/bin/sh
set -eu
# Railway sets PORT at runtime; avoid passing "$PORT" through Railway’s start UI (no shell expansion).
_port="${PORT:-8000}"
exec python -m uvicorn battlescope_api.main:app --host 0.0.0.0 --port "${_port}"
