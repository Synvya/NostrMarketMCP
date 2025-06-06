FROM python:3.11-slim

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copy application code
COPY . .

# Create data directory for database
RUN mkdir -p /app/data

# Set ownership to appuser
RUN chown -R appuser:appuser /app

# Expose port
EXPOSE 8080

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Switch to non-root user
USER appuser

# Set environment variables
ENV PYTHONPATH=/app
ENV ENVIRONMENT=production
ENV DATABASE_PATH=/app/data/nostr_profiles.db

# Run the secure server
CMD ["python", "simple_secure_server.py"]