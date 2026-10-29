FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5203 \
    CSV_PATH="locations - locations.csv" \
    LINK_PATH="link.txt"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

COPY main.py .
COPY ["locations - locations.csv", "./"]
COPY link.txt .

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 5203

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5203/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5203"]