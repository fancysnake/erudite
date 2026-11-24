"""Repositories: the adapter's public surface, speaking DTOs and write dicts."""

from pathlib import Path
from typing import override

from django.db import transaction
from django.forms import fields_for_model

from erudite.links.db.django.models import (
    Author,
    Book,
    BookAuthor,
    BookDetails,
    Decision,
    IgnoredExtension,
    RawBook,
)
from erudite.pacts import (
    BookFieldsData,
    BookRepositoryProtocol,
    BookSource,
    DecisionRepositoryProtocol,
    IgnoredExtensionsProtocol,
    NotFoundError,
    RawBookData,
)

# What a raw book gives to the book made for it.
_BOOK_FIELDS = set(fields_for_model(BookDetails))


def _credit(names: dict[int, list[str]]) -> None:
    """Link each book to its authors in order, each once; make missing authors."""
    # A book may name one author twice; dict keys keep the first place.
    groups = {book_id: dict.fromkeys(group) for book_id, group in names.items()}
    Author.objects.bulk_create(
        (Author(name=name) for name in {n for group in groups.values() for n in group}),
        ignore_conflicts=True,
    )
    authors = dict(Author.objects.values_list("name", "pk"))
    BookAuthor.objects.bulk_create(
        BookAuthor(book_id=book_id, author_id=authors[name], position=position)
        for book_id, group in groups.items()
        for position, name in enumerate(group)
    )


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
        with transaction.atomic():
            created = Book.objects.bulk_create(
                Book(**{k: v for k, v in book.items() if k in _BOOK_FIELDS})
                for book in books
            )
            _credit(
                {
                    book.pk: raw["authors"]
                    for book, raw in zip(created, books, strict=True)
                }
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
    def fields(self, book_id: int) -> BookFieldsData:
        try:
            book = Book.objects.get(pk=book_id)
        except Book.DoesNotExist as exc:
            msg = f"The library has no book {book_id}."
            raise NotFoundError(msg) from exc
        return BookFieldsData(
            title=book.title,
            authors=[str(c) for c in book.credits.select_related("author")],
            isbn10=book.isbn10,
            isbn13=book.isbn13,
            series=book.series,
            series_position=book.series_position,
        )

    @override
    def fill(self, book_id: int, values: BookFieldsData) -> None:
        with transaction.atomic():
            Book.objects.filter(pk=book_id).update(
                **{name: value for name, value in values.items() if name != "authors"}
            )
            if "authors" in values:
                BookAuthor.objects.filter(book_id=book_id).delete()
                _credit({book_id: values["authors"]})


class DecisionRepository(DecisionRepositoryProtocol):
    @override
    def exists(self, book_id: int) -> bool:
        return Decision.objects.filter(book_id=book_id).exists()

    @override
    def create(self, book_id: int, proposed: BookFieldsData) -> None:
        Decision.objects.create(book_id=book_id, proposed=proposed)


class IgnoredExtensions(IgnoredExtensionsProtocol):
    @override
    def extensions(self) -> set[str]:
        return set(IgnoredExtension.objects.values_list("extension", flat=True))
