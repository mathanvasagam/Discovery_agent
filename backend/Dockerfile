FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

RUN useradd --create-home --uid 10001 appuser
COPY --chown=appuser:appuser backend/ ./backend/
RUN mkdir -p /app/backend/data/uploads /app/backend/data/generated /app/backend/data/reports \
    && chown -R appuser:appuser /app/backend/data

USER appuser
ENV PYTHONPATH=/app:/app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" || exit 1

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
