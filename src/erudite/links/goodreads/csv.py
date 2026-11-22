"""The Goodreads library export, a CSV file the user downloads by hand."""

import csv
import datetime as dt
import re
from typing import TYPE_CHECKING, override

from erudite.pacts import (
    GoodreadsBookData,
    GoodreadsExportError,
    GoodreadsExportProtocol,
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
_STATUS_BY_SHELF = {
    "read": ReadingStatus.READ,
    "currently-reading": ReadingStatus.READING,
}


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _isbn(value: str) -> str:
    """Unwrap the spreadsheet formula the export hides ISBNs in: `="0552134627"`."""
    return re.sub(r"[^0-9Xx]", "", value).upper()


def _date(value: str) -> dt.date | None:
    return dt.date.strptime(value, "%Y/%m/%d") if value else None


def _book(row: dict[str, str]) -> GoodreadsBookData:
    title = row["Title"].strip()
    series = _SERIES.match(title)
    return GoodreadsBookData(
        goodreads_id=int(row["Book Id"]),
        title=series["title"] if series else title,
        authors=[*_split(row["Author"]), *_split(row["Additional Authors"])],
        isbn10=_isbn(row["ISBN"]),
        isbn13=_isbn(row["ISBN13"]),
        series=series["series"] if series else "",
        series_position=series["position"] if series else "",
        shelves=_split(row["Bookshelves"]),
        rating=int(row["My Rating"]) or None,
        date_added=_date(row["Date Added"]),
        date_read=_date(row["Date Read"]),
        # A shelf the app has no status for is still on the to-read side.
        status=_STATUS_BY_SHELF.get(row["Exclusive Shelf"], ReadingStatus.TO_READ),
    )


def _rows(path: Path) -> list[list[str]]:
    # utf-8-sig: a spreadsheet that saved the file again may have added a BOM.
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.reader(file))


class GoodreadsCsvExport(GoodreadsExportProtocol):
    @override
    def read(self, path: Path) -> list[GoodreadsBookData]:
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
        books: list[GoodreadsBookData] = []
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
