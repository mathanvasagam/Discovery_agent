FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir requests==2.34.2 pytest==9.1.1

USER 65534:65534
WORKDIR /workspace
