# CLAUDE.md

Local book manager: one library from Goodreads, e-book files and the shelf,
ordered by goal, series and topic. Python 3.14, Poetry, mise, Django, SQLite.
The plan is the epic, issue #2, and its sub-issues.

## Commands

`mise tasks` is the source of truth. The commit gate is `mise run fullcheck`;
`mise run pr-fix` is the same without the tingle debt budget.
Narrow first: `mise run lint:ruff`, `mise run test:unit`, `mise run test:int`.
Fresh clone: `mise run bootstrap`, then `mise run start` on localhost:8020.
Commit hooks run through hk (`hk.pkl`); `mise run lint:hk` runs them on every file.

## Architecture

GLIMPSE layers under `src/erudite/`, enforced by import-linter:
`pacts` (DTOs, protocols, enums) → `specs` (invariants) → `mills` (services, no
Django) → `links` (ORM, admin, external clients) → `gates` (views, commands) →
`inits` (DI, middleware) → `edges` (settings, wsgi). Load the `glimpse` skill
before adding or moving code.

- Views call `request.services.*` and render DTOs. ORM objects never leave `links`.
- Admin is django-unfold, model-coupled, lives in `links/db/django/admin.py`.

## Rules

- The app runs on one machine. No accounts, no hosting, no deployment code.
- Never write to, rename or move a book file.
- Never write to Goodreads.
- Only titles, authors, ISBNs and descriptions leave the machine.
- Zero Node: no `package.json`, no bundler. Plain CSS, HTMX as one vendored file.
- No inline lint suppressions, no global rule disabling to get green.
- Strings wrapped for i18n, English only; schema changes get a reversible migration.
