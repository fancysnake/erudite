"""Open Library over HTTPS: the search, the works and the cover images."""

import json
import threading
import time
from contextlib import ExitStack
from typing import TYPE_CHECKING, ClassVar, override
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from erudite.pacts import OpenLibraryError, OpenLibraryProtocol, WorkDTO

if TYPE_CHECKING:
    from http.client import HTTPResponse

_SITE = "openlibrary.org"
_COVERS = "covers.openlibrary.org"
_FIELDS = "key,title,author_name,first_publish_year,cover_i,edition_count"
_LIMIT = 10
_TIMEOUT = 20


type _Json = dict[str, _Json] | list[_Json] | str | int | float | None


# An answer is read field by field: a field of another type counts as absent.
def _fields(value: _Json) -> dict[str, _Json]:
    return value if isinstance(value, dict) else {}


def _items(value: _Json) -> list[_Json]:
    return value if isinstance(value, list) else []


def _text(value: _Json) -> str:
    return value if isinstance(value, str) else ""


def _number(value: _Json) -> int | None:
    return value if isinstance(value, int) else None


def _work(doc: dict[str, _Json]) -> WorkDTO:
    return WorkDTO(
        work_id=_text(doc.get("key")).removeprefix("/works/"),
        title=_text(doc.get("title")),
        authors=tuple(_text(name) for name in _items(doc.get("author_name"))),
        first_year=_number(doc.get("first_publish_year")),
        cover_id=_number(doc.get("cover_i")),
        edition_count=_number(doc.get("edition_count")) or 0,
    )


def _read(host: str, path: str) -> bytes:
    with ExitStack() as stack:
        answer: HTTPResponse = stack.enter_context(
            urlopen(
                Request(f"https://{host}{path}", headers={"User-Agent": "erudite"}),
                timeout=_TIMEOUT,
            )
        )
        return answer.read()


class OpenLibraryHttp(OpenLibraryProtocol):
    """Sends the query and no contact detail, so the rate is the unidentified one."""

    # Open Library allows one request each second; the process shares the pace.
    interval: ClassVar[float] = 1.0
    _lock: ClassVar[threading.Lock] = threading.Lock()
    _last: ClassVar[float] = 0.0

    def _get(self, host: str, path: str) -> bytes:
        with self._lock:
            time.sleep(max(0.0, self._last + self.interval - time.monotonic()))
            try:
                return _read(host, path)
            except OSError as exc:
                msg = f"Open Library gave no answer: {exc}"
                raise OpenLibraryError(msg) from exc
            finally:
                OpenLibraryHttp._last = time.monotonic()

    def _json(self, path: str) -> dict[str, _Json]:
        try:
            answer: _Json = json.loads(self._get(_SITE, path))
        except ValueError as exc:
            msg = "Open Library gave an answer that is not JSON."
            raise OpenLibraryError(msg) from exc
        if not isinstance(answer, dict):
            msg = "Open Library gave an answer of an unknown shape."
            raise OpenLibraryError(msg)
        return answer

    @override
    def search(self, query: str) -> list[WorkDTO]:
        params = urlencode({"q": query, "limit": _LIMIT, "fields": _FIELDS})
        docs = _items(self._json(f"/search.json?{params}").get("docs"))
        return [_work(_fields(doc)) for doc in docs]

    @override
    def description(self, work_id: str) -> str:
        text = self._json(f"/works/{work_id}.json").get("description")
        # Open Library gives the text bare, or wrapped together with its type.
        return _text(text) or _text(_fields(text).get("value"))

    @override
    def cover(self, cover_id: int) -> bytes:
        return self._get(_COVERS, f"/b/id/{cover_id}-L.jpg")
