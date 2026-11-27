"""ORM models, internal to the adapter."""

from typing import ClassVar, override

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from erudite.pacts import BookSource, ReadingStatus, SyncType

_STATUS_LABELS = {
    ReadingStatus.TO_READ: _("To read"),
    ReadingStatus.MUST_READ: _("Must read"),
    ReadingStatus.READING: _("Reading"),
    ReadingStatus.READ: _("Read"),
    ReadingStatus.DID_NOT_FINISH: _("Did not finish"),
}
_STATUS_CHOICES = [(status.value, _STATUS_LABELS[status]) for status in ReadingStatus]
_SOURCE_LABELS = {BookSource.GOODREADS: _("Goodreads"), BookSource.FILE: _("File")}
_SOURCE_CHOICES = [(source.value, _SOURCE_LABELS[source]) for source in BookSource]
_SYNC_LABELS = {
    SyncType.GOODREADS: _("Goodreads import"),
    SyncType.FILE: _("File scan"),
    SyncType.OPEN_LIBRARY: _("Open Library"),
}
_SYNC_CHOICES = [(sync.value, _SYNC_LABELS[sync]) for sync in SyncType]


class Author(models.Model):
    name = models.CharField(_("name"), max_length=255, unique=True)

    class Meta:
        ordering: ClassVar = ["name"]
        verbose_name = _("author")
        verbose_name_plural = _("authors")

    def __str__(self) -> str:
        return str(self.name)


class BookDetails(models.Model):
    """What a book and the raw book of its source both say about the book."""

    title = models.CharField(_("title"), max_length=510)
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
        abstract = True

    def __str__(self) -> str:
        return str(self.title)


class Book(BookDetails):
    authors = models.ManyToManyField(
        Author, through="BookAuthor", related_name="books", verbose_name=_("authors")
    )
    status = models.CharField(
        _("reading status"),
        max_length=20,
        choices=_STATUS_CHOICES,
        default=ReadingStatus.TO_READ.value,
    )
    description = models.TextField(_("description"), blank=True)
    cover = models.FileField(_("cover"), upload_to="covers/", blank=True)
    # The id Open Library has for the work, like OL45804W: all editions share it.
    open_library_work = models.CharField(
        _("Open Library work"), max_length=20, blank=True
    )

    class Meta:
        ordering: ClassVar = ["title"]
        verbose_name = _("book")
        verbose_name_plural = _("books")


class RawBook(BookDetails):
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
    authors = models.JSONField(_("authors"), default=list, blank=True)

    class Meta:
        ordering: ClassVar = ["title"]
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["source", "key"], name="raw_book_source_key_unique"
            )
        ]
        verbose_name = _("raw book")
        verbose_name_plural = _("raw books")


class Sync(models.Model):
    """The sync log: one entry for each time a source gave values to a book."""

    book = models.ForeignKey(
        Book, on_delete=models.CASCADE, related_name="syncs", verbose_name=_("book")
    )
    sync_type = models.CharField(_("sync type"), max_length=20, choices=_SYNC_CHOICES)
    time = models.DateTimeField(_("time"), auto_now_add=True)

    class Meta:
        ordering: ClassVar = ["-time"]
        verbose_name = _("sync")
        verbose_name_plural = _("syncs")

    def __str__(self) -> str:
        return f"{self.get_sync_type_display()}: {self.book}"


class Decision(models.Model):
    """Proposed values for a book, held until the user accepts or drops them."""

    book = models.OneToOneField(
        Book, on_delete=models.CASCADE, related_name="decision", verbose_name=_("book")
    )
    # Field name to proposed value; the authors are a list of names.
    proposed = models.JSONField(_("proposed"))

    class Meta:
        ordering: ClassVar = ["book__title"]
        verbose_name = _("decision")
        verbose_name_plural = _("decisions")

    def __str__(self) -> str:
        return str(self.book)


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
