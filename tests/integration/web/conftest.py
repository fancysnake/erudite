from collections import UserString

import pytest


class _StrictUndefined(UserString):
    """`string_if_invalid` that fails the test on an undefined template variable."""

    def __contains__(self, key):
        return key == "%s"

    def __mod__(self, name):
        msg = f"Undefined template variable {name!r}"
        raise AssertionError(msg)


@pytest.fixture(name="browser")
def browser_fixture(client, settings):
    """Return a client that fails on undefined template variables."""
    templates = [{**t, "OPTIONS": {**t["OPTIONS"]}} for t in settings.TEMPLATES]
    templates[0]["OPTIONS"]["string_if_invalid"] = _StrictUndefined("%s")
    settings.TEMPLATES = templates
    return client
