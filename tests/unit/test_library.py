from pathlib import Path
from unittest.mock import MagicMock

from erudite.mills import LibraryService
from erudite.pacts import SyncSummaryDTO

EXPORT = Path("goodreads_library_export.csv")
MORT = {"goodreads_id": 386372, "title": "Mort"}
DUNE = {"goodreads_id": 44767458, "title": "Dune"}


def _service(*, exported=(), known=()):
    books = MagicMock()
    books.goodreads_ids.return_value = set(known)
    goodreads = MagicMock()
    goodreads.read.return_value = list(exported)
    service = LibraryService(books=books, goodreads=goodreads)
    return service, books, goodreads


def test_the_book_count_is_the_repository_count():
    service, books, _ = _service()

    assert service.book_count() is books.count.return_value


def test_a_first_import_adds_every_book():
    service, books, goodreads = _service(exported=[MORT, DUNE])

    summary = service.import_goodreads(EXPORT)

    assert summary == SyncSummaryDTO(created=2, skipped=0)
    goodreads.read.assert_called_once_with(EXPORT)
    books.create_from_goodreads.assert_called_once_with([MORT, DUNE])


def test_a_book_already_in_the_library_is_skipped():
    service, books, _ = _service(exported=[MORT, DUNE], known=[386372])

    summary = service.import_goodreads(EXPORT)

    assert summary == SyncSummaryDTO(created=1, skipped=1)
    books.create_from_goodreads.assert_called_once_with([DUNE])


def test_a_book_listed_twice_is_added_once_as_its_last_line():
    again = MORT | {"title": "Mort, again"}
    service, books, _ = _service(exported=[MORT, DUNE, again])

    summary = service.import_goodreads(EXPORT)

    assert summary == SyncSummaryDTO(created=2, skipped=0)
    books.create_from_goodreads.assert_called_once_with([again, DUNE])
