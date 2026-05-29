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

import re
from datetime import datetime, timezone
from typing import Optional

from rich.table import Table
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


# ---------------------------------------------------------------------------
# Recipe content formatters
# ---------------------------------------------------------------------------

# Human-readable labels for schema.org NutritionInformation property names.
_NUTRITION_LABELS: dict[str, str] = {
    "calories":             "Calories",
    "fatContent":           "Fat",
    "saturatedFatContent":  "Saturated fat",
    "unsaturatedFatContent":"Unsaturated fat",
    "transFatContent":      "Trans fat",
    "carbohydrateContent":  "Carbohydrates",
    "sugarContent":         "Sugar",
    "fiberContent":         "Fibre",
    "proteinContent":       "Protein",
    "sodiumContent":        "Sodium",
    "cholesterolContent":   "Cholesterol",
}


def _nutrition_label(key: str) -> str:
    """Return a readable label for a schema.org nutrition property name."""
    if key in _NUTRITION_LABELS:
        return _NUTRITION_LABELS[key]
    # camelCase \u2192 "Title Case Words" for any unknown key.
    return re.sub(r"([A-Z])", r" \1", key).strip().title()


def format_ingredient_list(ingredients: list[str]) -> Text:
    """
    Render an ordered list of ingredient strings as a bulleted Rich Text.

    Each ingredient is prefixed with a bullet in the accent colour.  Returns
    an empty Text when the list is empty so callers can include the result
    unconditionally.

    Args:
        ingredients: Ordered list of ingredient strings from RecipeContent.

    Returns:
        A Rich Text object with one ingredient per line.
    """
    text: Text = Text()
    for i, ingredient in enumerate(ingredients):
        if i > 0:
            text.append("\n")
        text.append("\u2022 ", style=ACCENT)
        text.append(ingredient, style="white")
    return text


def format_step_list(steps: list[str]) -> Text:
    """
    Render an ordered list of preparation steps as a numbered Rich Text.

    Each step number is rendered in the accent colour and bold.  Steps are
    separated by a blank line to aid readability when steps are long.  Returns
    an empty Text when the list is empty.

    Args:
        steps: Ordered list of preparation-step strings from RecipeContent.

    Returns:
        A Rich Text object with one numbered step per paragraph.
    """
    text: Text = Text()
    for i, step in enumerate(steps, start=1):
        if i > 1:
            text.append("\n\n")
        text.append(f"{i}. ", style=f"bold {ACCENT}")
        text.append(step, style="white")
    return text


def format_nutrition_table(nutrition: dict[str, str]) -> Table:
    """
    Render a nutrition facts dict as a two-column Rich Table.

    Keys are schema.org NutritionInformation property names (e.g.
    "fatContent"); they are converted to readable labels via
    _nutrition_label().  The table has no header row or border so it
    sits cleanly inside a Panel.

    Args:
        nutrition: Mapping of property name to value string from
                   RecipeContent.nutrition.

    Returns:
        A borderless Rich Table with label and value columns.
    """
    table: Table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_column("key",   style=DIM,     no_wrap=True)
    table.add_column("value", style="white")
    for key, value in nutrition.items():
        table.add_row(_nutrition_label(key), value)
    return table
