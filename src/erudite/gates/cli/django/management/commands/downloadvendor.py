import base64
import hashlib
from typing import TYPE_CHECKING, override

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from erudite.gates.cli.django.services import build_services
from erudite.pacts import DownloadError

if TYPE_CHECKING:
    from argparse import ArgumentParser
    from pathlib import Path


def _sha384(content: bytes) -> str:
    """Hash as an SRI attribute writes it: base64."""
    return base64.b64encode(hashlib.sha384(content).digest()).decode("ascii")


class Command(BaseCommand):
    help = (
        "Download each file of settings.VENDOR_DEPENDENCIES to"
        " settings.VENDOR_STATIC_DIR. A file is saved only when its SHA-384 hash"
        " is the one the settings give."
    )

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Download a file again even if it is there with the right hash.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be downloaded; download nothing.",
        )

    @override
    def handle(self, *_args: str, **options: bool) -> None:
        dependencies: list[dict[str, str]] = settings.VENDOR_DEPENDENCIES
        vendor_dir: Path = settings.VENDOR_STATIC_DIR
        stats = {"downloaded": 0, "skipped": 0, "failed": 0}
        for dep in dependencies:
            result = self._process(
                dep,
                vendor_dir / dep["filename"],
                force=options["force"],
                dry_run=options["dry_run"],
            )
            stats[result] += 1
        self.stdout.write(
            f"Summary: {stats['downloaded']} downloaded, {stats['skipped']} skipped,"
            f" {stats['failed']} failed"
        )
        if stats["failed"]:
            msg = f"{stats['failed']} dependency download(s) failed."
            raise CommandError(msg)

    def _process(
        self, dep: dict[str, str], filepath: Path, *, force: bool, dry_run: bool
    ) -> str:
        """Return the key of `stats` the dependency counts in."""
        name, url, expected = dep["name"], dep["url"], dep["sha384"]
        if (
            not force
            and filepath.exists()
            and _sha384(filepath.read_bytes()) == expected
        ):
            self.stdout.write(f"{name}: Skipped (file exists with valid hash)")
            return "skipped"
        if dry_run:
            self.stdout.write(f"{name}: Would download from {url}")
            return "downloaded"
        try:
            content = build_services().vendor.download(url)
        except DownloadError as exc:
            self.stdout.write(self.style.ERROR(f"{name}: Download failed - {exc}"))
            return "failed"
        if (actual := _sha384(content)) != expected:
            self.stdout.write(
                self.style.ERROR(
                    f"{name}: Hash mismatch! Expected: {expected} Actual: {actual}"
                )
            )
            return "failed"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(content)
        self.stdout.write(f"{name}: Verified and saved to {filepath.name}")
        return "downloaded"
