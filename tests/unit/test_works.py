from copy import replace
from unittest.mock import MagicMock, call

import pytest

from erudite.mills import WorkService
from erudite.pacts import (
    CandidatesDTO,
    NotFoundError,
    OpenLibraryError,
    SyncType,
    WorkDTO,
)
from tests.open_library import FOX_WORK as FOX

BOOK = 7
FILM = WorkDTO(
    work_id="OL2W",
    title="Fantastic Mr. Fox",
    authors=("Wes Anderson",),
    first_year=2016,
    cover=None,
    edition_count=1,
    description="",
)


def _service(*, found=(), **held):
    books, open_library = MagicMock(), MagicMock()
    books.fields.return_value = {"title": "mr fox", "authors": ["Dahl"]} | held
    open_library.search.side_effect = [list(works) for works in found]
    service = WorkService(
        books=books,
        syncs=books.syncs,
        open_library=open_library,
        transaction=MagicMock(),
    )
    return service, books, open_library


def test_the_first_search_is_for_the_title_and_authors_of_the_book():
    service, books, open_library = _service(found=[[FOX, FILM]])

    candidates = service.candidates(BOOK)

    assert candidates == CandidatesDTO(
        book_id=BOOK,
        title="mr fox",
        authors=("Dahl",),
        query="mr fox Dahl",
        works=(FOX, FILM),
    )
    books.fields.assert_called_once_with(BOOK)
    open_library.search.assert_called_once_with("mr fox Dahl")


def test_candidates_without_a_search_hold_the_book_and_the_query_only():
    service, _books, open_library = _service(isbn13="9780140328721")

    candidates = service.candidates(BOOK, search=False)

    assert candidates == CandidatesDTO(
        book_id=BOOK, title="mr fox", authors=("Dahl",), query="mr fox Dahl", works=()
    )
    open_library.search.assert_not_called()


@pytest.mark.parametrize(
    ("held", "isbn"),
    (
        ({"isbn13": "9780140328721", "isbn10": "0140328726"}, "9780140328721"),
        ({"isbn13": "", "isbn10": "0140328726"}, "0140328726"),
    ),
)
def test_the_work_of_an_isbn_the_book_holds_comes_first_and_once(held, isbn):
    service, _books, open_library = _service(found=[[FOX], [FILM, FOX]], **held)

    candidates = service.candidates(BOOK)

    assert candidates.works == (FOX, FILM)
    assert open_library.search.call_args_list == [
        call(f"isbn:{isbn}"),
        call("mr fox Dahl"),
    ]


def test_a_search_the_user_typed_is_the_only_search():
    service, _books, open_library = _service(found=[[FILM]], isbn13="9780140328721")

    candidates = service.candidates(BOOK, "  fantastic fox ")

    assert candidates.query == "fantastic fox"
    assert candidates.works == (FILM,)
    open_library.search.assert_called_once_with("fantastic fox")


def test_an_empty_search_asks_open_library_nothing():
    service, _books, open_library = _service()

    candidates = service.candidates(BOOK, " ")

    assert not candidates.query
    assert not candidates.works
    open_library.search.assert_not_called()


def test_a_pick_gives_the_book_what_the_work_holds():
    service, books, open_library = _service(found=[[FOX]])
    open_library.cover.return_value = b"a JPEG"

    service.pick(BOOK, FOX.work_id)

    open_library.search.assert_called_once_with("key:/works/OL45804W")
    open_library.cover.assert_called_once_with(6498519)
    books.set_work.assert_called_once_with(
        BOOK,
        {
            "work_id": FOX.work_id,
            "description": "A fox outwits\nthree farmers.",
            "cover": b"a JPEG",
        },
    )
    books.fill.assert_called_once_with(
        BOOK, {"title": "Fantastic Mr Fox", "authors": ["Roald Dahl"]}
    )
    books.syncs.record.assert_called_once_with(BOOK, SyncType.OPEN_LIBRARY)


def test_a_pick_of_a_work_without_a_title_or_authors_fills_neither():
    service, books, _open_library = _service(
        found=[[replace(FILM, title="", authors=())]]
    )

    service.pick(BOOK, FILM.work_id)

    books.fill.assert_called_once_with(BOOK, {})


def test_a_pick_makes_both_writes_in_one_transaction():
    books, open_library, transaction = MagicMock(), MagicMock(), MagicMock()
    open_library.search.return_value = [FILM]
    writes = MagicMock()
    writes.attach_mock(transaction.atomic.return_value.__enter__, "begin")
    writes.attach_mock(books.set_work, "set_work")
    writes.attach_mock(books.fill, "fill")
    writes.attach_mock(transaction.atomic.return_value.__exit__, "end")

    WorkService(
        books=books,
        syncs=MagicMock(),
        open_library=open_library,
        transaction=transaction,
    ).pick(BOOK, FILM.work_id)

    assert [name for name, _args, _kwargs in writes.mock_calls] == [
        "begin",
        "set_work",
        "fill",
        "end",
    ]


def test_a_pick_of_a_work_without_a_cover_asks_for_no_image():
    service, books, open_library = _service(found=[[FILM]])

    service.pick(BOOK, FILM.work_id)

    open_library.cover.assert_not_called()
    assert books.set_work.call_args.args[1]["cover"] is None


def test_a_pick_of_a_work_open_library_lacks_changes_nothing():
    service, books, _open_library = _service(found=[[]])

    with pytest.raises(NotFoundError, match="no work OL9W"):
        service.pick(BOOK, "OL9W")

    books.set_work.assert_not_called()


@pytest.mark.parametrize("work_id", ("", "45804", "OL45804W/../x"))
def test_a_pick_of_something_that_is_no_work_id_asks_open_library_nothing(work_id):
    service, books, open_library = _service()

    with pytest.raises(NotFoundError, match="not an Open Library work id"):
        service.pick(BOOK, work_id)

    open_library.search.assert_not_called()
    books.set_work.assert_not_called()


def test_a_failed_search_still_gives_the_book_and_what_was_found():
    service, _books, open_library = _service(isbn13="9780140328721")
    open_library.search.side_effect = [[FOX], OpenLibraryError("no answer")]

    candidates = service.candidates(BOOK)

    assert candidates == CandidatesDTO(
        book_id=BOOK,
        title="mr fox",
        authors=("Dahl",),
        query="mr fox Dahl",
        works=(FOX,),
        failure="no answer",
    )


def test_a_pick_for_a_book_the_library_lacks_asks_open_library_nothing():
    service, books, open_library = _service()
    books.fields.side_effect = NotFoundError

    with pytest.raises(NotFoundError):
        service.pick(BOOK, FOX.work_id)

    open_library.search.assert_not_called()
