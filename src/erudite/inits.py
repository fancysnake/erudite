"""Composition root: builds the services and hands them to the request."""

from functools import cached_property
from typing import TYPE_CHECKING

from erudite.links.book_files.disk import DiskBookFiles
from erudite.links.db.django.repositories import (
    BookRepository,
    DecisionRepository,
    IgnoredExtensions,
)
from erudite.links.goodreads.csv import GoodreadsCsvExport
from erudite.links.open_library.http import OpenLibraryHttp
from erudite.mills import (
    BookFilesService,
    ClassificationService,
    LibraryService,
    WorkService,
)
from erudite.pacts import RootRequestProtocol, ServicesProtocol

if TYPE_CHECKING:
    from collections.abc import Callable


class Services(ServicesProtocol):
    """Built per request; one `cached_property` per service."""

    @cached_property
    def library(self) -> LibraryService:
        return LibraryService(books=BookRepository(), goodreads=GoodreadsCsvExport())

    @cached_property
    def book_files(self) -> BookFilesService:
        return BookFilesService(
            books=BookRepository(), ignored=IgnoredExtensions(), disk=DiskBookFiles()
        )

    @cached_property
    def classification(self) -> ClassificationService:
        return ClassificationService(
            books=BookRepository(), decisions=DecisionRepository()
        )

    @cached_property
    def works(self) -> WorkService:
        return WorkService(books=BookRepository(), open_library=OpenLibraryHttp())


class ServiceInjectionMiddleware[Response]:
    """Attach `request.services` so views reach mills through protocols only."""

    def __init__(self, get_response: Callable[[RootRequestProtocol], Response]) -> None:
        self.get_response = get_response

    def __call__(self, request: RootRequestProtocol) -> Response:
        request.services = Services()
        return self.get_response(request)
