from typing import TYPE_CHECKING

from django.http import Http404
from django.shortcuts import render

from erudite.pacts import NotFoundError

if TYPE_CHECKING:
    from django.http import HttpResponse

    from erudite.gates.web.django.rendering import RootRequest


def book(request: RootRequest, book_id: int) -> HttpResponse:
    try:
        found = request.services.library.book(book_id)
    except NotFoundError as exc:
        raise Http404(str(exc)) from exc
    return render(request, "erudite/pages/book.html", {"book": found})
