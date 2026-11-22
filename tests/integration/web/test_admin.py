from http import HTTPStatus

import pytest

from erudite.links.db.django.models import Author, Book
from erudite.pacts import ReadingStatus

pytestmark = pytest.mark.django_db


def _book(title, *names, **fields):
    book = Book.objects.create(title=title, **fields)
    for position, name in enumerate(names):
        author = Author.objects.get_or_create(name=name)[0]
        book.credits.create(author=author, position=position)
    return book


def test_admin_opens_for_a_superuser(admin_client):
    assert admin_client.get("/admin/").status_code == HTTPStatus.OK


@pytest.mark.parametrize(
    ("query", "titles"), (("pratchett", ["Mort"]), ("Jarosław", ["Święty spokój"]))
)
def test_admin_lists_books_and_finds_them_by_author(admin_client, *, query, titles):
    _book("Mort", "Terry Pratchett", series="Discworld")
    _book("Dune", "Frank Herbert")
    _book("Święty spokój", "Jarosław Gibas")

    response = admin_client.get("/admin/erudite_db/book/", {"q": query})

    assert response.status_code == HTTPStatus.OK
    assert [book.title for book in response.context["cl"].result_list] == titles


def test_admin_lists_the_authors_of_a_book_first_author_first(admin_client):
    _book("Good Omens", "Terry Pratchett", "Neil Gaiman")

    response = admin_client.get("/admin/erudite_db/book/")

    assert "Terry Pratchett, Neil Gaiman" in response.text


def test_admin_finds_an_author_by_name(admin_client):
    _book("Mort", "Terry Pratchett")
    _book("Dune", "Frank Herbert")

    response = admin_client.get("/admin/erudite_db/author/", {"q": "herbert"})

    assert response.status_code == HTTPStatus.OK
    assert [str(author) for author in response.context["cl"].result_list] == [
        "Frank Herbert"
    ]


def test_admin_changes_the_reading_status_and_adds_an_author(admin_client):
    book = _book("Good Omens", "Terry Pratchett")
    credit = book.credits.get()
    gaiman = Author.objects.create(name="Neil Gaiman")

    response = admin_client.post(
        f"/admin/erudite_db/book/{book.pk}/change/",
        {
            "title": "Good Omens",
            "shelves": "[]",
            "status": ReadingStatus.READING,
            "credits-TOTAL_FORMS": "2",
            "credits-INITIAL_FORMS": "1",
            "credits-0-id": credit.pk,
            "credits-0-book": book.pk,
            "credits-0-author": credit.author.pk,
            "credits-0-position": "0",
            "credits-1-book": book.pk,
            "credits-1-author": gaiman.pk,
            "credits-1-position": "1",
        },
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == "/admin/erudite_db/book/"
    book.refresh_from_db()
    assert book.status == ReadingStatus.READING
    assert [str(credit) for credit in book.credits.all()] == [
        "Terry Pratchett",
        "Neil Gaiman",
    ]


def test_admin_sends_a_visitor_to_the_login(client):
    response = client.get("/admin/")

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == "/admin/login/?next=/admin/"
