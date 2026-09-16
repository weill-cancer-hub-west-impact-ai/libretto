# Dockerfile for LLM Extract Worker Service
FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY worker/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared library
COPY libretto/ ./libretto/

# Copy worker source
COPY worker/ ./worker/

# Set Python path so modules can be imported
ENV PYTHONPATH=/app

# Set default environment variable
ENV WORKERS=2

# Set entrypoint
CMD ["sh", "-c", "python -m worker --workers $WORKERS"]