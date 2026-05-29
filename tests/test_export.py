"""Integration-style tests for export.py using a mocked NYTCookingClient session."""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ClientConfig
from export import export
from models import Recipe

FIXTURES = Path(__file__).parent / "fixtures"

_RECIPE_BOX_PAYLOAD = {
    "collectables_count": 1,
    "collectables": [
        {
            "id": 1234,
            "name": "Chocolate Chip Cookies",
            "byline": "By Melissa Clark",
            "url": "https://cooking.nytimes.com/recipes/1234-chocolate-chip-cookies",
            "yield": "5 dozen",
            "cooking_time": {"display": "45 minutes", "minutes": 45},
            "kicker": None,
            "avg_rating": 4.8,
            "num_ratings": 500,
            "has_video": False,
            "published_at": 1673740800000,
            "image": {"credit": "Photo by Johnny Miller"},
        }
    ],
}


def _make_config() -> ClientConfig:
    return ClientConfig(user_id="123", nyt_s_cookie="fake-cookie")


class TestExportWithContent:
    def test_enriched_json_includes_ingredients_and_steps(self, tmp_path):
        fixture_html = (FIXTURES / "recipe_jsonld.html").read_text(encoding="utf-8")

        mock_response_box = MagicMock()
        mock_response_box.raise_for_status = MagicMock()
        mock_response_box.json.return_value = _RECIPE_BOX_PAYLOAD

        mock_response_page = MagicMock()
        mock_response_page.raise_for_status = MagicMock()
        mock_response_page.text = fixture_html
        mock_response_page.status_code = 200

        with patch("client.Session") as MockSession:
            mock_session = MagicMock()
            MockSession.return_value = mock_session
            mock_session.get.side_effect = [
                mock_response_box,   # verify_auth (per_page=1)
                mock_response_box,   # page 1 of iter_saved_recipes
                mock_response_page,  # fetch_recipe_page
            ]
            mock_session.headers = {}
            mock_session.cookies = MagicMock()

            result = export(_make_config(), tmp_path, include_content=True, content_delay=0)

        assert len(result.recipes) == 1
        recipe = result.recipes[0]
        assert recipe.content is not None
        assert len(recipe.content.ingredients) == 3
        assert len(recipe.content.preparation_steps) == 3

        # Verify the JSON on disk includes the content
        exported = json.loads((tmp_path / "recipe_box.json").read_text(encoding="utf-8"))
        assert exported[0]["content"] is not None
        assert exported[0]["content"]["ingredients"][0] == "2 1/4 cups all-purpose flour"


class TestMetadataOnlyExport:
    def test_skips_page_fetch_and_content_is_null(self, tmp_path):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _RECIPE_BOX_PAYLOAD

        with patch("client.Session") as MockSession:
            mock_session = MagicMock()
            MockSession.return_value = mock_session
            mock_session.get.return_value = mock_response
            mock_session.headers = {}
            mock_session.cookies = MagicMock()

            result = export(_make_config(), tmp_path, include_content=False)

        assert len(result.recipes) == 1
        assert result.recipes[0].content is None

        exported = json.loads((tmp_path / "recipe_box.json").read_text(encoding="utf-8"))
        assert exported[0]["content"] is None

        # get() should have been called twice at most (auth probe + page 1), not for recipe page
        assert mock_session.get.call_count <= 2


class TestContentFetchFailureDegrades:
    def test_failed_page_fetch_leaves_content_none(self, tmp_path):
        mock_response_box = MagicMock()
        mock_response_box.raise_for_status = MagicMock()
        mock_response_box.json.return_value = _RECIPE_BOX_PAYLOAD

        with patch("client.Session") as MockSession:
            mock_session = MagicMock()
            MockSession.return_value = mock_session

            def _side_effect(*args, **kwargs):
                # First two calls (auth probe + page 1) succeed; third raises
                if mock_session.get.call_count <= 2:
                    return mock_response_box
                raise ConnectionError("Network failure")

            mock_session.get.side_effect = _side_effect
            mock_session.headers = {}
            mock_session.cookies = MagicMock()

            result = export(_make_config(), tmp_path, include_content=True, content_delay=0)

        # Export should succeed with content=None for the affected recipe
        assert len(result.recipes) == 1
        assert result.recipes[0].content is None
