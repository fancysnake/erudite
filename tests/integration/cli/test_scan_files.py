from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from erudite.links.db.django.models import Book, IgnoredExtension, RawBook
from erudite.pacts import BookSource, ReadingStatus
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


def test_every_file_becomes_a_book_once_and_no_file_changes(shelf):
    before = _contents(shelf)

    output = _run("scan_files", str(shelf))

    assert output == "Files added: 2. Already known: 0.\n"
    assert list(
        RawBook.objects.values_list("source", "title", "authors", "isbn13", "path")
    ) == [
        (
            BookSource.FILE,
            "Mort",
            ["Terry Pratchett"],
            "9780552131063",
            str(shelf / "mort.epub"),
        ),
        (BookSource.FILE, "scan_0042", [], "", str(shelf / "scan_0042.pdf")),
    ]
    assert [
        (book.title, book.isbn13, book.status, [str(c) for c in book.credits.all()])
        for book in Book.objects.all()
    ] == [
        ("Mort", "9780552131063", ReadingStatus.TO_READ, ["Terry Pratchett"]),
        ("scan_0042", "", ReadingStatus.TO_READ, []),
    ]
    assert [raw.book.title for raw in RawBook.objects.all()] == ["Mort", "scan_0042"]
    assert _contents(shelf) == before


def test_a_second_scan_adds_nothing_and_keeps_what_the_user_changed(shelf):
    _run("scan_files", str(shelf))
    Book.objects.filter(title="scan_0042").update(title="Dune")
    books, raw_books = list(Book.objects.values()), list(RawBook.objects.values())

    output = _run("scan_files", str(shelf))

    assert output == "Files added: 0. Already known: 2.\n"
    assert list(Book.objects.values()) == books
    assert list(RawBook.objects.values()) == raw_books


def test_a_book_the_user_deleted_does_not_come_back(shelf):
    _run("scan_files", str(shelf))
    Book.objects.get(title="scan_0042").delete()

    output = _run("scan_files", str(shelf))

    assert output == "Files added: 0. Already known: 2.\n"
    assert [str(book) for book in Book.objects.all()] == ["Mort"]
    assert RawBook.objects.get(title="scan_0042").book is None


def test_a_renamed_file_keeps_its_raw_book_under_the_new_path(shelf):
    _run("scan_files", str(shelf))
    (shelf / "mort.epub").rename(shelf / "pratchett-mort.epub")

    output = _run("scan_files", str(shelf))

    assert output == "Files added: 0. Already known: 2.\n"
    assert RawBook.objects.get(title="Mort").path == str(shelf / "pratchett-mort.epub")
    assert Book.objects.count() == len(["Mort", "scan_0042"])


def test_a_file_with_an_ignored_extension_is_not_stored(shelf):
    (shelf / "cover.png").write_bytes(b"image")
    (shelf / "comics.zip").write_bytes(b"archive")
    IgnoredExtension.objects.create(extension="png")

    output = _run("scan_files", str(shelf))

    assert output == "Files added: 3. Already known: 0.\n"
    titles = ["Mort", "comics", "scan_0042"]
    assert [str(raw) for raw in RawBook.objects.all()] == titles
    assert [str(book) for book in Book.objects.all()] == titles


def test_a_later_scan_keeps_a_known_file_whose_extension_became_ignored(shelf):
    _run("scan_files", str(shelf))
    IgnoredExtension.objects.create(extension="epub")

    output = _run("scan_files", str(shelf))

    assert output == "Files added: 0. Already known: 2.\n"
    assert RawBook.objects.filter(title="Mort").exists()


def test_a_path_that_is_no_directory_is_an_error(tmp_path):
    with pytest.raises(CommandError, match=r"missing: not a directory\.$"):
        call_command("scan_files", str(tmp_path / "missing"))
    assert not RawBook.objects.exists()
