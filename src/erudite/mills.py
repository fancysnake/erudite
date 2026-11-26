"""Business logic: services over the protocols in pacts."""

from typing import TYPE_CHECKING, override

from erudite.pacts import (
    BOOK_FIELDS,
    BookFieldsData,
    BookFilesServiceProtocol,
    BookSource,
    CandidatesDTO,
    ClassificationServiceProtocol,
    LibraryServiceProtocol,
    NotFoundError,
    OpenLibraryError,
    PickedWorkData,
    ProposalOutcome,
    RawBookData,
    SyncSummaryDTO,
    WorkServiceProtocol,
)
from erudite.specs import WORK_ID

if TYPE_CHECKING:
    from pathlib import Path

    from erudite.pacts import (
        BookRepositoryProtocol,
        DecisionRepositoryProtocol,
        DiskBookFilesProtocol,
        GoodreadsExportProtocol,
        IgnoredExtensionsProtocol,
        OpenLibraryProtocol,
        TransactionProtocol,
        WorkDTO,
    )


class LibraryService(LibraryServiceProtocol):
    def __init__(
        self, *, books: BookRepositoryProtocol, goodreads: GoodreadsExportProtocol
    ) -> None:
        self._books = books
        self._goodreads = goodreads

    @override
    def book_count(self) -> int:
        return self._books.count()

    @override
    def import_goodreads(self, path: Path) -> SyncSummaryDTO:
        # A book already in the library is left alone: its status and every
        # edit made in the app belong to the user.
        exported = {book["key"]: book for book in self._goodreads.read(path)}
        known = self._books.keys(BookSource.GOODREADS)
        new = [book for key, book in exported.items() if key not in known]
        self._books.create(new)
        return SyncSummaryDTO(created=len(new), skipped=len(exported) - len(new))


class BookFilesService(BookFilesServiceProtocol):
    def __init__(
        self,
        *,
        books: BookRepositoryProtocol,
        ignored: IgnoredExtensionsProtocol,
        disk: DiskBookFilesProtocol,
    ) -> None:
        self._books = books
        self._ignored = ignored
        self._disk = disk

    @override
    def scan(self, directory: Path) -> SyncSummaryDTO:
        found = self._disk.find(directory)
        known = self._books.file_paths()
        ignored = self._ignored.extensions()
        unknown = {h: p for h, p in found.items() if h not in known}
        new = [
            self._raw_book(content_hash, path)
            for content_hash, path in unknown.items()
            if path.suffix.lower().removeprefix(".") not in ignored
        ]
        stored = found.keys() & known.keys()
        for content_hash in stored:
            # A copy at a second path leaves the stored path alone.
            if known[content_hash] != found[content_hash] and not self._disk.exists(
                known[content_hash]
            ):
                self._books.move_file(content_hash, found[content_hash])
        self._books.create(new)
        return SyncSummaryDTO(
            created=len(new), skipped=len(stored), ignored=len(unknown) - len(new)
        )

    def _raw_book(self, content_hash: str, path: Path) -> RawBookData:
        metadata = self._disk.read(path)
        return RawBookData(
            source=BookSource.FILE,
            key=content_hash,
            title=metadata["title"] or path.stem,
            authors=metadata["authors"],
            path=path,
            isbn10=metadata["isbn10"],
            isbn13=metadata["isbn13"],
        )


class ClassificationService(ClassificationServiceProtocol):
    def __init__(
        self, *, books: BookRepositoryProtocol, decisions: DecisionRepositoryProtocol
    ) -> None:
        self._books = books
        self._decisions = decisions

    @override
    def propose(self, book_id: int, proposal: BookFieldsData) -> ProposalOutcome:
        if self._decisions.exists(book_id):
            return ProposalOutcome.ALREADY_WAITING
        held = self._books.fields(book_id)
        new = proposal.copy()
        if "authors" in new:
            # Trimmed, each name once in first place, none empty.
            names = (name.strip() for name in new["authors"])
            new["authors"] = list({name: None for name in names if name})
        for name in BOOK_FIELDS:
            # An empty value proposes nothing; a value the book holds changes nothing.
            if name in new and (not new[name] or new[name] == held.get(name)):
                del new[name]
        if not new:
            return ProposalOutcome.NOTHING_NEW
        if any(held.get(name) for name in new):
            self._decisions.create(book_id, new)
            return ProposalOutcome.WAITING
        self._books.fill(book_id, new)
        return ProposalOutcome.FILLED


def _first_visit(held: BookFieldsData) -> tuple[str, list[str]]:
    """Return the query a page shows before the user types one, and its searches.

    The searches are the ISBN, if the book holds one, then the query.
    """
    query = " ".join([held.get("title", ""), *held.get("authors", [])]).strip()
    isbn = held.get("isbn13") or held.get("isbn10")
    return query, [f"isbn:{isbn}", query] if isbn else [query]


class WorkService(WorkServiceProtocol):
    def __init__(
        self,
        *,
        books: BookRepositoryProtocol,
        open_library: OpenLibraryProtocol,
        transaction: TransactionProtocol,
    ) -> None:
        self._books = books
        self._open_library = open_library
        self._transaction = transaction

    @override
    def candidates(self, book_id: int, query: str | None = None) -> CandidatesDTO:
        held = self._books.fields(book_id)
        # `None` is a first visit; a blank query is one the user sent.
        if query is None:
            query, searches = _first_visit(held)
        else:
            query = query.strip()
            searches = [query]
        # By work id: a work two searches find stays in its first place.
        works: dict[str, WorkDTO] = {}
        failure = ""
        for search in [text for text in searches if text]:
            try:
                found = self._open_library.search(search)
            except OpenLibraryError as exc:
                failure = str(exc)
                break
            for work in found:
                works.setdefault(work.work_id, work)
        return CandidatesDTO(
            book_id=book_id,
            title=held.get("title", ""),
            authors=tuple(held.get("authors", [])),
            query=query,
            works=tuple(works.values()),
            failure=failure,
        )

    @override
    def pick(self, book_id: int, work_id: str) -> None:
        if not WORK_ID.fullmatch(work_id):
            msg = f"{work_id!r} is not an Open Library work id."
            raise NotFoundError(msg)
        # Fails here for a book the library lacks, before any request is sent.
        self._books.fields(book_id)
        if not (found := self._open_library.search(f"key:/works/{work_id}")):
            msg = f"Open Library has no work {work_id}."
            raise NotFoundError(msg)
        work = found[0]
        cover = self._open_library.cover(work.cover_id) if work.cover_id else None
        picked = PickedWorkData(
            work_id=work_id,
            description=self._open_library.description(work_id),
            cover=cover,
        )
        # An empty title or no author changes nothing.
        values = BookFieldsData()
        if work.title:
            values["title"] = work.title
        if work.authors:
            values["authors"] = list(work.authors)
        with self._transaction.atomic():
            self._books.set_work(book_id, picked)
            self._books.fill(book_id, values)
