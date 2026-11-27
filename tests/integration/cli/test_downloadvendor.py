import base64
import hashlib
from io import BytesIO, StringIO
from urllib.error import URLError

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from erudite.links.web import https

JS = b"console.log('hello');"
CSS = b"body { color: red; }"


def _dependency(filename, content):
    return {
        "name": filename,
        "url": f"https://cdn.example.com/{filename}",
        "filename": filename,
        "sha384": base64.b64encode(hashlib.sha384(content).digest()).decode(),
    }


def _run(*args):
    out = StringIO()
    call_command("downloadvendor", *args, stdout=out)
    return out.getvalue()


@pytest.fixture(name="vendor_dir")
def vendor_dir_fixture(settings, tmp_path):
    settings.VENDOR_STATIC_DIR = tmp_path / "vendor"
    settings.VENDOR_DEPENDENCIES = [_dependency("lib.min.js", JS)]
    return settings.VENDOR_STATIC_DIR


@pytest.fixture(name="cdn")
def cdn_fixture(monkeypatch):
    """Stand in for `urlopen`: maps a URL to its content, or to an error to raise."""
    answers = {"https://cdn.example.com/lib.min.js": JS}
    requests = []

    def fake(request, **_kwargs):
        requests.append(request)
        answer = answers[request.full_url]
        if isinstance(answer, Exception):
            raise answer
        return BytesIO(answer)

    monkeypatch.setattr(https, "urlopen", fake)
    answers["requests"] = requests
    return answers


def test_a_file_with_the_right_hash_is_saved(vendor_dir, cdn):
    output = _run()

    assert output == (
        "lib.min.js: Verified and saved to lib.min.js\n"
        "Summary: 1 downloaded, 0 skipped, 0 failed\n"
    )
    assert (vendor_dir / "lib.min.js").read_bytes() == JS
    (request,) = cdn["requests"]
    assert request.header_items() == [("User-agent", "erudite")]


def test_a_filename_with_a_directory_gets_the_directory(settings, vendor_dir, *, cdn):
    settings.VENDOR_DEPENDENCIES = [_dependency("fonts/icons.woff2", CSS)]
    cdn["https://cdn.example.com/fonts/icons.woff2"] = CSS

    _run()

    assert (vendor_dir / "fonts" / "icons.woff2").read_bytes() == CSS


def test_a_url_is_asked_over_https_only(settings, vendor_dir, *, cdn):
    settings.VENDOR_DEPENDENCIES[0]["url"] = "file:///etc/hosts"
    out = StringIO()

    with pytest.raises(CommandError):
        call_command("downloadvendor", stdout=out)

    assert (
        "lib.min.js: Download failed - file:///etc/hosts is not an HTTPS address."
    ) in out.getvalue()
    assert not cdn["requests"]
    assert not vendor_dir.exists()


def test_a_stored_file_with_the_right_hash_is_skipped(vendor_dir, cdn):
    vendor_dir.mkdir()
    (vendor_dir / "lib.min.js").write_bytes(JS)

    output = _run()

    assert output == (
        "lib.min.js: Skipped (file exists with valid hash)\n"
        "Summary: 0 downloaded, 1 skipped, 0 failed\n"
    )
    assert not cdn["requests"]


def test_a_stored_file_with_a_wrong_hash_is_downloaded_again(vendor_dir, cdn):
    vendor_dir.mkdir()
    (vendor_dir / "lib.min.js").write_bytes(b"damaged")

    _run()

    assert (vendor_dir / "lib.min.js").read_bytes() == JS
    assert len(cdn["requests"]) == 1


def test_force_downloads_a_stored_file_again(vendor_dir, cdn):
    vendor_dir.mkdir()
    (vendor_dir / "lib.min.js").write_bytes(JS)

    output = _run("--force")

    assert "1 downloaded, 0 skipped" in output
    assert len(cdn["requests"]) == 1


def test_a_dry_run_downloads_nothing(vendor_dir, cdn):
    output = _run("--dry-run")

    assert output == (
        "lib.min.js: Would download from https://cdn.example.com/lib.min.js\n"
        "Summary: 1 downloaded, 0 skipped, 0 failed\n"
    )
    assert not cdn["requests"]
    assert not vendor_dir.exists()


def test_a_file_with_a_wrong_hash_is_not_saved(vendor_dir, cdn):
    cdn["https://cdn.example.com/lib.min.js"] = b"something else"
    out = StringIO()

    with pytest.raises(CommandError, match=r"1 dependency download\(s\) failed"):
        call_command("downloadvendor", stdout=out)

    assert "lib.min.js: Hash mismatch!" in out.getvalue()
    assert not vendor_dir.exists()


def test_a_failed_download_does_not_stop_the_next_one(settings, vendor_dir, *, cdn):
    settings.VENDOR_DEPENDENCIES = [
        _dependency("lib.min.js", JS),
        _dependency("lib.min.css", CSS),
    ]
    cdn["https://cdn.example.com/lib.min.js"] = URLError("Connection refused")
    cdn["https://cdn.example.com/lib.min.css"] = CSS
    out = StringIO()

    with pytest.raises(CommandError, match=r"1 dependency download\(s\) failed"):
        call_command("downloadvendor", stdout=out)

    assert "lib.min.js: Download failed" in out.getvalue()
    assert "Summary: 1 downloaded, 0 skipped, 1 failed" in out.getvalue()
    assert not (vendor_dir / "lib.min.js").exists()
    assert (vendor_dir / "lib.min.css").read_bytes() == CSS
