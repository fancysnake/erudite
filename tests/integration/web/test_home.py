from http import HTTPStatus

import pytest

from erudite.links.db.django.models import Book

pytestmark = pytest.mark.django_db

TEMPLATES = ["erudite/pages/home.html", "erudite/base.html"]


def test_home_shows_the_empty_library(browser):
    response = browser.get("/")

    assert response.status_code == HTTPStatus.OK
    assert [t.name for t in response.templates] == TEMPLATES
    assert response.context["book_count"] == 0
    assert "No books yet." in response.text


@pytest.mark.parametrize(("count", "text"), ((1, "1 book."), (2, "2 books.")))
def test_home_counts_the_books(browser, *, count, text):
    Book.objects.bulk_create(Book(title=f"Book {number}") for number in range(count))

    response = browser.get("/")

    assert response.status_code == HTTPStatus.OK
    assert [t.name for t in response.templates] == TEMPLATES
    assert response.context["book_count"] == count
    assert text in response.text
    assert "No books yet." not in response.text
