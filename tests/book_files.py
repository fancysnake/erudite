import zipfile

from pypdf import PdfWriter

_PACKAGE = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">{}</metadata>
</package>"""

_CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="{}" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""


def package_xml(*, title="", creators=(), identifiers=()):
    fields = [("title", title)] if title else []
    fields += [("creator", name) for name in creators]
    fields += [("identifier", value) for value in identifiers]
    return _PACKAGE.format("".join(f"<dc:{k}>{v}</dc:{k}>" for k, v in fields))


def container_xml(package):
    """Return the container file that names `package` as the package document."""
    return _CONTAINER.format(package)


def add_package(path, name, *, xml, declared=True):
    """Add the package document `xml`; `declared` names it in the container."""
    with zipfile.ZipFile(path, "a") as archive:
        if declared:
            archive.writestr("META-INF/container.xml", container_xml(name))
        archive.writestr(name, xml)


def write_epub(
    path, *, title="", creators=(), identifiers=(), package="OEBPS/book.opf"
):
    """Write an EPUB with this metadata; `package=None` leaves the metadata out."""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
    if package:
        xml = package_xml(title=title, creators=creators, identifiers=identifiers)
        add_package(path, package, xml=xml)
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


def damage_epub(path, *, member="META-INF/container.xml"):
    """Overwrite the start of one member's compressed data with an invalid block."""
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo(member)
    with path.open("r+b") as file:
        file.seek(info.header_offset + 26)
        name_size, extra_size = int.from_bytes(file.read(2), "little"), int.from_bytes(
            file.read(2), "little"
        )
        file.seek(info.header_offset + 30 + name_size + extra_size)
        file.write(b"\xff" * 4)
    return path


def write_deflated_epub(path, *, title="Mort"):
    """Write an EPUB whose members are compressed, so their data can be damaged."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("META-INF/container.xml", container_xml("book.opf"))
        archive.writestr("book.opf", package_xml(title=title))
    return path
