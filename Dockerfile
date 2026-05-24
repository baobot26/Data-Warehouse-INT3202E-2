FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["sh", "-c", "if [ -f /app/core/etl/main_etl.py ]; then exec python -m core.etl.main_etl; else exec python -m etl.main_etl; fi"]
