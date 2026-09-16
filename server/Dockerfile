# Multi-stage build for LLM Extract Server
# Stage 1: Build SvelteKit frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# Copy package files
COPY server/frontend/package*.json ./
RUN npm ci

# Copy frontend source and build
COPY server/frontend/ ./
RUN npm run build

# Stage 2: Python runtime
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
COPY server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/build ./static/

# Copy shared library
COPY libretto/ ./libretto/

# Copy server source
COPY server/ ./server/

# Set Python path so modules can be imported
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Set entrypoint
CMD ["python", "-m", "server"]