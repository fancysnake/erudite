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

Open <http://localhost:8020>.

## Work on it

```sh
mise tasks          # every task, with a description
mise run check      # format and lint
mise run test:py    # all tests
mise run fullcheck  # the gate before a commit
```

`mise run bootstrap` installs the commit hooks. They run through
[hk](https://hk.jdx.dev/) and are configured in `hk.pkl`.
