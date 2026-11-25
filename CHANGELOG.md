# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog],
and this project adheres to [Semantic Versioning].

## [Unreleased]

### Added

- "Find on Open Library" on a book in the admin, and as an action on selected
  books, opens a page that searches Open Library with text the user can change.
  One pick gives the book the title, authors, description and cover of the
  work, and keeps the id of the work. Selected books come one after another,
  each with a skip. Nothing is saved before a pick, and an ISBN is never written.
- `mise run dj scan_files <directory>` adds every file under a directory as a
  book, with the metadata an EPUB or PDF carries; a second scan adds nothing and
  no file is written to.
- The scan leaves out a file whose extension is on the list of ignored file
  extensions, and its summary counts those files.
- `mise run dj import_goodreads <export.csv>` adds the books of a Goodreads
  library export; a second import leaves books already in the library unchanged.
- The import and the scan keep what they found as a read-only raw book next to
  the book. A book deleted from the library is not added again.
- Books show in the admin, where the reading status can be changed and a filter
  finds the books that have no author.
- The home page counts the books in the library.
- A proposal of details for a book fills the fields the book lacks. If the book
  holds one of the proposed fields, nothing is filled and the proposal waits in
  the admin as a decision, where the user accepts all fields, some or none.
- `mise run dj propose <book id> --title … --authors …` makes such a proposal by
  hand.

## [0.1.0] - 2026-11-21

### Added

- `mise run bootstrap` sets up a fresh clone: dependencies, commit hooks, database.
- `mise run start` serves the home page on <http://localhost:8020>.
- The Django admin answers at `/admin/`.

<!-- Links -->
[keep a changelog]: https://keepachangelog.com/en/1.0.0/
[semantic versioning]: https://semver.org/spec/v2.0.0.html

<!-- Versions -->
[unreleased]: https://github.com/fancysnake/erudite/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/fancysnake/erudite/releases/tag/v0.1.0
