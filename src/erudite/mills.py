"""Business logic: services over the protocols in pacts."""

from typing import TYPE_CHECKING, override

from erudite.pacts import BookFileData, ImportSummaryDTO, LibraryServiceProtocol

if TYPE_CHECKING:
    from pathlib import Path

    from erudite.pacts import (
        BookFileRepositoryProtocol,
        BookFilesProtocol,
        BookRepositoryProtocol,
        GoodreadsExportProtocol,
    )


class LibraryService(LibraryServiceProtocol):
    def __init__(
        self,
        *,
        books: BookRepositoryProtocol,
        goodreads: GoodreadsExportProtocol,
        files: BookFileRepositoryProtocol,
        disk: BookFilesProtocol,
    ) -> None:
        self._books = books
        self._goodreads = goodreads
        self._files = files
        self._disk = disk

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

    @override
    def scan_files(self, directory: Path) -> ImportSummaryDTO:
        found = self._disk.find(directory)
        known = self._files.paths()
        new: list[BookFileData] = []
        for content_hash, path in found.items():
            if content_hash not in known:
                metadata = self._disk.read(path)
                new.append(
                    BookFileData(
                        path=path,
                        content_hash=content_hash,
                        title=metadata["title"] or path.stem,
                        authors=metadata["authors"],
                        isbn=metadata["isbn"],
                    )
                )
            # A copy at a second path leaves the stored path alone.
            elif known[content_hash] != path and not self._disk.exists(
                known[content_hash]
            ):
                self._files.move(content_hash, path)
        self._files.create(new)
        return ImportSummaryDTO(created=len(new), skipped=len(found) - len(new))
