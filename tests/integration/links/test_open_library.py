import time
from io import BytesIO
from unittest.mock import MagicMock
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from erudite.links.web import https
from erudite.links.web.open_library import OpenLibraryHttp
from erudite.pacts import OpenLibraryError
from tests.open_library import BARE, BARE_WORK, COVER, FOX, FOX_WORK


def test_a_search_gives_the_works_found_best_first(open_library):
    open_library.searches = {"fantastic fox": [FOX, BARE]}

    works = OpenLibraryHttp().search("fantastic fox")

    assert works == [FOX_WORK, BARE_WORK]


def test_a_search_sends_the_query_and_no_contact_detail(open_library):
    OpenLibraryHttp().search("fantastic fox")

    (request,) = open_library.requests
    url = urlsplit(request.full_url)
    assert (url.scheme, url.netloc, url.path) == (
        "https",
        "openlibrary.org",
        "/search.json",
    )
    assert parse_qs(url.query) == {
        "q": ["fantastic fox"],
        "limit": ["10"],
        "fields": [
            "key,title,author_name,first_publish_year,cover_i,edition_count,description"
        ],
    }
    assert request.header_items() == [("User-agent", "erudite")]


def test_a_cover_is_the_large_image(open_library):
    assert OpenLibraryHttp().cover(6498519) == COVER
    (request,) = open_library.requests
    assert request.full_url == "https://covers.openlibrary.org/b/id/6498519-L.jpg"


def test_no_answer_from_open_library_is_an_error_after_three_requests(open_library):
    open_library.error = URLError("timed out")

    with pytest.raises(OpenLibraryError, match="gave no answer"):
        OpenLibraryHttp(interval=0).search("fox")
    assert len(open_library.requests) == 3


def test_a_request_that_fails_is_sent_again(monkeypatch):
    urlopen = MagicMock(
        side_effect=[ConnectionResetError(104, "reset"), BytesIO(COVER)]
    )
    monkeypatch.setattr(https, "urlopen", urlopen)

    assert OpenLibraryHttp(interval=0).cover(1) == COVER
    assert urlopen.call_count == 2


@pytest.mark.parametrize(
    ("answer", "message"), ((b"<html>", "not JSON"), (b"[]", "unknown shape"))
)
def test_an_answer_that_cannot_be_read_is_an_error(monkeypatch, *, answer, message):
    client = OpenLibraryHttp()
    monkeypatch.setattr(client, "_get", MagicMock(return_value=answer))

    with pytest.raises(OpenLibraryError, match=message):
        client.search("fox")


def test_a_request_waits_until_the_interval_passed_since_the_last(open_library):
    interval = 0.2
    client = OpenLibraryHttp(interval=interval)
    client.cover(1)
    first = time.monotonic()

    client.cover(2)

    assert time.monotonic() - first >= interval * 0.9
    assert len(open_library.requests) == 2
