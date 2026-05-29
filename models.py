"""
models.py — Domain model for the NYT Cooking recipe box exporter.

Defines the typed in-memory representations of API entities.  This module
imports nothing from the project; all other modules may safely import from
it without creating circular dependencies.

Classes:
    CookingTime    Structured cooking duration (display string + minutes).
    RecipeContent  Full recipe content parsed from the individual recipe page.
    Recipe         Canonical representation of a single saved recipe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# CookingTime
# ---------------------------------------------------------------------------

@dataclass
class CookingTime:
    """
    Human-readable and machine-readable cooking duration for a recipe.

    The NYT API returns cooking time as a nested object with both a display
    string (e.g. "45 minutes") and an integer minute count.  Retaining both
    representations avoids a lossy conversion at ingest time and lets the
    caller choose the form appropriate for their use case.

    Attributes:
        display: Human-readable duration string as returned by the API
                 (e.g. "1 hour 15 minutes").  Empty string when absent.
        minutes: Total cooking time in minutes, or None if the API did not
                 provide a numeric value.
    """

    display: str = ""
    minutes: Optional[int] = None

    @classmethod
    def from_dict(cls, d: Optional[dict[str, object]]) -> "CookingTime":
        """
        Construct a CookingTime from the nested API dict.

        Accepts None — the `cooking_time` key is sometimes absent from the
        API response — and returns a zero-value instance rather than
        propagating None to callers.

        Args:
            d: The raw dict at the `cooking_time` key of an API recipe
               object, or None if the key was missing.

        Returns:
            A populated CookingTime, or a default instance with empty/None
            fields if d is falsy.
        """
        if not d:
            return cls()
        return cls(
            display=str(d.get("display", "")),
            minutes=int(float(d["minutes"])) if d.get("minutes") is not None else None,
        )


# ---------------------------------------------------------------------------
# RecipeContent
# ---------------------------------------------------------------------------

@dataclass
class RecipeContent:
    """
    Full recipe content parsed from an individual NYT Cooking recipe page.

    Populated by a second HTTP pass after the recipe-box metadata export.
    All fields default to empty/None so that partial parsing never raises.

    Attributes:
        description:       Recipe introduction text.
        ingredients:       Ordered list of ingredient strings.
        preparation_steps: Ordered list of method step strings.
        yield_:            Serving size from the recipe page (may differ from
                           the recipe-box value).
        total_time:        ISO 8601 duration string (e.g. "PT1H30M").
        prep_time:         ISO 8601 prep-time duration string.
        cook_time:         ISO 8601 cook-time duration string.
        nutrition:         Key/value nutrition facts (keys are schema.org
                           NutritionInformation property names).
        keywords:          List of editorial keyword strings.
        categories:        Recipe category labels.
        cuisine:           Cuisine labels.
        method:            Cooking method label (e.g. "Baking").
        image_urls:        List of image URL strings from the page.
        source_url:        Canonical URL as declared in the structured data.
        date_published:    ISO 8601 date string.
        date_modified:     ISO 8601 date string.
    """

    description: str = ""
    ingredients: list[str] = field(default_factory=list)
    preparation_steps: list[str] = field(default_factory=list)
    yield_: str = ""
    total_time: str = ""
    prep_time: str = ""
    cook_time: str = ""
    nutrition: dict[str, str] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    cuisine: list[str] = field(default_factory=list)
    method: str = ""
    image_urls: list[str] = field(default_factory=list)
    source_url: str = ""
    date_published: str = ""
    date_modified: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> "RecipeContent":
        """Reconstruct a RecipeContent from the exported JSON dict."""
        return cls(
            description=str(d.get("description", "")),
            ingredients=list(d.get("ingredients") or []),
            preparation_steps=list(d.get("preparation_steps") or []),
            yield_=str(d.get("yield_", "")),
            total_time=str(d.get("total_time", "")),
            prep_time=str(d.get("prep_time", "")),
            cook_time=str(d.get("cook_time", "")),
            nutrition=dict(d.get("nutrition") or {}),
            keywords=list(d.get("keywords") or []),
            categories=list(d.get("categories") or []),
            cuisine=list(d.get("cuisine") or []),
            method=str(d.get("method", "")),
            image_urls=list(d.get("image_urls") or []),
            source_url=str(d.get("source_url", "")),
            date_published=str(d.get("date_published", "")),
            date_modified=str(d.get("date_modified", "")),
        )


# ---------------------------------------------------------------------------
# Recipe
# ---------------------------------------------------------------------------

@dataclass
class Recipe:
    """
    Canonical in-memory representation of a single NYT Cooking recipe.

    This is the domain type used throughout the package.  All contact with
    raw API dicts is confined to `from_api`; every other layer works
    exclusively with typed Recipe instances.

    Attributes:
        id:              Unique integer recipe identifier assigned by NYT.
        name:            Recipe title, whitespace-normalised.
        byline:          Author credit line (e.g. "By Melissa Clark").
        url:             Canonical URL of the recipe on cooking.nytimes.com.
        yield_:          Serving size description (e.g. "4 servings").
                         Trailing underscore avoids shadowing the built-in.
        cooking_time:    Structured cooking duration.
        kicker:          Editorial label attached to the recipe
                         (e.g. "easy", "healthy").  Empty string if absent.
        avg_rating:      Mean star rating across all user submissions, or
                         None if no ratings exist yet.
        num_ratings:     Total number of ratings submitted, or None if the
                         field is absent from the API response.
        has_video:       True if the recipe has an associated video.
        published_at_ms: Unix timestamp in milliseconds of the original
                         publication date, or None if absent.
        image_credit:    Photographer or illustrator credit for the lead
                         image.  Empty string if absent.
    """

    id: int
    name: str
    byline: str
    url: str
    yield_: str
    cooking_time: CookingTime
    kicker: str
    avg_rating: Optional[float]
    num_ratings: Optional[int]
    has_video: bool
    published_at_ms: Optional[int]
    image_credit: str
    content: Optional[RecipeContent] = None

    @classmethod
    def from_api(cls, r: dict[str, object]) -> "Recipe":
        """
        Construct a Recipe from a raw API response dict.

        This is the single point at which untyped API data is coerced into
        the domain model.  Every field that the API may omit is handled here
        with an explicit default so that callers never receive a KeyError or
        an unexpected None where the type annotation promises a concrete type.

        Args:
            r: A single element from the `collectables` list in an API
               response payload.

        Returns:
            A fully populated Recipe instance.

        Raises:
            KeyError: If the mandatory `id` field is absent, indicating a
                      malformed API response.
        """
        return cls(
            id=int(r["id"]),
            name=(str(r.get("name") or "")).strip(),
            byline=str(r.get("byline", "")),
            url=str(r.get("url", "")),
            yield_=str(r.get("yield", "")),
            cooking_time=CookingTime.from_dict(
                r.get("cooking_time")  # type: ignore[arg-type]
            ),
            kicker=str((r.get("kicker") or {}).get("name", "")),  # type: ignore[union-attr]
            avg_rating=float(r["avg_rating"]) if r.get("avg_rating") is not None else None,
            num_ratings=int(r["num_ratings"]) if r.get("num_ratings") is not None else None,
            has_video=bool(r.get("has_video", False)),
            published_at_ms=int(r["published_at"]) if r.get("published_at") is not None else None,
            image_credit=str((r.get("image") or {}).get("credit", "")),  # type: ignore[union-attr]
        )

    @classmethod
    def from_export(cls, r: dict[str, object]) -> "Recipe":
        """
        Construct a Recipe from this project's exported JSON representation.

        The exported JSON is produced from dataclasses.asdict(), so a few
        field names differ from the live API payload: `yield_` is already
        disambiguated, `published_at_ms` is already converted, and
        `image_credit` is flattened.
        """
        content_data = r.get("content")
        return cls(
            id=int(r["id"]),
            name=(str(r.get("name") or "")).strip(),
            byline=str(r.get("byline", "")),
            url=str(r.get("url", "")),
            yield_=str(r.get("yield_", r.get("yield", ""))),
            cooking_time=CookingTime.from_dict(
                r.get("cooking_time")  # type: ignore[arg-type]
            ),
            kicker=str(r.get("kicker", "")),
            avg_rating=float(r["avg_rating"]) if r.get("avg_rating") is not None else None,
            num_ratings=int(r["num_ratings"]) if r.get("num_ratings") is not None else None,
            has_video=bool(r.get("has_video", False)),
            published_at_ms=int(r["published_at_ms"]) if r.get("published_at_ms") is not None else None,
            image_credit=str(r.get("image_credit", "")),
            content=RecipeContent.from_dict(content_data) if isinstance(content_data, dict) else None,
        )

    def to_flat_dict(self) -> dict[str, object]:
        """
        Return a flat dict representation suitable for CSV serialisation.

        CSV rows must be flat key/value mappings.  The nested CookingTime is
        expanded into two prefixed columns.  Column names use underscores so
        they import cleanly into spreadsheet tools and SQL without quoting.

        Returns:
            An ordered dict whose keys form the CSV header row and whose
            values are all JSON-serialisable scalars.
        """
        return {
            "id": self.id,
            "name": self.name,
            "byline": self.byline,
            "url": self.url,
            "yield": self.yield_,
            "cooking_time_display": self.cooking_time.display,
            "cooking_time_minutes": self.cooking_time.minutes,
            "kicker": self.kicker,
            "avg_rating": self.avg_rating,
            "num_ratings": self.num_ratings,
            "has_video": self.has_video,
            "published_at_ms": self.published_at_ms,
            "image_credit": self.image_credit,
        }
