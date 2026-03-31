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
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir .

# Copy source
COPY src/ src/
COPY config/ config/
COPY scripts/ scripts/

# Data & logs directories
RUN mkdir -p data logs && chown -R cryptoguardian:cryptoguardian /app

USER cryptoguardian

# Health check — bot exposes HTTP /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["python", "-m", "src.main"]
