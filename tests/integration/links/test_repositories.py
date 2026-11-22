import pytest
from django.db import IntegrityError

from erudite.links.db.django.models import Book
from erudite.links.db.django.repositories import BookRepository
from tests.goodreads import MORT_BOOK

pytestmark = pytest.mark.django_db

SOURCERY = MORT_BOOK | {
    "goodreads_id": 34499,
    "title": "Sourcery",
    "series_position": "5",
}


def test_books_from_goodreads_are_stored_field_by_field():
    BookRepository().create_from_goodreads([MORT_BOOK, SOURCERY])

    assert list(Book.objects.values(*MORT_BOOK)) == [MORT_BOOK, SOURCERY]
    assert str(Book.objects.first()) == "Mort"


def test_a_goodreads_id_already_stored_adds_none_of_the_books():
    books = BookRepository()
    books.create_from_goodreads([MORT_BOOK])

    with pytest.raises(IntegrityError):
        books.create_from_goodreads([SOURCERY, MORT_BOOK])
    assert books.count() == 1


def test_goodreads_ids_leave_out_books_from_elsewhere():
    Book.objects.create(title="A book from the shelf", authors=["Anonymous"])
    books = BookRepository()
    books.create_from_goodreads([MORT_BOOK, SOURCERY])

    assert books.goodreads_ids() == {386372, 34499}
    assert books.count() == 3
