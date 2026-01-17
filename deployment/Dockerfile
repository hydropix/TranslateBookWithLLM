FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install curl for healthcheck
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY src/ /app/src/
COPY prompts/ /app/prompts/
COPY translation_api.py /app/
COPY translate.py /app/

# Create necessary directories
RUN mkdir -p /app/translated_files /app/logs /app/data/uploads

ARG PORT=5000
ENV PORT=$PORT
EXPOSE $PORT

VOLUME /app/translated_files
VOLUME /app/logs
VOLUME /app/data

# Healthcheck to verify the server is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/health || exit 1

CMD ["python", "translation_api.py"]