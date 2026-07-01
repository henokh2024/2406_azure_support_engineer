FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (build-essential, libpq-dev if compiling psycopg2, but psycopg2-binary has pre-compiled wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]