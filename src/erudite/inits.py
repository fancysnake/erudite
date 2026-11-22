"""Composition root: builds the services and hands them to the request."""

from functools import cached_property
from typing import TYPE_CHECKING

from erudite.links.book_files.disk import DiskBookFiles
from erudite.links.db.django.repositories import BookFileRepository, BookRepository
from erudite.links.goodreads.csv import GoodreadsCsvExport
from erudite.mills import LibraryService
from erudite.pacts import RootRequestProtocol, ServicesProtocol

if TYPE_CHECKING:
    from collections.abc import Callable


class Services(ServicesProtocol):
    """Built per request; one `cached_property` per service."""

    @cached_property
    def library(self) -> LibraryService:
        return LibraryService(
            books=BookRepository(),
            goodreads=GoodreadsCsvExport(),
            files=BookFileRepository(),
            disk=DiskBookFiles(),
        )


class ServiceInjectionMiddleware[Response]:
    """Attach `request.services` so views reach mills through protocols only."""

    def __init__(self, get_response: Callable[[RootRequestProtocol], Response]) -> None:
        self.get_response = get_response

    def __call__(self, request: RootRequestProtocol) -> Response:
        request.services = Services()
        return self.get_response(request)
