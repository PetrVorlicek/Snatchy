# Snatchy

Small real-estate crawler project (Bezrealitky + Sreality) using Playwright, SQLAlchemy, and Alembic.

## Quick Start (uv)

### 1) Install dependencies

```powershell
uv sync
uv run playwright install chromium
```

### 2) Create `.env`

Add these keys to `.env` in project root:

```env
POSTGRES_HOST=...
POSTGRES_PORT=...
POSTGRES_USER=...
POSTGRES_PASSWORD=...
POSTGRES_DB=...
```

Optional:

```env
SNATCHY_SQL_ECHO=0
SNATCHY_HEADLESS=1
```

### 3) Run DB migrations

```powershell
uv run alembic upgrade head
```

## Run Crawlers

Main runner:

```powershell
uv run python app/main.py
```

Useful modes:

```powershell
# Run due targets once, then exit
uv run python app/main.py --once

# Run one target immediately (ignores due-time checks)
uv run python app/main.py --target-id 1

# Run all enabled targets immediately (ignores due-time checks)
uv run python app/main.py --all-now
```

## Crawl Targets (DB)

Targets are configured in `crawl_targets` table.  
Each row controls URL, parser, frequency, enabled flag, and runtime overrides.

Common columns:

- `parser_key` (`bezrealitky`, `sreality`)
- `enabled`
- `frequency_minutes`
- `headless`
- `nav_timeout_ms`
- `max_attempts`
- `retry_sleep_ms`
- `networkidle_timeout_ms`
- `cookie_wait_ms`
- `cmp_wait_ms`
- `manual_wait_ms`

Example SQL:

```sql
-- Enable/disable target
UPDATE crawl_targets SET enabled = TRUE WHERE id = 1;

-- Run Sreality headed, keep Bezrealitky headless
UPDATE crawl_targets SET headless = FALSE WHERE id = 1;
UPDATE crawl_targets SET headless = TRUE WHERE id = 2;
```

## HTML Debugging

```powershell
# Print HTML to stdout
$env:SNATCHY_PRINT_HTML="1"

# Limit printed characters (0 = full HTML)
$env:SNATCHY_HTML_PREVIEW_CHARS="5000"

# Save fetched HTML to file
$env:SNATCHY_HTML_DUMP_PATH="debug/target_{target_id}.html"
```

Then run:

```powershell
uv run python app/main.py --target-id 1
```

## Minimal uv Project Bootstrap (from scratch)

If you want to recreate a similar project with uv:

```powershell
uv init snatchy
cd snatchy
uv add alembic asyncpg bs4 fastapi playwright playwright-stealth psycopg2-binary python-dotenv sqlalchemy uvicorn
uv run playwright install chromium
```

