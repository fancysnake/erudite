from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from erudite.links.db.django.models import BookFile, IgnoredExtension
from tests.book_files import write_epub, write_pdf

pytestmark = pytest.mark.django_db


def _run(*args):
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


@pytest.fixture(name="shelf")
def shelf_fixture(tmp_path):
    write_epub(
        tmp_path / "mort.epub",
        title="Mort",
        creators=["Terry Pratchett"],
        identifiers=["urn:isbn:9780552131063"],
    )
    write_pdf(tmp_path / "scan_0042.pdf", Creator="Word")
    return tmp_path


def _contents(directory):
    return {path: path.read_bytes() for path in directory.iterdir()}


def test_every_file_appears_once_and_no_file_changes(shelf):
    before = _contents(shelf)

    output = _run("scan_files", str(shelf))

    assert output == "Files added: 2. Already known: 0.\n"
    assert list(BookFile.objects.values_list("title", "authors", "isbn", "path")) == [
        ("Mort", ["Terry Pratchett"], "9780552131063", str(shelf / "mort.epub")),
        ("scan_0042", [], "", str(shelf / "scan_0042.pdf")),
    ]
    assert _contents(shelf) == before


def test_a_second_scan_adds_nothing_and_keeps_what_the_user_changed(shelf):
    _run("scan_files", str(shelf))
    BookFile.objects.filter(title="scan_0042").update(title="Dune")
    before = list(BookFile.objects.values())

    output = _run("scan_files", str(shelf))

    assert output == "Files added: 0. Already known: 2.\n"
    assert list(BookFile.objects.values()) == before


def test_a_renamed_file_keeps_its_record_under_the_new_path(shelf):
    _run("scan_files", str(shelf))
    (shelf / "mort.epub").rename(shelf / "pratchett-mort.epub")

    output = _run("scan_files", str(shelf))

    assert output == "Files added: 0. Already known: 2.\n"
    assert BookFile.objects.get(title="Mort").path == str(shelf / "pratchett-mort.epub")


def test_every_file_is_recorded_and_an_ignored_extension_marks_its_files(shelf):
    (shelf / "cover.png").write_bytes(b"image")
    (shelf / "comics.zip").write_bytes(b"archive")
    IgnoredExtension.objects.create(extension="png")

    output = _run("scan_files", str(shelf))

    assert output == "Files added: 4. Already known: 0.\n"
    assert list(BookFile.objects.values_list("title", "ignored")) == [
        ("Mort", False),
        ("comics", False),
        ("cover", True),
        ("scan_0042", False),
    ]


def test_a_later_scan_leaves_the_ignored_choice_of_a_known_file_alone(shelf):
    IgnoredExtension.objects.create(extension="pdf")
    _run("scan_files", str(shelf))
    BookFile.objects.filter(title="scan_0042").update(ignored=False)
    IgnoredExtension.objects.create(extension="epub")

    _run("scan_files", str(shelf))

    assert not BookFile.objects.filter(ignored=True).exists()


def test_a_path_that_is_no_directory_is_an_error(tmp_path):
    with pytest.raises(CommandError, match=r"missing: not a directory\.$"):
        call_command("scan_files", str(tmp_path / "missing"))
    assert not BookFile.objects.exists()
