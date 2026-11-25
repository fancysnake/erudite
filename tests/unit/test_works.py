from unittest.mock import MagicMock, call

import pytest

from erudite.mills import WorkService
from erudite.pacts import CandidatesDTO, NotFoundError, WorkDTO
from tests.open_library import FOX_WORK as FOX

BOOK = 7
FILM = WorkDTO(
    work_id="OL2W",
    title="Fantastic Mr. Fox",
    authors=("Wes Anderson",),
    first_year=2016,
    cover_id=None,
    edition_count=1,
)


def _service(*, found=(), **held):
    books, open_library = MagicMock(), MagicMock()
    books.fields.return_value = {"title": "mr fox", "authors": ["Dahl"]} | held
    open_library.search.side_effect = [list(works) for works in found]
    return WorkService(books=books, open_library=open_library), books, open_library


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
    open_library.description.return_value = "A fox outwits three farmers."
    open_library.cover.return_value = b"a JPEG"

    service.pick(BOOK, FOX.work_id)

    open_library.search.assert_called_once_with("key:/works/OL45804W")
    open_library.description.assert_called_once_with(FOX.work_id)
    open_library.cover.assert_called_once_with(FOX.cover_id)
    books.set_work.assert_called_once_with(
        BOOK,
        {
            "work_id": FOX.work_id,
            "title": "Fantastic Mr Fox",
            "authors": ["Roald Dahl"],
            "description": "A fox outwits three farmers.",
            "cover": b"a JPEG",
        },
    )


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


def test_a_pick_for_a_book_the_library_lacks_asks_open_library_nothing():
    service, books, open_library = _service()
    books.fields.side_effect = NotFoundError

    with pytest.raises(NotFoundError):
        service.pick(BOOK, FOX.work_id)

    open_library.search.assert_not_called()
