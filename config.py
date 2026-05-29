"""
config.py — Runtime configuration for the NYT Cooking recipe box exporter.

Defines ClientConfig, an immutable dataclass that consolidates all
externally-supplied parameters.  The only coupling this module has is to
the standard library; nothing in the project imports from it.

Loading order for environment variables:
    1. A .env file in the current working directory, if python-dotenv is
       installed and the file exists.
    2. The process environment (which takes precedence over .env values when
       python-dotenv is used with override=False, the default).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Optional dotenv support
# ---------------------------------------------------------------------------
# python-dotenv is not a hard dependency.  If it is installed we load .env
# automatically so that the caller does not need to source it manually.
# The import is attempted at module load time so that os.environ is fully
# populated before from_env() reads from it.

try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv()
except ModuleNotFoundError:
    pass  # python-dotenv not installed; rely on the ambient environment.


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClientConfig:
    """
    Immutable runtime configuration for NYTCookingClient.

    All fields that originate from external sources (environment variables,
    CLI flags) are collected here so that the rest of the package can treat
    them as constants.  Using a frozen dataclass rather than a plain dict or
    module-level globals makes it trivial to inject different configurations
    in tests without monkey-patching os.environ.

    Attributes:
        user_id:        Numeric NYT user ID, stored as a string to avoid
                        precision loss on unusually large values.
        nyt_s_cookie:   Value of the NYT-S session cookie used for
                        authentication.
        per_page:       Number of recipes to request per API call.  The
                        maximum accepted by the endpoint is 48.
        request_delay:  Seconds to sleep between successive page requests
                        to avoid hammering the API.
        timeout:        HTTP request timeout in seconds.
        base_url:       Root URL of the NYT Cooking site.  Exposed as a
                        field rather than a hard-coded string so that tests
                        can point the client at a local stub server.
    """

    user_id: str
    nyt_s_cookie: str
    per_page: int = 48
    request_delay: float = 0.5
    timeout: int = 30
    base_url: str = "https://cooking.nytimes.com"

    @classmethod
    def from_env(cls) -> "ClientConfig":
        """
        Construct a ClientConfig from environment variables.

        Reads NYT_USER_ID and NYT_S_COOKIE from the process environment.
        Both variables must be non-empty; if either is absent an
        EnvironmentError is raised so that the caller can surface a clear
        diagnostic rather than a cryptic HTTP 401 downstream.

        Optional overrides are read from NYT_PER_PAGE, NYT_REQUEST_DELAY,
        NYT_TIMEOUT, and NYT_BASE_URL; their defaults are used when the
        variables are absent.

        Returns:
            A fully populated, frozen ClientConfig instance.

        Raises:
            EnvironmentError: If NYT_USER_ID or NYT_S_COOKIE is unset or
                              blank after stripping whitespace.
            ValueError:       If an optional numeric variable is present but
                              cannot be parsed as the expected type.
        """
        user_id: str = os.environ.get("NYT_USER_ID", "").strip()
        cookie: str = os.environ.get("NYT_S_COOKIE", "").strip()

        if not user_id:
            raise EnvironmentError(
                "NYT_USER_ID is not set. "
                "Add it to .env or export it in your shell."
            )
        if not cookie:
            raise EnvironmentError(
                "NYT_S_COOKIE is not set. "
                "Add it to .env or export it in your shell."
            )

        return cls(
            user_id=user_id,
            nyt_s_cookie=cookie,
            per_page=int(os.environ.get("NYT_PER_PAGE", "48")),
            request_delay=float(os.environ.get("NYT_REQUEST_DELAY", "0.5")),
            timeout=int(os.environ.get("NYT_TIMEOUT", "30")),
            base_url=os.environ.get(
                "NYT_BASE_URL", "https://cooking.nytimes.com"
            ).rstrip("/"),
        )
