"""Business logic: services over the protocols in pacts."""

from typing import TYPE_CHECKING, override

from erudite.pacts import (
    BookFilesServiceProtocol,
    BookSource,
    LibraryServiceProtocol,
    RawBookData,
    SyncSummaryDTO,
)

if TYPE_CHECKING:
    from pathlib import Path

    from erudite.pacts import (
        BookRepositoryProtocol,
        DiskBookFilesProtocol,
        GoodreadsExportProtocol,
    )

_ISBN13_LENGTH = 13


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
        self, *, books: BookRepositoryProtocol, disk: DiskBookFilesProtocol
    ) -> None:
        self._books = books
        self._disk = disk

    @override
    def scan(self, directory: Path) -> SyncSummaryDTO:
        found = self._disk.find(directory)
        known = self._books.file_paths()
        ignored = self._books.ignored_extensions()
        new = [
            self._raw_book(content_hash, path)
            for content_hash, path in found.items()
            if content_hash not in known
            and path.suffix.lower().removeprefix(".") not in ignored
        ]
        stored = found.keys() & known.keys()
        for content_hash in stored:
            # A copy at a second path leaves the stored path alone.
            if known[content_hash] != found[content_hash] and not self._disk.exists(
                known[content_hash]
            ):
                self._books.move_file(content_hash, found[content_hash])
        self._books.create(new)
        return SyncSummaryDTO(created=len(new), skipped=len(stored))

    def _raw_book(self, content_hash: str, path: Path) -> RawBookData:
        metadata = self._disk.read(path)
        book = RawBookData(
            source=BookSource.FILE,
            key=content_hash,
            title=metadata["title"] or path.stem,
            authors=metadata["authors"],
            path=path,
        )
        if len(isbn := metadata["isbn"]) == _ISBN13_LENGTH:
            book["isbn13"] = isbn
        elif isbn:
            book["isbn10"] = isbn
        return book
