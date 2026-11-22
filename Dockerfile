FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt asyncpg redis

COPY taxi_bot ./taxi_bot
RUN useradd --create-home taxi && mkdir -p /app/data && chown taxi /app/data
USER taxi
VOLUME ["/app/data"]

CMD ["python", "-m", "taxi_bot"]
