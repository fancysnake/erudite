from pathlib import Path

import pytest
from django.db import IntegrityError

from erudite.links.db.django.models import Author, Book, IgnoredExtension, RawBook
from erudite.links.db.django.repositories import BookRepository
from erudite.pacts import BookSource, ReadingStatus
from tests.goodreads import MORT_BOOK

pytestmark = pytest.mark.django_db

SOURCERY = MORT_BOOK | {"key": "34499", "title": "Sourcery", "series_position": "5"}
GOOD_OMENS = MORT_BOOK | {
    "key": "12067",
    "title": "Good Omens",
    "authors": ["Terry Pratchett", "Neil Gaiman", "Terry Pratchett"],
    "series": "",
    "series_position": "",
}
MORT_FILE = {
    "source": BookSource.FILE,
    "key": "aa",
    "title": "Mort",
    "authors": ["Terry Pratchett"],
    "path": Path("/books/mort.epub"),
    "isbn10": "0552131067",
}
DUNE_FILE = {
    "source": BookSource.FILE,
    "key": "bb",
    "title": "dune",
    "authors": [],
    "path": Path("/books/dune.pdf"),
}
_COPIED = [field for field in MORT_BOOK if field not in {"source", "key", "authors"}]


def test_a_raw_book_is_stored_as_given_with_a_book_that_copies_it():
    BookRepository().create([MORT_BOOK, SOURCERY])

    assert list(RawBook.objects.values(*MORT_BOOK, "path", "book__title")) == [
        MORT_BOOK | {"path": "", "book__title": "Mort"},
        SOURCERY | {"path": "", "book__title": "Sourcery"},
    ]
    assert list(Book.objects.values(*_COPIED)) == [
        {field: book[field] for field in _COPIED} for book in (MORT_BOOK, SOURCERY)
    ]
    assert str(Book.objects.first()) == "Mort"
    assert str(RawBook.objects.first()) == "Mort"


def test_a_raw_book_from_a_file_keeps_its_path_and_leaves_the_rest_empty():
    BookRepository().create([MORT_FILE, DUNE_FILE])

    fields = ("path", "isbn10", "isbn13", "status", "rating", "authors")
    assert list(RawBook.objects.values_list(*fields)) == [
        ("/books/mort.epub", "0552131067", "", "", None, ["Terry Pratchett"]),
        ("/books/dune.pdf", "", "", "", None, []),
    ]
    assert list(Book.objects.values_list("title", "isbn10", "status")) == [
        ("Mort", "0552131067", ReadingStatus.TO_READ),
        ("dune", "", ReadingStatus.TO_READ),
    ]
    assert [book.credits.count() for book in Book.objects.all()] == [1, 0]


def test_books_share_an_author_and_keep_the_order_of_their_authors():
    Author.objects.create(name="Neil Gaiman")

    BookRepository().create([MORT_BOOK, GOOD_OMENS])

    assert [str(author) for author in Author.objects.all()] == [
        "Neil Gaiman",
        "Terry Pratchett",
    ]
    assert {
        book.title: [str(credit) for credit in book.credits.all()]
        for book in Book.objects.all()
    } == {"Good Omens": ["Terry Pratchett", "Neil Gaiman"], "Mort": ["Terry Pratchett"]}


def test_a_key_already_stored_for_the_source_adds_none_of_the_books():
    books = BookRepository()
    books.create([MORT_BOOK])

    with pytest.raises(IntegrityError):
        books.create([SOURCERY | {"authors": ["Rincewind"]}, MORT_BOOK])
    assert books.count() == 1
    assert Author.objects.count() == 1


def test_two_sources_may_use_the_same_key():
    books = BookRepository()

    books.create([MORT_BOOK, MORT_FILE | {"key": MORT_BOOK["key"]}])

    assert books.count() == len([MORT_BOOK, MORT_FILE])


def test_keys_and_file_paths_are_those_of_one_source():
    Book.objects.create(title="A book from the shelf")
    books = BookRepository()
    books.create([MORT_BOOK, SOURCERY, MORT_FILE])

    assert books.keys(BookSource.GOODREADS) == {"386372", "34499"}
    assert books.file_paths() == {"aa": Path("/books/mort.epub")}
    assert books.count() == len(["shelf", MORT_BOOK, SOURCERY, MORT_FILE])


def test_move_file_changes_the_path_of_the_file_with_that_content():
    books = BookRepository()
    books.create([MORT_FILE, DUNE_FILE, MORT_BOOK | {"key": "aa"}])

    books.move_file("aa", Path("/sorted/mort.epub"))

    assert books.file_paths() == {
        "aa": Path("/sorted/mort.epub"),
        "bb": Path("/books/dune.pdf"),
    }
    assert not RawBook.objects.get(source=BookSource.GOODREADS).path


def test_ignored_extensions_are_the_stored_extensions():
    for extension in ("png", "pdf"):
        IgnoredExtension.objects.create(extension=extension)

    assert BookRepository().ignored_extensions() == {"png", "pdf"}


def test_no_ignored_extension_gives_an_empty_set():
    assert BookRepository().ignored_extensions() == set()
