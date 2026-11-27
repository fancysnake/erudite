"""Composition root: builds the services and hands them to the request."""

from functools import cached_property
from typing import TYPE_CHECKING

from django.db import transaction

from erudite.links.book_files.disk import DiskBookFiles
from erudite.links.db.django.repositories import (
    BookRepository,
    DecisionRepository,
    IgnoredExtensions,
    SyncRepository,
)
from erudite.links.goodreads.csv import GoodreadsCsvExport
from erudite.links.web.https import HttpsWebFiles
from erudite.links.web.open_library import OpenLibraryHttp
from erudite.mills import (
    BookFilesService,
    ClassificationService,
    LibraryService,
    VendorService,
    WorkService,
)
from erudite.pacts import RootRequestProtocol, ServicesProtocol

if TYPE_CHECKING:
    from collections.abc import Callable


# One for the process: the client paces the requests of every request together.
OPEN_LIBRARY = OpenLibraryHttp()


class Services(ServicesProtocol):
    """Built per request; one `cached_property` per service."""

    @cached_property
    def library(self) -> LibraryService:
        return LibraryService(
            books=BookRepository(),
            syncs=SyncRepository(),
            goodreads=GoodreadsCsvExport(),
        )

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
        return WorkService(
            books=BookRepository(),
            syncs=SyncRepository(),
            open_library=OPEN_LIBRARY,
            transaction=transaction,
        )

    @cached_property
    def vendor(self) -> VendorService:
        return VendorService(web=HttpsWebFiles())


class ServiceInjectionMiddleware[Response]:
    """Attach `request.services` so views reach mills through protocols only."""

    def __init__(self, get_response: Callable[[RootRequestProtocol], Response]) -> None:
        self.get_response = get_response

    def __call__(self, request: RootRequestProtocol) -> Response:
        request.services = Services()
        return self.get_response(request)
