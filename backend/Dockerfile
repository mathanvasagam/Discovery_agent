FROM node:22-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_API_URL=
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    nodejs \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

RUN useradd --create-home --uid 10001 appuser
COPY --chown=appuser:appuser backend/ ./backend/
COPY --from=frontend-build --chown=appuser:appuser /frontend/dist ./frontend/dist
RUN mkdir -p /app/backend/data/uploads /app/backend/data/generated /app/backend/data/reports \
    && chown -R appuser:appuser /app/backend/data

USER appuser
ENV PYTHONPATH=/app:/app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').getenv('PORT', '8000') + '/ready', timeout=2)" || exit 1

CMD ["sh", "-c", "python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
