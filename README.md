# NYT Cooking Recipe Box Exporter

Exports your saved NYT Cooking recipes to JSON and CSV, and lets you browse
them in an interactive terminal viewer.

---

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Credentials](#credentials)
- [Exporting your recipe box](#exporting-your-recipe-box)
- [Browsing recipes in the terminal](#browsing-recipes-in-the-terminal)
- [Output files](#output-files)
- [Project structure](#project-structure)
- [Limitations](#limitations)

---

## Requirements

- Python 3.10 or later
- An active NYT Cooking subscription
- `requests` — HTTP client used by the exporter
- `rich` — terminal rendering used by the viewer
- `python-dotenv` — loads local `.env` files

---

## Installation

Clone or download the project directory, then install dependencies:

```bash
pip install -r requirements.txt
```

The code can run without `python-dotenv` if credentials are exported directly
in your shell, but the provided `requirements.txt` installs it so `.env` files
work out of the box.

---

## Credentials

The exporter authenticates using two values from your browser session: your
NYT user ID and a session cookie. Both are required.

### Finding your user ID

1. Log in to [cooking.nytimes.com](https://cooking.nytimes.com) and open your
   recipe box.
2. Open your browser's developer tools (F12 or Cmd-Option-I on Mac).
3. Go to the **Network** tab and filter by **Fetch/XHR**.
4. Reload the page. Look for a request to a URL containing
   `/api/v2/users/`. Your user ID is the number in that path.

### Finding your session cookie

1. In the same developer tools session, click any request to
   `cooking.nytimes.com`.
2. Open the **Cookies** tab (or look in the **Request Headers** for `cookie:`).
3. Find the cookie named `NYT-S`. Copy its value — it is a long alphanumeric
   string.

The session cookie expires when you log out or after a period of inactivity.
If the exporter returns HTTP 401 or 403, your cookie has expired and you need
to copy a fresh one.

### Setting credentials

Copy `.env` from the template and fill in your values:

```bash
cp .env.example .env
```

```ini
NYT_USER_ID=1234567890
NYT_S_COOKIE=your-cookie-value-here
OUTPUT_DIR=recipes/
```

Alternatively, export them in your shell:

```bash
export NYT_USER_ID=1234567890
export NYT_S_COOKIE=your-cookie-value-here
```

Shell exports take precedence over `.env` values.

**Never commit `.env` to version control.** It is already listed in
`.gitignore`.

Generated exports (`recipe_box.json` and `recipe_box.csv`) are also ignored
by default because they reveal your saved recipe list.

---

## Exporting your recipe box

Run the exporter from the project directory:

```bash
python main.py
```

By default, output files are written to the directory named by `OUTPUT_DIR`
in `.env` (`recipes/` in the template). To write elsewhere for a single run:

```bash
python main.py --out-dir ./exports
```

To see detailed per-request logging:

```bash
python main.py --log-level DEBUG
```

### Exporter flags

| Flag | Default | Description |
|---|---|---|
| `--out-dir DIR` | `OUTPUT_DIR` | Directory to write output files |
| `--log-level LEVEL` | `INFO` | Verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Optional environment variables

These can be set in `.env` or exported in your shell. The defaults are
appropriate for most uses.

| Variable | Default | Description |
|---|---|---|
| `OUTPUT_DIR` | `.` | Directory to write `recipe_box.json` and `recipe_box.csv`. |
| `NYT_PER_PAGE` | `48` | Recipes per API request. 48 is the server maximum. |
| `NYT_REQUEST_DELAY` | `0.5` | Seconds to pause between page requests. |
| `NYT_TIMEOUT` | `30` | HTTP request timeout in seconds. |

---

## Browsing recipes in the terminal

The viewer reads the exported `recipe_box.json` and presents an interactive
terminal UI built with [Rich](https://github.com/Textualize/rich).

Run the viewer from the project directory:

```bash
python -m viewer
```

If your JSON file is in a different location:

```bash
python -m viewer --data ./exports/recipe_box.json
```

### Viewer flags

| Flag | Default | Description |
|---|---|---|
| `--data FILE` | `OUTPUT_DIR/recipe_box.json` | Path to the exported JSON file |

### Controls

The viewer has two screens: the **list view** and the **detail view**.

**List view**

| Input | Action |
|---|---|
| Type any text | Filter recipes by name or author |
| Press Enter (no input) | Clear the active filter |
| Enter a number | Open that recipe in the detail view |
| `q` | Quit |

**Detail view**

| Input | Action |
|---|---|
| `b` or Enter | Return to the list |
| `q` | Quit |

The URL shown in the detail view is a clickable hyperlink in terminals that
support OSC 8 links — iTerm2, Kitty, WezTerm, and most modern terminal
emulators. Clicking it opens the recipe on cooking.nytimes.com in your browser.

---

## Output files

The exporter writes two files.

### `recipe_box.json`

A JSON array where each element represents one saved recipe. This is the
authoritative output and is what the viewer reads. Fields:

| Field | Type | Description |
|---|---|---|
| `id` | integer | NYT's unique recipe identifier |
| `name` | string | Recipe title |
| `byline` | string | Author credit (e.g. "By Melissa Clark") |
| `url` | string | Canonical URL on cooking.nytimes.com |
| `yield_` | string | Serving size (e.g. "4 servings") |
| `cooking_time.display` | string | Human-readable duration (e.g. "45 minutes") |
| `cooking_time.minutes` | integer or null | Duration in minutes |
| `kicker` | string | Editorial label (e.g. "easy", "healthy") — empty if absent |
| `avg_rating` | float or null | Mean star rating on a 0–5 scale |
| `num_ratings` | integer or null | Total number of ratings |
| `has_video` | boolean | Whether the recipe has an associated video |
| `published_at_ms` | integer or null | Publication date as a millisecond Unix timestamp |
| `image_credit` | string | Photographer or illustrator credit — empty if absent |

### `recipe_box.csv`

A flat CSV representation of the same data, suitable for Excel, Google Sheets,
or any data tool. The `cooking_time` object is expanded into two columns:
`cooking_time_display` and `cooking_time_minutes`. The `yield_` field becomes
`yield` in the CSV header.

---

## Project structure

```
NYTRecipeScraper/
├── .env                    Credentials (never commit this)
├── .env.example            Credential template
├── main.py                 Exporter CLI entry point
├── config.py               Immutable configuration, loaded from environment
├── client.py               HTTP client for the NYT Cooking API
├── models.py               Recipe and CookingTime domain types
├── export.py               Serialisation: JSON and CSV output
├── recipes/                Default export directory (contents ignored)
│   └── .gitkeep            Keeps the empty directory in version control
└── viewer/                 Interactive terminal viewer package
    ├── __init__.py         Re-exports run() and main()
    ├── __main__.py         Enables python -m viewer
    ├── formatting.py       Pure formatting helpers (no output)
    ├── renderers.py        Rich panel composers
    ├── loop.py             State machine and input parsing
    └── main.py             Viewer CLI entry point and file loading
```

---

## Limitations

**Authentication is session-based.** The exporter uses a browser session
cookie rather than an official API key. NYT does not publish a public API for
recipe box access. The cookie typically expires after a few weeks or when you
log out; you will need to copy a fresh one when it does.

**The API endpoint is internal and undocumented.** NYT could change its
structure, authentication requirements, or rate limits at any time without
notice. If the exporter stops working, inspect network traffic in your browser
to find the new endpoint or field names.

**Recipe content is not exported.** The exporter captures metadata only —
title, author, cooking time, ratings, and URL. Ingredient lists, method steps,
and notes are not available from the recipe box search endpoint used here.
To access full recipe content you would need to fetch each recipe's individual
page, which would require substantially more requests and carries a higher risk
of triggering rate limiting.

**The viewer is read-only.** You cannot add, remove, or re-order saved recipes
from the terminal UI. It is a browser for the exported data only.

**Ratings and metadata reflect the state at export time.** The JSON and CSV
files are a snapshot. They are not updated automatically; run `main.py` again
to refresh them.

**Rate limiting.** The exporter pauses 0.5 seconds between page requests by
default. Reducing `NYT_REQUEST_DELAY` significantly may result in temporary
rate limiting or blocked requests from NYT's servers.

**The date format in `recipe_box.csv` is platform-dependent.** The
`%-d %B %Y` strftime format (e.g. "1 January 2024") works on Linux and macOS.
On Windows, replace `%-d` with `%#d` in `viewer/formatting.py` if you are
running the viewer there.
