"""Contracts between layers: protocols, DTOs, errors."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, NotRequired, Protocol, TypedDict

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


class BookSource(StrEnum):
    GOODREADS = "goodreads"
    FILE = "file"


class RawBookData(TypedDict):
    """One book as a source gives it; a field the source does not have is left out.

    `key` is the name the source has for the book: a Goodreads id, the content
    hash of a file. `status` is only the first value of the book in the app.
    """

    source: BookSource
    key: str
    title: str
    authors: list[str]
    path: NotRequired[Path]
    isbn10: NotRequired[str]
    isbn13: NotRequired[str]
    series: NotRequired[str]
    series_position: NotRequired[str]
    rating: NotRequired[int | None]
    date_added: NotRequired[dt.date | None]
    date_read: NotRequired[dt.date | None]
    status: NotRequired[ReadingStatus]


class FileScanError(Exception):
    """The directory cannot be scanned for book files."""


class BookFileMetadata(TypedDict):
    """What a book file says about itself; empty where it says nothing."""

    title: str
    authors: list[str]
    isbn10: str
    isbn13: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SyncSummaryDTO:
    created: int
    skipped: int
    ignored: int = 0


class GoodreadsExportProtocol(Protocol):
    def read(self, path: Path) -> list[RawBookData]:
        """Every book in the export at `path`; `GoodreadsExportError` if unreadable."""


class BookRepositoryProtocol(Protocol):
    def count(self) -> int: ...

    def keys(self, source: BookSource) -> set[str]:
        """Return the key of every raw book that `source` gave."""

    def file_paths(self) -> dict[str, Path]:
        """Map content hash to path for every raw book that is a file."""

    def create(self, books: list[RawBookData]) -> None:
        """Add each of `books` as a raw book with a book of its own, or add none."""

    def move_file(self, content_hash: str, path: Path) -> None:
        """Point the raw book of the file with this content at `path`."""


class IgnoredExtensionsProtocol(Protocol):
    def extensions(self) -> set[str]:
        """Return the extensions the user ignores: lowercase, without the dot."""


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


class LibraryServiceProtocol(Protocol):
    def book_count(self) -> int: ...

    def import_goodreads(self, path: Path) -> SyncSummaryDTO:
        """Add the books of the export at `path` that the library does not hold."""


class BookFilesServiceProtocol(Protocol):
    def scan(self, directory: Path) -> SyncSummaryDTO:
        """Add each file under `directory` that is not stored, as a book.

        A new file with an ignored extension is left out and counted in
        `ignored`. A stored file found at a new path, while its old path is gone,
        gets the new path. `skipped` counts every file that was already stored,
        moved ones included.
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
