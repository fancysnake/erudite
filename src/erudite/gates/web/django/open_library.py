import re
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from erudite.pacts import NotFoundError, OpenLibraryError

if TYPE_CHECKING:
    from django.http import HttpResponse

    from erudite.gates.web.django.rendering import RootRequest

_TEMPLATE = "erudite/pages/open_library.html"
_WORK_ID = re.compile(r"OL\d+W")


def _after(book_id: int, queue: str) -> str:
    """Where a pick or a skip leads: the next book of the queue, or the book."""
    first, _comma, rest = queue.partition(",")
    if not first.isdecimal():
        return reverse("admin:erudite_db_book_change", args=[book_id])
    url = reverse("open_library", args=[int(first)])
    return f"{url}?{urlencode({'queue': rest})}" if rest else url


def _pick(request: RootRequest, book_id: int, *, after: str) -> HttpResponse:
    work_id = request.POST.get("work", "")
    if not _WORK_ID.fullmatch(work_id):
        return HttpResponseBadRequest()
    try:
        request.services.works.pick(book_id, work_id)
    except NotFoundError as exc:
        raise Http404(str(exc)) from exc
    except OpenLibraryError as exc:
        messages.error(request, str(exc))
        return redirect(request.get_full_path())
    messages.success(request, _("The picked work is written to the book."))
    return redirect(after)


# A pick changes a book: the picker asks for the login the admin asks for.
@staff_member_required
@require_http_methods(["GET", "POST"])
def open_library(request: RootRequest, book_id: int) -> HttpResponse:
    """Show the works Open Library finds for a book; a POST picks one of them."""
    queue = request.GET.get("queue", "")
    after = _after(book_id, queue)
    if request.method == "POST":
        return _pick(request, book_id, after=after)
    try:
        candidates = request.services.works.candidates(book_id, request.GET.get("q"))
    except NotFoundError as exc:
        raise Http404(str(exc)) from exc
    except OpenLibraryError as exc:
        messages.error(request, str(exc))
        candidates = None
    context = {"candidates": candidates, "queue": queue, "after": after}
    return render(request, _TEMPLATE, context)
