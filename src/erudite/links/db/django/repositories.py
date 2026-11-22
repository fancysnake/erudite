"""Repositories: the adapter's public surface, speaking DTOs and write dicts."""

from typing import override

from django.db import transaction

from erudite.links.db.django.models import Author, Book, BookAuthor
from erudite.pacts import BookRepositoryProtocol, GoodreadsBookData


class BookRepository(BookRepositoryProtocol):
    @override
    def count(self) -> int:
        return Book.objects.count()

    @override
    def goodreads_ids(self) -> set[int]:
        ids = Book.objects.filter(goodreads_id__isnull=False).values_list(
            "goodreads_id", flat=True
        )
        # The filter leaves no NULL; the check only narrows the nullable column type.
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
