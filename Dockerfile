FROM python:3.11-slim

# System deps Scrapling / Patchright browsers need to run headless on Linux
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg ca-certificates libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# CRITICAL: Download the stealth browsers and fingerprint deps Scrapling needs
RUN scrapling install

COPY main.py .

ENV PORT=10000
EXPOSE 10000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
