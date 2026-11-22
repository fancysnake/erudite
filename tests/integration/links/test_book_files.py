import hashlib
import zipfile
from pathlib import Path

import pytest

from erudite.links.book_files.disk import DiskBookFiles
from erudite.pacts import FileScanError
from tests.book_files import (
    add_package,
    container_xml,
    package_xml,
    write_epub,
    write_pdf,
)

NOTHING = {"title": "", "authors": [], "isbn": ""}


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_find_maps_the_hash_of_every_file_below_the_directory(tmp_path):
    (tmp_path / "shelf").mkdir()
    mort = write_epub(tmp_path / "shelf" / "mort.EPUB", title="Mort")
    dune = write_pdf(tmp_path / "dune.pdf", Title="Dune")
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"not a book")
    (tmp_path / "folder.pdf").mkdir()

    found = DiskBookFiles().find(tmp_path)

    assert found == {_hash(cover): cover, _hash(dune): dune, _hash(mort): mort}


def test_find_keeps_the_first_path_of_files_with_equal_content(tmp_path):
    first = write_epub(tmp_path / "a.epub", title="Mort")
    (tmp_path / "b.epub").write_bytes(first.read_bytes())

    assert DiskBookFiles().find(tmp_path) == {_hash(first): first}


def test_find_returns_absolute_paths(tmp_path, monkeypatch):
    mort = write_epub(tmp_path / "mort.epub", title="Mort")
    monkeypatch.chdir(tmp_path)

    assert list(DiskBookFiles().find(Path()).values()) == [mort]


def test_find_rejects_a_path_that_is_no_directory(tmp_path):
    with pytest.raises(FileScanError, match=r"missing: not a directory\.$"):
        DiskBookFiles().find(tmp_path / "missing")


def test_find_reports_a_file_it_cannot_open(tmp_path):
    write_epub(tmp_path / "mort.epub", title="Mort").chmod(0)

    with pytest.raises(FileScanError, match="Permission denied"):
        DiskBookFiles().find(tmp_path)


def test_an_epub_gives_its_title_authors_and_isbn(tmp_path):
    path = write_epub(
        tmp_path / "omens.epub",
        title="Good  Omens",
        creators=["Terry Pratchett", " ", "Neil Gaiman"],
        identifiers=["urn:uuid:1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed", "0-552-13703-0"],
    )

    assert DiskBookFiles().read(path) == {
        "title": "Good Omens",
        "authors": ["Terry Pratchett", "Neil Gaiman"],
        "isbn": "0552137030",
    }


@pytest.mark.parametrize(
    ("identifier", "isbn"),
    (
        ("urn:isbn:978-0-552-13106-3", "9780552131063"),
        ("ISBN:055213106x", "055213106X"),
        (" 978 0552131063 ", "9780552131063"),
        ("1234567890123", ""),
        ("urn:uuid:1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed", ""),
        ("B000FC1PJI", ""),
    ),
)
def test_an_epub_identifier_counts_only_when_it_is_an_isbn(
    tmp_path, *, identifier, isbn
):
    path = write_epub(tmp_path / "mort.epub", identifiers=[identifier])

    assert DiskBookFiles().read(path) == NOTHING | {"isbn": isbn}


def test_an_epub_without_a_package_document_gives_nothing(tmp_path):
    path = write_epub(tmp_path / "mort.epub", package=None)

    assert DiskBookFiles().read(path) == NOTHING


@pytest.mark.parametrize("content", (b"not a zip archive", b"%PDF-1.7 not a pdf"))
@pytest.mark.parametrize("suffix", (".epub", ".pdf"))
def test_a_damaged_file_gives_nothing(tmp_path, *, content, suffix):
    path = tmp_path / f"mort{suffix}"
    path.write_bytes(content)

    assert DiskBookFiles().read(path) == NOTHING


@pytest.mark.parametrize(
    "package",
    ("<package><metadata>", '<!DOCTYPE p [<!ENTITY a "aaaa">]><package>&a;</package>'),
)
def test_an_epub_with_a_bad_package_document_gives_nothing(tmp_path, *, package):
    path = write_epub(tmp_path / "mort.epub", package=None)
    add_package(path, "book.opf", xml=package)

    assert DiskBookFiles().read(path) == NOTHING


def test_an_epub_takes_the_package_document_its_container_names(tmp_path):
    path = write_epub(tmp_path / "mort.epub", package=None)
    add_package(path, "a.opf", xml=package_xml(title="Decoy"), declared=False)
    add_package(path, "b.opf", xml=package_xml(title="Mort"))

    assert DiskBookFiles().read(path) == NOTHING | {"title": "Mort"}


def test_an_epub_whose_package_document_is_not_named_gives_nothing(tmp_path):
    path = write_epub(tmp_path / "mort.epub", package=None)
    add_package(path, "book.opf", xml=package_xml(title="Mort"), declared=False)

    assert DiskBookFiles().read(path) == NOTHING


def test_an_epub_whose_container_names_a_missing_file_gives_nothing(tmp_path):
    path = write_epub(tmp_path / "mort.epub", package=None)
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("META-INF/container.xml", container_xml("missing.opf"))

    assert DiskBookFiles().read(path) == NOTHING


def test_an_epub_whose_container_names_no_package_document_gives_nothing(tmp_path):
    path = write_epub(tmp_path / "mort.epub", package=None)
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr(
            "META-INF/container.xml",
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"/>',
        )

    assert DiskBookFiles().read(path) == NOTHING


def test_a_file_of_another_format_gives_nothing_and_is_not_opened(tmp_path):
    assert DiskBookFiles().read(tmp_path / "missing.zip") == NOTHING


@pytest.mark.parametrize("suffix", (".epub", ".pdf"))
def test_read_reports_a_file_that_is_gone(tmp_path, *, suffix):
    with pytest.raises(FileScanError, match=r"mort\.\w+: .*No such file"):
        DiskBookFiles().read(tmp_path / f"mort{suffix}")


def test_every_unreadable_file_gives_its_own_empty_result(tmp_path):
    first = DiskBookFiles().read(write_epub(tmp_path / "a.epub", package=None))
    first["authors"].append("Terry Pratchett")

    assert (
        DiskBookFiles().read(write_epub(tmp_path / "b.epub", package=None)) == NOTHING
    )


def test_a_pdf_gives_its_title_and_author_tags(tmp_path):
    path = write_pdf(
        tmp_path / "omens.pdf",
        Title=" Good Omens ",
        Author="Terry Pratchett; Neil Gaiman",
        Creator="LaTeX with hyperref",
        bookmarks=["Not the title"],
    )

    assert DiskBookFiles().read(path) == {
        "title": "Good Omens",
        "authors": ["Terry Pratchett", "Neil Gaiman"],
        "isbn": "",
    }


@pytest.mark.parametrize(
    ("bookmarks", "title"),
    ((["Mort"], "Mort"), (["Chapter 1", "Chapter 2"], ""), ([], "")),
)
def test_a_pdf_without_a_title_tag_takes_its_only_top_bookmark(
    tmp_path, *, bookmarks, title
):
    path = write_pdf(tmp_path / "mort.pdf", Creator="Word", bookmarks=bookmarks)

    assert DiskBookFiles().read(path) == NOTHING | {"title": title}


def test_a_pdf_without_tags_gives_nothing(tmp_path):
    path = write_pdf(tmp_path / "mort.pdf")

    assert DiskBookFiles().read(path) == NOTHING


def test_exists_is_true_for_a_file_only(tmp_path):
    path = write_epub(tmp_path / "mort.epub")

    assert DiskBookFiles().exists(path)
    assert not DiskBookFiles().exists(tmp_path)
    assert not DiskBookFiles().exists(tmp_path / "missing.epub")
