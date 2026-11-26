"""Names in use where vulture does not look. `lint:vulture` reads this file too."""

from erudite.links.db.django.models import Sync
from erudite.pacts import BookDTO, BookListDTO

# Read by the book page template.
_ = BookDTO.cover_url
# Read by the book list template.
_ = BookListDTO.total
# Written and filtered by keyword only.
_ = Sync.sync_type
