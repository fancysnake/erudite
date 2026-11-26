from typing import TYPE_CHECKING

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods

from erudite.pacts import NotFoundError, OpenLibraryError

if TYPE_CHECKING:
    from django.http import HttpResponse

    from erudite.gates.web.django.rendering import RootRequest

_TEMPLATE = "erudite/pages/open_library.html"
# The works found, which the page asks for once it shows.
_WORKS = "erudite/parts/works.html"


def _picker(queue: list[str]) -> str:
    """Return the picker of the first book; the rest of the queue waits in it."""
    first, *rest = queue
    return reverse("open_library", args=[int(first)], query={"queue": rest})


def _after(book_id: int, queue: list[str]) -> str:
    """Where a pick or a skip leads: the next book of the queue, or the book."""
    if not queue or not queue[0].isdecimal():
        return reverse("book", args=[book_id])
    return _picker(queue)


@staff_member_required
@require_GET
def open_library_queue(request: RootRequest) -> HttpResponse:
    """Open the picker for the first selected book; the rest wait in its queue."""
    queue = request.GET.getlist("book")
    if not queue or not all(book.isdecimal() for book in queue):
        messages.error(request, _("Select the books to find on Open Library."))
        return redirect("home")
    return redirect(_picker(queue))


def _pick(request: RootRequest, book_id: int, *, after: str) -> HttpResponse:
    try:
        request.services.works.pick(book_id, request.POST.get("work", ""))
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
    """Show the picker of a book and the works found; a POST picks one of them."""
    queue = request.GET.getlist("queue")
    after = _after(book_id, queue)
    if request.method == "POST":
        return _pick(request, book_id, after=after)
    # The page shows at once; HTMX then asks for the works, and only that
    # request waits for Open Library.
    asks_for_works = bool(request.headers.get("HX-Request"))
    try:
        candidates = request.services.works.candidates(
            book_id, request.GET.get("q"), search=asks_for_works
        )
    except NotFoundError as exc:
        raise Http404(str(exc)) from exc
    if asks_for_works:
        return render(request, _WORKS, {"candidates": candidates})
    context = {"candidates": candidates, "queue": queue, "after": after}
    return render(request, _TEMPLATE, context)
