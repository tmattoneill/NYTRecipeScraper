"""
viewer — Interactive terminal recipe viewer package.

Exposes the two entry points that external callers need.  The internal
module structure (formatting, renderers, loop, main) is an implementation
detail; nothing outside this package should import from submodules directly.

Public API:
    run(recipes)  Launch the interactive viewer with a list of Recipe objects.
    main()        CLI entry point: parse args, load recipes, call run().

Usage:
    # Programmatic
    from viewer import run
    run(my_recipes)

    # CLI
    python -m viewer --data ./exports/recipe_box.json
"""

from viewer.loop import run
from viewer.main import main

__all__: list[str] = ["run", "main"]
