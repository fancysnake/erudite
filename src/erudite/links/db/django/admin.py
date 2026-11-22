"""Admin registrations (django-unfold), model-coupled by design."""

from typing import TYPE_CHECKING

from django.contrib import admin

from erudite.links.db.django.models import Book

if TYPE_CHECKING:
    # Unfold's admin classes are Django's, restyled; type-check against Django's.
    BookAdminBase = admin.ModelAdmin[Book]
else:
    from unfold.admin import ModelAdmin as BookAdminBase


@admin.register(Book)
class BookAdmin(BookAdminBase):
    list_display = ("title", "authors", "series", "series_position", "status")
    list_filter = ("status",)
    search_fields = ("title", "authors", "series", "isbn10", "isbn13")
