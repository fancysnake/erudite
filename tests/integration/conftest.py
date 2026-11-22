import csv

import pytest

from tests.goodreads import GOODREADS_COLUMNS


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
