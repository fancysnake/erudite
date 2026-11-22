from pathlib import Path

import pytest
from django.db import IntegrityError

from erudite.links.db.django.models import Author, Book, BookFile, IgnoredExtension
from erudite.links.db.django.repositories import BookFileRepository, BookRepository
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


MORT_FILE = {
    "path": Path("/books/mort.epub"),
    "content_hash": "aa",
    "title": "Mort",
    "authors": ["Terry Pratchett"],
    "isbn": "0552131067",
}
DUNE_FILE = MORT_FILE | {
    "path": Path("/books/dune.pdf"),
    "content_hash": "bb",
    "title": "dune",
    "authors": [],
    "isbn": "",
}


def test_book_files_are_stored_field_by_field():
    BookFileRepository().create([MORT_FILE, DUNE_FILE])

    assert list(BookFile.objects.values(*MORT_FILE)) == [
        MORT_FILE | {"path": "/books/mort.epub"},
        DUNE_FILE | {"path": "/books/dune.pdf"},
    ]
    assert str(BookFile.objects.first()) == "Mort"


def test_a_content_hash_already_stored_adds_none_of_the_files():
    files = BookFileRepository()
    files.create([MORT_FILE])

    with pytest.raises(IntegrityError):
        files.create([DUNE_FILE, MORT_FILE])
    assert files.paths() == {"aa": Path("/books/mort.epub")}


def test_move_changes_the_path_of_the_file_with_that_content():
    files = BookFileRepository()
    files.create([MORT_FILE, DUNE_FILE])

    files.move("aa", Path("/sorted/mort.epub"))

    assert files.paths() == {
        "aa": Path("/sorted/mort.epub"),
        "bb": Path("/books/dune.pdf"),
    }


def test_files_with_an_ignored_extension_are_marked_and_the_others_are_not():
    files = BookFileRepository()
    cover = MORT_FILE | {"path": Path("/books/Cover.PNG"), "content_hash": "cc"}
    files.create([MORT_FILE, DUNE_FILE, cover])
    for extension in ("png", " .PDF", "."):
        IgnoredExtension.objects.create(extension=extension)

    files.ignore_by_extension()

    assert set(BookFile.objects.values_list("content_hash", "ignored")) == {
        ("aa", False),
        ("bb", True),
        ("cc", True),
    }
    assert str(IgnoredExtension.objects.first()) == " .PDF"


def test_no_ignored_extension_leaves_every_file_as_it_is():
    files = BookFileRepository()
    files.create([MORT_FILE])

    files.ignore_by_extension()

    assert not BookFile.objects.get().ignored
