from pathlib import Path
from unittest.mock import MagicMock

from erudite.mills import BookFilesService
from erudite.pacts import ImportSummaryDTO

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
    service = BookFilesService(files=files, disk=disk)
    return service, files, disk


def test_a_first_scan_adds_every_file_with_its_metadata():
    service, files, disk = _scanner(found={"aa": MORT_FILE})

    summary = service.scan(SHELF)

    assert summary == ImportSummaryDTO(created=1, skipped=0)
    disk.find.assert_called_once_with(SHELF)
    files.create.assert_called_once_with(
        [{"path": MORT_FILE, "content_hash": "aa"} | MORT_METADATA]
    )
    files.move.assert_not_called()


def test_a_scan_marks_the_files_with_an_ignored_extension_after_it_adds_files():
    service, files, _ = _scanner(found={"aa": MORT_FILE})

    service.scan(SHELF)

    assert [call[0] for call in files.method_calls] == [
        "paths",
        "create",
        "ignore_by_extension",
    ]


def test_a_file_that_gives_no_title_takes_its_file_name():
    service, files, _ = _scanner(found={"bb": DUNE_FILE})

    service.scan(SHELF)

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

    summary = service.scan(SHELF)

    assert summary == ImportSummaryDTO(created=1, skipped=1)
    disk.read.assert_called_once_with(DUNE_FILE)
    disk.exists.assert_not_called()
    files.move.assert_not_called()


def test_a_known_file_that_moved_gets_its_new_path():
    old = SHELF / "unsorted" / "mort.epub"
    service, files, _ = _scanner(found={"aa": MORT_FILE}, known={"aa": old})

    summary = service.scan(SHELF)

    assert summary == ImportSummaryDTO(created=0, skipped=1)
    files.move.assert_called_once_with("aa", MORT_FILE)
    files.create.assert_called_once_with([])


def test_a_copy_of_a_known_file_leaves_the_stored_path_alone():
    old = Path("/elsewhere/mort.epub")
    service, files, disk = _scanner(
        found={"aa": MORT_FILE}, known={"aa": old}, on_disk=[old]
    )

    service.scan(SHELF)

    disk.exists.assert_called_once_with(old)
    files.move.assert_not_called()
