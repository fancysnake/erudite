from http import HTTPStatus

import pytest

pytestmark = pytest.mark.django_db


def test_home_shows_the_empty_library(browser):
    response = browser.get("/")

    assert response.status_code == HTTPStatus.OK
    assert [t.name for t in response.templates] == [
        "erudite/pages/home.html",
        "erudite/base.html",
    ]
    assert "No books yet." in response.text
