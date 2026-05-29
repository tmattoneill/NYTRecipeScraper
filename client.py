"""
client.py — HTTP client for the NYT Cooking recipe-box search endpoint.

Owns a single requests.Session for connection pooling and cookie persistence
across paginated requests.  Returns raw API dicts; all domain-model
construction is left to the caller so that this module stays focused on
transport concerns.

Imports:
    config.ClientConfig  — all HTTP parameters are derived from this object.
    models.Recipe        — not imported here; the caller maps raw dicts to
                           domain types after iterating.
"""

from __future__ import annotations

import logging
import time
from typing import Iterator, Optional
from urllib.parse import urljoin

from requests import Session

from config import ClientConfig

log: logging.Logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# HTTP headers that mimic a standard browser session against the NYT Cooking
# frontend.  The x-cooking-api header is required by the API gateway; without
# it the endpoint returns 403.
_DEFAULT_HEADERS: dict[str, str] = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
    "x-cooking-api": "cooking-frontend",
}

# Image crop variants passed verbatim in the `include_crops` query parameter.
# They control which image URLs are embedded in each recipe object.  Not used
# by the exporter itself, but included so the raw payload matches what the
# browser receives, which is useful when debugging against the live API.
_CROP_SIZES: tuple[str, ...] = (
    "ipad_mediumThreeByTwo440",
    "card",
    "mediumThreeByTwo440",
    "mediumThreeByTwo252",
)

# Hard upper bound on page number in iter_saved_recipes.  Guards against an
# infinite loop if the API never returns an empty page and collectables_count
# is absent from the payload.
_MAX_PAGES: int = 10_000


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class NYTCookingClient:
    """
    Thin HTTP client for the NYT Cooking recipe-box search endpoint.

    The public interface is intentionally narrow: callers should use
    `iter_saved_recipes` and treat all other methods as implementation
    details.  The client does not construct domain-model objects; it yields
    raw dicts so that the caller decides how to map them (typically via
    Recipe.from_api).

    Attributes:
        _config:    Frozen ClientConfig instance; all request parameters are
                    derived from it.
        _session:   Shared requests.Session; constructed once and reused
                    across all page requests for connection pooling.
        _endpoint:  Fully-qualified URL of the recipe-box search endpoint,
                    built once at initialisation from config.base_url and
                    config.user_id.
    """

    def __init__(self, config: ClientConfig) -> None:
        """
        Initialise the client and build the underlying HTTP session.

        Args:
            config: Fully populated, frozen ClientConfig instance.  All HTTP
                    parameters are derived from this object.
        """
        self._config: ClientConfig = config
        self._session: Session = self._build_session()
        # Constructed once; config is frozen so this is safe to cache.
        self._endpoint: str = (
            f"{config.base_url}/api/v2/users/{config.user_id}"
            "/search/recipe_box_search"
        )

    def _build_session(self) -> Session:
        """
        Construct and configure a requests.Session for this client.

        Sets browser-compatible default headers on the session so that they
        are sent with every request automatically.  The NYT-S authentication
        cookie is scoped to .nytimes.com so it is not leaked to other hosts
        if the session is ever reused outside this module.

        The `origin` and `referer` headers must match the Cooking frontend
        or the API gateway returns 403.

        Returns:
            A configured requests.Session ready for use.
        """
        s: Session = Session()
        s.headers.update(_DEFAULT_HEADERS)
        s.headers["origin"] = self._config.base_url
        s.headers["referer"] = urljoin(self._config.base_url, "/recipe-box")
        s.cookies.set(
            "NYT-S", self._config.nyt_s_cookie, domain=".nytimes.com"
        )
        return s

    def _fetch_page(self, page: int) -> dict[str, object]:
        """
        Request a single page of recipe-box results from the API.

        Args:
            page: 1-based page number to request.  The API is 1-indexed.

        Returns:
            The decoded JSON payload as a dict.  Relevant keys:
                collectables        list of recipe dicts for this page.
                collectables_count  total recipes across all pages (first
                                    page only; may be absent).

        Raises:
            requests.HTTPError: If the server returns a non-2xx status.
            requests.Timeout:   If the server does not respond within
                                config.timeout seconds.
        """
        params: dict[str, object] = {
            "q": "",
            "per_page": self._config.per_page,
            "page": page,
            "include_crops": ",".join(_CROP_SIZES),
        }
        response = self._session.get(
            self._endpoint,
            params=params,
            timeout=self._config.timeout,
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    def iter_saved_recipes(self) -> Iterator[dict[str, object]]:
        """
        Yield raw recipe dicts from the API, paginating automatically.

        Fetches pages sequentially, sleeping config.request_delay seconds
        between requests.  Iteration terminates on the first of:

        * The API returns an empty `collectables` list (server sentinel).
        * The cumulative yield count reaches `collectables_count` as declared
          by the first-page response (client-side guard against off-by-one
          errors in the server's pagination).
        * The page counter exceeds _MAX_PAGES (safety valve against infinite
          loops when the API behaves unexpectedly).

        The sleep is skipped after the final page to avoid an unnecessary
        delay before the caller receives the StopIteration signal.

        Yields:
            Raw dict objects as returned by the API for each recipe.  Pass
            each one to Recipe.from_api() to obtain a typed domain object.
        """
        total: Optional[int] = None
        yielded: int = 0

        for page in range(1, _MAX_PAGES + 1):
            payload: dict[str, object] = self._fetch_page(page)
            records: list[dict[str, object]] = payload.get("collectables") or []  # type: ignore[assignment]

            # Read collectables_count once from the first page only.
            if total is None:
                total = payload.get("collectables_count")  # type: ignore[assignment]
                log.info("Recipe box contains %s recipes.", total)

            log.debug("Page %d: received %d records.", page, len(records))

            if not records:
                log.debug("Empty page received; stopping pagination.")
                break

            yield from records
            yielded += len(records)

            if total is not None and yielded >= total:
                log.debug("Yielded %d/%d records; stopping pagination.", yielded, total)
                break

            time.sleep(self._config.request_delay)
