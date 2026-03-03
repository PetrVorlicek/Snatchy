FROM python:3.12-slim

# Install uv dependencies
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install app dependencies
WORKDIR /snatchy
COPY pyproject.toml .
# Depending on how pyproject.toml is setup, we might need a dummy README or similar, but normally sync passes
RUN uv sync --no-dev --no-cache

# Run app
COPY app/model ./app/model
# app.model.models.models needs app.domain.utils.time
COPY app/domain/utils/time.py ./app/domain/utils/time.py
# Add __init__.py files manually for those copied folders to avoid ModuleNotFoundError
RUN touch ./app/__init__.py ./app/domain/__init__.py ./app/domain/utils/__init__.py

COPY api_server ./api_server

CMD ["uv", "run", "uvicorn", "api_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
