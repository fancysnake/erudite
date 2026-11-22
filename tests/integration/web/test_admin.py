import re
from http import HTTPStatus

import pytest

from erudite.links.db.django import admin as admin_module
from erudite.links.db.django.models import Author, Book
from erudite.pacts import ReadingStatus

pytestmark = pytest.mark.django_db

LINK = "text-primary-600 dark:text-primary-500 underline"


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
    book = _book("Good Omens", "Terry Pratchett", "Neil Gaiman")
    pratchett, gaiman = (credit.author.pk for credit in book.credits.all())

    response = admin_client.get("/admin/erudite_db/book/")

    assert (
        f'<a href="/admin/erudite_db/author/{pratchett}/change/" class="{LINK}">'
        "Terry Pratchett</a>, "
        f'<a href="/admin/erudite_db/author/{gaiman}/change/" class="{LINK}">'
        "Neil Gaiman</a>"
    ) in response.text


def test_admin_links_an_author_to_their_books(admin_client):
    mort = _book("Mort", "Terry Pratchett")
    omens = _book("Good Omens", "Terry Pratchett", "Neil Gaiman")
    _book("Dune", "Frank Herbert")
    author = mort.credits.get().author

    response = admin_client.get(f"/admin/erudite_db/author/{author.pk}/change/")

    assert response.status_code == HTTPStatus.OK
    assert (
        f'<a href="/admin/erudite_db/book/{omens.pk}/change/" class="{LINK}">'
        "Good Omens</a>\n"
        f'<a href="/admin/erudite_db/book/{mort.pk}/change/" class="{LINK}">Mort</a>'
    ) in response.text
    assert "Dune" not in response.text


def test_admin_finds_an_author_by_name(admin_client):
    _book("Mort", "Terry Pratchett")
    _book("Dune", "Frank Herbert")

    response = admin_client.get("/admin/erudite_db/author/", {"q": "herbert"})

    assert response.status_code == HTTPStatus.OK
    assert [str(author) for author in response.context["cl"].result_list] == [
        "Frank Herbert"
    ]


@pytest.mark.parametrize(
    ("order", "names"),
    (
        ("-2", ["Terry Pratchett", "Frank Herbert"]),
        ("2", ["Frank Herbert", "Terry Pratchett"]),
    ),
)
def test_admin_counts_the_books_of_each_author_and_sorts_by_it(
    admin_client, *, order, names
):
    _book("Mort", "Terry Pratchett")
    _book("Sourcery", "Terry Pratchett")
    _book("Dune", "Frank Herbert")

    response = admin_client.get("/admin/erudite_db/author/", {"o": order})

    assert response.status_code == HTTPStatus.OK
    assert [str(author) for author in response.context["cl"].result_list] == names
    assert re.findall(r"<td[^>]*field-_book_count[^>]*>\s*(\d+)", response.text) == [
        str(Author.objects.get(name=name).books.count()) for name in names
    ]


def test_admin_changes_the_reading_status_and_adds_an_author(admin_client):
    book = _book("Good Omens", "Terry Pratchett")
    credit = book.credits.get()
    gaiman = Author.objects.create(name="Neil Gaiman")

    response = admin_client.post(
        f"/admin/erudite_db/book/{book.pk}/change/",
        {
            "title": "Good Omens",
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


def test_author_book_count_column_rejects_an_author_without_the_count():
    with pytest.raises(TypeError, match="book count"):
        admin_module.AuthorAdmin.list_display[1](Author(name="Terry Pratchett"))
