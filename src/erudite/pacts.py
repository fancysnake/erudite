"""Contracts between layers: protocols, DTOs, errors."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, NotRequired, Protocol, TypedDict

if TYPE_CHECKING:
    import datetime as dt
    from contextlib import AbstractContextManager
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


class OpenLibraryError(Exception):
    """Open Library gave no answer, or one that cannot be read."""


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


class BookFieldsData(TypedDict, total=False):
    """The fields of a book that a classification may propose; empty is unknown."""

    title: str
    authors: list[str]
    isbn10: str
    isbn13: str
    series: str
    series_position: str


type BookField = Literal[
    "title", "authors", "isbn10", "isbn13", "series", "series_position"
]
# The keys of `BookFieldsData`, typed so a loop over them may index it.
BOOK_FIELDS: tuple[BookField, ...] = (
    "title",
    "authors",
    "isbn10",
    "isbn13",
    "series",
    "series_position",
)


class ProposalOutcome(StrEnum):
    FILLED = "filled"
    WAITING = "waiting"
    ALREADY_WAITING = "already_waiting"
    NOTHING_NEW = "nothing_new"


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


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkDTO:
    """A work at Open Library: one for all its editions. `work_id` is like OL45804W."""

    work_id: str
    title: str
    authors: tuple[str, ...]
    first_year: int | None
    cover_id: int | None
    # The address of a medium cover image for a page to show; empty without one.
    cover_url: str
    edition_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidatesDTO:
    """A book as the library holds it, and the works a search found for it.

    `failure` says why a search failed; `works` then holds what was found before.
    """

    book_id: int
    title: str
    authors: tuple[str, ...]
    query: str
    works: tuple[WorkDTO, ...]
    failure: str = ""


class PickedWorkData(TypedDict):
    """What the picked work gives its book beside `BookFieldsData`; empty is none."""

    work_id: str
    description: str
    cover: bytes | None


class OpenLibraryProtocol(Protocol):
    """Every method raises `OpenLibraryError` when Open Library cannot be read."""

    def search(self, query: str) -> list[WorkDTO]:
        """Return the first works Open Library finds for `query`, best first."""

    def description(self, work_id: str) -> str:
        """Return the description of the work; empty if it has none."""

    def cover(self, cover_id: int) -> bytes:
        """Return the cover image, a JPEG."""


class TransactionProtocol(Protocol):
    def atomic(self) -> AbstractContextManager[None]:
        """Keep every write made inside the block, or none of them."""


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

    def fields(self, book_id: int) -> BookFieldsData:
        """Return every proposable field of the book; empty where it holds none.

        `NotFoundError` if the library has no such book.
        """

    def fill(self, book_id: int, values: BookFieldsData) -> None:
        """Write `values` to the book."""

    def set_work(self, book_id: int, work: PickedWorkData) -> None:
        """Write the picked work to the book; an empty value changes nothing.

        `NotFoundError` if the library has no such book.
        """


class DecisionRepositoryProtocol(Protocol):
    def exists(self, book_id: int) -> bool:
        """Say if a decision waits for the book."""

    def create(self, book_id: int, proposed: BookFieldsData) -> None:
        """Store `proposed` as the decision that waits for the book."""


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
        wait as a decision. A book with a waiting decision is left alone.
        """


class WorkServiceProtocol(Protocol):
    def candidates(self, book_id: int, query: str | None = None) -> CandidatesDTO:
        """Search Open Library for the works the book may be.

        Without `query` the search is for the title and authors of the book, and
        the work of an ISBN the book holds comes first. `NotFoundError` if the
        library has no such book; `OpenLibraryError` if the search fails.
        """

    def pick(self, book_id: int, work_id: str) -> None:
        """Give the book the title, authors, description and cover of the work.

        `NotFoundError` if the library has no such book or Open Library no such
        work; `OpenLibraryError` if the work cannot be read.
        """


class ServicesProtocol(Protocol):
    """The namespace gates reach services through."""

    @property
    def library(self) -> LibraryServiceProtocol: ...

    @property
    def book_files(self) -> BookFilesServiceProtocol: ...

    @property
    def classification(self) -> ClassificationServiceProtocol: ...

    @property
    def works(self) -> WorkServiceProtocol: ...


class RootRequestProtocol(Protocol):
    """The slice of the framework request the middleware touches."""

    services: ServicesProtocol
