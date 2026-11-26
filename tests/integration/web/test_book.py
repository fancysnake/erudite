from http import HTTPStatus

import pytest
from django.core.files.base import ContentFile

from erudite.links.db.django.models import Author, Book
from erudite.pacts import BookDTO, BookSummaryDTO

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("media")]

TEMPLATES = ["erudite/pages/book.html", "erudite/base.html"]


def test_the_book_page_shows_everything_the_book_holds(browser):
    book = Book.objects.create(
        title="Fantastic Mr Fox",
        series="Dahl",
        series_position="2",
        description="A fox outwits\nthree farmers.",
        open_library_work="OL45804W",
    )
    book.credits.create(author=Author.objects.create(name="Roald Dahl"))
    book.cover.save("fox.jpg", ContentFile(b"a JPEG"))

    response = browser.get(f"/books/{book.pk}/")

    assert response.status_code == HTTPStatus.OK
    assert [t.name for t in response.templates] == TEMPLATES
    assert response.context["book"] == BookDTO(
        summary=BookSummaryDTO(
            book_id=book.pk,
            title="Fantastic Mr Fox",
            authors=("Roald Dahl",),
            series="Dahl",
            series_position="2",
            status="To read",
        ),
        description="A fox outwits\nthree farmers.",
        cover_url="/media/covers/fox.jpg",
        open_library_work="OL45804W",
    )
    assert "<h1>Fantastic Mr Fox</h1>" in response.text
    assert "Roald Dahl" in response.text
    assert "#2" in response.text
    assert 'src="/media/covers/fox.jpg"' in response.text
    assert "<p>A fox outwits<br>three farmers.</p>" in response.text
    assert (
        '<a href="https://openlibrary.org/works/OL45804W">OL45804W</a>'
    ) in response.text
    assert f'<a href="/books/{book.pk}/open-library/">Find on Open Library</a>' in (
        response.text
    )
    assert f'href="/admin/erudite_db/book/{book.pk}/change/"' in response.text
    assert '<a href="/">Back to the library</a>' in response.text


def test_the_book_page_says_what_a_bare_book_lacks(browser):
    book = Book.objects.create(title="scan_0042")

    response = browser.get(f"/books/{book.pk}/")

    assert response.status_code == HTTPStatus.OK
    assert [t.name for t in response.templates] == TEMPLATES
    assert response.context["book"] == BookDTO(
        summary=BookSummaryDTO(
            book_id=book.pk,
            title="scan_0042",
            authors=(),
            series="",
            series_position="",
            status="To read",
        ),
        description="",
        cover_url="",
        open_library_work="",
    )
    assert "No cover" in response.text
    assert "No description." in response.text
    assert "No work picked." in response.text
    assert "<img" not in response.text


def test_the_book_page_does_not_know_a_book_the_library_lacks(browser):
    response = browser.get("/books/404/")

    assert response.status_code == HTTPStatus.NOT_FOUND
