# Contributing

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

If you want to work on the documentation site:

```bash
pip install -e ".[docs]"
```

## Local Checks

Run the standard checks before opening a pull request:

```bash
ruff check src tests
ruff format --check src tests
ty check src/
pytest -q
```

If docs dependencies are installed, you can preview the site locally:

```bash
zensical serve
```

## CI

One workflow per kind of work. A *feature* ref is any branch other than
`dev`/`master`/`main`; an *integration* ref is one of those, or a pull request
into one. A pull request from a branch of this repository does not re-run
what its push already ran: lint and docs never, the full test tier only when
the head is a feature branch (its push ran the fast tier).

| workflow | feature branch (fork or MolCrafts) | integration ref (fork or MolCrafts) | MolCrafts only |
|---|---|---|---|
| `lint.yml` | `lint / hooks` (pre-commit stage, all files) | same | — |
| `test.yml` | `test / py3.12 (ubuntu-latest)`, `test / package` | `test / py{3.12,3.13} ({ubuntu,macos}-latest)`, `test / package` | — |
| `docs.yml` | `docs / build` (`zensical build --strict`) | same | deploy: Cloudflare Pages, outside Actions |
| `release.yml` | — | — | `v*` tag: lint + test + `release / build` + `release / pypi`; `workflow_dispatch` = dry run (no upload) |

The `protect-master` ruleset on `master` requires a pull request, blocks force
pushes and deletion, and requires the integration-tier `lint /`, `test /` and `docs /` checks.


## Change Expectations

- Keep public API changes intentional and documented.
- Add or update tests for behavior changes and bug fixes.
- Update `README.md` and `docs/` when public behavior changes.
  Release history lives in git tags / GitHub Releases (no `CHANGELOG.md`).
- Keep scheduler-specific changes explicit about which backend they affect.

## Pull Requests

- Keep each PR scoped to one logical change.
- Describe user-visible impact clearly.
- Include migration notes if existing user code needs to change.
