"""
parser.py — Extracts structured recipe content from NYT Cooking recipe pages.

Parsing strategy (in order):
    1. <script type="application/ld+json"> block containing @type: Recipe.
    2. <script id="__NEXT_DATA__"> hydration payload, searched depth-first for
       a node with @type: Recipe.

Both paths produce a RecipeContent via the same normalisation helpers.
Returns None with a warning if neither strategy finds usable data.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from models import RecipeContent

log: logging.Logger = logging.getLogger(__name__)

_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_NEXTDATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_recipe_content(html: str, url: str = "") -> Optional[RecipeContent]:
    """
    Extract RecipeContent from the HTML of a NYT Cooking recipe page.

    Args:
        html: Full HTML source of the recipe page.
        url:  URL used only for warning messages; not required for parsing.

    Returns:
        A populated RecipeContent, or None if no structured data was found.
    """
    content = _from_jsonld(html)
    if content is not None:
        return content

    content = _from_nextjs(html)
    if content is not None:
        return content

    log.warning("No parseable recipe content found%s.", f" for {url}" if url else "")
    return None


# ---------------------------------------------------------------------------
# JSON-LD path
# ---------------------------------------------------------------------------

def _from_jsonld(html: str) -> Optional[RecipeContent]:
    for match in _JSONLD_RE.finditer(html):
        try:
            blob = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue

        candidates: list = blob if isinstance(blob, list) else [blob]
        for node in candidates:
            if isinstance(node, dict) and node.get("@type") == "Recipe":
                log.debug("Extracted recipe content from JSON-LD.")
                return _build_content(node)
    return None


# ---------------------------------------------------------------------------
# Next.js hydration path
# ---------------------------------------------------------------------------

def _from_nextjs(html: str) -> Optional[RecipeContent]:
    match = _NEXTDATA_RE.search(html)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

    node = _find_recipe_node(data, depth=0)
    if node is not None:
        log.debug("Extracted recipe content from Next.js hydration payload.")
        return _build_content(node)
    return None


def _find_recipe_node(obj: object, depth: int) -> Optional[dict]:
    if depth > 20:
        return None
    if isinstance(obj, dict):
        if obj.get("@type") == "Recipe":
            return obj
        for v in obj.values():
            result = _find_recipe_node(v, depth + 1)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _find_recipe_node(item, depth + 1)
            if result is not None:
                return result
    return None


# ---------------------------------------------------------------------------
# Schema.org node → RecipeContent
# ---------------------------------------------------------------------------

def _build_content(node: dict) -> RecipeContent:
    return RecipeContent(
        description=str(node.get("description", "")),
        ingredients=_to_str_list(node.get("recipeIngredient")),
        preparation_steps=_extract_steps(node.get("recipeInstructions")),
        yield_=_to_str(node.get("recipeYield")),
        total_time=str(node.get("totalTime", "")),
        prep_time=str(node.get("prepTime", "")),
        cook_time=str(node.get("cookTime", "")),
        nutrition=_extract_nutrition(node.get("nutrition")),
        keywords=_extract_keywords(node.get("keywords")),
        categories=_to_str_list(node.get("recipeCategory")),
        cuisine=_to_str_list(node.get("recipeCuisine")),
        method=str(node.get("cookingMethod", "")),
        image_urls=_extract_images(node.get("image")),
        source_url=str(node.get("url", "")),
        date_published=str(node.get("datePublished", "")),
        date_modified=str(node.get("dateModified", "")),
    )


def _extract_steps(raw: object) -> list[str]:
    if not raw:
        return []
    items: list = raw if isinstance(raw, list) else [raw]
    steps: list[str] = []
    for item in items:
        if isinstance(item, str):
            if item.strip():
                steps.append(item.strip())
        elif isinstance(item, dict):
            t = item.get("@type", "")
            if t == "HowToSection":
                steps.extend(_extract_steps(item.get("itemListElement")))
            else:
                text = str(item.get("text", item.get("name", ""))).strip()
                if text:
                    steps.append(text)
    return steps


def _to_str_list(raw: object) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw] if raw else []
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    return [str(raw)]


def _to_str(raw: object) -> str:
    if not raw:
        return ""
    if isinstance(raw, list):
        return str(raw[0]) if raw else ""
    return str(raw)


def _extract_keywords(raw: object) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [k.strip() for k in raw.split(",") if k.strip()]
    return _to_str_list(raw)


def _extract_nutrition(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {k: str(v) for k, v in raw.items() if k != "@type" and v}


def _extract_images(raw: object) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, dict):
        url = raw.get("url", "")
        return [str(url)] if url else []
    if isinstance(raw, list):
        result: list[str] = []
        for item in raw:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                url = item.get("url", "")
                if url:
                    result.append(str(url))
        return result
    return []
