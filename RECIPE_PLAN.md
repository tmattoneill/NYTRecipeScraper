# Enrich NYT Recipe Box Export With Recipe Page Content

  ## Summary

  Add a second authenticated fetch pass after the existing recipe-box metadata export. For each saved
  recipe URL, fetch the individual NYT Cooking recipe page, parse canonical recipe structured data
  first, and write enriched structured JSON. Use browser/JS automation only as a fallback, because the
  target page exposes recipe fields through recipe schema data such as ingredients and instructions.

  ## Key Changes

  - Add a RecipeContent model containing:
      - description
      - ingredients: list[str]
      - preparation_steps: list[str]
      - yield_
      - total_time, prep_time, cook_time where present
      - nutrition, keywords, categories, cuisine, method
      - image_urls, source_url, date_published, date_modified

  - Extend Recipe with optional content: RecipeContent | None.
  - Add a page-content fetcher to NYTCookingClient:
      - Reuse the existing authenticated requests.Session.
      - Fetch each recipe.url with browser-like headers and the existing NYT-S cookie.
      - Respect NYT_REQUEST_DELAY between page requests.
      - Raise the existing AuthenticationError for 401/403.

  - Add a parser module that extracts in this order:
      - <script type="application/ld+json"> with @type: Recipe.
      - Next.js hydration payload as fallback.
      - CSS selector fallback only for known stable section names such as ingredients/preparation
        wrappers.

  - Update export flow:
      - Keep existing recipe-box pagination unchanged.
      - For each recipe, fetch and attach RecipeContent.
      - Continue exporting recipe_box.json, now enriched.
      - Keep CSV metadata-only unless a separate content CSV is explicitly added later.

  - Add CLI options:
      - --include-content default enabled for the new behavior.
      - --metadata-only to preserve the current fast export path.
      - --content-delay SECONDS optional override, defaulting to NYT_REQUEST_DELAY.

  ## Exclusions

  - Do not scrape ads, navigation, recommendation carousels, save/rating UI state, or reader comments.
  - Do not archive raw HTML by default.
  - Do not add Playwright as a dependency unless requests-based parsing fails against authenticated
    pages during implementation.

  ## Test Plan

  - Unit test JSON-LD parsing with a saved fixture from the provided recipe page.
  - Unit test fallback parsing when JSON-LD is absent but a Next.js payload exists.
  - Unit test malformed/missing content returns content=None with a warning, not a failed full export.
  - Unit test enriched JSON serialization and Recipe.from_export.
  - Integration-style test using a mocked NYTCookingClient session:
      - recipe-box metadata fetch returns one recipe URL.
      - recipe page fetch returns fixture HTML.
      - output JSON includes ingredients and preparation steps.

  - Manual verification:
      - Run python main.py --out-dir recipes --log-level DEBUG.
      - Confirm recipes/recipe_box.json includes content.ingredients and content.preparation_steps.
      - Run python main.py --metadata-only and confirm old metadata-only behavior still works.

  ## Assumptions

  - The goal is enriching every saved recipe in the existing recipe-box export.
  - Output should be structured JSON, not Markdown.
  - “Entire page contents” means canonical recipe content, not comments, ads, nav, or recommendation
    modules.

  - The implementation uses the user’s authenticated NYT session for personal export and does not
    attempt to bypass access controls.