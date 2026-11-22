from pathlib import Path
from unittest.mock import MagicMock

from erudite.mills import LibraryService
from erudite.pacts import ImportSummaryDTO

EXPORT = Path("goodreads_library_export.csv")
MORT = {"goodreads_id": 386372, "title": "Mort"}
DUNE = {"goodreads_id": 44767458, "title": "Dune"}


def _service(*, exported=(), known=()):
    books = MagicMock()
    books.goodreads_ids.return_value = set(known)
    goodreads = MagicMock()
    goodreads.read.return_value = list(exported)
    service = LibraryService(
        books=books, goodreads=goodreads, files=MagicMock(), disk=MagicMock()
    )
    return service, books, goodreads


def test_the_book_count_is_the_repository_count():
    service, books, _ = _service()

    assert service.book_count() is books.count.return_value


def test_a_first_import_adds_every_book():
    service, books, goodreads = _service(exported=[MORT, DUNE])

    summary = service.import_goodreads(EXPORT)

    assert summary == ImportSummaryDTO(created=2, skipped=0)
    goodreads.read.assert_called_once_with(EXPORT)
    books.create_from_goodreads.assert_called_once_with([MORT, DUNE])


def test_a_book_already_in_the_library_is_skipped():
    service, books, _ = _service(exported=[MORT, DUNE], known=[386372])

    summary = service.import_goodreads(EXPORT)

    assert summary == ImportSummaryDTO(created=1, skipped=1)
    books.create_from_goodreads.assert_called_once_with([DUNE])


def test_a_book_listed_twice_is_added_once_as_its_last_line():
    again = MORT | {"title": "Mort, again"}
    service, books, _ = _service(exported=[MORT, DUNE, again])

    summary = service.import_goodreads(EXPORT)

    assert summary == ImportSummaryDTO(created=2, skipped=0)
    books.create_from_goodreads.assert_called_once_with([again, DUNE])


SHELF = Path("/books")
MORT_FILE = SHELF / "mort.epub"
DUNE_FILE = SHELF / "scan_0042.pdf"
MORT_METADATA = {"title": "Mort", "authors": ["Terry Pratchett"], "isbn": "0552131067"}
NO_METADATA = {"title": "", "authors": [], "isbn": ""}


def _scanner(*, found, known=None, on_disk=()):
    files = MagicMock()
    files.paths.return_value = known or {}
    disk = MagicMock()
    disk.find.return_value = found
    disk.read.side_effect = lambda path: (
        MORT_METADATA if path == MORT_FILE else NO_METADATA
    )
    disk.exists.side_effect = lambda path: path in on_disk
    service = LibraryService(
        books=MagicMock(), goodreads=MagicMock(), files=files, disk=disk
    )
    return service, files, disk


def test_a_first_scan_adds_every_file_with_its_metadata():
    service, files, disk = _scanner(found={"aa": MORT_FILE})

    summary = service.scan_files(SHELF)

    assert summary == ImportSummaryDTO(created=1, skipped=0)
    disk.find.assert_called_once_with(SHELF)
    files.create.assert_called_once_with(
        [{"path": MORT_FILE, "content_hash": "aa"} | MORT_METADATA]
    )
    files.move.assert_not_called()


def test_a_file_that_gives_no_title_takes_its_file_name():
    service, files, _ = _scanner(found={"bb": DUNE_FILE})

    service.scan_files(SHELF)

    files.create.assert_called_once_with(
        [
            {"path": DUNE_FILE, "content_hash": "bb"}
            | NO_METADATA
            | {"title": "scan_0042"}
        ]
    )


def test_a_known_file_is_skipped_and_not_read_again():
    service, files, disk = _scanner(
        found={"aa": MORT_FILE, "bb": DUNE_FILE}, known={"aa": MORT_FILE}
    )

    summary = service.scan_files(SHELF)

    assert summary == ImportSummaryDTO(created=1, skipped=1)
    disk.read.assert_called_once_with(DUNE_FILE)
    disk.exists.assert_not_called()
    files.move.assert_not_called()


def test_a_known_file_that_moved_gets_its_new_path():
    old = SHELF / "unsorted" / "mort.epub"
    service, files, _ = _scanner(found={"aa": MORT_FILE}, known={"aa": old})

    summary = service.scan_files(SHELF)

    assert summary == ImportSummaryDTO(created=0, skipped=1)
    files.move.assert_called_once_with("aa", MORT_FILE)
    files.create.assert_called_once_with([])


def test_a_copy_of_a_known_file_leaves_the_stored_path_alone():
    old = Path("/elsewhere/mort.epub")
    service, files, disk = _scanner(
        found={"aa": MORT_FILE}, known={"aa": old}, on_disk=[old]
    )

    service.scan_files(SHELF)

    disk.exists.assert_called_once_with(old)
    files.move.assert_not_called()
