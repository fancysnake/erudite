"""Repositories: the adapter's public surface, speaking DTOs and write dicts."""

from pathlib import Path
from typing import override

from django.db import transaction

from erudite.links.db.django.models import (
    Author,
    Book,
    BookAuthor,
    IgnoredExtension,
    RawBook,
)
from erudite.pacts import BookRepositoryProtocol, BookSource, RawBookData

# What a raw book holds that the book made for it does not copy.
_RAW_ONLY = {"source", "key", "path", "authors"}


class BookRepository(BookRepositoryProtocol):
    @override
    def count(self) -> int:
        return Book.objects.count()

    @override
    def keys(self, source: BookSource) -> set[str]:
        return set(RawBook.objects.filter(source=source).values_list("key", flat=True))

    @override
    def file_paths(self) -> dict[str, Path]:
        rows = RawBook.objects.filter(source=BookSource.FILE)
        return {key: Path(path) for key, path in rows.values_list("key", "path")}

    @override
    def create(self, books: list[RawBookData]) -> None:
        # A book may name one author twice; dict keys keep the first place.
        names = [list(dict.fromkeys(book["authors"])) for book in books]
        with transaction.atomic():
            Author.objects.bulk_create(
                (Author(name=name) for name in {n for group in names for n in group}),
                ignore_conflicts=True,
            )
            authors = {author.name: author for author in Author.objects.all()}
            created = Book.objects.bulk_create(
                Book(**{k: v for k, v in book.items() if k not in _RAW_ONLY})
                for book in books
            )
            BookAuthor.objects.bulk_create(
                BookAuthor(book=book, author=authors[name], position=position)
                for book, group in zip(created, names, strict=True)
                for position, name in enumerate(group)
            )
            RawBook.objects.bulk_create(
                RawBook(**raw | {"path": str(raw.get("path", ""))}, book=book)
                for book, raw in zip(created, books, strict=True)
            )

    @override
    def move_file(self, content_hash: str, path: Path) -> None:
        RawBook.objects.filter(source=BookSource.FILE, key=content_hash).update(
            path=str(path)
        )

    @override
    def ignored_extensions(self) -> set[str]:
        return set(IgnoredExtension.objects.values_list("extension", flat=True))
