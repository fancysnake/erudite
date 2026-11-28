import datetime as dt
from pathlib import Path

import pytest
from django.db import IntegrityError, connection
from django.test.utils import CaptureQueriesContext

from erudite.links.db.django.models import (
    Author,
    Book,
    Decision,
    IgnoredExtension,
    RawBook,
    Sync,
)
from erudite.links.db.django.repositories import (
    BookRepository,
    DecisionRepository,
    IgnoredExtensions,
    SyncRepository,
)
from erudite.pacts import (
    BookDTO,
    BookSource,
    BookSummaryDTO,
    NotFoundError,
    ReadingStatus,
    SyncType,
)
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

    assert BookRepository().fields(Book.objects.get().pk) == {
        "title": "Good Omens",
        "authors": ["Terry Pratchett", "Neil Gaiman"],
        "isbn10": GOOD_OMENS["isbn10"],
        "isbn13": "9780552137034",
        "series": "",
        "series_position": "",
    }


def test_the_fields_of_a_book_the_library_does_not_hold_are_not_found():
    with pytest.raises(NotFoundError, match="no book 404"):
        BookRepository().fields(404)


def test_filling_a_book_writes_the_values_and_leaves_the_other_fields():
    book = _mort()

    BookRepository().fill(book.pk, {"isbn13": "9780552131063", "series": "Death"})

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

    BookRepository().fill(
        book.pk, {"authors": ["Neil Gaiman", "Terry Pratchett", "Neil Gaiman"]}
    )

    assert _authors(book) == ["Neil Gaiman", "Terry Pratchett"]
    assert Author.objects.count() == len(_authors(book))


def test_filling_the_empty_fields_of_a_book_writes_them_and_its_authors():
    book = Book.objects.create(title="Good Omens")

    filled = BookRepository().fill_empty(
        book.pk, {"isbn13": "9780552137034", "authors": ["Terry Pratchett"]}
    )

    assert filled
    book.refresh_from_db()
    assert book.isbn13 == "9780552137034"
    assert _authors(book) == ["Terry Pratchett"]


def test_filling_only_the_authors_of_a_book_without_authors_writes_them():
    book = Book.objects.create(title="Good Omens")

    assert BookRepository().fill_empty(book.pk, {"authors": ["Neil Gaiman"]})

    assert _authors(book) == ["Neil Gaiman"]


def test_filling_an_empty_field_alone_leaves_the_book_without_authors():
    book = Book.objects.create(title="Mort")

    assert BookRepository().fill_empty(book.pk, {"series": "Discworld"})

    book.refresh_from_db()
    assert book.series == "Discworld"
    assert not _authors(book)


def test_filling_the_empty_fields_writes_nothing_when_the_book_holds_one():
    book = _mort()

    filled = BookRepository().fill_empty(
        book.pk, {"isbn13": "9780552131063", "series": "Death"}
    )

    assert not filled
    assert list(Book.objects.values_list("isbn13", "series")) == [
        (MORT_BOOK["isbn13"], MORT_BOOK["series"])
    ]


def test_filling_the_empty_fields_writes_nothing_when_the_book_has_authors():
    book = _mort()
    Book.objects.update(isbn13="")

    filled = BookRepository().fill_empty(
        book.pk, {"isbn13": "9780552131063", "authors": ["Neil Gaiman"]}
    )

    assert not filled
    book.refresh_from_db()
    assert not book.isbn13
    assert _authors(book) == ["Terry Pratchett"]


def test_filling_the_empty_fields_writes_nothing_when_a_decision_waits():
    book = Book.objects.create(title="scan_0042")
    Decision.objects.create(book=book, proposed={"title": "Dune"})
    repository = BookRepository()

    assert not repository.fill_empty(book.pk, {"series": "Dune"})
    assert not repository.fill_empty(book.pk, {"authors": ["Frank Herbert"]})

    book.refresh_from_db()
    assert not book.series
    assert not _authors(book)


@pytest.mark.django_db(transaction=True)
def test_a_fill_takes_the_write_lock_before_it_reads():
    book = Book.objects.create(title="Good Omens")

    with CaptureQueriesContext(connection) as queries:
        BookRepository().fill_empty(book.pk, {"authors": ["Neil Gaiman"]})

    assert queries[0]["sql"] == "BEGIN IMMEDIATE"


def test_a_decision_waits_for_its_book_only_and_one_book_holds_one():
    BookRepository().create([MORT_BOOK, SOURCERY])
    mort, sourcery = Book.objects.all()
    repository = DecisionRepository()

    repository.create(mort.pk, {"title": "Mort!"})

    assert repository.exists(mort.pk)
    assert not repository.exists(sourcery.pk)
    assert str(Decision.objects.get()) == "Mort"


def _picked(**values):
    return {
        "work_id": "OL45804W",
        "description": "A fox outwits three farmers.",
        "cover": b"a JPEG",
    } | values


@pytest.mark.usefixtures("media")
def test_a_picked_work_replaces_the_description_and_cover():
    BookRepository().create([MORT_BOOK])
    book = Book.objects.get()
    BookRepository().set_work(book.pk, _picked(cover=b"an old JPEG"))

    BookRepository().set_work(book.pk, _picked())

    book.refresh_from_db()
    assert book.title == MORT_BOOK["title"]
    assert book.description == "A fox outwits three farmers."
    assert book.open_library_work == "OL45804W"
    assert book.cover.name == f"covers/{book.pk}.jpg"
    assert book.cover.read() == b"a JPEG"
    assert book.isbn13 == MORT_BOOK["isbn13"]


@pytest.mark.usefixtures("media")
def test_a_picked_work_changes_nothing_where_it_holds_nothing():
    BookRepository().create([MORT_BOOK])
    book = Book.objects.get()
    BookRepository().set_work(book.pk, _picked())

    BookRepository().set_work(book.pk, _picked(description="", cover=None))

    book.refresh_from_db()
    assert book.description == "A fox outwits three farmers."
    assert book.cover.read() == b"a JPEG"


def test_a_picked_work_for_a_book_the_library_lacks_is_not_found():
    with pytest.raises(NotFoundError, match="no book 404"):
        BookRepository().set_work(404, _picked())


@pytest.mark.parametrize(
    ("query", "titles"),
    (
        ("", ["Good Omens", "Mort", "dune"]),
        ("OMENS", ["Good Omens"]),
        ("discworld", ["Mort"]),
        ("pratchett", ["Good Omens", "Mort"]),
        ("terry", ["Good Omens", "Mort"]),
        ("hobbit", []),
    ),
)
def test_a_search_finds_books_by_title_series_or_author_in_title_order(
    *, query, titles
):
    BookRepository().create([MORT_BOOK, GOOD_OMENS, DUNE_FILE])

    found = BookRepository().search(query)

    assert [book.title for book in found] == titles


def test_a_search_gives_each_book_as_a_list_shows_it():
    BookRepository().create([GOOD_OMENS])

    (found,) = BookRepository().search("")

    assert found == BookSummaryDTO(
        book_id=Book.objects.get().pk,
        title="Good Omens",
        authors=("Terry Pratchett", "Neil Gaiman"),
        series="",
        series_position="",
        status="Read",
    )


@pytest.mark.usefixtures("media")
def test_a_book_is_given_with_its_description_cover_and_work():
    book = Book.objects.create(title="Mort", description="Death takes an apprentice.")
    BookRepository().set_work(
        book.pk, {"work_id": "OL1W", "description": "", "cover": b"a JPEG"}
    )

    assert BookRepository().get(book.pk) == BookDTO(
        summary=BookSummaryDTO(
            book_id=book.pk,
            title="Mort",
            authors=(),
            series="",
            series_position="",
            status="To read",
        ),
        description="Death takes an apprentice.",
        cover_url=f"/media/covers/{book.pk}.jpg",
        open_library_work="OL1W",
    )
    assert not BookRepository().get(Book.objects.create(title="dune").pk).cover_url


def test_a_book_the_library_lacks_cannot_be_given():
    with pytest.raises(NotFoundError, match="no book 404"):
        BookRepository().get(404)


def test_a_new_book_gets_an_entry_in_the_sync_log_for_its_source():
    BookRepository().create([MORT_BOOK, DUNE_FILE])

    assert set(Sync.objects.values_list("book__title", "sync_type")) == {
        ("Mort", "goodreads"),
        ("dune", "file"),
    }
    assert str(Sync.objects.get(sync_type="file")) == "File scan: dune"


def test_a_recorded_sync_is_an_entry_with_the_time_of_now():
    book = Book.objects.create(title="Mort")
    before = dt.datetime.now(dt.UTC)

    SyncRepository().record(book.pk, SyncType.OPEN_LIBRARY)

    sync = Sync.objects.get()
    assert (sync.book, sync.sync_type) == (book, "open_library")
    assert before <= sync.time <= dt.datetime.now(dt.UTC)


@pytest.mark.parametrize(
    ("filters", "titles"),
    (
        ({}, ["Dune", "Emma", "Mort"]),
        ({"done": (SyncType.OPEN_LIBRARY,)}, ["Dune", "Mort"]),
        ({"done": (SyncType.OPEN_LIBRARY, SyncType.FILE)}, ["Mort"]),
        ({"done": (SyncType.GOODREADS,)}, []),
        ({"todo": (SyncType.OPEN_LIBRARY,)}, ["Emma"]),
        ({"todo": (SyncType.FILE,)}, ["Dune", "Emma"]),
        ({"done": (SyncType.OPEN_LIBRARY,), "todo": (SyncType.FILE,)}, ["Dune"]),
    ),
)
def test_a_search_keeps_the_books_some_syncs_reached_and_others_did_not(
    *, filters, titles
):
    dune, mort = Book.objects.create(title="Dune"), Book.objects.create(title="Mort")
    Book.objects.create(title="Emma")
    Sync.objects.create(book=dune, sync_type="open_library")
    Sync.objects.create(book=mort, sync_type="file")
    Sync.objects.create(book=mort, sync_type="open_library")

    found = BookRepository().search("", **filters)

    assert [book.title for book in found] == titles


def test_the_sync_counts_are_the_books_each_sync_reached_once():
    dune, mort = Book.objects.create(title="Dune"), Book.objects.create(title="Mort")
    for book, sync in ((dune, "open_library"), (mort, "open_library"), (mort, "file")):
        Sync.objects.create(book=book, sync_type=sync)
    Sync.objects.create(book=mort, sync_type="open_library")

    assert SyncRepository().counts() == {SyncType.OPEN_LIBRARY: 2, SyncType.FILE: 1}


def test_a_second_decision_for_a_book_is_not_stored_and_the_first_stays():
    book = _mort()
    repository = DecisionRepository()

    assert repository.create(book.pk, {"title": "Mort!"})
    assert not repository.create(book.pk, {"title": "Mort?"})

    assert Decision.objects.get().proposed == {"title": "Mort!"}


def test_dropped_fields_leave_a_decision_and_the_rest_waits():
    book = _mort()
    proposed = {"title": "Mort!", "authors": ["T. Pratchett"], "series": "Discworld"}
    Decision.objects.create(book=book, proposed=proposed)

    DecisionRepository().drop_fields(book.pk, {"title", "authors"})

    assert Decision.objects.get().proposed == {"series": "Discworld"}


def test_a_decision_with_no_field_left_is_removed():
    book = _mort()
    Decision.objects.create(book=book, proposed={"title": "Mort!"})

    DecisionRepository().drop_fields(book.pk, {"title", "authors"})

    assert not Decision.objects.exists()


def test_dropping_fields_of_a_book_without_a_decision_changes_nothing():
    book = _mort()

    DecisionRepository().drop_fields(book.pk, {"title"})

    assert not Decision.objects.exists()
