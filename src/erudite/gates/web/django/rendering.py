"""What every view shares: the typed request."""

from typing import TYPE_CHECKING

from django.http import HttpRequest

if TYPE_CHECKING:
    from erudite.pacts import ServicesProtocol


class RootRequest(HttpRequest):
    """For typing only; the middleware sets `services` on the real request."""

    services: ServicesProtocol
