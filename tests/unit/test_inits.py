from unittest.mock import MagicMock

from erudite.inits import ServiceInjectionMiddleware, Services


def test_the_middleware_gives_each_request_its_services():
    request = MagicMock()
    get_response = MagicMock()

    response = ServiceInjectionMiddleware(get_response)(request)

    assert isinstance(request.services, Services)
    assert response is get_response.return_value
    get_response.assert_called_once_with(request)
