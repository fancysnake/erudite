from http import HTTPStatus
from urllib.error import URLError

import pytest
from django.contrib.messages import get_messages

from erudite.links.db.django.models import Author, Book, Sync
from erudite.pacts import CandidatesDTO
from tests.open_library import BARE, BARE_WORK, COVER, FOX, FOX_ID, FOX_WORK

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("media")]

TEMPLATES = ["erudite/pages/open_library.html", "erudite/base.html"]
WORKS = "erudite/parts/works.html"
HTMX = {"HX-Request": "true"}


@pytest.fixture(name="book")
def book_fixture():
    book = Book.objects.create(title="mr fox 2", isbn13="9780140328721")
    book.credits.create(author=Author.objects.create(name="Dahl"))
    return book


@pytest.fixture(name="staff")
def staff_fixture(browser, admin_user):
    """Return the strict client, logged in as the admin logs in."""
    browser.force_login(admin_user)
    return browser


def _url(book, query=""):
    return f"/books/{book.pk}/open-library/{query}"


def _messages(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


def test_the_picker_shows_at_once_and_asks_for_the_works_itself(
    staff, book, *, open_library
):
    response = staff.get(_url(book))

    assert response.status_code == HTTPStatus.OK
    assert [t.name for t in response.templates] == TEMPLATES
    assert response.context["candidates"] == CandidatesDTO(
        book_id=book.pk,
        title="mr fox 2",
        authors=("Dahl",),
        query="mr fox 2 Dahl",
        works=(),
    )
    assert not open_library.requests
    assert not response.context["queue"]
    assert response.context["after"] == f"/books/{book.pk}/"
    assert "“mr fox 2” by Dahl" in response.text
    assert 'value="mr fox 2 Dahl"' in response.text
    assert f'hx-get="/books/{book.pk}/open-library/"' in response.text
    assert 'hx-trigger="load"' in response.text
    assert "Searching Open Library…" in response.text
    assert "vendor/htmx.min.js" in response.text
    assert 'name="queue"' not in response.text
    assert f'<a href="/books/{book.pk}/">Back to the book</a>' in response.text
    assert "Skip this book" not in response.text


def test_the_picker_keeps_the_typed_search_and_the_queue(staff, book, *, open_library):
    response = staff.get(_url(book), {"q": "fantastic fox", "queue": ["5", "6"]})

    assert response.status_code == HTTPStatus.OK
    assert [t.name for t in response.templates] == TEMPLATES
    assert not open_library.requests
    assert response.context["candidates"].query == "fantastic fox"
    assert response.context["queue"] == ["5", "6"]
    assert response.context["after"] == "/books/5/open-library/?queue=6"
    assert 'value="fantastic fox"' in response.text
    assert (
        f'hx-get="/books/{book.pk}/open-library/'
        '?q=fantastic+fox&amp;queue=5&amp;queue=6"'
    ) in response.text
    assert (
        '<input type="hidden" name="queue" value="5">'
        '<input type="hidden" name="queue" value="6">'
    ) in response.text
    assert '<a href="/books/5/open-library/?queue=6">Skip this book</a>' in (
        response.text
    )


def test_the_works_are_the_ones_found_for_the_book(staff, book, *, open_library):
    open_library.searches = {"isbn:9780140328721": [FOX], "mr fox 2 Dahl": [BARE, FOX]}

    response = staff.get(_url(book), headers=HTMX)

    assert response.status_code == HTTPStatus.OK
    assert [t.name for t in response.templates] == [WORKS]
    assert response.context["candidates"] == CandidatesDTO(
        book_id=book.pk,
        title="mr fox 2",
        authors=("Dahl",),
        query="mr fox 2 Dahl",
        works=(FOX_WORK, BARE_WORK),
    )
    assert "<html" not in response.text
    assert "https://covers.openlibrary.org/b/id/6498519-M.jpg" in response.text
    assert "First published in 1970." in response.text
    assert "161 editions." in response.text
    assert "No cover" in response.text
    assert "1 edition." in response.text
    assert "<p>A fox outwits<br>three farmers.</p>" in response.text
    assert "No description." in response.text
    assert '<a href="https://openlibrary.org/works/OL45804W">' in response.text
    assert "OL45804W at Open Library" in response.text
    assert f'name="work" value="{FOX_ID}"' in response.text
    assert "Search again" not in response.text


def test_the_works_are_the_ones_found_for_what_the_user_typed(
    staff, book, *, open_library
):
    response = staff.get(_url(book), {"q": "fantastic fox"}, headers=HTMX)

    assert response.status_code == HTTPStatus.OK
    assert [t.name for t in response.templates] == [WORKS]
    assert open_library.queries == ["fantastic fox"]
    assert response.context["candidates"].query == "fantastic fox"
    assert response.context["candidates"].works == ()
    assert "Open Library found no work." in response.text


def test_the_works_say_when_open_library_gives_no_answer(staff, book, *, open_library):
    open_library.error = URLError("timed out")

    response = staff.get(_url(book, "?queue=5"), headers=HTMX)

    assert response.status_code == HTTPStatus.OK
    assert [t.name for t in response.templates] == [WORKS]
    assert response.context["candidates"] == CandidatesDTO(
        book_id=book.pk,
        title="mr fox 2",
        authors=("Dahl",),
        query="mr fox 2 Dahl",
        works=(),
        failure="Open Library gave no answer: <urlopen error timed out>",
    )
    assert not _messages(response)
    assert "Open Library gave no answer" in response.text
    assert f'hx-get="/books/{book.pk}/open-library/?queue=5"' in response.text
    assert "Search again" in response.text
    assert "Open Library found no work." not in response.text


@pytest.mark.parametrize("method", ("get", "post"))
def test_the_picker_does_not_know_a_book_the_library_lacks(
    staff, open_library, *, method
):
    response = getattr(staff, method)(
        "/books/404/open-library/", {"work": FOX_ID}, headers=HTMX
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert not open_library.requests


def test_a_pick_writes_the_work_to_the_book(staff, book, *, open_library):
    open_library.searches = {f"key:/works/{FOX_ID}": [FOX]}

    response = staff.post(_url(book), {"work": FOX_ID})

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == f"/books/{book.pk}/"
    assert _messages(response) == ["The picked work is written to the book."]
    book.refresh_from_db()
    assert book.title == "Fantastic Mr Fox"
    assert [str(credit) for credit in book.credits.all()] == ["Roald Dahl"]
    assert book.description == "A fox outwits three farmers."
    assert book.open_library_work == FOX_ID
    assert book.cover.name == f"covers/{book.pk}.jpg"
    assert book.cover.read() == COVER
    assert book.isbn13 == "9780140328721"
    assert [(sync.book, sync.sync_type) for sync in Sync.objects.all()] == [
        (book, "open_library")
    ]


@pytest.mark.parametrize(
    ("queue", "target"),
    (
        ("queue=5&queue=6", "/books/5/open-library/?queue=6"),
        ("queue=5", "/books/5/open-library/"),
        ("queue=x", None),
    ),
)
def test_a_pick_leads_to_the_next_book_of_the_queue(
    staff, book, *, open_library, queue, target
):
    open_library.searches = {f"key:/works/{FOX_ID}": [FOX]}

    response = staff.post(_url(book, f"?{queue}"), {"work": FOX_ID})

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == (target or f"/books/{book.pk}/")


@pytest.mark.usefixtures("open_library")
def test_a_pick_of_a_work_open_library_lacks_is_not_found(staff, book):
    response = staff.post(_url(book), {"work": FOX_ID})

    assert response.status_code == HTTPStatus.NOT_FOUND
    book.refresh_from_db()
    assert book.title == "mr fox 2"


@pytest.mark.parametrize("work", ("", "45804", "OL45804W/../x"))
def test_a_pick_of_something_that_is_no_work_id_is_not_found(
    staff, book, *, open_library, work
):
    response = staff.post(_url(book), {"work": work})

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert not open_library.requests


def test_a_pick_that_open_library_does_not_answer_changes_nothing(
    staff, book, *, open_library
):
    open_library.error = URLError("timed out")

    response = staff.post(_url(book, "?queue=5"), {"work": FOX_ID})

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == _url(book, "?queue=5")
    assert _messages(response) == [
        "Open Library gave no answer: <urlopen error timed out>"
    ]
    book.refresh_from_db()
    assert book.title == "mr fox 2"
    assert not book.cover


@pytest.mark.usefixtures("open_library")
def test_the_picker_shows_a_book_that_names_no_author(staff):
    book = Book.objects.create(title="scan_0042")

    response = staff.get(_url(book))

    assert response.status_code == HTTPStatus.OK
    assert response.context["candidates"].authors == ()
    assert "“scan_0042”, with no author." in response.text


@pytest.mark.parametrize("method", ("get", "post"))
def test_the_picker_asks_a_visitor_to_log_in_and_changes_nothing(
    browser, book, *, open_library, method
):
    response = getattr(browser, method)(_url(book), {"work": FOX_ID})

    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(f"/admin/login/?next=/books/{book.pk}/open-library/")
    assert not open_library.requests
    book.refresh_from_db()
    assert book.title == "mr fox 2"


@pytest.mark.parametrize(
    ("books", "target"),
    (
        (["7", "5", "6"], "/books/7/open-library/?queue=5&queue=6"),
        (["7"], "/books/7/open-library/"),
    ),
)
def test_the_selected_books_go_to_the_picker_as_a_queue(staff, *, books, target):
    response = staff.get("/books/open-library/", {"book": books})

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == target


@pytest.mark.parametrize("books", ([], ["x"], ["7", ""]))
def test_a_selection_that_names_no_books_goes_back_to_the_list(staff, *, books):
    response = staff.get("/books/open-library/", {"book": books})

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == "/"
    assert _messages(response) == ["Select the books to find on Open Library."]


def test_the_selection_asks_a_visitor_to_log_in(browser):
    response = browser.get("/books/open-library/", {"book": ["7"]})

    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith("/admin/login/?next=/books/open-library/")
