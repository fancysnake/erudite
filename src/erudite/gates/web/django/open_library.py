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


def _book_ids(values: list[str]) -> list[int] | None:
    """Return the values of a queue as book ids; `None` if one is no number."""
    if not all(value.isdecimal() for value in values):
        return None
    return [int(value) for value in values]


def _picker(queue: list[int]) -> str:
    """Return the picker of the first book; the rest of the queue waits in it."""
    first, *rest = queue
    return reverse("open_library", args=[first], query={"queue": rest})


def _after(book_id: int, queue: list[int]) -> str:
    """Where a pick or a skip leads: the next book of the queue, or the book."""
    if not queue:
        return reverse("book", args=[book_id])
    return _picker(queue)


@staff_member_required
@require_GET
def open_library_queue(request: RootRequest) -> HttpResponse:
    """Open the picker for the first selected book; the rest wait in its queue."""
    if not (queue := _book_ids(request.GET.getlist("book"))):
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
    if (queue := _book_ids(request.GET.getlist("queue"))) is None:
        msg = "The queue holds an item that is not a book number."
        raise Http404(msg)
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
