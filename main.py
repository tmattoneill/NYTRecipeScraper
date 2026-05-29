"""
main.py — CLI entry point for the NYT Cooking recipe box exporter.

Responsibilities:
    * Configure the logging subsystem.
    * Parse command-line arguments.
    * Load ClientConfig from the environment (which includes .env via
      config.py's optional dotenv integration).
    * Delegate all work to export.export() and report the outcome.

This module imports from every other module in the package but nothing in
the package imports from here, keeping the dependency graph acyclic.

Usage:
    python main.py
    python main.py --out-dir ./exports
    python main.py --out-dir ./exports --log-level DEBUG
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from config import ClientConfig
from export import export, ExportResult

log: logging.Logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """
    Construct the argument parser for the CLI.

    Defined as a standalone function so that it can be tested independently
    of the startup sequence and reused if a sub-command structure is added
    in future.

    Returns:
        A configured ArgumentParser instance, not yet evaluated against
        sys.argv.
    """
    parser = argparse.ArgumentParser(
        description="Export your NYT Cooking recipe box to JSON and CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Environment variables (can also be set in .env):\n"
            "  NYT_USER_ID       Your numeric NYT user ID (required)\n"
            "  NYT_S_COOKIE      Value of the NYT-S session cookie (required)\n"
            "  NYT_PER_PAGE      Recipes per API page, max 48 (default: 48)\n"
            "  NYT_REQUEST_DELAY Seconds between page requests (default: 0.5)\n"
            "  NYT_TIMEOUT       HTTP timeout in seconds (default: 30)\n"
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("."),
        metavar="DIR",
        help="Directory to write output files (default: current directory)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        metavar="LEVEL",
        help="Logging verbosity: DEBUG | INFO | WARNING | ERROR (default: INFO)",
    )
    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Parse arguments, load configuration, and run the export.

    Exits with status 1 and a human-readable message if required environment
    variables are missing.  All other exceptions (network errors, permission
    errors on the output directory) are allowed to propagate so that the
    default Python traceback is shown; these represent unexpected conditions
    that warrant inspection rather than a clean user-facing error message.
    """
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    try:
        config: ClientConfig = ClientConfig.from_env()
    except EnvironmentError as exc:
        # Surface a clean diagnostic for the most common failure mode.
        log.error("Configuration error: %s", exc)
        sys.exit(1)

    out_dir: Path = args.out_dir
    log.info("Writing output to %s", out_dir.resolve())

    result: ExportResult = export(config, out_dir)
    print(f"Exported {len(result.recipes)} recipes → {out_dir.resolve()}")


if __name__ == "__main__":
    main()
