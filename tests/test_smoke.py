"""Smoke tests covering CLI flags, viewer compatibility, pagination, CSV, and URL guard."""

from __future__ import annotations

import csv
import dataclasses
import json
import os
import sys
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import main as main_module
from client import AuthenticationError, NYTCookingClient
from config import ClientConfig
from export import ExportResult
from models import CookingTime, Recipe, RecipeContent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> ClientConfig:
    return ClientConfig(user_id="123", nyt_s_cookie="fake-cookie")


def _make_recipe(
    name: str = "Test Recipe",
    url: str = "https://cooking.nytimes.com/recipes/1-test",
    content: Optional[RecipeContent] = None,
) -> Recipe:
    return Recipe(
        id=1,
        name=name,
        byline="By Test Author",
        url=url,
        yield_="4 servings",
        cooking_time=CookingTime(display="30 minutes", minutes=30),
        kicker="easy",
        avg_rating=4.5,
        num_ratings=100,
        has_video=False,
        published_at_ms=1_700_000_000_000,
        image_credit="Photo by Tester",
        content=content,
    )


def _make_page_payload(records: list, count: Optional[int] = None) -> dict:
    payload: dict = {"collectables": records}
    if count is not None:
        payload["collectables_count"] = count
    return payload


def _mock_response(json_data=None, text: Optional[str] = None) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.status_code = 200
    if json_data is not None:
        resp.json.return_value = json_data
    if text is not None:
        resp.text = text
    return resp


def _raw_recipe_dict(id: int = 1, url: str = "https://cooking.nytimes.com/recipes/1") -> dict:
    return {
        "id": id,
        "name": f"Recipe {id}",
        "byline": "By Author",
        "url": url,
        "yield": "2 servings",
        "cooking_time": {"display": "30 minutes", "minutes": 30},
        "kicker": None,
        "avg_rating": 4.0,
        "num_ratings": 50,
        "has_video": False,
        "published_at": 1_673_740_800_000,
        "image": {"credit": "Photo"},
    }


def _setup_session_mock(MockSession: MagicMock) -> MagicMock:
    mock_session = MagicMock()
    MockSession.return_value = mock_session
    mock_session.headers = {}
    mock_session.cookies = MagicMock()
    return mock_session


# ---------------------------------------------------------------------------
# TestCLIFlags
# ---------------------------------------------------------------------------

class TestCLIFlags:
    """CLI flags wire correctly to export() and error paths exit with code 1."""

    _BASE_ENV = {"NYT_USER_ID": "123", "NYT_S_COOKIE": "fake"}

    def _run(
        self,
        argv: list[str],
        extra_env: Optional[dict] = None,
        fake_result: Optional[ExportResult] = None,
    ) -> MagicMock:
        """Run main.main() with mocked export(); return the mock for inspection."""
        env = {**self._BASE_ENV, **(extra_env or {})}
        result = fake_result if fake_result is not None else ExportResult(recipes=[_make_recipe()])
        mock_export = MagicMock(return_value=result)
        with patch("sys.argv", ["main.py", *argv]):
            with patch.dict(os.environ, env):
                with patch("logging.basicConfig"):
                    with patch("main.export", mock_export):
                        main_module.main()
        return mock_export

    def test_metadata_only_calls_export_without_content(self, tmp_path):
        mock_export = self._run(["--metadata-only", "--out-dir", str(tmp_path)])
        assert mock_export.call_args[1]["include_content"] is False

    def test_content_delay_flag_wires_to_export(self, tmp_path):
        mock_export = self._run(["--content-delay", "2.5", "--out-dir", str(tmp_path)])
        assert mock_export.call_args[1]["content_delay"] == 2.5

    def test_exit_code_1_on_authentication_error(self, tmp_path):
        with patch("sys.argv", ["main.py", "--out-dir", str(tmp_path)]):
            with patch.dict(os.environ, self._BASE_ENV):
                with patch("logging.basicConfig"):
                    with patch("main.export", side_effect=AuthenticationError("expired")):
                        with pytest.raises(SystemExit) as exc_info:
                            main_module.main()
        assert exc_info.value.code == 1

    def test_exit_code_1_on_missing_nyt_user_id(self, tmp_path):
        with patch("sys.argv", ["main.py", "--out-dir", str(tmp_path)]):
            with patch.dict(os.environ, {"NYT_USER_ID": "", "NYT_S_COOKIE": "x"}):
                with patch("logging.basicConfig"):
                    with pytest.raises(SystemExit) as exc_info:
                        main_module.main()
        assert exc_info.value.code == 1

    def test_exit_code_1_on_missing_nyt_s_cookie(self, tmp_path):
        with patch("sys.argv", ["main.py", "--out-dir", str(tmp_path)]):
            with patch.dict(os.environ, {"NYT_USER_ID": "123", "NYT_S_COOKIE": ""}):
                with patch("logging.basicConfig"):
                    with pytest.raises(SystemExit) as exc_info:
                        main_module.main()
        assert exc_info.value.code == 1

    def test_success_message_with_content(self, tmp_path, capsys):
        recipes = [
            _make_recipe(name="A", content=RecipeContent(ingredients=["flour"])),
            _make_recipe(name="B", content=None),
        ]
        self._run(["--out-dir", str(tmp_path)], fake_result=ExportResult(recipes=recipes))
        out = capsys.readouterr().out
        assert "Exported 2 recipes" in out
        assert "1 with full content" in out

    def test_success_message_metadata_only(self, tmp_path, capsys):
        recipes = [_make_recipe(name="A"), _make_recipe(name="B")]
        self._run(
            ["--metadata-only", "--out-dir", str(tmp_path)],
            fake_result=ExportResult(recipes=recipes),
        )
        out = capsys.readouterr().out
        assert "Exported 2 recipes" in out
        assert "metadata only" in out


# ---------------------------------------------------------------------------
# TestViewerBackwardCompatibility
# ---------------------------------------------------------------------------

class TestViewerBackwardCompatibility:
    """Viewer loads recipe_box.json correctly whether content is absent, null, or populated."""

    def _write_json(self, tmp_path: Path, records: list[dict]) -> Path:
        p = tmp_path / "recipe_box.json"
        p.write_text(json.dumps(records), encoding="utf-8")
        return p

    def test_load_recipes_content_null(self, tmp_path):
        from viewer.main import _load_recipes
        d = dataclasses.asdict(_make_recipe())
        d["content"] = None
        recipes = _load_recipes(self._write_json(tmp_path, [d]))
        assert len(recipes) == 1
        assert recipes[0].content is None

    def test_load_recipes_content_absent_legacy(self, tmp_path):
        from viewer.main import _load_recipes
        d = dataclasses.asdict(_make_recipe())
        del d["content"]
        recipes = _load_recipes(self._write_json(tmp_path, [d]))
        assert recipes[0].content is None

    def test_load_recipes_content_populated(self, tmp_path):
        from viewer.main import _load_recipes
        content = RecipeContent(ingredients=["1 cup flour", "2 eggs"], preparation_steps=["Mix.", "Bake."])
        d = dataclasses.asdict(_make_recipe(content=content))
        recipes = _load_recipes(self._write_json(tmp_path, [d]))
        assert recipes[0].content is not None
        assert recipes[0].content.ingredients == ["1 cup flour", "2 eggs"]

    def test_load_recipes_mixed(self, tmp_path):
        from viewer.main import _load_recipes
        d1 = dataclasses.asdict(_make_recipe(name="Alpha"))
        d1["content"] = None
        d2 = dataclasses.asdict(_make_recipe(name="Beta", content=RecipeContent(ingredients=["salt"])))
        recipes = _load_recipes(self._write_json(tmp_path, [d1, d2]))
        assert len(recipes) == 2
        assert recipes[0].name == "Alpha"
        assert recipes[0].content is None
        assert recipes[1].name == "Beta"
        assert recipes[1].content is not None

    def test_load_recipes_sorts_alphabetically(self, tmp_path):
        from viewer.main import _load_recipes
        dicts = [dataclasses.asdict(_make_recipe(name=n)) for n in ["Zucchini Bread", "Muffins", "Apple Cake"]]
        recipes = _load_recipes(self._write_json(tmp_path, dicts))
        assert [r.name for r in recipes] == ["Apple Cake", "Muffins", "Zucchini Bread"]

    def test_load_recipes_file_not_found_raises_system_exit(self, tmp_path):
        from viewer.main import _load_recipes
        with pytest.raises(SystemExit):
            _load_recipes(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# TestPaginationSleepTiming
# ---------------------------------------------------------------------------

class TestPaginationSleepTiming:
    """time.sleep fires between pages but not after the last page."""

    def _iter(self, responses: list, count: Optional[int] = None) -> tuple[list, MagicMock]:
        """Run iter_saved_recipes with given page responses; return (records, mock_sleep)."""
        with patch("client.Session") as MockSession:
            with patch("client.time.sleep") as mock_sleep:
                mock_session = _setup_session_mock(MockSession)
                mock_session.get.side_effect = [_mock_response(json_data=r) for r in responses]
                client = NYTCookingClient(_make_config())
                records = list(client.iter_saved_recipes())
        return records, mock_sleep

    def test_sleep_skipped_when_count_satisfied_on_first_page(self):
        payload = _make_page_payload([_raw_recipe_dict(1), _raw_recipe_dict(2)], count=2)
        records, mock_sleep = self._iter([payload])
        assert len(records) == 2
        assert mock_sleep.call_count == 0

    def test_sleep_fires_once_between_two_pages(self):
        page1 = _make_page_payload([_raw_recipe_dict(1), _raw_recipe_dict(2)], count=4)
        page2 = _make_page_payload([_raw_recipe_dict(3), _raw_recipe_dict(4)], count=4)
        records, mock_sleep = self._iter([page1, page2])
        assert len(records) == 4
        assert mock_sleep.call_count == 1

    def test_sleep_fires_n_minus_1_times_for_n_pages(self):
        pages = [
            _make_page_payload([_raw_recipe_dict(i * 2 + 1), _raw_recipe_dict(i * 2 + 2)], count=6)
            for i in range(3)
        ]
        records, mock_sleep = self._iter(pages)
        assert len(records) == 6
        assert mock_sleep.call_count == 2

    def test_stops_on_empty_page_when_count_absent(self):
        page1 = _make_page_payload([_raw_recipe_dict(1), _raw_recipe_dict(2)])
        page2 = _make_page_payload([])
        records, mock_sleep = self._iter([page1, page2])
        assert len(records) == 2
        assert mock_sleep.call_count == 1


# ---------------------------------------------------------------------------
# TestCSVOutput
# ---------------------------------------------------------------------------

class TestCSVOutput:
    """CSV has the right header, excludes content, handles special chars, and skips on empty."""

    _EXPECTED_HEADER = [
        "id", "name", "byline", "url", "yield",
        "cooking_time_display", "cooking_time_minutes",
        "kicker", "avg_rating", "num_ratings",
        "has_video", "published_at_ms", "image_credit",
    ]

    def test_csv_header_exact(self, tmp_path):
        ExportResult(recipes=[_make_recipe()]).write(tmp_path)
        with (tmp_path / "recipe_box.csv").open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            assert reader.fieldnames == self._EXPECTED_HEADER

    def test_csv_content_field_absent(self, tmp_path):
        recipe = _make_recipe(content=RecipeContent(ingredients=["flour"], preparation_steps=["Mix."]))
        ExportResult(recipes=[recipe]).write(tmp_path)
        with (tmp_path / "recipe_box.csv").open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            assert "content" not in (reader.fieldnames or [])

    def test_csv_special_chars_roundtrip(self, tmp_path):
        recipe = dataclasses.replace(_make_recipe(), name='Cookies, Deluxe', byline='By "Chef" Alice')
        ExportResult(recipes=[recipe]).write(tmp_path)
        with (tmp_path / "recipe_box.csv").open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert rows[0]["name"] == "Cookies, Deluxe"
        assert rows[0]["byline"] == 'By "Chef" Alice'

    def test_csv_empty_recipe_list_writes_no_file(self, tmp_path):
        ExportResult(recipes=[]).write(tmp_path)
        assert not (tmp_path / "recipe_box.csv").exists()


# ---------------------------------------------------------------------------
# TestRecipeWithoutURL
# ---------------------------------------------------------------------------

class TestRecipeWithoutURL:
    """Recipes with an empty URL are skipped during content enrichment."""

    def test_no_fetch_for_empty_url(self, tmp_path):
        from export import export as run_export

        box_payload = {
            "collectables_count": 1,
            "collectables": [_raw_recipe_dict(id=1, url="")],
        }
        box_resp = _mock_response(json_data=box_payload)

        with patch("client.Session") as MockSession:
            mock_session = _setup_session_mock(MockSession)
            # auth probe + page 1; no third call for fetch_recipe_page
            mock_session.get.side_effect = [box_resp, box_resp]
            result = run_export(_make_config(), tmp_path, include_content=True, content_delay=0)

        assert result.recipes[0].content is None
        assert mock_session.get.call_count == 2
