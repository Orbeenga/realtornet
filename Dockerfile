FROM python:3.11-slim

# Install system deps (PostGIS client libs not needed - we connect to Supabase remotely)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Railway injects $PORT - app/main.py reads it
ENV PYTHONPATH=/app
EXPOSE 8000

ARG CACHEBUST=1
CMD ["python", "-c", "import os, uvicorn; uvicorn.run('app.main:app', host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))"]
