"""
viewer/formatting.py — Pure formatting helpers for the recipe viewer.

All functions in this module are pure: they accept domain values and return
Rich renderables or plain strings, with no console output and no side effects.
Nothing in the project imports from this module except viewer/renderers.py.

Constants:
    ACCENT       NYT red, used as the primary accent colour throughout.
    DIM          Muted grey used for secondary labels and borders.
    STAR_FILLED  Unicode filled star character.
    STAR_EMPTY   Unicode empty star character.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from rich.text import Text

from models import CookingTime

# ---------------------------------------------------------------------------
# Shared style constants
# ---------------------------------------------------------------------------

# Exported so that renderers.py can reference the same values without
# re-declaring them, keeping colour decisions in one place.
ACCENT: str = "#D63B33"
DIM: str = "grey50"
STAR_FILLED: str = "\u2605"
STAR_EMPTY: str = "\u2606"


# ---------------------------------------------------------------------------
# Formatting functions
# ---------------------------------------------------------------------------

def format_star_rating(avg: Optional[float], count: Optional[int]) -> Text:
    """
    Render a star rating as a Rich Text object.

    Fills whole stars up to the rounded average and leaves the remainder as
    empty stars.  Appends the numeric average and vote count in muted text.
    Returns "Not yet rated" in muted text when avg is None.

    Args:
        avg:   Mean rating on a 0–5 scale, or None if the recipe is unrated.
        count: Total number of ratings submitted, or None.

    Returns:
        A Rich Text object ready for inclusion in any renderable.
    """
    text: Text = Text()
    if avg is None:
        text.append("Not yet rated", style=DIM)
        return text

    filled: int = round(avg)
    text.append(STAR_FILLED * filled,       style=f"bold {ACCENT}")
    text.append(STAR_EMPTY  * (5 - filled), style=DIM)
    text.append(f"  {avg:.1f}",             style="bold white")
    if count:
        text.append(f"  ({count:,} ratings)", style=DIM)
    return text


def format_kicker(kicker: str) -> Text:
    """
    Render a kicker label as a coloured badge.

    Returns an empty Text when kicker is blank so callers can include the
    result unconditionally without a prior emptiness check.

    Args:
        kicker: The editorial label from a Recipe (e.g. "easy", "healthy").
                May be an empty string.

    Returns:
        A Rich Text badge, or an empty Text if kicker is blank.
    """
    text: Text = Text()
    if kicker:
        text.append(f" {kicker.upper()} ", style=f"bold white on {ACCENT}")
    return text


def format_cooking_time(ct: CookingTime) -> str:
    """
    Return the best available string representation of a CookingTime.

    Preference order:
        1. The API's display string (e.g. "1 hour 15 minutes").
        2. A string derived from the minute count (e.g. "1h 15m").
        3. An em dash when neither is available.

    Args:
        ct: A CookingTime instance from a Recipe.

    Returns:
        A human-readable duration string, never empty.
    """
    if ct.display:
        return ct.display
    if ct.minutes is not None:
        hours, mins = divmod(ct.minutes, 60)
        if hours and mins:
            return f"{hours}h {mins}m"
        return f"{hours}h" if hours else f"{mins}m"
    return "\u2014"


def format_published_date(published_at_ms: Optional[int]) -> str:
    """
    Convert a millisecond Unix timestamp to a human-readable date string.

    Args:
        published_at_ms: Millisecond-precision Unix timestamp, or None.

    Returns:
        A date string formatted as "1 January 2024", or an em dash if the
        timestamp is absent.
    """
    if published_at_ms is None:
        return "\u2014"
    dt: datetime = datetime.fromtimestamp(
        published_at_ms / 1000, tz=timezone.utc
    )
    return dt.strftime("%-d %B %Y")
