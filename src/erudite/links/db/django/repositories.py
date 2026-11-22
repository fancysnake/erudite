"""Repositories: the adapter's public surface, speaking DTOs and write dicts."""

from typing import override

from erudite.links.db.django.models import Book
from erudite.pacts import BookRepositoryProtocol, GoodreadsBookData


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
        Book.objects.bulk_create(Book(**book) for book in books)
