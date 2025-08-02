FROM python:3.12-slim AS builder
WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN adduser --disabled-password --gecos "" appuser
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY whatsapp_payment_reminder ./whatsapp_payment_reminder

USER appuser
EXPOSE 8000
CMD ["sh", "-c", "uvicorn whatsapp_payment_reminder.main:app --host 0.0.0.0 --port ${PORT:-8000}"]