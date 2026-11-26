"""Business logic: services over the protocols in pacts."""

from typing import TYPE_CHECKING, override

from erudite.pacts import (
    BOOK_FIELDS,
    BookFilesServiceProtocol,
    BookSource,
    ClassificationServiceProtocol,
    LibraryServiceProtocol,
    ProposalOutcome,
    RawBookData,
    SyncSummaryDTO,
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
        if self._books.fill_empty(book_id, new):
            return ProposalOutcome.FILLED
        if self._decisions.create(book_id, new):
            return ProposalOutcome.WAITING
        return ProposalOutcome.ALREADY_WAITING
