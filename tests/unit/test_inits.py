from unittest.mock import MagicMock

from erudite import inits
from erudite.inits import ServiceInjectionMiddleware, Services


def test_the_middleware_gives_each_request_its_services():
    request = MagicMock()
    get_response = MagicMock()

    response = ServiceInjectionMiddleware(get_response)(request)

    assert isinstance(request.services, Services)
    assert response is get_response.return_value
    get_response.assert_called_once_with(request)


def test_every_request_shares_one_open_library_client(monkeypatch):
    work_service = MagicMock()
    monkeypatch.setattr(inits, "WorkService", work_service)

    for services in (Services(), Services()):
        assert services.works is work_service.return_value

    first, second = work_service.call_args_list
    assert first.kwargs["open_library"] is second.kwargs["open_library"]
