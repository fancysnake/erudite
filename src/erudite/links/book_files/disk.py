"""EPUB and PDF files in a directory on this machine, opened for reading only."""

import hashlib
import re
import zipfile
from typing import TYPE_CHECKING, override

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from erudite.pacts import BookFileMetadata, BookFilesProtocol, FileScanError

if TYPE_CHECKING:
    from pathlib import Path

_DUBLIN_CORE = "{http://purl.org/dc/elements/1.1/}"
_ISBN = re.compile(r"97[89]\d{10}|\d{9}[\dX]")
_ISBN_PREFIX = re.compile(r"^(urn:)?isbn:", re.IGNORECASE)
_NOTHING = BookFileMetadata(title="", authors=[], isbn="")


def _squeeze(value: str | None) -> str:
    return " ".join((value or "").split())


def _isbn(identifier: str) -> str:
    """`urn:isbn:978-0-552-13106-3` → `9780552131063`; any other identifier → ``."""
    digits = re.sub(r"[\s-]", "", _ISBN_PREFIX.sub("", identifier.strip())).upper()
    return digits if _ISBN.fullmatch(digits) else ""


def _epub(path: Path) -> BookFileMetadata:
    with zipfile.ZipFile(path) as archive:
        # The package document holds the metadata; an EPUB has one.
        name = next((n for n in archive.namelist() if n.endswith(".opf")), None)
        if name is None:
            return _NOTHING
        package = ElementTree.fromstring(archive.read(name))

    def texts(tag: str) -> list[str]:
        found = (_squeeze(node.text) for node in package.iter(_DUBLIN_CORE + tag))
        return [text for text in found if text]

    return BookFileMetadata(
        title=next(iter(texts("title")), ""),
        authors=texts("creator"),
        isbn=next((isbn for text in texts("identifier") if (isbn := _isbn(text))), ""),
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
        isbn="",
    )


_READERS = {".epub": _epub, ".pdf": _pdf}


def _by_hash(directory: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in sorted(directory.resolve().rglob("*")):
        if path.suffix.lower() in _READERS and path.is_file():
            with path.open("rb") as file:
                content_hash = hashlib.file_digest(file, "sha256").hexdigest()
            found.setdefault(content_hash, path)
    return found


class DiskBookFiles(BookFilesProtocol):
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
        try:
            return _READERS[path.suffix.lower()](path)
        except (
            zipfile.BadZipFile,
            ElementTree.ParseError,
            DefusedXmlException,
            PyPdfError,
        ):
            # A damaged file is still a file the user owns.
            return _NOTHING

    @override
    def exists(self, path: Path) -> bool:
        return path.is_file()
