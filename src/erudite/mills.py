"""Business logic: services over the protocols in pacts."""

from typing import TYPE_CHECKING, override

from erudite.pacts import (
    BOOK_FIELDS,
    BookFilesServiceProtocol,
    BookSource,
    CandidatesDTO,
    ClassificationServiceProtocol,
    LibraryServiceProtocol,
    NotFoundError,
    PickedWorkData,
    ProposalOutcome,
    RawBookData,
    SyncSummaryDTO,
    WorkServiceProtocol,
)

if TYPE_CHECKING:
    from pathlib import Path

    from erudite.pacts import (
        BookFieldsData,
        BookRepositoryProtocol,
        DecisionRepositoryProtocol,
        DiskBookFilesProtocol,
        GoodreadsExportProtocol,
        IgnoredExtensionsProtocol,
        OpenLibraryProtocol,
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


class WorkService(WorkServiceProtocol):
    def __init__(
        self, *, books: BookRepositoryProtocol, open_library: OpenLibraryProtocol
    ) -> None:
        self._books = books
        self._open_library = open_library

    @override
    def candidates(self, book_id: int, query: str | None = None) -> CandidatesDTO:
        held = self._books.fields(book_id)
        title, authors = held.get("title", ""), held.get("authors", [])
        works: list[WorkDTO] = []
        if query is None:
            query = " ".join([title, *authors])
            if isbn := held.get("isbn13") or held.get("isbn10"):
                works = self._open_library.search(f"isbn:{isbn}")
        if query := query.strip():
            known = {work.work_id for work in works}
            found = self._open_library.search(query)
            works += [work for work in found if work.work_id not in known]
        return CandidatesDTO(
            book_id=book_id,
            title=title,
            authors=tuple(authors),
            query=query,
            works=tuple(works),
        )

    @override
    def pick(self, book_id: int, work_id: str) -> None:
        # Fails here for a book the library lacks, before any request is sent.
        self._books.fields(book_id)
        if not (found := self._open_library.search(f"key:/works/{work_id}")):
            msg = f"Open Library has no work {work_id}."
            raise NotFoundError(msg)
        work = found[0]
        cover = self._open_library.cover(work.cover_id) if work.cover_id else None
        self._books.set_work(
            book_id,
            PickedWorkData(
                work_id=work_id,
                title=work.title,
                authors=list(work.authors),
                description=self._open_library.description(work_id),
                cover=cover,
            ),
        )
