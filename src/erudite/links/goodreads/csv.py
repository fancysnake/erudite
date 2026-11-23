"""The Goodreads library export, a CSV file the user downloads by hand."""

import csv
import datetime as dt
import re
from typing import TYPE_CHECKING, override

from erudite.pacts import (
    BookSource,
    GoodreadsExportError,
    GoodreadsExportProtocol,
    RawBookData,
    ReadingStatus,
)

if TYPE_CHECKING:
    from pathlib import Path

# "Mort (Discworld, #4)"; of several series, the first one counts.
_SERIES = re.compile(
    r"^(?P<title>.+?)\s*"
    r"\((?P<series>[^();]+?),?\s+#(?P<position>[\d.]+(?:-[\d.]+)?)(?:;[^()]*)?\)$"
)
_COLUMNS = (
    "Book Id",
    "Title",
    "Author",
    "Additional Authors",
    "ISBN",
    "ISBN13",
    "My Rating",
    "Bookshelves",
    "Date Added",
    "Date Read",
    "Exclusive Shelf",
)
# The shelves that name a status, strongest first. Every other shelf is a topic
# and is dropped.
_STATUS_BY_SHELF = {
    "did-not-finish": ReadingStatus.DID_NOT_FINISH,
    "read": ReadingStatus.READ,
    "currently-reading": ReadingStatus.READING,
    "must-read": ReadingStatus.MUST_READ,
}


def _squeeze(value: str) -> str:
    """Goodreads pads names with runs of spaces: `Klaus  Brenner`."""
    return " ".join(value.split())


def _split(value: str) -> list[str]:
    return [name for part in value.split(",") if (name := _squeeze(part))]


def _rating(value: str) -> int | None:
    """Read `5` and `5.0` alike; `0` means the book has no rating."""
    rating = float(value)
    if not rating.is_integer():
        msg = f"invalid rating: {value!r}"
        raise ValueError(msg)
    return int(rating) or None


def _isbn(value: str) -> str:
    """Unwrap the spreadsheet formula the export hides ISBNs in: `="0552134627"`."""
    return re.sub(r"[^0-9Xx]", "", value).upper()


def _date(value: str) -> dt.date | None:
    return dt.date.strptime(value, "%Y/%m/%d") if value else None


def _status(row: dict[str, str]) -> ReadingStatus:
    shelves = {row["Exclusive Shelf"], *_split(row["Bookshelves"])}
    return next(
        (status for shelf, status in _STATUS_BY_SHELF.items() if shelf in shelves),
        ReadingStatus.TO_READ,
    )


def _book(row: dict[str, str]) -> RawBookData:
    title = _squeeze(row["Title"])
    series = _SERIES.match(title)
    return RawBookData(
        source=BookSource.GOODREADS,
        key=str(int(row["Book Id"])),
        title=series["title"] if series else title,
        authors=[*_split(row["Author"]), *_split(row["Additional Authors"])],
        isbn10=_isbn(row["ISBN"]),
        isbn13=_isbn(row["ISBN13"]),
        series=series["series"] if series else "",
        series_position=series["position"] if series else "",
        rating=_rating(row["My Rating"]),
        date_added=_date(row["Date Added"]),
        date_read=_date(row["Date Read"]),
        status=_status(row),
    )


def _rows(path: Path) -> list[list[str]]:
    # utf-8-sig: a spreadsheet that saved the file again may have added a BOM.
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.reader(file))


class GoodreadsCsvExport(GoodreadsExportProtocol):
    @override
    def read(self, path: Path) -> list[RawBookData]:
        try:
            table = _rows(path)
        except OSError as exc:
            msg = f"{path}: {exc.strerror}."
            raise GoodreadsExportError(msg) from exc
        except (UnicodeDecodeError, csv.Error) as exc:
            msg = f"{path}: {exc}"
            raise GoodreadsExportError(msg) from exc
        header, rows = (table[0] if table else []), table[1:]
        for column in _COLUMNS:
            if column not in header:
                msg = f"{path}: no {column!r} column."
                raise GoodreadsExportError(msg)
        books: list[RawBookData] = []
        # Rows, not lines: a review may span several lines. The header is row 1.
        for number, row in enumerate(rows, start=2):
            if len(row) != len(header):
                msg = (
                    f"{path}, row {number}: expected {len(header)} fields, "
                    f"found {len(row)}."
                )
                raise GoodreadsExportError(msg)
            try:
                books.append(_book(dict(zip(header, row, strict=True))))
            except ValueError as exc:
                msg = f"{path}, row {number}: {exc}"
                raise GoodreadsExportError(msg) from exc
        return books
