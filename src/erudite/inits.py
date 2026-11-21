"""Composition root: builds the services and hands them to the request."""

from typing import TYPE_CHECKING

from erudite.pacts import RootRequestProtocol, ServicesProtocol

if TYPE_CHECKING:
    from collections.abc import Callable


class Services(ServicesProtocol):
    """Built per request; one `cached_property` per service."""


class ServiceInjectionMiddleware[Response]:
    """Attach `request.services` so views reach mills through protocols only."""

    def __init__(self, get_response: Callable[[RootRequestProtocol], Response]) -> None:
        self.get_response = get_response

    def __call__(self, request: RootRequestProtocol) -> Response:
        request.services = Services()
        return self.get_response(request)
