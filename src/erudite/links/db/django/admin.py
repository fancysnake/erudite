"""Admin registrations (django-unfold), model-coupled by design."""

from typing import TYPE_CHECKING, Protocol, override, runtime_checkable
from urllib.parse import urlencode

from django import forms
from django.contrib import admin
from django.db.models import Count
from django.forms import fields_for_model
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html_join
from django.utils.text import capfirst
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from erudite.links.db.django.models import (
    Author,
    Book,
    BookAuthor,
    Decision,
    IgnoredExtension,
    RawBook,
)
from erudite.links.db.django.repositories import BookRepository

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.core.files.uploadedfile import UploadedFile
    from django.db.models import QuerySet
    from django.forms import CheckboxSelectMultiple as CheckboxesWidget
    from django.http import HttpRequest, HttpResponse, QueryDict
    from django.utils.datastructures import MultiValueDict
    from django.utils.safestring import SafeString

    # Unfold's admin classes are Django's, restyled; type-check against Django's.
    AuthorAdminBase = admin.ModelAdmin[Author]
    BookAdminBase = admin.ModelAdmin[Book]
    RawBookAdminBase = admin.ModelAdmin[RawBook]
    IgnoredExtensionAdminBase = admin.ModelAdmin[IgnoredExtension]
    DecisionAdminBase = admin.ModelAdmin[Decision]
    DecisionFormBase = forms.ModelForm[Decision]
    type Files = MultiValueDict[str, UploadedFile[bytes]]
    BookAuthorInlineBase = admin.TabularInline[BookAuthor, Book]
else:
    from unfold.admin import ModelAdmin, TabularInline
    from unfold.widgets import (
        UnfoldAdminCheckboxSelectMultipleWidget as CheckboxesWidget,
    )

    AuthorAdminBase = BookAdminBase = RawBookAdminBase = ModelAdmin
    IgnoredExtensionAdminBase = DecisionAdminBase = ModelAdmin
    DecisionFormBase = forms.ModelForm
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


@admin.action(description=_("Find the selected books on Open Library"))
def _find_on_open_library(
    _admin: BookAdminBase, _request: HttpRequest, queryset: QuerySet[Book]
) -> HttpResponse:
    """Open the picker for the first book; the rest wait in its queue."""
    first, *rest = (str(pk) for pk in queryset.values_list("pk", flat=True))
    url = reverse("open_library", args=[first])
    return redirect(f"{url}?{urlencode({'queue': ','.join(rest)})}" if rest else url)


@admin.register(Book)
class BookAdmin(BookAdminBase):
    list_display = ("title", _author_links, "series", "series_position", "status")
    # A book from a file that names no author has none: the filter finds those.
    list_filter = ("status", ("credits", admin.EmptyFieldListFilter))
    search_fields = ("title", "authors__name", "series", "isbn10", "isbn13")
    inlines = (BookAuthorInline,)

    actions = (_find_on_open_library,)

    @override
    def get_queryset(self, request: HttpRequest) -> QuerySet[Book]:
        return super().get_queryset(request).prefetch_related("credits__author")


@admin.display(description=_("authors"))
def _author_names(raw_book: RawBook) -> str:
    return ", ".join(raw_book.authors)


@admin.register(RawBook)
class RawBookAdmin(RawBookAdminBase):
    list_display = ("title", _author_names, "source", "path", "book")
    list_filter = ("source",)
    search_fields = ("title", "authors", "isbn10", "isbn13", "path")
    # Only a source writes a raw book; the user edits the book.
    readonly_fields = tuple(fields_for_model(RawBook))

    @override
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False


@admin.register(IgnoredExtension)
class IgnoredExtensionAdmin(IgnoredExtensionAdminBase):
    search_fields = ("extension",)


def _label(name: str) -> str:
    return str(capfirst(getattr(Book, name).field.verbose_name))


def _shown(value: object) -> str:
    return (", ".join(value) if isinstance(value, list) else str(value)) or "—"


@admin.display(description=_("proposed fields"))
def _proposed_fields(decision: Decision) -> str:
    return ", ".join(_label(name) for name in decision.proposed)


class DecisionForm(DecisionFormBase):
    # Declared so the admin may name it; `__init__` gives it the choices.
    accept = forms.MultipleChoiceField()

    def __init__(
        self,
        data: QueryDict | None = None,
        files: Files | None = None,
        *,
        instance: Decision,
    ) -> None:
        super().__init__(data, files, instance=instance)
        held = BookRepository().fields(instance.book_id)
        # One ticked box per proposed field: what the book has, then the proposal.
        self.fields["accept"] = forms.MultipleChoiceField(
            label=_("accept"),
            required=False,
            widget=CheckboxesWidget,
            choices=[
                (name, f"{_label(name)}: {_shown(held.get(name))} → {_shown(value)}")
                for name, value in instance.proposed.items()
            ],
            initial=list(instance.proposed),
        )


@admin.register(Decision)
class DecisionAdmin(DecisionAdminBase):
    form = DecisionForm
    list_display = ("book", _proposed_fields)
    search_fields = ("book__title",)
    fields = ("accept",)

    # Only a classification makes a decision.
    @override
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    # Django calls this inside the save transaction, once the form is valid, so
    # the accepted names are proposed ones. The decision is gone after it: the
    # reply goes to the list.
    @override
    def response_change(self, request: HttpRequest, obj: Decision) -> HttpResponse:
        accepted = obj.proposed.copy()
        for name in obj.proposed.keys() - set(request.POST.getlist("accept")):
            del accepted[name]
        BookRepository().fill(obj.book_id, accepted)
        obj.delete()
        self.message_user(
            request,
            gettext("The accepted fields are written to “%(book)s”.") % {"book": obj},
        )
        return self.response_post_save_change(request, obj)
