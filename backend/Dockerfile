FROM python:3.10-slim

# Install system dependencies (e.g. Tesseract OCR for PDF/Image scanning)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files
COPY backend/ ./backend
COPY data/ ./data

# Expose port 8000
EXPOSE 8000

ENV PYTHONPATH=/app

# Run uvicorn server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
