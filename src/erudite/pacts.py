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


class FileScanError(Exception):
    """The directory cannot be scanned for book files."""


class BookFileMetadata(TypedDict):
    """What a book file says about itself; empty where it says nothing."""

    title: str
    authors: list[str]
    isbn: str


class BookFileData(BookFileMetadata):
    path: Path
    content_hash: str
    ignored: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class SyncSummaryDTO:
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


class DiskBookFilesProtocol(Protocol):
    def find(self, directory: Path) -> dict[str, Path]:
        """Map content hash to path for every file under `directory`.

        Of files with equal content, the first path in sort order stays.
        `FileScanError` if the directory or a file cannot be read.
        """

    def read(self, path: Path) -> BookFileMetadata:
        """Read the metadata embedded in an EPUB or PDF; never its pages.

        A damaged file, or one of another format, gives empty metadata.
        `FileScanError` if the file cannot be opened or read.
        """

    def exists(self, path: Path) -> bool: ...


class BookFileRepositoryProtocol(Protocol):
    def paths(self) -> dict[str, Path]:
        """Map content hash to path for every stored file."""

    def create(self, files: list[BookFileData]) -> None:
        """Add all of `files`, or none of them."""

    def move(self, content_hash: str, path: Path) -> None:
        """Point the stored file with this content at `path`."""

    def ignored_extensions(self) -> set[str]:
        """Return the extensions the user ignores: lowercase, without the dot."""


class LibraryServiceProtocol(Protocol):
    def book_count(self) -> int: ...

    def import_goodreads(self, path: Path) -> SyncSummaryDTO:
        """Add the books of the export at `path` that the library does not hold."""


class BookFilesServiceProtocol(Protocol):
    def scan(self, directory: Path) -> SyncSummaryDTO:
        """Add the files under `directory` that are not stored.

        A new file with an ignored extension is stored as ignored; a stored file
        keeps what the user chose for it. A stored file found at a new path,
        while its old path is gone, gets the new path. `skipped` counts every
        file that was already stored, moved ones included.
        """


class ServicesProtocol(Protocol):
    """The namespace gates reach services through."""

    @property
    def library(self) -> LibraryServiceProtocol: ...

    @property
    def book_files(self) -> BookFilesServiceProtocol: ...


class RootRequestProtocol(Protocol):
    """The slice of the framework request the middleware touches."""

    services: ServicesProtocol
