import pytest
from django.db import IntegrityError

from erudite.links.db.django.models import Author, Book
from erudite.links.db.django.repositories import BookRepository
from tests.goodreads import MORT_BOOK

pytestmark = pytest.mark.django_db

SOURCERY = MORT_BOOK | {
    "goodreads_id": 34499,
    "title": "Sourcery",
    "series_position": "5",
}
GOOD_OMENS = MORT_BOOK | {
    "goodreads_id": 12067,
    "title": "Good Omens",
    "authors": ["Terry Pratchett", "Neil Gaiman", "Terry Pratchett"],
    "series": "",
    "series_position": "",
}
_COLUMNS = [field for field in MORT_BOOK if field != "authors"]


def _without_authors(book):
    return {field: book[field] for field in _COLUMNS}


def test_books_from_goodreads_are_stored_field_by_field():
    BookRepository().create_from_goodreads([MORT_BOOK, SOURCERY])

    assert list(Book.objects.values(*_COLUMNS)) == [
        _without_authors(MORT_BOOK),
        _without_authors(SOURCERY),
    ]
    assert str(Book.objects.first()) == "Mort"


def test_books_share_an_author_and_keep_the_order_of_their_authors():
    Author.objects.create(name="Neil Gaiman")

    BookRepository().create_from_goodreads([MORT_BOOK, GOOD_OMENS])

    assert [str(author) for author in Author.objects.all()] == [
        "Neil Gaiman",
        "Terry Pratchett",
    ]
    assert {
        book.title: [str(credit) for credit in book.credits.all()]
        for book in Book.objects.all()
    } == {"Good Omens": ["Terry Pratchett", "Neil Gaiman"], "Mort": ["Terry Pratchett"]}


def test_a_goodreads_id_already_stored_adds_none_of_the_books():
    books = BookRepository()
    books.create_from_goodreads([MORT_BOOK])

    with pytest.raises(IntegrityError):
        books.create_from_goodreads([SOURCERY | {"authors": ["Rincewind"]}, MORT_BOOK])
    assert books.count() == 1
    assert Author.objects.count() == 1


def test_goodreads_ids_leave_out_books_from_elsewhere():
    Book.objects.create(title="A book from the shelf")
    books = BookRepository()
    books.create_from_goodreads([MORT_BOOK, SOURCERY])

    assert books.goodreads_ids() == {386372, 34499}
    assert books.count() == 3
