"""
viewer/loop.py — Interaction loop and input parsing for the recipe viewer.

Defines the _View state enum, two input-parsing functions, and the run()
function that owns all mutable viewer state.  Rendering is delegated entirely
to viewer/renderers.py; this module contains no Rich markup or panel
construction.

Imports:
    viewer.renderers  — render_list, render_detail, and the shared console.
    models.Recipe     — the domain type the loop operates on.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Optional

from rich.prompt import Prompt
from rich.rule import Rule

from models import Recipe
from viewer.renderers import console, render_detail, render_list
from viewer.formatting import DIM


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class _View(Enum):
    """
    Enumeration of the two states the viewer can occupy.

    Using an explicit enum rather than boolean flags makes each branch of
    run() unambiguous: it handles exactly one state, and transitions are a
    single assignment.

    Members:
        LIST    The filterable recipe list is displayed.
        DETAIL  A single recipe's detail panel is displayed.
    """

    LIST = auto()
    DETAIL = auto()


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------

def _read_list_input(visible_count: int) -> tuple[str, Optional[int]]:
    """
    Read and classify a single line of input in the list view.

    Returns a (query, index) pair so the caller can branch on outcome without
    re-parsing the raw string.  The four possible outcomes are:

        ("q",  None)   User wants to quit.
        ("",   None)   Empty input; caller should clear the active filter.
        (text, None)   Non-numeric text; use as the new filter query.
        ("",   int)    Valid selection; int is the 0-based recipe index.

    Out-of-range numbers fall through to the text case so that a mistyped
    number does not silently discard the current filter.

    Args:
        visible_count: Number of recipes currently displayed, used to
                       validate the numeric selection range.

    Returns:
        A (query, index) tuple as described above.
    """
    raw: str = Prompt.ask(
        f"\n[{DIM}]Number to view \u00b7 type to filter \u00b7 [bold]q[/] quit[/]",
        console=console,
        default="",
    ).strip()

    if raw.lower() == "q":
        return "q", None

    if raw.isdigit():
        choice: int = int(raw)
        if 1 <= choice <= visible_count:
            return "", choice - 1  # convert to 0-based index
        # Out of range: fall through and treat as a filter string.

    return raw, None


def _read_detail_input() -> str:
    """
    Read a single navigation command in the detail view.

    Only "b" (back) and "q" (quit) are meaningful; any other input — including
    a bare Enter — is normalised to "b" so the user can dismiss the panel
    without typing a command.

    Returns:
        "b" to return to the list, or "q" to quit.
    """
    raw: str = Prompt.ask(
        f"[{DIM}][bold]b[/] back \u00b7 [bold]q[/] quit[/]",
        console=console,
        default="b",
    ).strip().lower()
    return raw if raw in ("b", "q") else "b"


# ---------------------------------------------------------------------------
# Interaction loop
# ---------------------------------------------------------------------------

def run(recipes: list[Recipe]) -> None:
    """
    Run the interactive recipe viewer until the user quits.

    Implements a two-state machine (_View.LIST and _View.DETAIL).  All
    mutable state — current view, active filter query, selected recipe — is
    owned here.  Rendering and input parsing are stateless and called as
    needed on each iteration.

    The loop exits by returning normally; it does not call sys.exit() so
    that the caller (main()) retains control over the exit code and any
    cleanup.

    Args:
        recipes: The full list of Recipe instances to browse.  Must be
                 non-empty; the caller is responsible for verifying this
                 before invoking run().
    """
    view: _View = _View.LIST
    query: str = ""
    selected: Optional[Recipe] = None

    while True:

        if view is _View.DETAIL:
            assert selected is not None  # invariant: selected is always set on DETAIL entry
            render_detail(selected)
            console.print(Rule(style=DIM))
            if _read_detail_input() == "q":
                return
            # "b": transition back to the list.
            view = _View.LIST
            selected = None
            continue

        # _View.LIST
        console.clear()
        visible: list[Recipe] = render_list(recipes, query)

        if not visible:
            console.print(
                f"[{DIM}]No recipes match \u2018{query}\u2019. "
                "Press Enter to clear the filter.[/]"
            )
            Prompt.ask("", console=console, default="")
            query = ""
            continue

        new_query, index = _read_list_input(len(visible))

        if new_query == "q":
            return
        if index is not None:
            selected = visible[index]
            view = _View.DETAIL
        else:
            query = new_query
