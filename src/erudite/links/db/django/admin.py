"""Admin registrations (django-unfold), model-coupled by design."""

from typing import TYPE_CHECKING, override

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from erudite.links.db.django.models import Author, Book, BookAuthor

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

    # Unfold's admin classes are Django's, restyled; type-check against Django's.
    AuthorAdminBase = admin.ModelAdmin[Author]
    BookAdminBase = admin.ModelAdmin[Book]
    BookAuthorInlineBase = admin.TabularInline[BookAuthor, Book]
else:
    from unfold.admin import ModelAdmin, TabularInline

    AuthorAdminBase = BookAdminBase = ModelAdmin
    BookAuthorInlineBase = TabularInline


@admin.register(Author)
class AuthorAdmin(AuthorAdminBase):
    search_fields = ("name",)


class BookAuthorInline(BookAuthorInlineBase):
    model = BookAuthor
    extra = 0
    autocomplete_fields = ("author",)


@admin.display(description=_("authors"))
def _author_names(book: Book) -> str:
    return ", ".join(credit.author.name for credit in book.credits.all())


@admin.register(Book)
class BookAdmin(BookAdminBase):
    list_display = ("title", _author_names, "series", "series_position", "status")
    list_filter = ("status",)
    search_fields = ("title", "authors__name", "series", "isbn10", "isbn13")
    inlines = (BookAuthorInline,)

    @override
    def get_queryset(self, request: HttpRequest) -> QuerySet[Book]:
        return super().get_queryset(request).prefetch_related("credits__author")
