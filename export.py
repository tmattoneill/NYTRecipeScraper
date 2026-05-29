"""
export.py — Serialisation layer for the NYT Cooking recipe box exporter.

Defines ExportResult, a value object that holds a completed collection of
Recipe instances and knows how to write them to disk as JSON and CSV.  Also
exposes the module-level `export()` function, which is the primary entry
point for programmatic use and composes the client, domain model, and this
serialisation layer into a single call.

Imports:
    models.Recipe  — the domain type being serialised.
    client.NYTCookingClient  — fetches raw API data.
    config.ClientConfig      — passed through to the client.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from client import NYTCookingClient
from config import ClientConfig
from models import Recipe

log: logging.Logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ExportResult
# ---------------------------------------------------------------------------

@dataclass
class ExportResult:
    """
    Value object that holds a completed recipe collection and serialises it.

    Keeping serialisation on this object rather than in `export()` or in
    main.py means the caller can inspect `recipes` before writing, retry a
    write to a different directory without re-fetching, or add new output
    formats by subclassing.

    Attributes:
        recipes:   Ordered list of Recipe instances in the same sequence they
                   were returned by the API.
        raw_pages: Optional list of raw API response payloads retained for
                   debugging or archival.  Not written to disk by `write()`;
                   callers that need the raw data should serialise this field
                   themselves.
    """

    recipes: list[Recipe]
    raw_pages: list[dict[str, object]] = field(default_factory=list)

    def write(self, out_dir: Path) -> None:
        """
        Serialise all recipes to JSON and CSV files inside `out_dir`.

        Creates `out_dir` (and any missing parents) if it does not exist.
        Existing files with the same names are silently overwritten so that
        re-running the exporter is idempotent.

        Args:
            out_dir: Directory in which to write `recipe_box.json` and
                     `recipe_box.csv`.
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(out_dir / "recipe_box.json")
        self._write_csv(out_dir / "recipe_box.csv")
        log.info("Wrote %d recipes to %s.", len(self.recipes), out_dir)

    def _write_json(self, path: Path) -> None:
        """
        Write all recipes to a UTF-8 encoded JSON file at `path`.

        dataclasses.asdict() is used for serialisation because it recursively
        converts nested dataclasses (e.g. CookingTime) to plain dicts, which
        json.dumps can handle without a custom encoder.

        Args:
            path: Destination file path.  The parent directory must already
                  exist (guaranteed by `write`).
        """
        data: list[dict[str, object]] = [asdict(r) for r in self.recipes]
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log.debug("JSON → %s", path)

    def _write_csv(self, path: Path) -> None:
        """
        Write all recipes to a UTF-8 encoded CSV file at `path`.

        Uses Recipe.to_flat_dict() to expand nested fields into top-level
        columns.  Column order follows the key insertion order of
        to_flat_dict(), which is stable across Python 3.7+.

        Does nothing if the recipe list is empty rather than writing a
        header-only file, which would be indistinguishable from a failed
        export to a downstream consumer.

        Args:
            path: Destination file path.  The parent directory must already
                  exist (guaranteed by `write`).
        """
        rows: list[dict[str, object]] = [r.to_flat_dict() for r in self.recipes]
        if not rows:
            log.warning("No recipes to write; skipping CSV output.")
            return
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer: csv.DictWriter[str] = csv.DictWriter(
                fh, fieldnames=list(rows[0].keys())
            )
            writer.writeheader()
            writer.writerows(rows)
        log.debug("CSV → %s", path)


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def export(config: ClientConfig, out_dir: Path) -> ExportResult:
    """
    Fetch all saved recipes and write them to `out_dir`.

    Composes NYTCookingClient, Recipe.from_api(), and ExportResult.write()
    into a single call for callers that do not need to control each step
    individually.

    Args:
        config:  Fully populated ClientConfig instance.
        out_dir: Directory in which to write output files.

    Returns:
        An ExportResult containing all fetched and parsed Recipe instances.
        Output files have already been written to out_dir by the time this
        function returns.
    """
    client: NYTCookingClient = NYTCookingClient(config)
    client.verify_auth()
    recipes: list[Recipe] = [
        Recipe.from_api(raw) for raw in client.iter_saved_recipes()
    ]
    result: ExportResult = ExportResult(recipes=recipes)
    result.write(out_dir)
    return result
