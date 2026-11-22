"""ORM models, internal to the adapter."""

from typing import ClassVar

from django.db import models
from django.utils.translation import gettext_lazy as _

from erudite.pacts import ReadingStatus

_STATUS_LABELS = {
    ReadingStatus.TO_READ: _("To read"),
    ReadingStatus.READING: _("Reading"),
    ReadingStatus.READ: _("Read"),
}


class Book(models.Model):
    # Empty for a book that did not come from Goodreads.
    goodreads_id = models.PositiveBigIntegerField(
        _("Goodreads id"), unique=True, null=True, blank=True
    )
    title = models.CharField(_("title"), max_length=510)
    authors = models.JSONField(_("authors"), default=list)
    isbn10 = models.CharField(_("ISBN-10"), max_length=10, blank=True)
    isbn13 = models.CharField(_("ISBN-13"), max_length=13, blank=True)
    series = models.CharField(_("series"), max_length=255, blank=True)
    series_position = models.CharField(
        _("position in series"), max_length=20, blank=True
    )
    shelves = models.JSONField(_("shelves"), default=list, blank=True)
    rating = models.PositiveSmallIntegerField(_("rating"), null=True, blank=True)
    date_added = models.DateField(_("date added"), null=True, blank=True)
    date_read = models.DateField(_("date read"), null=True, blank=True)
    status = models.CharField(
        _("reading status"),
        max_length=20,
        choices=[(status.value, _STATUS_LABELS[status]) for status in ReadingStatus],
        default=ReadingStatus.TO_READ.value,
    )

    class Meta:
        ordering: ClassVar = ["title"]
        verbose_name = _("book")
        verbose_name_plural = _("books")

    def __str__(self) -> str:
        return str(self.title)
