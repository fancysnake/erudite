from pathlib import Path
from unittest.mock import MagicMock

import pytest

from erudite.mills import LibraryService
from erudite.pacts import (
    BookListDTO,
    BookSource,
    NotFoundError,
    SyncProgressDTO,
    SyncSummaryDTO,
    SyncType,
)

EXPORT = Path("goodreads_library_export.csv")
MORT = {"key": "386372", "title": "Mort"}
DUNE = {"key": "44767458", "title": "Dune"}


def _asked(**changed):
    return {"query": "", "page": 1, "size": 10, "done": (), "todo": ()} | changed


def _service(*, exported=(), known=()):
    books = MagicMock()
    books.keys.return_value = set(known)
    goodreads = MagicMock()
    goodreads.read.return_value = list(exported)
    service = LibraryService(books=books, syncs=MagicMock(), goodreads=goodreads)
    return service, books, goodreads


@pytest.mark.parametrize(
    ("found", "page", "shown", "pages"),
    (
        (0, 1, [], 1),
        (10, 1, list(range(10)), 1),
        (11, 1, list(range(10)), 2),
        (11, 2, [10], 2),
    ),
)
def test_the_book_list_is_one_page_of_the_books_found(*, found, page, shown, pages):
    service, books, _ = _service()
    books.search.return_value = list(range(found))

    listed = service.books(_asked(query=" mort ", page=page))

    assert listed == BookListDTO(
        query="mort", size=10, books=tuple(shown), total=found, page=page, pages=pages
    )
    books.search.assert_called_once_with("mort", done=(), todo=())


@pytest.mark.parametrize(("found", "page"), ((0, 0), (0, 2), (10, 2), (11, 3)))
def test_the_book_list_has_no_page_outside_the_books_found(*, found, page):
    service, books, _ = _service()
    books.search.return_value = list(range(found))

    with pytest.raises(NotFoundError, match=f"no page {page}"):
        service.books(_asked(page=page))


@pytest.mark.parametrize("size", (0, 7, 1000))
def test_the_book_list_has_only_the_page_sizes_the_user_may_set(size):
    service, books, _ = _service()

    with pytest.raises(NotFoundError, match=f"no pages of {size} books"):
        service.books(_asked(size=size))
    books.search.assert_not_called()


def test_the_book_list_keeps_the_books_the_sync_filters_name():
    service, books, _ = _service()
    books.search.return_value = []

    service.books(_asked(done=(SyncType.OPEN_LIBRARY,), todo=(SyncType.FILE,)))

    books.search.assert_called_once_with(
        "", done=(SyncType.OPEN_LIBRARY,), todo=(SyncType.FILE,)
    )


def test_the_sync_progress_counts_the_books_each_sync_reached():
    books, syncs = MagicMock(), MagicMock()
    books.count.return_value = 5
    syncs.counts.return_value = {SyncType.OPEN_LIBRARY: 2}
    service = LibraryService(books=books, syncs=syncs, goodreads=MagicMock())

    assert service.sync_progress() == (
        SyncProgressDTO(sync=SyncType.GOODREADS, done=0, total=5),
        SyncProgressDTO(sync=SyncType.FILE, done=0, total=5),
        SyncProgressDTO(sync=SyncType.OPEN_LIBRARY, done=2, total=5),
    )


def test_a_book_is_the_one_the_repository_holds():
    service, books, _ = _service()

    assert service.book(7) is books.get.return_value
    books.get.assert_called_once_with(7)


def test_a_first_import_adds_every_book():
    service, books, goodreads = _service(exported=[MORT, DUNE])

    summary = service.import_goodreads(EXPORT)

    assert summary == SyncSummaryDTO(created=2, skipped=0)
    goodreads.read.assert_called_once_with(EXPORT)
    books.keys.assert_called_once_with(BookSource.GOODREADS)
    books.create.assert_called_once_with([MORT, DUNE])


def test_a_book_already_in_the_library_is_skipped():
    service, books, _ = _service(exported=[MORT, DUNE], known=["386372"])

    summary = service.import_goodreads(EXPORT)

    assert summary == SyncSummaryDTO(created=1, skipped=1)
    books.create.assert_called_once_with([DUNE])


def test_a_book_listed_twice_is_added_once_as_its_last_line():
    again = MORT | {"title": "Mort, again"}
    service, books, _ = _service(exported=[MORT, DUNE, again])

    summary = service.import_goodreads(EXPORT)

    assert summary == SyncSummaryDTO(created=2, skipped=0)
    books.create.assert_called_once_with([again, DUNE])
