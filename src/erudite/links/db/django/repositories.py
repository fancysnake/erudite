"""Repositories: the adapter's public surface, speaking DTOs and write dicts."""

from pathlib import Path
from typing import override

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.forms import fields_for_model

from erudite.links.db.django.models import (
    Author,
    Book,
    BookAuthor,
    BookDetails,
    Decision,
    IgnoredExtension,
    RawBook,
    Sync,
)
from erudite.pacts import (
    BookDTO,
    BookFieldsData,
    BookRepositoryProtocol,
    BookSource,
    BookSummaryDTO,
    DecisionRepositoryProtocol,
    IgnoredExtensionsProtocol,
    NotFoundError,
    PickedWorkData,
    RawBookData,
    SyncRepositoryProtocol,
    SyncType,
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


def _book(book_id: int) -> Book:
    try:
        return Book.objects.get(pk=book_id)
    except Book.DoesNotExist as exc:
        msg = f"The library has no book {book_id}."
        raise NotFoundError(msg) from exc


def _summary(book: Book) -> BookSummaryDTO:
    return BookSummaryDTO(
        book_id=book.pk,
        title=book.title,
        authors=tuple(str(credit) for credit in book.credits.all()),
        series=book.series,
        series_position=book.series_position,
        status=str(book.get_status_display()),
    )


class BookRepository(BookRepositoryProtocol):
    @override
    def count(self) -> int:
        return Book.objects.count()

    @override
    def search(
        self,
        query: str,
        *,
        done: tuple[SyncType, ...] = (),
        todo: tuple[SyncType, ...] = (),
    ) -> list[BookSummaryDTO]:
        books = Book.objects.prefetch_related("credits__author")
        syncs = Sync.objects.filter(book=OuterRef("pk"))
        for sync in done:
            books = books.filter(Exists(syncs.filter(sync_type=sync)))
        for sync in todo:
            books = books.filter(~Exists(syncs.filter(sync_type=sync)))
        if query:
            # A book with two authors that match is still one book.
            books = books.filter(
                Q(title__icontains=query)
                | Q(series__icontains=query)
                | Q(authors__name__icontains=query)
            ).distinct()
        return [_summary(book) for book in books]

    @override
    def get(self, book_id: int) -> BookDTO:
        book = _book(book_id)
        return BookDTO(
            summary=_summary(book),
            description=book.description,
            cover_url=book.cover.url if book.cover else "",
            open_library_work=book.open_library_work,
        )

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
            Sync.objects.bulk_create(
                Sync(book=book, sync_type=raw["source"])
                for book, raw in zip(created, books, strict=True)
            )

    @override
    def move_file(self, content_hash: str, path: Path) -> None:
        RawBook.objects.filter(source=BookSource.FILE, key=content_hash).update(
            path=str(path)
        )

    @override
    def fields(self, book_id: int) -> BookFieldsData:
        book = _book(book_id)
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

    @override
    def set_work(self, book_id: int, work: PickedWorkData) -> None:
        with transaction.atomic():
            book = _book(book_id)
            book.open_library_work = work["work_id"]
            book.description = work["description"] or book.description
            if work["cover"] is not None:
                # The storage never overwrites: without this the old image stays.
                book.cover.delete(save=False)
                book.cover.save(
                    f"{book_id}.jpg", ContentFile(work["cover"]), save=False
                )
            book.save()

    @override
    def fill_empty(self, book_id: int, values: BookFieldsData) -> bool:
        empty = Book.objects.filter(
            pk=book_id,
            decision__isnull=True,
            **dict.fromkeys(values.keys() - {"authors"}, ""),
        )
        if "authors" in values:
            empty = empty.filter(credits__isnull=True)
        with transaction.atomic():
            if not empty.exists():
                return False
            self.fill(book_id, values)
        return True


class SyncRepository(SyncRepositoryProtocol):
    @override
    def counts(self) -> dict[SyncType, int]:
        rows = Sync.objects.values("sync_type").annotate(
            books=Count("book", distinct=True)
        )
        return {SyncType(row["sync_type"]): row["books"] for row in rows.order_by()}

    @override
    def record(self, book_id: int, sync: SyncType) -> None:
        Sync.objects.create(book_id=book_id, sync_type=sync)


class DecisionRepository(DecisionRepositoryProtocol):
    @override
    def exists(self, book_id: int) -> bool:
        return Decision.objects.filter(book_id=book_id).exists()

    @override
    def create(self, book_id: int, proposed: BookFieldsData) -> bool:
        _, created = Decision.objects.get_or_create(
            book_id=book_id, defaults={"proposed": proposed}
        )
        return created


class IgnoredExtensions(IgnoredExtensionsProtocol):
    @override
    def extensions(self) -> set[str]:
        return set(IgnoredExtension.objects.values_list("extension", flat=True))
