"""Business invariants: pure constants, read by mills only."""

import re

# An Open Library work id, like OL45804W. It goes into request paths and searches.
WORK_ID = re.compile(r"OL\d+W")
