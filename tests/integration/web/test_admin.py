from http import HTTPStatus

import pytest

pytestmark = pytest.mark.django_db


def test_admin_opens_for_a_superuser(admin):
    assert admin.get("/admin/").status_code == HTTPStatus.OK


def test_admin_sends_a_visitor_to_the_login(client):
    response = client.get("/admin/")

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == "/admin/login/?next=/admin/"
