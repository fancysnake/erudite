from typing import TYPE_CHECKING

from django.shortcuts import render

if TYPE_CHECKING:
    from django.http import HttpResponse

    from erudite.gates.web.django.rendering import RootRequest


def home(request: RootRequest) -> HttpResponse:
    context = {"book_count": request.services.library.book_count()}
    return render(request, "erudite/pages/home.html", context)
