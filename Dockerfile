FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libc-dev \
    libpq-dev \
    postgresql-client \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ✅ REMOVED: Don't COPY source code (use volumes instead)
# COPY . .  # ← DELETE THIS LINE

EXPOSE 8000 8501

# Default CMD
CMD ["sh", "-c", "echo 'Use docker-compose'"]
