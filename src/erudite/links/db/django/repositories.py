"""Repositories: the adapter's public surface, speaking DTOs and write dicts."""

from pathlib import Path
from typing import override

from django.db import transaction

from erudite.links.db.django.models import Author, Book, BookAuthor, BookFile
from erudite.pacts import (
    BookFileData,
    BookFileRepositoryProtocol,
    BookRepositoryProtocol,
    GoodreadsBookData,
)


class BookRepository(BookRepositoryProtocol):
    @override
    def count(self) -> int:
        return Book.objects.count()

    @override
    def goodreads_ids(self) -> set[int]:
        ids = Book.objects.values_list("goodreads_id", flat=True)
        return {key for key in ids if key is not None}

    @override
    def create_from_goodreads(self, books: list[GoodreadsBookData]) -> None:
        # A book may name one author twice; dict keys keep the first place.
        names = [list(dict.fromkeys(book["authors"])) for book in books]
        with transaction.atomic():
            Author.objects.bulk_create(
                (Author(name=name) for name in {n for group in names for n in group}),
                ignore_conflicts=True,
            )
            authors = {author.name: author for author in Author.objects.all()}
            created = Book.objects.bulk_create(
                Book(**{k: v for k, v in book.items() if k != "authors"})
                for book in books
            )
            BookAuthor.objects.bulk_create(
                BookAuthor(book=book, author=authors[name], position=position)
                for book, group in zip(created, names, strict=True)
                for position, name in enumerate(group)
            )


class BookFileRepository(BookFileRepositoryProtocol):
    @override
    def paths(self) -> dict[str, Path]:
        rows = BookFile.objects.values_list("content_hash", "path")
        return {content_hash: Path(path) for content_hash, path in rows}

    @override
    def create(self, files: list[BookFileData]) -> None:
        with transaction.atomic():
            BookFile.objects.bulk_create(
                BookFile(**file | {"path": str(file["path"])}) for file in files
            )

    @override
    def move(self, content_hash: str, path: Path) -> None:
        BookFile.objects.filter(content_hash=content_hash).update(path=str(path))
