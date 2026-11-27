from unittest.mock import MagicMock

import pytest

from erudite.mills import VendorService
from erudite.pacts import DownloadError


@pytest.mark.parametrize(
    ("url", "path"),
    (
        ("https://cdn.example.com/lib.min.js", "/lib.min.js"),
        ("https://cdn.example.com/css?family=Lora", "/css?family=Lora"),
    ),
)
def test_a_download_reads_the_host_and_path_of_the_address(url, path):
    web = MagicMock()

    assert VendorService(web=web).download(url) == web.read.return_value
    web.read.assert_called_once_with("cdn.example.com", path)


@pytest.mark.parametrize(
    "url", ("http://cdn.example.com/lib.js", "file:///etc/hosts", "cdn.example.com")
)
def test_an_address_that_is_not_https_is_not_read(url):
    web = MagicMock()

    with pytest.raises(DownloadError, match="is not an HTTPS address"):
        VendorService(web=web).download(url)
    web.read.assert_not_called()
