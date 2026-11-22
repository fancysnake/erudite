"""Admin registrations (django-unfold), model-coupled by design."""

from typing import TYPE_CHECKING, Protocol, override, runtime_checkable

from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html_join
from django.utils.translation import gettext_lazy as _

from erudite.links.db.django.models import Author, Book, BookAuthor, BookFile

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.models import QuerySet
    from django.http import HttpRequest
    from django.utils.safestring import SafeString

    # Unfold's admin classes are Django's, restyled; type-check against Django's.
    AuthorAdminBase = admin.ModelAdmin[Author]
    BookAdminBase = admin.ModelAdmin[Book]
    BookFileAdminBase = admin.ModelAdmin[BookFile]
    BookAuthorInlineBase = admin.TabularInline[BookAuthor, Book]
else:
    from unfold.admin import ModelAdmin, TabularInline

    AuthorAdminBase = BookAdminBase = BookFileAdminBase = ModelAdmin
    BookAuthorInlineBase = TabularInline


@runtime_checkable
class _CountedAuthor(Protocol):
    """An author from `AuthorAdmin.get_queryset`, which annotates the count."""

    book_count: int


_LINK = '<a href="{}" class="text-primary-600 dark:text-primary-500 underline">{}</a>'


def _links(page: str, rows: Iterable[Author | Book], *, separator: str) -> SafeString:
    """Link each row to its change page in the admin."""
    return format_html_join(
        separator,
        _LINK,
        (
            (reverse(f"admin:erudite_db_{page}_change", args=[row.pk]), row)
            for row in rows
        ),
    )


@admin.display(description=_("books"), ordering="book_count")
def _book_count(author: Author) -> str:
    if not isinstance(author, _CountedAuthor):
        msg = "The author needs the book count from AuthorAdmin.get_queryset."
        raise TypeError(msg)
    return str(author.book_count)


@admin.register(Author)
class AuthorAdmin(AuthorAdminBase):
    list_display = ("name", _book_count)
    search_fields = ("name",)

    # The form options take a field by name only, so the links are a method.
    @staticmethod
    @admin.display(description=_("books"))
    def book_links(author: Author) -> SafeString:
        return _links("book", author.books.all(), separator="\n")

    fields = ("name", book_links.__name__)
    readonly_fields = (book_links.__name__,)

    @override
    def get_queryset(self, request: HttpRequest) -> QuerySet[Author]:
        # The books column sorts by this count.
        return super().get_queryset(request).annotate(book_count=Count("books"))


class BookAuthorInline(BookAuthorInlineBase):
    model = BookAuthor
    extra = 0
    autocomplete_fields = ("author",)


@admin.display(description=_("authors"))
def _author_links(book: Book) -> SafeString:
    authors = (credit.author for credit in book.credits.all())
    return _links("author", authors, separator=", ")


@admin.register(Book)
class BookAdmin(BookAdminBase):
    list_display = ("title", _author_links, "series", "series_position", "status")
    list_filter = ("status",)
    search_fields = ("title", "authors__name", "series", "isbn10", "isbn13")
    inlines = (BookAuthorInline,)

    @override
    def get_queryset(self, request: HttpRequest) -> QuerySet[Book]:
        return super().get_queryset(request).prefetch_related("credits__author")


@admin.display(description=_("authors"))
def _author_names(file: BookFile) -> str:
    return ", ".join(file.authors)


@admin.register(BookFile)
class BookFileAdmin(BookFileAdminBase):
    list_display = ("title", _author_names, "isbn", "path")
    search_fields = ("title", "authors", "isbn", "path")
    readonly_fields = ("path", "content_hash")
