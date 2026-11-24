from typing import TYPE_CHECKING, override

from django.core.management.base import BaseCommand, CommandError

from erudite.gates.cli.django.services import build_services
from erudite.pacts import BookFieldsData, NotFoundError, ProposalOutcome

if TYPE_CHECKING:
    from argparse import ArgumentParser

_MESSAGES = {
    ProposalOutcome.FILLED: "The book had none of these fields: they are filled.",
    ProposalOutcome.WAITING: "The book holds one of these fields: a decision waits.",
    ProposalOutcome.ALREADY_WAITING: "Skipped: a decision waits for the book already.",
    ProposalOutcome.NOTHING_NEW: "Skipped: nothing proposed differs from the book.",
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
        proposal = BookFieldsData(
            title=options["title"],
            authors=options["authors"].split(";"),
            isbn10=options["isbn10"],
            isbn13=options["isbn13"],
            series=options["series"],
            series_position=options["series_position"],
        )
        try:
            outcome = build_services().classification.propose(
                int(options["book_id"]), proposal
            )
        except NotFoundError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(_MESSAGES[outcome]))
