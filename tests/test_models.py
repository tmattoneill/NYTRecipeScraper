"""Tests for RecipeContent serialisation round-trip and Recipe.from_export."""

from __future__ import annotations

import sys
import dataclasses
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import Recipe, RecipeContent, CookingTime


def _base_recipe() -> Recipe:
    return Recipe(
        id=42,
        name="Test Recipe",
        byline="By Test Author",
        url="https://cooking.nytimes.com/recipes/42-test",
        yield_="4 servings",
        cooking_time=CookingTime(display="30 minutes", minutes=30),
        kicker="easy",
        avg_rating=4.5,
        num_ratings=100,
        has_video=False,
        published_at_ms=1_700_000_000_000,
        image_credit="Photo by Test",
    )


class TestRecipeContentRoundTrip:
    def test_full_content_survives_asdict_from_export(self):
        content = RecipeContent(
            description="A test recipe.",
            ingredients=["1 cup flour", "2 eggs"],
            preparation_steps=["Mix.", "Bake."],
            yield_="4 servings",
            total_time="PT1H",
            prep_time="PT15M",
            cook_time="PT45M",
            nutrition={"calories": "200 calories"},
            keywords=["easy", "baking"],
            categories=["Dessert"],
            cuisine=["American"],
            method="Baking",
            image_urls=["https://example.com/img.jpg"],
            source_url="https://cooking.nytimes.com/recipes/42-test",
            date_published="2024-01-01",
            date_modified="2024-06-01",
        )
        recipe = dataclasses.replace(_base_recipe(), content=content)
        exported = dataclasses.asdict(recipe)

        restored = Recipe.from_export(exported)
        assert restored.content is not None
        assert restored.content.ingredients == ["1 cup flour", "2 eggs"]
        assert restored.content.preparation_steps == ["Mix.", "Bake."]
        assert restored.content.nutrition == {"calories": "200 calories"}
        assert restored.content.keywords == ["easy", "baking"]
        assert restored.content.image_urls == ["https://example.com/img.jpg"]
        assert restored.content.date_published == "2024-01-01"

    def test_null_content_survives_round_trip(self):
        recipe = _base_recipe()
        exported = dataclasses.asdict(recipe)
        restored = Recipe.from_export(exported)
        assert restored.content is None

    def test_content_none_in_exported_json_gives_none(self):
        exported = dataclasses.asdict(_base_recipe())
        exported["content"] = None
        restored = Recipe.from_export(exported)
        assert restored.content is None


class TestRecipeFromApi:
    def test_content_defaults_to_none(self):
        raw = {
            "id": 99,
            "name": "Simple",
            "byline": "By Author",
            "url": "https://cooking.nytimes.com/recipes/99",
            "yield": "2 servings",
            "cooking_time": None,
            "kicker": None,
            "avg_rating": None,
            "num_ratings": None,
            "has_video": False,
            "published_at": None,
            "image": None,
        }
        recipe = Recipe.from_api(raw)
        assert recipe.content is None
