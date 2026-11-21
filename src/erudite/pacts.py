"""Contracts between layers: protocols, DTOs, errors."""

from typing import Protocol


class ServicesProtocol(Protocol):
    """The namespace gates reach services through."""


class RootRequestProtocol(Protocol):
    """The slice of the framework request the middleware touches."""

    services: ServicesProtocol
