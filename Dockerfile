FROM python:3.12-slim AS base

# System deps for cryptography, numpy, web3
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (security best practice)
RUN groupadd -r cryptoguardian && useradd -r -g cryptoguardian -m cryptoguardian

WORKDIR /app

# Install Python deps first (Docker cache layer optimization)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY showcase/ showcase/
COPY examples/ examples/
COPY dashboard_demo.py ./

# Data & logs directories
RUN mkdir -p data logs && chown -R cryptoguardian:cryptoguardian /app

USER cryptoguardian

ENTRYPOINT ["python", "dashboard_demo.py"]
