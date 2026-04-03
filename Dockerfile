FROM python:3.12-slim

WORKDIR /app

# System deps: PostgreSQL client, Xvfb (virtual display for headed Chrome), Chrome deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    xvfb \
    wget gnupg2 \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    fonts-liberation xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Install Playwright browsers
RUN playwright install chromium

COPY . .

# Xvfb wrapper script for headed Chrome
COPY scripts/xvfb-run-worker.sh /usr/local/bin/xvfb-run-worker.sh
RUN chmod +x /usr/local/bin/xvfb-run-worker.sh

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
