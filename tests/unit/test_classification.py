from unittest.mock import MagicMock

from erudite.mills import ClassificationService
from erudite.pacts import ProposalOutcome

BOOK = 7
NO_AUTHOR = {
    "title": "scan_0042",
    "authors": [],
    "isbn10": "",
    "isbn13": "",
    "series": "",
    "series_position": "",
}


def _service(*, held=None, waiting=False):
    decisions = MagicMock()
    decisions.exists.return_value = waiting
    decisions.book_fields.return_value = NO_AUTHOR | (held or {})
    return ClassificationService(decisions=decisions), decisions


def test_a_proposal_for_fields_the_book_does_not_hold_is_filled_at_once():
    service, decisions = _service()
    proposal = {"authors": ["Frank Herbert"], "isbn13": "9780441172719"}

    outcome = service.propose(BOOK, proposal)

    assert outcome == ProposalOutcome.FILLED
    decisions.fill.assert_called_once_with(BOOK, proposal)
    decisions.create.assert_not_called()


def test_a_proposal_for_a_field_the_book_holds_fills_nothing_and_waits():
    service, decisions = _service()
    proposal = {"title": "Dune", "authors": ["Frank Herbert"]}

    outcome = service.propose(BOOK, proposal)

    assert outcome == ProposalOutcome.WAITING
    decisions.create.assert_called_once_with(BOOK, proposal)
    decisions.fill.assert_not_called()


def test_a_book_with_a_waiting_decision_is_skipped():
    service, decisions = _service(waiting=True)

    outcome = service.propose(BOOK, {"authors": ["Frank Herbert"]})

    assert outcome == ProposalOutcome.SKIPPED
    decisions.exists.assert_called_once_with(BOOK)
    decisions.fill.assert_not_called()
    decisions.create.assert_not_called()


def test_a_proposal_that_says_what_the_book_says_is_skipped():
    service, decisions = _service(held={"authors": ["Frank Herbert"]})

    outcome = service.propose(
        BOOK, {"title": "scan_0042", "authors": ["Frank Herbert"], "isbn10": ""}
    )

    assert outcome == ProposalOutcome.SKIPPED
    decisions.fill.assert_not_called()
    decisions.create.assert_not_called()


def test_only_the_values_that_differ_from_the_book_are_filled():
    service, decisions = _service()

    outcome = service.propose(
        BOOK, {"title": "scan_0042", "authors": ["Frank Herbert"], "series": ""}
    )

    assert outcome == ProposalOutcome.FILLED
    decisions.fill.assert_called_once_with(BOOK, {"authors": ["Frank Herbert"]})
