import csv
import datetime as dt

import pytest

from erudite.pacts import ReadingStatus

# The header of a Goodreads library export, in the order Goodreads writes it.
GOODREADS_COLUMNS = (
    "Book Id",
    "Title",
    "Author",
    "Author l-f",
    "Additional Authors",
    "ISBN",
    "ISBN13",
    "My Rating",
    "Average Rating",
    "Publisher",
    "Binding",
    "Number of Pages",
    "Year Published",
    "Original Publication Year",
    "Date Read",
    "Date Added",
    "Bookshelves",
    "Bookshelves with positions",
    "Exclusive Shelf",
    "My Review",
    "Spoiler",
    "Private Notes",
    "Read Count",
    "Owned Copies",
)
MORT = {
    "Book Id": "386372",
    "Title": "Mort (Discworld, #4)",
    "Author": "Terry Pratchett",
    "ISBN": '="0552131067"',
    "ISBN13": '="9780552131063"',
    "My Rating": "5",
    "Date Read": "2020/03/01",
    "Date Added": "2019/12/24",
    "Bookshelves": "fantasy, favourites",
    "Exclusive Shelf": "read",
}
# What the app holds for the `MORT` row.
MORT_BOOK = {
    "goodreads_id": 386372,
    "title": "Mort",
    "authors": ["Terry Pratchett"],
    "isbn10": "0552131067",
    "isbn13": "9780552131063",
    "series": "Discworld",
    "series_position": "4",
    "shelves": ["fantasy", "favourites"],
    "rating": 5,
    "date_added": dt.date(2019, 12, 24),
    "date_read": dt.date(2020, 3, 1),
    "status": ReadingStatus.READ,
}
DUNE = {
    "Book Id": "44767458",
    "Title": "Dune",
    "Author": "Frank Herbert",
    "ISBN": '=""',
    "ISBN13": '=""',
    "My Rating": "0",
    "Date Added": "2021/05/05",
    "Bookshelves": "to-read",
    "Exclusive Shelf": "to-read",
}


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
