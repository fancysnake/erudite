from http import HTTPStatus

import pytest

from erudite.links.db.django.models import Book
from erudite.pacts import ReadingStatus

pytestmark = pytest.mark.django_db


def test_admin_opens_for_a_superuser(admin_client):
    assert admin_client.get("/admin/").status_code == HTTPStatus.OK


def test_admin_lists_books_and_finds_them_by_author(admin_client):
    Book.objects.create(title="Mort", authors=["Terry Pratchett"], series="Discworld")
    Book.objects.create(title="Dune", authors=["Frank Herbert"])

    response = admin_client.get("/admin/erudite_db/book/", {"q": "pratchett"})

    assert response.status_code == HTTPStatus.OK
    assert [book.title for book in response.context["cl"].result_list] == ["Mort"]


def test_admin_changes_the_reading_status(admin_client):
    book = Book.objects.create(title="Dune", authors=["Frank Herbert"])

    response = admin_client.post(
        f"/admin/erudite_db/book/{book.pk}/change/",
        {
            "title": "Dune",
            "authors": '["Frank Herbert"]',
            "shelves": "[]",
            "status": ReadingStatus.READING,
        },
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == "/admin/erudite_db/book/"
    book.refresh_from_db()
    assert book.status == ReadingStatus.READING


def test_admin_sends_a_visitor_to_the_login(client):
    response = client.get("/admin/")

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == "/admin/login/?next=/admin/"
