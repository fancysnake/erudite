from pathlib import Path

import pytest
from django.db import IntegrityError

from erudite.links.db.django.models import (
    Author,
    Book,
    Decision,
    IgnoredExtension,
    RawBook,
)
from erudite.links.db.django.repositories import (
    BookRepository,
    DecisionRepository,
    IgnoredExtensions,
)
from erudite.pacts import BookSource, NotFoundError, ReadingStatus
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

    assert IgnoredExtensions().extensions() == {"png", "pdf"}


def test_no_ignored_extension_gives_an_empty_set():
    assert IgnoredExtensions().extensions() == set()


def _mort():
    BookRepository().create([MORT_BOOK])
    return Book.objects.get()


def _authors(book):
    return [str(credit) for credit in book.credits.all()]


def test_the_fields_of_a_book_are_read_with_its_authors_in_order():
    BookRepository().create([GOOD_OMENS | {"isbn13": "9780552137034"}])

    assert DecisionRepository().book_fields(Book.objects.get().pk) == {
        "title": "Good Omens",
        "authors": ["Terry Pratchett", "Neil Gaiman"],
        "isbn10": GOOD_OMENS["isbn10"],
        "isbn13": "9780552137034",
        "series": "",
        "series_position": "",
    }


def test_the_fields_of_a_book_the_library_does_not_hold_are_not_found():
    with pytest.raises(NotFoundError, match="no book 404"):
        DecisionRepository().book_fields(404)


def test_filling_a_book_writes_the_values_and_leaves_the_other_fields():
    book = _mort()

    DecisionRepository().fill(book.pk, {"isbn13": "9780552131063", "series": "Death"})

    assert list(Book.objects.values("title", "isbn13", "series", "status")) == [
        {
            "title": "Mort",
            "isbn13": "9780552131063",
            "series": "Death",
            "status": MORT_BOOK["status"],
        }
    ]
    assert _authors(book) == ["Terry Pratchett"]


def test_filling_the_authors_replaces_them_in_the_given_order_each_once():
    book = _mort()

    DecisionRepository().fill(
        book.pk, {"authors": ["Neil Gaiman", "Terry Pratchett", "Neil Gaiman"]}
    )

    assert _authors(book) == ["Neil Gaiman", "Terry Pratchett"]
    assert Author.objects.count() == len(_authors(book))


def test_a_decision_waits_for_its_book_only_and_one_book_holds_one():
    BookRepository().create([MORT_BOOK, SOURCERY])
    mort, sourcery = Book.objects.all()
    repository = DecisionRepository()

    repository.create(mort.pk, {"title": "Mort!"})

    assert repository.exists(mort.pk)
    assert not repository.exists(sourcery.pk)
    assert str(Decision.objects.get()) == "Mort"
    with pytest.raises(IntegrityError):
        repository.create(mort.pk, {"title": "Mort?"})


def test_accepting_writes_only_the_chosen_proposed_fields_and_removes_the_decision():
    book = _mort()
    repository = DecisionRepository()
    repository.create(
        book.pk, {"title": "Mort!", "authors": ["Neil Gaiman"], "series": "Death"}
    )

    repository.accept(book.pk, {"authors", "series", "status"})

    book.refresh_from_db()
    assert (book.title, book.series, book.status) == (
        "Mort",
        "Death",
        MORT_BOOK["status"],
    )
    assert _authors(book) == ["Neil Gaiman"]
    assert not Decision.objects.exists()


def test_accepting_no_field_removes_the_decision_and_leaves_the_book():
    book = _mort()
    before = Book.objects.values().get()
    repository = DecisionRepository()
    repository.create(book.pk, {"title": "Mort!"})

    repository.accept(book.pk, set())

    assert Book.objects.values().get() == before
    assert not repository.exists(book.pk)
