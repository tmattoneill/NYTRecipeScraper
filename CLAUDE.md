# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal tool that exports a user's NYT Cooking saved-recipe box to JSON and CSV, and lets them browse the export in an interactive terminal viewer. Authentication uses a browser session cookie (`NYT-S`), not a public API key.

## Running the tools

```bash
# Install dependencies (use uv or pip)
pip install -r requirements.txt

# Export recipe box to recipes/ (requires .env with NYT_USER_ID and NYT_S_COOKIE)
python main.py

# Export to a custom directory with verbose logging
python main.py --out-dir ./exports --log-level DEBUG

# Skip enrichment, metadata only (once --metadata-only flag is added)
python main.py --metadata-only

# Launch the terminal viewer
python -m viewer

# Viewer pointing at a specific JSON file
python -m viewer --data ./exports/recipe_box.json
```

## Architecture

The dependency graph is strictly acyclic:

```
main.py  →  export.py  →  client.py  →  config.py
                       →  models.py
         →  models.py
         →  config.py

viewer/main.py  →  viewer/loop.py  →  viewer/renderers.py  →  viewer/formatting.py
               →  viewer/renderers.py
               →  models.py
```

- **config.py** — frozen `ClientConfig` dataclass loaded from env vars (and `.env` via optional `python-dotenv`). No project imports. The base URL is a field so tests can point at a stub server.
- **models.py** — `Recipe` and `CookingTime` dataclasses. No project imports. `Recipe.from_api()` maps raw API dicts; `Recipe.from_export()` maps the serialised JSON (field names differ slightly). `Recipe.to_flat_dict()` produces the CSV row.
- **client.py** — `NYTCookingClient` wraps a `requests.Session` with NYT auth headers. Public interface is `verify_auth()` and `iter_saved_recipes()` (a generator). Raises `AuthenticationError` on 401/403.
- **export.py** — `ExportResult` holds `list[Recipe]` and writes JSON/CSV. `export()` is the convenience entry point that composes client + models + result.
- **viewer/** — `loop.py` owns a two-state machine (`_View.LIST` / `_View.DETAIL`); `renderers.py` owns Rich panel construction; `formatting.py` is pure formatting helpers with no output side-effects. The shared `Console` singleton lives in `renderers.py` and is imported wherever output is needed.

## Feature branch: `feature/full-recipes` (implemented)

Full recipe content enrichment is in place. The export now does a second HTTP pass after collecting recipe-box metadata: it fetches each recipe's individual page, extracts structured content, and attaches it to `Recipe.content`.

- **`parser.py`** — new module; tries JSON-LD first (`<script type="application/ld+json">` with `@type: Recipe`), falls back to `__NEXT_DATA__` hydration payload. Returns `None` with a warning on failure; never raises.
- **`models.RecipeContent`** — new dataclass; all fields have defaults so partial parsing is safe. `RecipeContent.from_dict()` handles deserialisation from exported JSON.
- **`Recipe.content`** — new optional field (default `None`); `from_api` leaves it `None`, `from_export` deserialises it when present.
- **`NYTCookingClient.fetch_recipe_page(url)`** — new method; reuses the authenticated session, raises `AuthenticationError` on 401/403.
- **`export.export()`** — two new params: `include_content=True` and `content_delay=None` (defaults to `config.request_delay`).
- **`main.py`** — two new flags: `--metadata-only` (skips content fetch) and `--content-delay SECONDS`.
- **`tests/`** — 27 unit tests covering JSON-LD parsing, Next.js fallback, malformed input, model round-trips, and mocked integration export.

## Key constraints

- The `x-cooking-api: cooking-frontend` header is required by the API gateway or it returns 403.
- `NYT_S` cookie is scoped to `.nytimes.com` in the session to avoid leaking it to other hosts.
- Rate limiting: default 0.5 s delay between page requests; honour `NYT_REQUEST_DELAY` for the per-recipe fetch pass too.
- `recipe_box.json` uses `yield_` as the field name (Python keyword avoidance); the CSV header uses `yield`. `Recipe.from_export()` handles both spellings.
