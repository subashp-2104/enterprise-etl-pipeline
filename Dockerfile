FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies required for compilation of packages (like psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY src/ ./src/
COPY tests/ ./tests/
COPY README.md .

# Create raw_data and quarantine directories
RUN mkdir -p /app/raw_data /app/quarantine

# Expose Web Dashboard Port
EXPOSE 5000

# Default command launches the FastAPI Web Dashboard
CMD ["python", "src/dashboard.py"]
