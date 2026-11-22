"""Contracts between layers: protocols, DTOs, errors."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, TypedDict

if TYPE_CHECKING:
    import datetime as dt
    from pathlib import Path


class ReadingStatus(StrEnum):
    TO_READ = "to_read"
    MUST_READ = "must_read"
    READING = "reading"
    READ = "read"
    DID_NOT_FINISH = "did_not_finish"


class GoodreadsExportError(Exception):
    """The file cannot be read as a Goodreads library export."""


class GoodreadsBookData(TypedDict):
    """One book of a Goodreads export; `status` is only its first value in the app."""

    goodreads_id: int
    title: str
    authors: list[str]
    isbn10: str
    isbn13: str
    series: str
    series_position: str
    rating: int | None
    date_added: dt.date | None
    date_read: dt.date | None
    status: ReadingStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class ImportSummaryDTO:
    created: int
    skipped: int


class GoodreadsExportProtocol(Protocol):
    def read(self, path: Path) -> list[GoodreadsBookData]:
        """Every book in the export at `path`; `GoodreadsExportError` if unreadable."""


class BookRepositoryProtocol(Protocol):
    def count(self) -> int: ...

    def goodreads_ids(self) -> set[int]:
        """Return the Goodreads id of every book that has one."""

    def create_from_goodreads(self, books: list[GoodreadsBookData]) -> None:
        """Add all of `books`, or none of them."""


class LibraryServiceProtocol(Protocol):
    def book_count(self) -> int: ...

    def import_goodreads(self, path: Path) -> ImportSummaryDTO:
        """Add the books of the export at `path` that the library does not hold."""


class ServicesProtocol(Protocol):
    """The namespace gates reach services through."""

    @property
    def library(self) -> LibraryServiceProtocol: ...


class RootRequestProtocol(Protocol):
    """The slice of the framework request the middleware touches."""

    services: ServicesProtocol
