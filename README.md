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

The scan adds every file under the directory as a book. For an EPUB or PDF the
book gets the title, authors and ISBN the file carries. A file that carries no
title becomes a book named after the file, with no author; correct it in the
admin under Books, where the filter on authors finds the books that have none.
The scan only reads the files. Run it again after you add files: it skips the
ones it knows, even after you rename or move them.

To leave out files that are not books, add their extension, for example `png`,
in the admin under Ignored file extensions. The next scan does not add new
files with that extension; books it already added stay. To leave out one file,
for example a ZIP archive that holds only images, delete its book: the scan
does not add it again.

## Raw books

The import and the scan store what they found as a raw book, next to the book
you see and edit. The admin lists raw books with their source and file path.
They are read-only: your edits go to the book and the next run leaves it alone.

## Set up the local model

The features that read your files with a model use
[Ollama](https://ollama.com/), which runs the model on your machine. The text
of your files never leaves it. Install Ollama on the machine that holds the
files:

```sh
curl -fsSL https://ollama.com/install.sh | sh
```

On Linux the installer starts Ollama as a service at `localhost:11434`. Check
that it answers:

```sh
curl http://localhost:11434/api/version
```

Ollama uses a graphics card if the machine has one and the processor if not;
on the processor each file takes longer.

## Work on it

```sh
mise tasks          # every task, with a description
mise run check      # format and lint
mise run test:py    # all tests
mise run fullcheck  # the gate before a commit
```

`mise run bootstrap` installs the commit hooks. They run through
[hk](https://hk.jdx.dev/) and are configured in `hk.pkl`.
