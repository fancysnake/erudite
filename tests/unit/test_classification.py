from unittest.mock import MagicMock

from erudite.mills import ClassificationService
from erudite.pacts import BOOK_FIELDS, BookFieldsData, ProposalOutcome

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
    books, decisions = MagicMock(), MagicMock()
    decisions.exists.return_value = waiting
    books.fields.return_value = NO_AUTHOR | (held or {})
    return ClassificationService(books=books, decisions=decisions), books, decisions


def test_the_book_field_names_are_the_keys_of_the_book_fields():
    assert set(BOOK_FIELDS) == BookFieldsData.__optional_keys__


def test_a_proposal_for_fields_the_book_does_not_hold_is_filled_at_once():
    service, books, decisions = _service()
    proposal = {"authors": ["Frank Herbert"], "isbn13": "9780441172719"}

    outcome = service.propose(BOOK, proposal)

    assert outcome == ProposalOutcome.FILLED
    books.fill.assert_called_once_with(BOOK, proposal)
    decisions.create.assert_not_called()


def test_a_proposal_for_a_field_the_book_holds_fills_nothing_and_waits():
    service, books, decisions = _service()
    proposal = {"title": "Dune", "authors": ["Frank Herbert"]}

    outcome = service.propose(BOOK, proposal)

    assert outcome == ProposalOutcome.WAITING
    decisions.create.assert_called_once_with(BOOK, proposal)
    books.fill.assert_not_called()


def test_a_book_with_a_waiting_decision_is_left_alone():
    service, books, decisions = _service(waiting=True)

    outcome = service.propose(BOOK, {"authors": ["Frank Herbert"]})

    assert outcome == ProposalOutcome.ALREADY_WAITING
    decisions.exists.assert_called_once_with(BOOK)
    books.fill.assert_not_called()
    decisions.create.assert_not_called()


def test_a_proposal_that_says_what_the_book_says_brings_nothing_new():
    service, books, decisions = _service(held={"authors": ["Frank Herbert"]})

    outcome = service.propose(
        BOOK, {"title": "scan_0042", "authors": ["Frank Herbert"], "isbn10": ""}
    )

    assert outcome == ProposalOutcome.NOTHING_NEW
    books.fill.assert_not_called()
    decisions.create.assert_not_called()


def test_only_the_values_that_differ_from_the_book_are_filled():
    service, books, _ = _service()

    outcome = service.propose(
        BOOK, {"title": "scan_0042", "authors": ["Frank Herbert"], "series": ""}
    )

    assert outcome == ProposalOutcome.FILLED
    books.fill.assert_called_once_with(BOOK, {"authors": ["Frank Herbert"]})


def test_proposed_author_names_are_trimmed_once_each_and_never_empty():
    service, books, _ = _service()

    service.propose(BOOK, {"authors": [" Frank Herbert", "Frank Herbert ", "", " "]})

    books.fill.assert_called_once_with(BOOK, {"authors": ["Frank Herbert"]})


def test_authors_the_book_holds_are_nothing_new_however_they_are_written():
    service, books, decisions = _service(held={"authors": ["Frank Herbert"]})

    outcome = service.propose(BOOK, {"authors": ["Frank Herbert", " Frank Herbert"]})

    assert outcome == ProposalOutcome.NOTHING_NEW
    books.fill.assert_not_called()
    decisions.create.assert_not_called()
