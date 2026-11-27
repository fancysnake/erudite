"""What is read over HTTPS."""

from typing import TYPE_CHECKING, override
from urllib.request import Request, urlopen

from erudite.pacts import DownloadError, WebFilesProtocol

if TYPE_CHECKING:
    from http.client import HTTPResponse

# A downloaded file may be large.
_TIMEOUT = 30


def read(host: str, path: str, *, timeout: float) -> bytes:
    """Return the answer to a GET of `https://{host}{path}`; `OSError` if none."""
    # `urlopen` is typed as `Any`: the declaration gives the answer its type.
    answer: HTTPResponse
    with urlopen(
        Request(f"https://{host}{path}", headers={"User-Agent": "erudite"}),
        timeout=timeout,
    ) as answer:
        return answer.read()


class HttpsWebFiles(WebFilesProtocol):
    @override
    def read(self, host: str, path: str) -> bytes:
        try:
            return read(host, path, timeout=_TIMEOUT)
        except OSError as exc:
            raise DownloadError(str(exc)) from exc
