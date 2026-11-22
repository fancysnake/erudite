from pathlib import Path
from typing import TYPE_CHECKING, override

from django.core.management.base import BaseCommand, CommandError

from erudite.gates.cli.django.services import build_services
from erudite.pacts import GoodreadsExportError

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Command(BaseCommand):
    help = (
        "Add the books of a Goodreads library export (CSV) that the library does"
        " not hold yet. Books already in the library stay as they are."
    )

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("export", type=Path)

    @override
    def handle(self, *_args: str, **options: Path) -> None:
        try:
            summary = build_services().library.import_goodreads(options["export"])
        except GoodreadsExportError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Books added: {summary.created}."
                f" Already in the library: {summary.skipped}."
            )
        )
