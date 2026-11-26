"""Names in use where vulture does not look. `lint:vulture` reads this file too."""

from erudite.pacts import WorkDTO

# Read by the Open Library picker template.
_ = WorkDTO.cover_url
