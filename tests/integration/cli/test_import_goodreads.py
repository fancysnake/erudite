from io import StringIO

import pytest
from django.core.management import call_command, load_command_class
from django.core.management.base import CommandError

from erudite.links.db.django.models import Book, RawBook
from erudite.pacts import BookSource, ReadingStatus
from tests.goodreads import DUNE, MORT

pytestmark = pytest.mark.django_db


def _run(*args):
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def test_every_book_of_the_export_appears_once(goodreads_export):
    output = _run("import_goodreads", str(goodreads_export(MORT, DUNE)))

    assert output == "Books added: 2. Already in the library: 0.\n"
    assert list(Book.objects.values_list("title", "series", "status")) == [
        ("Dune", "", ReadingStatus.TO_READ),
        ("Mort", "Discworld", ReadingStatus.READ),
    ]
    assert list(RawBook.objects.values_list("source", "key", "book__title")) == [
        (BookSource.GOODREADS, "44767458", "Dune"),
        (BookSource.GOODREADS, "386372", "Mort"),
    ]


def test_importing_the_same_export_twice_changes_nothing(goodreads_export):
    path = str(goodreads_export(MORT, DUNE))
    _run("import_goodreads", path)
    before = list(Book.objects.values())

    output = _run("import_goodreads", path)

    assert output == "Books added: 0. Already in the library: 2.\n"
    assert list(Book.objects.values()) == before


def test_what_the_user_changed_survives_the_next_import(goodreads_export):
    _run("import_goodreads", str(goodreads_export(DUNE)))
    Book.objects.update(status=ReadingStatus.READING, title="Dune (my copy)")

    output = _run("import_goodreads", str(goodreads_export(DUNE, MORT)))

    assert output == "Books added: 1. Already in the library: 1.\n"
    assert list(Book.objects.values_list("title", "status")) == [
        ("Dune (my copy)", ReadingStatus.READING),
        ("Mort", ReadingStatus.READ),
    ]


def test_an_export_with_a_bad_row_adds_no_book(goodreads_export):
    path = goodreads_export(DUNE, MORT | {"Date Added": "yesterday"})

    with pytest.raises(CommandError, match=r"\.csv, row 3: "):
        call_command("import_goodreads", str(path))
    assert not Book.objects.exists()
    assert not RawBook.objects.exists()


def test_help_builds_no_services(settings):
    settings.SERVICES_FACTORY = "erudite.missing.Services"

    load_command_class("erudite.gates.cli.django", "import_goodreads").create_parser(
        "manage.py", "import_goodreads"
    )
