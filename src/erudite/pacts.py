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


class NotFoundError(Exception):
    """The library does not hold what was asked for."""


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


# The fields of a book that a classification may propose, by name: `title`,
# `isbn10`, `isbn13`, `series`, `series_position`, and `authors` as a list.
type BookFieldsData = dict[str, str | list[str]]


class ProposalOutcome(StrEnum):
    FILLED = "filled"
    WAITING = "waiting"
    SKIPPED = "skipped"


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


class DecisionRepositoryProtocol(Protocol):
    def exists(self, book_id: int) -> bool:
        """Say if a decision waits for the book."""

    def book_fields(self, book_id: int) -> BookFieldsData:
        """Return every proposable field of the book; empty where it holds none.

        `NotFoundError` if the library has no such book.
        """

    def fill(self, book_id: int, values: BookFieldsData) -> None:
        """Write `values` to the book."""

    def create(self, book_id: int, proposed: BookFieldsData) -> None:
        """Store `proposed` as the decision that waits for the book."""

    def accept(self, book_id: int, names: set[str]) -> None:
        """Write the proposed fields in `names` to the book; remove the decision."""


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


class ClassificationServiceProtocol(Protocol):
    def propose(self, book_id: int, proposal: BookFieldsData) -> ProposalOutcome:
        """Fill the book from `proposal`, or hold the proposal as a decision.

        Only values that differ from the book count. They are filled when the
        book holds none of their fields; otherwise nothing is filled and they
        wait as a decision. A book with a waiting decision is skipped.
        """


class ServicesProtocol(Protocol):
    """The namespace gates reach services through."""

    @property
    def library(self) -> LibraryServiceProtocol: ...

    @property
    def book_files(self) -> BookFilesServiceProtocol: ...

    @property
    def classification(self) -> ClassificationServiceProtocol: ...


class RootRequestProtocol(Protocol):
    """The slice of the framework request the middleware touches."""

    services: ServicesProtocol
