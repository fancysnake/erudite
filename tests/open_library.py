import json
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

from erudite.pacts import CoverDTO, WorkDTO

FOX_ID = "OL45804W"
FOX = {
    "key": f"/works/{FOX_ID}",
    "title": "Fantastic Mr Fox",
    "author_name": ["Roald Dahl"],
    "first_publish_year": 1970,
    "cover_i": 6498519,
    "edition_count": 161,
    "description": "A fox outwits\nthree farmers.",
}
# A work that has only what every work has.
BARE_ID = "OL1W"
BARE = {"key": f"/works/{BARE_ID}", "title": "Untitled", "edition_count": 1}
COVER = b"a JPEG"
# `FOX` and `BARE` as the client gives them.
FOX_WORK = WorkDTO(
    work_id=FOX_ID,
    title="Fantastic Mr Fox",
    authors=("Roald Dahl",),
    first_year=1970,
    cover=CoverDTO(
        cover_id=6498519, url="https://covers.openlibrary.org/b/id/6498519-M.jpg"
    ),
    edition_count=161,
    description="A fox outwits\nthree farmers.",
)
BARE_WORK = WorkDTO(
    work_id=BARE_ID,
    title="Untitled",
    authors=(),
    first_year=None,
    cover=None,
    edition_count=1,
    description="",
)


class FakeOpenLibrary:
    """Stands in for `urlopen`: answers by path and keeps every request.

    `searches` maps a query to the works found for it; `error` is raised in
    place of an answer.
    """

    def __init__(self):
        self.searches = {}
        self.error = None
        self.requests = []

    @property
    def queries(self):
        return [
            parse_qs(urlsplit(request.full_url).query)["q"][0]
            for request in self.requests
            if "/search.json" in request.full_url
        ]

    def __call__(self, request, timeout):
        self.requests.append(request)
        if self.error:
            raise self.error
        url = urlsplit(request.full_url)
        if url.path == "/search.json":
            docs = self.searches.get(parse_qs(url.query)["q"][0], [])
            return BytesIO(json.dumps({"docs": docs}).encode())
        return BytesIO(COVER)
