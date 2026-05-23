FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY etl ./etl
COPY dashboard ./dashboard

CMD ["python", "-m", "etl.main_etl"]
