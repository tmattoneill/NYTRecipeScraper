"""
viewer/renderers.py — Stateless Rich panel renderers for the recipe viewer.

Each function in this module composes Rich renderables and prints them to the
shared console.  Rendering functions are stateless: they accept data, produce
output, and return a value where the caller needs it (e.g. the filtered recipe
list from render_list).  No input is read here; that is the responsibility of
viewer/input.py.

Imports:
    viewer.formatting  — pure formatting helpers for individual field values.
    models.Recipe      — the domain type being rendered.
"""

from __future__ import annotations

from typing import Optional

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from models import Recipe
from viewer.formatting import (
    ACCENT,
    DIM,
    format_cooking_time,
    format_kicker,
    format_published_date,
    format_star_rating,
)

# Singleton console shared across the viewer package.  Defined here and
# imported by input.py so that all output flows through one stream.
console: Console = Console()


# ---------------------------------------------------------------------------
# List view
# ---------------------------------------------------------------------------

def render_list(recipes: list[Recipe], query: str) -> list[Recipe]:
    """
    Print a numbered, filterable table of recipes and return the visible subset.

    Applies a case-insensitive substring filter across recipe name and byline
    when query is non-empty.  The 1-based row numbers shown in the table are
    the indices the interaction loop uses to map user input to Recipe instances.

    Args:
        recipes: Full list of Recipe instances to draw from.
        query:   Active filter string.  Empty string disables filtering and
                 displays all recipes.

    Returns:
        The filtered (or complete) list in table display order.  The caller
        must use this return value when resolving a selection number, not the
        original `recipes` argument.
    """
    q: str = query.lower()
    visible: list[Recipe] = (
        [r for r in recipes if q in r.name.lower() or q in r.byline.lower()]
        if query
        else list(recipes)
    )

    table: Table = Table(
        box=box.SIMPLE_HEAD,
        header_style=f"bold {ACCENT}",
        show_edge=False,
        pad_edge=False,
        expand=True,
    )
    table.add_column("#",      style=DIM,          width=4,  no_wrap=True)
    table.add_column("Recipe", style="bold white",  ratio=5)
    table.add_column("Author", style=DIM,           ratio=3)
    table.add_column("Time",   style="cyan",        width=14, no_wrap=True)
    table.add_column("Rating",                      width=22, no_wrap=True)
    table.add_column("Kicker",                      width=10, no_wrap=True)

    for idx, recipe in enumerate(visible, start=1):
        table.add_row(
            str(idx),
            recipe.name,
            recipe.byline,
            format_cooking_time(recipe.cooking_time),
            format_star_rating(recipe.avg_rating, recipe.num_ratings),
            format_kicker(recipe.kicker),
        )

    subtitle: str = (
        f"{len(visible)} of {len(recipes)} recipes"
        if query
        else f"{len(recipes)} recipes"
    )

    console.print()
    console.print(
        Panel(
            table,
            title=f"[bold {ACCENT}]NYT Cooking \u2014 Recipe Box[/]",
            subtitle=f"[{DIM}]{subtitle}[/]",
            border_style=ACCENT,
            padding=(0, 1),
        )
    )
    return visible


# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------

def render_detail(recipe: Recipe) -> None:
    """
    Print a three-panel detail view for a single recipe.

    Layout:
        Panel 1  Title and kicker badge.
        Panel 2  Two-column metadata grid: cooking info (left) and
                 publication info (right).
        Panel 3  Clickable URL (supported in iTerm2 and most modern terminals).

    Args:
        recipe: The Recipe instance to display.
    """
    # Panel 1: title + kicker badge
    title_text: Text = Text()
    title_text.append(recipe.name, style="bold white")
    if recipe.kicker:
        title_text.append("  ")
        title_text.append(format_kicker(recipe.kicker))

    # Panel 2, left column: cooking metadata
    left: Table = Table(box=None, show_header=False, padding=(0, 1))
    left.add_column("key",   style=DIM, no_wrap=True)
    left.add_column("value", style="white")
    left.add_row("Author", recipe.byline or "\u2014")
    left.add_row("Time",   format_cooking_time(recipe.cooking_time))
    left.add_row("Yield",  recipe.yield_ or "\u2014")
    left.add_row("Rating", format_star_rating(recipe.avg_rating, recipe.num_ratings))
    left.add_row("Video",  "Yes" if recipe.has_video else "No")

    # Panel 2, right column: publication metadata
    right: Table = Table(box=None, show_header=False, padding=(0, 1))
    right.add_column("key",   style=DIM, no_wrap=True)
    right.add_column("value", style="white")
    right.add_row("Published", format_published_date(recipe.published_at_ms))
    right.add_row("Recipe ID", str(recipe.id))
    if recipe.image_credit:
        right.add_row("Photo", recipe.image_credit)

    # Panel 3: clickable URL
    url_text: Text = Text()
    url_text.append(recipe.url, style=f"link {recipe.url} underline {ACCENT}")

    console.print()
    console.print(Panel(title_text,
                        border_style=ACCENT, padding=(0, 1)))
    console.print(Panel(Columns([left, right]),
                        border_style=DIM,    padding=(0, 1)))
    console.print(Panel(url_text, title=f"[{DIM}]URL[/]",
                        border_style=DIM,    padding=(0, 1)))
