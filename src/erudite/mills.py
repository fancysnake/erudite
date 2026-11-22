"""Business logic: services over the protocols in pacts."""

from typing import TYPE_CHECKING, override

from erudite.pacts import ImportSummaryDTO, LibraryServiceProtocol

if TYPE_CHECKING:
    from pathlib import Path

    from erudite.pacts import BookRepositoryProtocol, GoodreadsExportProtocol


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
    def import_goodreads(self, path: Path) -> ImportSummaryDTO:
        # A book already in the library is left alone: its status and every
        # edit made in the app belong to the user.
        exported = {book["goodreads_id"]: book for book in self._goodreads.read(path)}
        known = self._books.goodreads_ids()
        new = [book for key, book in exported.items() if key not in known]
        self._books.create_from_goodreads(new)
        return ImportSummaryDTO(created=len(new), skipped=len(exported) - len(new))
