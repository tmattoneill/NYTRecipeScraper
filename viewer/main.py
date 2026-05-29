"""
viewer/main.py — I/O and CLI entry point for the recipe viewer.

Responsible for loading recipes from disk, parsing CLI arguments, and
launching the interaction loop.  This is the only module in the viewer
package that touches the filesystem or sys.argv.

Imports:
    viewer.loop     — run(), the interaction loop.
    viewer.renderers — the shared console, used for error output.
    models.Recipe   — the domain type loaded from JSON.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from models import Recipe
from viewer.formatting import ACCENT, DIM
from viewer.loop import run
from viewer.renderers import console

try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv()
except ModuleNotFoundError:
    pass


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def _load_recipes(data_path: Path) -> list[Recipe]:
    """
    Load and parse Recipe instances from a JSON file produced by export.py.

    Args:
        data_path: Path to a recipe_box.json file written by ExportResult.

    Returns:
        A list of Recipe instances sorted alphabetically by name.

    Raises:
        SystemExit: With status 1 if the file is absent or cannot be parsed
                    as valid JSON.
    """
    if not data_path.exists():
        console.print(
            f"[{ACCENT}]Error:[/] {data_path} not found.  "
            "Run [bold]main.py[/] first to export your recipe box."
        )
        raise SystemExit(1)

    try:
        raw: list[dict[str, object]] = json.loads(
            data_path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        console.print(f"[{ACCENT}]Error:[/] Could not parse {data_path}: {exc}")
        raise SystemExit(1)

    return sorted(
        (Recipe.from_export(r) for r in raw),
        key=lambda r: r.name.lower(),
    )


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """
    Construct the argument parser for the viewer CLI.

    Returns:
        A configured ArgumentParser, not yet evaluated against sys.argv.
    """
    parser = argparse.ArgumentParser(
        description="Browse your exported NYT Cooking recipe box in the terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Controls:\n"
            "  Number    Select a recipe and enter the detail view.\n"
            "  Text      Filter the list by name or author.\n"
            "  Enter     Clear the current filter.\n"
            "  q         Quit from anywhere.\n"
            "  b         Return to the list from the detail view.\n"
        ),
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(os.environ.get("OUTPUT_DIR", ".")) / "recipe_box.json",
        metavar="FILE",
        help="Path to recipe_box.json (default: OUTPUT_DIR/recipe_box.json)",
    )
    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    CLI entry point: parse arguments, load recipes, and launch the viewer.

    Handles KeyboardInterrupt and EOFError (Ctrl-C / Ctrl-D) with a clean
    exit rather than a traceback, since these are expected ways to dismiss
    a terminal UI.
    """
    args = _build_parser().parse_args()
    recipes: list[Recipe] = _load_recipes(args.data)

    if not recipes:
        console.print(f"[{DIM}]No recipes found in {args.data}.[/]")
        raise SystemExit(0)

    try:
        run(recipes)
    except (KeyboardInterrupt, EOFError):
        console.print()
        raise SystemExit(0)


if __name__ == "__main__":
    main()
