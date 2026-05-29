"""Tests for parser.py."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on path when running tests directly.
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from parser import parse_recipe_content
from models import RecipeContent

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestJsonLdParsing:
    def setup_method(self):
        self.html = _load("recipe_jsonld.html")
        self.content = parse_recipe_content(self.html, url="https://example.com/recipe")

    def test_returns_recipe_content(self):
        assert isinstance(self.content, RecipeContent)

    def test_ingredients(self):
        assert len(self.content.ingredients) == 3
        assert "2 1/4 cups all-purpose flour" in self.content.ingredients

    def test_preparation_steps(self):
        # Three steps: two direct HowToStep + one nested in HowToSection
        assert len(self.content.preparation_steps) == 3
        assert "Heat oven to 375 degrees." in self.content.preparation_steps
        assert "Bake for 11 to 13 minutes." in self.content.preparation_steps

    def test_description(self):
        assert self.content.description == "The classic cookie."

    def test_yield(self):
        assert self.content.yield_ == "5 dozen cookies"

    def test_times(self):
        assert self.content.total_time == "PT45M"
        assert self.content.prep_time == "PT20M"
        assert self.content.cook_time == "PT13M"

    def test_nutrition(self):
        assert self.content.nutrition.get("calories") == "150 calories"
        assert "@type" not in self.content.nutrition

    def test_keywords(self):
        assert "cookies" in self.content.keywords
        assert "chocolate" in self.content.keywords
        assert "dessert" in self.content.keywords

    def test_categories(self):
        assert "Dessert" in self.content.categories

    def test_cuisine(self):
        assert "American" in self.content.cuisine

    def test_method(self):
        assert self.content.method == "Baking"

    def test_image_urls(self):
        assert "https://example.com/cookie.jpg" in self.content.image_urls
        assert "https://example.com/cookie2.jpg" in self.content.image_urls

    def test_dates(self):
        assert self.content.date_published == "2023-01-15"
        assert self.content.date_modified == "2024-03-10"


class TestNextJsParsing:
    def setup_method(self):
        self.html = _load("recipe_nextjs.html")
        self.content = parse_recipe_content(self.html, url="https://example.com/recipe")

    def test_returns_recipe_content(self):
        assert isinstance(self.content, RecipeContent)

    def test_ingredients(self):
        assert len(self.content.ingredients) == 3
        assert "200g spaghetti" in self.content.ingredients

    def test_preparation_steps(self):
        assert len(self.content.preparation_steps) == 3
        assert "Cook pasta in salted boiling water." in self.content.preparation_steps

    def test_image_url_string(self):
        assert "https://example.com/carbonara.jpg" in self.content.image_urls


class TestMissingContent:
    def test_returns_none_on_no_structured_data(self):
        html = _load("recipe_no_content.html")
        result = parse_recipe_content(html, url="https://example.com/page")
        assert result is None

    def test_returns_none_on_empty_html(self):
        result = parse_recipe_content("", url="https://example.com/empty")
        assert result is None

    def test_returns_none_on_malformed_jsonld(self):
        html = '<script type="application/ld+json">{ broken json </script>'
        result = parse_recipe_content(html)
        assert result is None
