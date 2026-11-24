from typing import TYPE_CHECKING, override

from django.core.management.base import BaseCommand, CommandError

from erudite.gates.cli.django.services import build_services
from erudite.pacts import NotFoundError, ProposalOutcome

if TYPE_CHECKING:
    from argparse import ArgumentParser

    from erudite.pacts import BookFieldsData

_MESSAGES = {
    ProposalOutcome.FILLED: "The book had none of these fields: they are filled.",
    ProposalOutcome.WAITING: "The book holds one of these fields: a decision waits.",
    ProposalOutcome.SKIPPED: "Skipped: a decision waits already, or nothing is new.",
}


class Command(BaseCommand):
    help = (
        "Propose details for a book the way a classification does. They are"
        " filled where the book holds none of them; otherwise they wait in the"
        " admin as a decision."
    )

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("book_id", type=int)
        parser.add_argument("--title", default="")
        parser.add_argument("--authors", default="", help="Names with ; between.")
        parser.add_argument("--isbn10", default="")
        parser.add_argument("--isbn13", default="")
        parser.add_argument("--series", default="")
        parser.add_argument("--series-position", default="")

    @override
    def handle(self, *_args: str, **options: str) -> None:
        names = ("title", "isbn10", "isbn13", "series", "series_position")
        proposal: BookFieldsData = {name: options[name] for name in names}
        proposal["authors"] = [
            name.strip() for name in options["authors"].split(";") if name.strip()
        ]
        try:
            outcome = build_services().classification.propose(
                int(options["book_id"]), proposal
            )
        except NotFoundError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(_MESSAGES[outcome]))
