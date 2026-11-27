from typing import TYPE_CHECKING

from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from erudite.pacts import PAGE_SIZES, BookListQuery, NotFoundError, SyncType

if TYPE_CHECKING:
    from django.http import HttpResponse

    from erudite.gates.web.django.rendering import RootRequest

_SYNC_LABELS = {
    SyncType.GOODREADS: _("Goodreads"),
    SyncType.FILE: _("Files"),
    SyncType.OPEN_LIBRARY: _("Open Library"),
}


def home(request: RootRequest) -> HttpResponse:
    """List the books a search and the sync filters find, and how far each sync is."""
    try:
        asked = BookListQuery(
            query=request.GET.get("q", ""),
            page=int(request.GET.get("page", "1")),
            size=int(request.GET.get("size", PAGE_SIZES[0])),
            done=tuple(SyncType(sync) for sync in request.GET.getlist("with")),
            todo=tuple(SyncType(sync) for sync in request.GET.getlist("without")),
        )
    except ValueError as exc:
        raise Http404 from exc
    try:
        books = request.services.library.books(asked)
    except NotFoundError as exc:
        raise Http404(str(exc)) from exc
    context = {
        "books": books,
        "asked": asked,
        "sizes": PAGE_SIZES,
        "syncs": [
            (progress, _SYNC_LABELS[progress.sync])
            for progress in request.services.library.sync_progress()
        ],
    }
    return render(request, "erudite/pages/home.html", context)
