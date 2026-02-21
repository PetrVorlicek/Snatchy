FROM python:3.12-slim

# Install uv and Playwright dependencies
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
# NOTE: Pip install playwright system-wide so we can run "playwright install"
RUN uv pip install --system --no-cache playwright==1.57.0 && playwright install --with-deps chromium

# Install app dependencies
WORKDIR /snatchy
COPY pyproject.toml .
RUN uv sync --no-dev --no-cache

# Run app
COPY app ./app
CMD ["uv", "run", "./app/main.py"]
