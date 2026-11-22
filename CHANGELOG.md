# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog],
and this project adheres to [Semantic Versioning].

## [Unreleased]

### Added

- `mise run dj scan_files <directory>` records the EPUB and PDF files under a
  directory with the metadata they carry; a second scan adds nothing and no
  file is written to.
- Book files show in the admin, where their details can be corrected.
- `mise run dj import_goodreads <export.csv>` adds the books of a Goodreads
  library export; a second import leaves books already in the library unchanged.
- Books show in the admin, where the reading status can be changed.
- The home page counts the books in the library.

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
