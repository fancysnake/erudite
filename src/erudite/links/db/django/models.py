"""ORM models, internal to the adapter."""

from typing import ClassVar, override

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from erudite.pacts import BookSource, ReadingStatus

_STATUS_LABELS = {
    ReadingStatus.TO_READ: _("To read"),
    ReadingStatus.MUST_READ: _("Must read"),
    ReadingStatus.READING: _("Reading"),
    ReadingStatus.READ: _("Read"),
    ReadingStatus.DID_NOT_FINISH: _("Did not finish"),
}
_STATUS_CHOICES = [(status.value, _STATUS_LABELS[status]) for status in ReadingStatus]
_SOURCE_CHOICES = [
    (BookSource.GOODREADS.value, _("Goodreads")),
    (BookSource.FILE.value, _("File")),
]


class Author(models.Model):
    name = models.CharField(_("name"), max_length=255, unique=True)

    class Meta:
        ordering: ClassVar = ["name"]
        verbose_name = _("author")
        verbose_name_plural = _("authors")

    def __str__(self) -> str:
        return str(self.name)


class Book(models.Model):
    title = models.CharField(_("title"), max_length=510)
    authors = models.ManyToManyField(
        Author, through="BookAuthor", related_name="books", verbose_name=_("authors")
    )
    isbn10 = models.CharField(_("ISBN-10"), max_length=10, blank=True)
    isbn13 = models.CharField(_("ISBN-13"), max_length=13, blank=True)
    series = models.CharField(_("series"), max_length=255, blank=True)
    series_position = models.CharField(
        _("position in series"), max_length=20, blank=True
    )
    rating = models.PositiveSmallIntegerField(_("rating"), null=True, blank=True)
    date_added = models.DateField(_("date added"), null=True, blank=True)
    date_read = models.DateField(_("date read"), null=True, blank=True)
    status = models.CharField(
        _("reading status"),
        max_length=20,
        choices=_STATUS_CHOICES,
        default=ReadingStatus.TO_READ.value,
    )

    class Meta:
        ordering: ClassVar = ["title"]
        verbose_name = _("book")
        verbose_name_plural = _("books")

    def __str__(self) -> str:
        return str(self.title)


class RawBook(models.Model):
    """A book as its source gave it; only the source writes it."""

    # Empty once the user deleted the book: the source does not add it again.
    book = models.ForeignKey(
        Book,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="raw_books",
        verbose_name=_("book"),
    )
    source = models.CharField(_("source"), max_length=20, choices=_SOURCE_CHOICES)
    # The name the source has for the book: a Goodreads id, the SHA-256 of a
    # file's content in hex, so the same file under a new name is known.
    key = models.CharField(_("key"), max_length=64)
    path = models.CharField(_("path"), max_length=4096, blank=True)
    title = models.CharField(_("title"), max_length=510)
    authors = models.JSONField(_("authors"), default=list, blank=True)
    isbn10 = models.CharField(_("ISBN-10"), max_length=10, blank=True)
    isbn13 = models.CharField(_("ISBN-13"), max_length=13, blank=True)
    series = models.CharField(_("series"), max_length=255, blank=True)
    series_position = models.CharField(
        _("position in series"), max_length=20, blank=True
    )
    rating = models.PositiveSmallIntegerField(_("rating"), null=True, blank=True)
    date_added = models.DateField(_("date added"), null=True, blank=True)
    date_read = models.DateField(_("date read"), null=True, blank=True)
    status = models.CharField(
        _("reading status"), max_length=20, choices=_STATUS_CHOICES, blank=True
    )

    class Meta:
        ordering: ClassVar = ["title"]
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["source", "key"], name="raw_book_source_key_unique"
            )
        ]
        verbose_name = _("raw book")
        verbose_name_plural = _("raw books")

    def __str__(self) -> str:
        return str(self.title)


class IgnoredExtension(models.Model):
    extension = models.CharField(
        _("extension"),
        max_length=20,
        unique=True,
        help_text=_("Without the dot, for example: png."),
    )

    class Meta:
        ordering: ClassVar = ["extension"]
        verbose_name = _("ignored file extension")
        verbose_name_plural = _("ignored file extensions")

    def __str__(self) -> str:
        return str(self.extension)

    @override
    def clean(self) -> None:
        # The user may type ` .PNG` for `png`; the scan compares the clean form.
        self.extension = str(self.extension).strip().lstrip(".").strip().lower()
        if not self.extension:
            raise ValidationError({"extension": _("Enter an extension.")})


class BookAuthor(models.Model):
    book = models.ForeignKey(
        Book, on_delete=models.CASCADE, related_name="credits", verbose_name=_("book")
    )
    author = models.ForeignKey(
        Author,
        on_delete=models.CASCADE,
        related_name="credits",
        verbose_name=_("author"),
    )
    # The first author of a book is the one Goodreads names as its author.
    position = models.PositiveSmallIntegerField(_("position"), default=0)

    class Meta:
        ordering: ClassVar = ["position"]
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["book", "author"], name="book_author_unique"
            )
        ]
        verbose_name = _("book author")
        verbose_name_plural = _("book authors")

    def __str__(self) -> str:
        return str(self.author)
