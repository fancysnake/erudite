import zipfile

from pypdf import PdfWriter

_PACKAGE = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">{}</metadata>
</package>"""


def write_epub(
    path, *, title="", creators=(), identifiers=(), package="OEBPS/book.opf"
):
    """Write an EPUB with this metadata; `package=None` leaves the metadata out."""
    fields = [("title", title)] if title else []
    fields += [("creator", name) for name in creators]
    fields += [("identifier", value) for value in identifiers]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        if package:
            archive.writestr(
                package,
                _PACKAGE.format("".join(f"<dc:{k}>{v}</dc:{k}>" for k, v in fields)),
            )
    return path


def write_pdf(path, *, bookmarks=(), **tags):
    """Write a one-page PDF with these tags (`Title`, `Author`) and top bookmarks."""
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    if tags:
        writer.add_metadata({f"/{name}": value for name, value in tags.items()})
    for bookmark in bookmarks:
        parent = writer.add_outline_item(title=bookmark, page_number=0)
        writer.add_outline_item(
            title=f"{bookmark}, part one", page_number=0, parent=parent
        )
    writer.write(path)
    return path
