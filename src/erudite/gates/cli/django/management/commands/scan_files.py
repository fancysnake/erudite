from pathlib import Path
from typing import TYPE_CHECKING, override

from django.core.management.base import BaseCommand, CommandError

from erudite.gates.cli.django.services import build_services
from erudite.pacts import FileScanError

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Command(BaseCommand):
    help = (
        "Add the EPUB and PDF files under a directory that the library does not"
        " know yet. The files are only read; files already known stay as they are."
    )

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("directory", type=Path)

    @override
    def handle(self, *_args: str, **options: Path) -> None:
        try:
            summary = build_services().book_files.scan(options["directory"])
        except FileScanError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Files added: {summary.created}. Already known: {summary.skipped}."
            )
        )
