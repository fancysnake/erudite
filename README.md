# erudite

A book manager that runs on your own machine. It builds one library from a
Goodreads export, a directory of e-book files and the books on your shelf,
then orders the to-read list by goal, by series and by topic.

The plan is in [issue #2](https://github.com/fancysnake/erudite/issues/2).

## Run it

You need [mise](https://mise.jdx.dev/).

```sh
mise install
mise run bootstrap
mise run start
```

Open <http://localhost:8020>. The admin is at `/admin/`; create a login with
`mise run dj createsuperuser`.

## Import your Goodreads library

Export it at <https://www.goodreads.com/review/import>, then:

```sh
mise run dj import_goodreads ~/Downloads/goodreads_library_export.csv
```

The import adds the books the library does not hold yet. It never changes a
book that is already there, so you can run it again after each new export.

## Scan your e-book files

```sh
mise run dj scan_files ~/Books
```

The scan records every file under the directory. For an EPUB or PDF it records
the title, authors and ISBN the file carries. A file that carries no title is
recorded under its file name; correct it in the admin under Book files. The
scan only reads the files. Run it again after you add files: it skips the ones
it knows, even after you rename or move them.

To leave out files that are not books, add their extension, for example `png`,
in the admin under Ignored file extensions. The next scan marks the new files
with that extension as ignored; files it already knows keep their Ignored tick. To ignore one file, for example a ZIP archive that
holds only images, tick Ignored on that file under Book files.

## Work on it

```sh
mise tasks          # every task, with a description
mise run check      # format and lint
mise run test:py    # all tests
mise run fullcheck  # the gate before a commit
```

`mise run bootstrap` installs the commit hooks. They run through
[hk](https://hk.jdx.dev/) and are configured in `hk.pkl`.
