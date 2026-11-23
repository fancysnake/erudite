"""Files in a directory on this machine, opened for reading only."""

import hashlib
import re
import zipfile
import zlib
from typing import TYPE_CHECKING, override

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from erudite.pacts import BookFileMetadata, DiskBookFilesProtocol, FileScanError

if TYPE_CHECKING:
    from pathlib import Path
    from xml.etree.ElementTree import Element

_DUBLIN_CORE = "{http://purl.org/dc/elements/1.1/}"
_ISBN10 = re.compile(r"\d{9}[\dX]")
_ISBN13 = re.compile(r"97[89]\d{10}")
_ISBN_PREFIX = re.compile(r"^(urn:)?isbn:", re.IGNORECASE)
_CONTAINER = "META-INF/container.xml"
_OCF = "{urn:oasis:names:tc:opendocument:xmlns:container}"


def _nothing() -> BookFileMetadata:
    return BookFileMetadata(title="", authors=[], isbn10="", isbn13="")


def _squeeze(value: str | None) -> str:
    return " ".join((value or "").split())


def _digits(identifier: str) -> str:
    """`urn:isbn:978-0-552-13106-3` → `9780552131063`."""
    return re.sub(r"[\s-]", "", _ISBN_PREFIX.sub("", identifier.strip())).upper()


def _first_match(pattern: re.Pattern[str], identifiers: list[str]) -> str:
    return next((d for i in identifiers if pattern.fullmatch(d := _digits(i))), "")


def _xml(archive: zipfile.ZipFile, name: str) -> Element | None:
    try:
        data = archive.read(name)
    except KeyError:
        return None
    return ElementTree.fromstring(data)


def _package(archive: zipfile.ZipFile) -> Element | None:
    """Return the package document that the container names; it holds the metadata."""
    if (container := _xml(archive, _CONTAINER)) is None:
        return None
    if (rootfile := container.find(f".//{_OCF}rootfile")) is None:
        return None
    return _xml(archive, rootfile.get("full-path", ""))


def _epub(path: Path) -> BookFileMetadata:
    with zipfile.ZipFile(path) as archive:
        package = _package(archive)
    if package is None:
        return _nothing()

    def texts(tag: str) -> list[str]:
        found = (_squeeze(node.text) for node in package.iter(_DUBLIN_CORE + tag))
        return [text for text in found if text]

    identifiers = texts("identifier")
    return BookFileMetadata(
        title=next(iter(texts("title")), ""),
        authors=texts("creator"),
        isbn10=_first_match(_ISBN10, identifiers),
        isbn13=_first_match(_ISBN13, identifiers),
    )


def _pdf_title(reader: PdfReader) -> str:
    if title := _squeeze(reader.metadata.title if reader.metadata else ""):
        return title
    # One top bookmark names the book; several name its chapters.
    top = [item for item in reader.outline if not isinstance(item, list)]
    return _squeeze(top[0].title) if len(top) == 1 else ""


def _pdf(path: Path) -> BookFileMetadata:
    reader = PdfReader(path)
    author = (reader.metadata.author if reader.metadata else "") or ""
    return BookFileMetadata(
        title=_pdf_title(reader),
        authors=[name for part in author.split(";") if (name := _squeeze(part))],
        isbn10="",
        isbn13="",
    )


# What each parser raises for a damaged file, beyond the OSError of a failed read.
_EPUB_ERRORS = (
    zipfile.BadZipFile,
    zlib.error,
    EOFError,
    ElementTree.ParseError,
    DefusedXmlException,
)
_PDF_ERRORS = (PyPdfError, ValueError, KeyError, TypeError)
_READERS = {".epub": (_epub, _EPUB_ERRORS), ".pdf": (_pdf, _PDF_ERRORS)}


def _by_hash(directory: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in sorted(directory.resolve().rglob("*")):
        if path.is_file():
            with path.open("rb") as file:
                content_hash = hashlib.file_digest(file, "sha256").hexdigest()
            found.setdefault(content_hash, path)
    return found


class DiskBookFiles(DiskBookFilesProtocol):
    @override
    def find(self, directory: Path) -> dict[str, Path]:
        if not directory.is_dir():
            msg = f"{directory}: not a directory."
            raise FileScanError(msg)
        try:
            return _by_hash(directory)
        except OSError as exc:
            msg = f"{directory}: {exc}"
            raise FileScanError(msg) from exc

    @override
    def read(self, path: Path) -> BookFileMetadata:
        if (found := _READERS.get(path.suffix.lower())) is None:
            return _nothing()
        reader, damaged = found
        try:
            return reader(path)
        except damaged:
            # A damaged file is still a file the user owns.
            return _nothing()
        except OSError as exc:
            msg = f"{path}: {exc}"
            raise FileScanError(msg) from exc

    @override
    def exists(self, path: Path) -> bool:
        return path.is_file()
