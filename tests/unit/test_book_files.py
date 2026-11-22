from pathlib import Path
from unittest.mock import MagicMock

import pytest

from erudite.mills import BookFilesService
from erudite.pacts import BookSource, SyncSummaryDTO

SHELF = Path("/books")
MORT_FILE = SHELF / "mort.epub"
DUNE_FILE = SHELF / "scan_0042.pdf"
MORT_METADATA = {"title": "Mort", "authors": ["Terry Pratchett"], "isbn": "0552131067"}
NO_METADATA = {"title": "", "authors": [], "isbn": ""}
MORT_BOOK = {
    "source": BookSource.FILE,
    "key": "aa",
    "title": "Mort",
    "authors": ["Terry Pratchett"],
    "path": MORT_FILE,
    "isbn10": "0552131067",
}


def _scanner(*, found, known=None, on_disk=(), ignored=(), metadata=None):
    books = MagicMock()
    books.file_paths.return_value = known or {}
    books.ignored_extensions.return_value = set(ignored)
    disk = MagicMock()
    disk.find.return_value = found
    disk.read.side_effect = lambda path: (
        (metadata or MORT_METADATA) if path == MORT_FILE else NO_METADATA
    )
    disk.exists.side_effect = lambda path: path in on_disk
    service = BookFilesService(books=books, disk=disk)
    return service, books, disk


def test_a_first_scan_adds_every_file_as_a_raw_book_with_its_metadata():
    service, books, disk = _scanner(found={"aa": MORT_FILE})

    summary = service.scan(SHELF)

    assert summary == SyncSummaryDTO(created=1, skipped=0)
    disk.find.assert_called_once_with(SHELF)
    books.create.assert_called_once_with([MORT_BOOK])
    books.move_file.assert_not_called()


def test_an_isbn_of_thirteen_digits_is_stored_as_isbn13():
    metadata = MORT_METADATA | {"isbn": "9780552131063"}
    service, books, _ = _scanner(found={"aa": MORT_FILE}, metadata=metadata)

    service.scan(SHELF)

    expected = {k: v for k, v in MORT_BOOK.items() if k != "isbn10"}
    books.create.assert_called_once_with([expected | {"isbn13": "9780552131063"}])


@pytest.mark.parametrize("path", (DUNE_FILE, SHELF / "Cover.PDF"))
def test_a_new_file_with_an_ignored_extension_is_left_out_and_not_read(path):
    service, books, disk = _scanner(
        found={"aa": MORT_FILE, "bb": path}, ignored=["pdf"]
    )

    summary = service.scan(SHELF)

    assert summary == SyncSummaryDTO(created=1, skipped=0)
    books.create.assert_called_once_with([MORT_BOOK])
    disk.read.assert_called_once_with(MORT_FILE)


def test_a_stored_file_stays_when_its_extension_becomes_ignored():
    service, books, _ = _scanner(
        found={"aa": MORT_FILE}, known={"aa": MORT_FILE}, ignored=["epub"]
    )

    summary = service.scan(SHELF)

    assert summary == SyncSummaryDTO(created=0, skipped=1)
    books.create.assert_called_once_with([])
    books.move_file.assert_not_called()


def test_a_file_that_gives_no_title_takes_its_file_name():
    service, books, _ = _scanner(found={"bb": DUNE_FILE})

    service.scan(SHELF)

    books.create.assert_called_once_with(
        [
            {
                "source": BookSource.FILE,
                "key": "bb",
                "title": "scan_0042",
                "authors": [],
                "path": DUNE_FILE,
            }
        ]
    )


def test_a_known_file_is_skipped_and_not_read_again():
    service, books, disk = _scanner(
        found={"aa": MORT_FILE, "bb": DUNE_FILE}, known={"aa": MORT_FILE}
    )

    summary = service.scan(SHELF)

    assert summary == SyncSummaryDTO(created=1, skipped=1)
    disk.read.assert_called_once_with(DUNE_FILE)
    disk.exists.assert_not_called()
    books.move_file.assert_not_called()


def test_a_known_file_that_moved_gets_its_new_path():
    old = SHELF / "unsorted" / "mort.epub"
    service, books, _ = _scanner(found={"aa": MORT_FILE}, known={"aa": old})

    summary = service.scan(SHELF)

    assert summary == SyncSummaryDTO(created=0, skipped=1)
    books.move_file.assert_called_once_with("aa", MORT_FILE)
    books.create.assert_called_once_with([])


def test_a_copy_of_a_known_file_leaves_the_stored_path_alone():
    old = Path("/elsewhere/mort.epub")
    service, books, disk = _scanner(
        found={"aa": MORT_FILE}, known={"aa": old}, on_disk=[old]
    )

    service.scan(SHELF)

    disk.exists.assert_called_once_with(old)
    books.move_file.assert_not_called()
