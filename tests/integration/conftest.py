import csv

import pytest

from erudite import inits
from erudite.links.open_library import http
from tests.goodreads import GOODREADS_COLUMNS
from tests.open_library import FakeOpenLibrary


@pytest.fixture(name="goodreads_export")
def goodreads_export_fixture(tmp_path):
    """Return a function that writes its rows as an export and returns the path."""

    def write(*rows, columns=GOODREADS_COLUMNS):
        path = tmp_path / "goodreads_library_export.csv"
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, columns, restval="", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return path

    return write


@pytest.fixture(name="media")
def media_fixture(settings, tmp_path):
    """Keep the cover images a test writes out of the working directory."""
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture(name="open_library")
def open_library_fixture(monkeypatch):
    """Answer for Open Library, without the wait between two requests."""
    fake = FakeOpenLibrary()
    monkeypatch.setattr(http, "urlopen", fake)
    monkeypatch.setattr(inits, "OPEN_LIBRARY", http.OpenLibraryHttp(interval=0))
    return fake
