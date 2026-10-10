FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install required system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install cloudflared for public temporary URL tunneling
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then CF_ARCH="amd64"; elif [ "$ARCH" = "aarch64" ]; then CF_ARCH="arm64"; else CF_ARCH="amd64"; fi && \
    curl -sL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}" -o /usr/local/bin/cloudflared && \
    chmod +x /usr/local/bin/cloudflared

# Copy requirements and install Python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application code
COPY backend /app/backend
COPY frontend /app/frontend
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Create target directories
RUN mkdir -p /app/backend/dataset/parquet /app/backend/dataset/docs /app/db/chroma_db_gemini

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
