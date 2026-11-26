import re
from http import HTTPStatus

import pytest

from erudite.links.db.django.models import Author, Book, Sync
from erudite.pacts import BookListDTO, BookSummaryDTO, SyncProgressDTO, SyncType

pytestmark = pytest.mark.django_db

TEMPLATES = ["erudite/pages/home.html", "erudite/base.html"]


def test_home_shows_the_empty_library(browser):
    response = browser.get("/")

    assert response.status_code == HTTPStatus.OK
    assert [t.name for t in response.templates] == TEMPLATES
    assert response.context["books"] == BookListDTO(
        query="", size=10, books=(), total=0, page=1, pages=1
    )
    assert "No books yet." in response.text
    assert "<table" not in response.text


def test_home_lists_the_books_with_a_link_and_a_box_to_select_each(browser):
    mort = Book.objects.create(title="Mort", series="Discworld", series_position="4")
    mort.credits.create(author=Author.objects.create(name="Terry Pratchett"))

    response = browser.get("/")

    assert response.status_code == HTTPStatus.OK
    assert [t.name for t in response.templates] == TEMPLATES
    assert response.context["sizes"] == (10, 25, 50, 100)
    assert response.context["asked"] == {
        "query": "",
        "page": 1,
        "size": 10,
        "done": (),
        "todo": (),
    }
    assert response.context["syncs"] == [
        (SyncProgressDTO(sync=SyncType.GOODREADS, done=0, total=1), "Goodreads"),
        (SyncProgressDTO(sync=SyncType.FILE, done=0, total=1), "Files"),
        (SyncProgressDTO(sync=SyncType.OPEN_LIBRARY, done=0, total=1), "Open Library"),
    ]
    assert response.context["books"] == BookListDTO(
        query="",
        size=10,
        books=(
            BookSummaryDTO(
                book_id=mort.pk,
                title="Mort",
                authors=("Terry Pratchett",),
                series="Discworld",
                series_position="4",
                status="To read",
            ),
        ),
        total=1,
        page=1,
        pages=1,
    )
    assert "1 book." in response.text
    assert (
        f'<a class="books__title" href="/books/{mort.pk}/">Mort</a>'
    ) in response.text
    assert '<span class="books__authors">Terry Pratchett</span>' in response.text
    assert "#4" in response.text
    assert '<tr class="status--to-read">' in response.text
    assert '<td class="books__status">To read</td>' in response.text
    assert f'<input type="checkbox" name="book" value="{mort.pk}">' in response.text
    assert "Select “Mort”" in response.text
    assert 'action="/books/open-library/"' in response.text
    assert "No books yet." not in response.text
    assert "Page 1 of 1" not in response.text


def test_home_finds_books_by_what_the_user_typed(browser):
    Book.objects.bulk_create([Book(title="Mort"), Book(title="Dune")])

    response = browser.get("/", {"q": " dune "})

    assert response.status_code == HTTPStatus.OK
    assert response.context["books"].query == "dune"
    assert [book.title for book in response.context["books"].books] == ["Dune"]
    assert 'value="dune"' in response.text
    assert "1 book." in response.text


def test_home_says_when_no_book_matches_the_search(browser):
    Book.objects.create(title="Mort")

    response = browser.get("/", {"q": "dune"})

    assert response.status_code == HTTPStatus.OK
    assert response.context["books"] == BookListDTO(
        query="dune", size=10, books=(), total=0, page=1, pages=1
    )
    assert "No book matches the search and the filters." in response.text
    assert "No books yet." not in response.text


@pytest.mark.parametrize(
    ("page", "first", "links"),
    (
        ("1", "Book 000", ["?q=book&amp;page=2"]),
        ("2", "Book 010", ["?q=book&amp;page=1", "?q=book&amp;page=3"]),
        ("3", "Book 020", ["?q=book&amp;page=2"]),
    ),
)
def test_home_cuts_the_list_into_pages_that_keep_the_search(
    browser, *, page, first, links
):
    Book.objects.bulk_create(Book(title=f"Book {number:03}") for number in range(21))

    response = browser.get("/", {"q": "book", "page": page})

    assert response.status_code == HTTPStatus.OK
    books = response.context["books"]
    assert (books.total, books.page, books.pages) == (21, int(page), 3)
    assert books.books[0].title == first
    assert "21 books." in response.text
    assert f"Page {page} of 3" in response.text
    assert [
        link
        for link in ("?q=book&amp;page=1", "?q=book&amp;page=2", "?q=book&amp;page=3")
        if f'href="{link}"' in response.text
    ] == links


def test_home_shows_as_many_books_a_page_as_the_user_set(browser):
    Book.objects.bulk_create(Book(title=f"Book {number:03}") for number in range(30))

    response = browser.get("/", {"size": "25", "page": "2"})

    assert response.status_code == HTTPStatus.OK
    books = response.context["books"]
    assert (books.size, books.page, books.pages, len(books.books)) == (25, 2, 2, 5)
    assert '<option value="25" selected>' in response.text
    assert '<option value="10">' in response.text
    assert "25 per page" in response.text
    assert 'href="?size=25&amp;page=1"' in response.text


@pytest.mark.parametrize(
    "query",
    (
        {"page": "0"},
        {"page": "2"},
        {"page": "x"},
        {"size": "7"},
        {"size": "x"},
        {"with": "x"},
        {"without": "x"},
    ),
)
def test_home_does_not_know_a_page_the_list_lacks(browser, *, query):
    response = browser.get("/", query)

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    ("query", "titles"),
    (
        ({"with": ["open_library"]}, ["Mort"]),
        ({"without": ["open_library"]}, ["Dune", "Emma"]),
        ({"without": ["open_library"], "with": ["file"]}, ["Emma"]),
        ({"with": ["open_library", "file"]}, []),
        ({"without": ["open_library", "file"]}, ["Dune"]),
    ),
)
def test_home_keeps_the_books_the_sync_filters_name(browser, *, query, titles):
    mort, emma = Book.objects.create(title="Mort"), Book.objects.create(title="Emma")
    Book.objects.create(title="Dune")
    Sync.objects.create(book=mort, sync_type="open_library")
    Sync.objects.create(book=emma, sync_type="file")

    response = browser.get("/", query)

    assert response.status_code == HTTPStatus.OK
    assert [book.title for book in response.context["books"].books] == titles
    asked = response.context["asked"]
    assert list(asked["done"]) == query.get("with", [])
    assert list(asked["todo"]) == query.get("without", [])
    checked = re.findall(r'name="(\w+)"\s+value="(\w+)" checked>', response.text)
    assert sorted(checked) == sorted(
        (name, value) for name, values in query.items() for value in values
    )
    if not titles:
        assert "No book matches the search and the filters." in response.text


def test_home_shows_how_far_each_sync_is_and_a_box_to_select_every_book(browser):
    mort = Book.objects.create(title="Mort")
    Book.objects.create(title="Dune")
    Sync.objects.create(book=mort, sync_type="open_library")

    response = browser.get("/")

    assert response.status_code == HTTPStatus.OK
    assert [
        (progress.done, progress.total) for progress, _ in response.context["syncs"]
    ] == [(0, 2), (0, 2), (1, 2)]
    assert 'Open Library <span class="filters__count">1</span>' in response.text
    assert 'id="select-all"' in response.text
    assert "erudite/select-all.js" in response.text
