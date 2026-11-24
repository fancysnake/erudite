from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from erudite.links.db.django.models import Book, Decision

pytestmark = pytest.mark.django_db


def _run(*args):
    out = StringIO()
    call_command("propose", *args, stdout=out)
    return out.getvalue()


def test_a_proposal_for_a_book_with_a_title_and_no_author_waits_as_a_decision():
    book = Book.objects.create(title="scan_0042")

    output = _run(str(book.pk), "--title", "Dune", "--authors", "Frank Herbert")

    assert output == "The book holds one of these fields: a decision waits.\n"
    assert Decision.objects.get().proposed == {
        "title": "Dune",
        "authors": ["Frank Herbert"],
    }
    book.refresh_from_db()
    assert book.title == "scan_0042"
    assert not book.credits.exists()


def test_a_proposal_for_fields_the_book_does_not_hold_is_filled():
    book = Book.objects.create(title="Good Omens")

    output = _run(
        str(book.pk),
        "--authors",
        "Terry Pratchett; Neil Gaiman;",
        "--isbn13",
        "9780552137034",
    )

    assert output == "The book had none of these fields: they are filled.\n"
    book.refresh_from_db()
    assert book.isbn13 == "9780552137034"
    assert [str(credit) for credit in book.credits.all()] == [
        "Terry Pratchett",
        "Neil Gaiman",
    ]
    assert not Decision.objects.exists()


def test_a_second_proposal_for_a_book_with_a_waiting_decision_is_skipped():
    book = Book.objects.create(title="scan_0042")
    _run(str(book.pk), "--title", "Dune")

    output = _run(str(book.pk), "--title", "Dune Messiah")

    assert output == "Skipped: a decision waits for the book already.\n"
    assert Decision.objects.get().proposed == {"title": "Dune"}


def test_a_proposal_of_what_the_book_holds_already_is_skipped():
    book = Book.objects.create(title="Dune")

    output = _run(str(book.pk), "--title", "Dune")

    assert output == "Skipped: nothing proposed differs from the book.\n"
    assert not Decision.objects.exists()


def test_a_proposal_for_a_book_the_library_does_not_hold_is_an_error():
    with pytest.raises(CommandError, match="The library has no book 404"):
        _run("404", "--title", "Dune")
