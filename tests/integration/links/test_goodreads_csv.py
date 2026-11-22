import datetime as dt

import pytest

from erudite.links.goodreads.csv import GoodreadsCsvExport
from erudite.pacts import GoodreadsExportError, ReadingStatus
from tests.goodreads import DUNE, GOODREADS_COLUMNS, MORT, MORT_BOOK


def _read_one(goodreads_export, **changes):
    return GoodreadsCsvExport().read(goodreads_export(MORT | changes))[0]


def test_a_book_keeps_everything_the_export_says_about_it(goodreads_export):
    books = GoodreadsCsvExport().read(goodreads_export(MORT, DUNE))

    assert books == [
        MORT_BOOK,
        {
            "goodreads_id": 44767458,
            "title": "Dune",
            "authors": ["Frank Herbert"],
            "isbn10": "",
            "isbn13": "",
            "series": "",
            "series_position": "",
            "shelves": ["to-read"],
            "rating": None,
            "date_added": dt.date(2021, 5, 5),
            "date_read": None,
            "status": ReadingStatus.TO_READ,
        },
    ]


@pytest.mark.parametrize(
    ("exported", "title", "series", "position"),
    (
        ("Mort (Discworld, #4)", "Mort", "Discworld", "4"),
        ("Mort (Discworld #4)", "Mort", "Discworld", "4"),
        ("Mort (Discworld, #4; Death, #1)", "Mort", "Discworld", "4"),
        ("The Sandman (The Sandman, #1-3)", "The Sandman", "The Sandman", "1-3"),
        ("Edgedancer (Stormlight, #2.5)", "Edgedancer", "Stormlight", "2.5"),
        ("Dune (Deluxe Edition)", "Dune (Deluxe Edition)", "", ""),
        ("Catch-22", "Catch-22", "", ""),
    ),
)
def test_series_and_position_come_from_the_title(
    goodreads_export, *, exported, title, series, position
):
    book = _read_one(goodreads_export, Title=exported)

    assert (book["title"], book["series"], book["series_position"]) == (
        title,
        series,
        position,
    )


@pytest.mark.parametrize(
    ("exported", "isbn"),
    (
        ('="0552131067"', "0552131067"),
        ('="055213106x"', "055213106X"),
        ("0552131067", "0552131067"),
        ('=""', ""),
        ("", ""),
    ),
)
def test_an_isbn_loses_its_spreadsheet_formula(goodreads_export, *, exported, isbn):
    assert _read_one(goodreads_export, ISBN=exported)["isbn10"] == isbn


@pytest.mark.parametrize(
    ("shelf", "status"),
    (
        ("read", ReadingStatus.READ),
        ("currently-reading", ReadingStatus.READING),
        ("to-read", ReadingStatus.TO_READ),
        ("abandoned", ReadingStatus.TO_READ),
    ),
)
def test_the_exclusive_shelf_gives_the_status(goodreads_export, *, shelf, status):
    book = _read_one(goodreads_export, **{"Exclusive Shelf": shelf})

    assert book["status"] == status


@pytest.mark.parametrize(
    ("exported", "rating"), (("5", 5), ("5.0", 5), ("0", None), ("0.0", None))
)
def test_a_rating_is_a_whole_number_or_nothing(goodreads_export, *, exported, rating):
    assert _read_one(goodreads_export, **{"My Rating": exported})["rating"] == rating


def test_names_and_titles_lose_their_extra_spaces(goodreads_export):
    book = _read_one(
        goodreads_export,
        Title="Night's  Master  (Flat Earth #1)",
        Author="Tanith  Lee",
        **{"Additional Authors": "Klaus  Brenner"},
    )

    assert (book["title"], book["authors"]) == (
        "Night's Master",
        ["Tanith Lee", "Klaus Brenner"],
    )


def test_additional_authors_follow_the_author(goodreads_export):
    book = _read_one(
        goodreads_export,
        Author="Terry Pratchett",
        **{"Additional Authors": "Neil Gaiman,  Paul Kidby"},
    )

    assert book["authors"] == ["Terry Pratchett", "Neil Gaiman", "Paul Kidby"]


def test_a_byte_order_mark_does_not_hide_the_first_column(goodreads_export):
    path = goodreads_export(MORT)
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())

    assert GoodreadsCsvExport().read(path) == [MORT_BOOK]


def test_an_export_with_no_books_is_empty(goodreads_export):
    assert not GoodreadsCsvExport().read(goodreads_export())


def test_a_missing_column_is_named(goodreads_export):
    columns = [name for name in GOODREADS_COLUMNS if name != "ISBN13"]
    path = goodreads_export(MORT, columns=columns)

    with pytest.raises(GoodreadsExportError, match=r"\.csv: no 'ISBN13' column\.$"):
        GoodreadsCsvExport().read(path)


@pytest.mark.parametrize("columns", ((), ("Title", "Author")))
def test_an_export_with_no_books_and_the_wrong_columns_is_rejected(
    goodreads_export, columns
):
    path = goodreads_export(columns=columns)

    with pytest.raises(GoodreadsExportError, match=r"\.csv: no 'Book Id' column\.$"):
        GoodreadsCsvExport().read(path)


@pytest.mark.parametrize(
    "changes",
    (
        {"Book Id": "mort"},
        {"Date Added": "24.12.2019"},
        {"My Rating": "five"},
        {"My Rating": "4.5"},
    ),
)
def test_a_value_that_does_not_parse_names_its_row(goodreads_export, changes):
    path = goodreads_export(DUNE, MORT | changes)

    with pytest.raises(GoodreadsExportError, match=r"\.csv, row 3: "):
        GoodreadsCsvExport().read(path)


def test_a_row_of_another_width_names_its_row(goodreads_export):
    path = goodreads_export(MORT)
    path.write_text(path.read_text() + "386373,Sourcery\n")

    with pytest.raises(
        GoodreadsExportError, match=r"\.csv, row 3: expected \d+ fields, found 2\.$"
    ):
        GoodreadsCsvExport().read(path)


def test_a_file_that_is_not_there_is_reported(tmp_path):
    with pytest.raises(
        GoodreadsExportError, match=r"missing\.csv: No such file or directory\.$"
    ):
        GoodreadsCsvExport().read(tmp_path / "missing.csv")


def test_a_file_that_is_not_text_is_reported(tmp_path):
    path = tmp_path / "book.epub"
    path.write_bytes(b"PK\x03\x04\xff\xfe")

    with pytest.raises(GoodreadsExportError, match=r"book\.epub: .*codec"):
        GoodreadsCsvExport().read(path)
