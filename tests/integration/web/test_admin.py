import re
from http import HTTPStatus

import pytest

from erudite.links.db.django import admin as admin_module
from erudite.links.db.django.models import (
    Author,
    Book,
    Decision,
    IgnoredExtension,
    RawBook,
)
from erudite.pacts import BookSource, ReadingStatus

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


def test_admin_filters_the_books_that_have_no_author(admin_client):
    _book("Mort", "Terry Pratchett")
    _book("scan_0042")

    response = admin_client.get("/admin/erudite_db/book/", {"credits__isempty": "1"})

    assert response.status_code == HTTPStatus.OK
    assert [str(book) for book in response.context["cl"].result_list] == ["scan_0042"]


def _raw_book(title, **fields):
    return RawBook.objects.create(
        source=BookSource.FILE, key=title, title=title, **fields
    )


def test_admin_lists_raw_books_and_finds_them_by_author(admin_client):
    _raw_book(
        "Good Omens",
        authors=["Terry Pratchett", "Neil Gaiman"],
        path="/books/omens.epub",
        book=_book("Good Omens (my copy)"),
    )
    _raw_book("dune", path="/books/dune.pdf")

    response = admin_client.get("/admin/erudite_db/rawbook/", {"q": "gaiman"})

    assert response.status_code == HTTPStatus.OK
    assert [str(raw) for raw in response.context["cl"].result_list] == ["Good Omens"]
    assert "Terry Pratchett, Neil Gaiman" in response.text
    assert "/books/omens.epub" in response.text
    assert "Good Omens (my copy)" in response.text


def test_admin_filters_raw_books_by_source(admin_client):
    _raw_book("Mort")
    RawBook.objects.create(source=BookSource.GOODREADS, key="386372", title="Dune")

    response = admin_client.get(
        "/admin/erudite_db/rawbook/", {"source__exact": BookSource.GOODREADS}
    )

    assert response.status_code == HTTPStatus.OK
    assert [str(raw) for raw in response.context["cl"].result_list] == ["Dune"]


def test_admin_shows_a_raw_book_and_neither_changes_nor_adds_one(admin_client):
    raw = _raw_book("scan_0042", path="/books/scan_0042.pdf")
    before = RawBook.objects.values().get()
    url = f"/admin/erudite_db/rawbook/{raw.pk}/change/"

    assert admin_client.get(url).status_code == HTTPStatus.OK
    admin_client.post(url, {"title": "Dune", "path": "/elsewhere.pdf", "key": "cc"})

    assert RawBook.objects.values().get() == before
    assert (
        admin_client.get("/admin/erudite_db/rawbook/add/").status_code
        == HTTPStatus.FORBIDDEN
    )


def test_admin_adds_an_ignored_file_extension(admin_client):
    response = admin_client.post(
        "/admin/erudite_db/ignoredextension/add/", {"extension": "png"}
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == "/admin/erudite_db/ignoredextension/"
    assert IgnoredExtension.objects.values_list("extension", flat=True).get() == "png"


@pytest.mark.parametrize("typed", (" .PNG ", ".png", "PNG", "png"))
def test_admin_cleans_an_ignored_file_extension_before_it_stores_it(
    admin_client, *, typed
):
    admin_client.post("/admin/erudite_db/ignoredextension/add/", {"extension": typed})

    assert IgnoredExtension.objects.values_list("extension", flat=True).get() == "png"


@pytest.mark.parametrize("typed", ("", " ", ".", " . "))
def test_admin_rejects_an_empty_ignored_file_extension(admin_client, *, typed):
    response = admin_client.post(
        "/admin/erudite_db/ignoredextension/add/", {"extension": typed}
    )

    assert response.status_code == HTTPStatus.OK
    assert not IgnoredExtension.objects.exists()


def _decision(book, **proposed):
    return Decision.objects.create(book=book, proposed=proposed)


def test_admin_lists_decisions_with_their_proposed_fields(admin_client):
    _decision(_book("scan_0042"), title="Dune", authors=["Frank Herbert"])
    _decision(_book("Mort"), isbn13="9780552131063")

    response = admin_client.get("/admin/erudite_db/decision/", {"q": "scan"})

    assert response.status_code == HTTPStatus.OK
    assert [str(row) for row in response.context["cl"].result_list] == ["scan_0042"]
    assert "Title, Authors" in response.text


def _accept_field(response):
    field = response.context["adminform"].form["accept"]
    return list(field.field.choices), field.value()


def test_admin_shows_what_the_book_has_next_to_what_is_proposed(admin_client):
    book = _book("Good <i>Omens</i>", "Terry Pratchett")
    decision = _decision(
        book, authors=["Terry Pratchett", "Neil Gaiman"], isbn13="9780552137034"
    )

    response = admin_client.get(f"/admin/erudite_db/decision/{decision.pk}/change/")

    assert response.status_code == HTTPStatus.OK
    assert _accept_field(response) == (
        [
            ("authors", "Authors: Terry Pratchett → Terry Pratchett, Neil Gaiman"),
            ("isbn13", "ISBN-13: — → 9780552137034"),
        ],
        ["authors", "isbn13"],
    )
    assert "<i>Omens</i>" not in response.text
    assert 'name="_continue"' not in response.text


def test_admin_shows_a_dash_for_a_book_with_no_authors(admin_client):
    decision = _decision(_book("scan_0042"), authors=["Frank Herbert"])

    response = admin_client.get(f"/admin/erudite_db/decision/{decision.pk}/change/")

    assert _accept_field(response)[0] == [("authors", "Authors: — → Frank Herbert")]


@pytest.mark.parametrize("button", ("_save", "_continue"))
def test_admin_writes_only_the_accepted_fields_and_removes_the_decision(
    admin_client, button
):
    book = _book("scan_0042", status=ReadingStatus.READING)
    decision = _decision(book, title="Dune", authors=["Frank Herbert"])

    response = admin_client.post(
        f"/admin/erudite_db/decision/{decision.pk}/change/",
        {"accept": ["authors"], button: "1"},
        follow=True,
    )

    assert response.redirect_chain == [
        ("/admin/erudite_db/decision/", HTTPStatus.FOUND)
    ]
    assert [str(m) for m in response.context["messages"]] == [
        "The accepted fields are written to “scan_0042”."
    ]
    book.refresh_from_db()
    assert (book.title, book.status) == ("scan_0042", ReadingStatus.READING)
    assert [str(credit) for credit in book.credits.all()] == ["Frank Herbert"]
    assert not Decision.objects.exists()


def test_admin_accepting_no_field_removes_the_decision_and_leaves_the_book(
    admin_client,
):
    book = _book("scan_0042", "Frank Herbert")
    before = Book.objects.values().get()
    decision = _decision(book, title="Dune")

    response = admin_client.post(f"/admin/erudite_db/decision/{decision.pk}/change/")

    assert response.status_code == HTTPStatus.FOUND
    assert Book.objects.values().get() == before
    assert not Decision.objects.exists()


def test_admin_rejects_accepting_a_field_that_is_not_proposed(admin_client):
    book = _book("scan_0042")
    decision = _decision(book, title="Dune")

    response = admin_client.post(
        f"/admin/erudite_db/decision/{decision.pk}/change/", {"accept": ["status"]}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["adminform"].form.errors["accept"]
    assert Decision.objects.get() == decision


def test_admin_adds_no_decision_by_hand(admin_client):
    response = admin_client.get("/admin/erudite_db/decision/add/")

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.parametrize(
    ("titles", "target"),
    (
        (("Dune", "Mort", "Sourcery"), "/books/{0}/open-library/?queue={1}&queue={2}"),
        (("Dune",), "/books/{0}/open-library/"),
    ),
)
def test_admin_sends_the_selected_books_to_the_open_library_picker(
    admin_client, *, titles, target
):
    books = [_book(title).pk for title in titles]

    response = admin_client.post(
        "/admin/erudite_db/book/",
        {"action": "_find_on_open_library", "_selected_action": books},
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == target.format(*books)


def test_admin_links_a_book_to_its_open_library_picker(admin_client):
    book = _book("Dune", "Frank Herbert")

    response = admin_client.get(f"/admin/erudite_db/book/{book.pk}/change/")

    assert response.status_code == HTTPStatus.OK
    assert f'href="/books/{book.pk}/open-library/"' in response.text
    assert "Find on Open Library" in response.text
