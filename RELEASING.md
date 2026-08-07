# Releasing

This repository uses a static version in `pyproject.toml`.

## PyPI Trusted Publisher

This repository is set up to publish through PyPI trusted publishing from GitHub Actions.
No PyPI API token should be stored in GitHub secrets for the normal release flow.

Configure the trusted publisher in PyPI with:

- Project name: `molcrafts-molq`
- Owner: `MolCrafts`
- Repository: `molq`
- Workflow: `release.yml`
- Environment: `pypi`

The GitHub repository must also have an environment named `pypi`.

## Release Checklist

1. Ensure `pyproject.toml` has the intended version (e.g. `0.6.0`).
2. Optionally refresh `docs/release-notes.md` for user-facing highlights.
   Full history is git log / tags — no `CHANGELOG.md`. Keep README /
   CLAUDE.md / docs paths current.
3. Local CI parity (must match `.github/workflows/ci.yml`):

   ```bash
   ruff format --check src tests
   ruff check src tests
   pre-commit run --all-files
   pytest -q --cov=molq --cov-report=xml
   ```

   Install hooks once with `pre-commit install` so commit/push gate the same
   checks (static on commit; full pytest on push).

4. Tag the release (tag must match the version, with a `v` prefix):

   ```bash
   git tag v0.7.0
   git push origin v0.7.0
   ```

5. Wait for the `Release` workflow. It re-runs lint and the test suite,
   verifies the tag matches `pyproject.toml`, then builds and publishes.
6. Publish a GitHub release for the tag; draft notes from `git log` since the
   previous tag (or from `docs/release-notes.md` if you keep highlights there).

> **Do not build or upload by hand.** Trusted publishing means the artifact
> that reaches PyPI is the one CI builds from the tag. `python -m build`
> locally is only ever a debugging aid — the `Package` job in `ci.yml` already
> builds the wheel, runs `twine check --strict`, installs it into a clean
> environment, imports every subpackage, and runs a job through the console
> script on every push and pull request.

## Documentation Release

If documentation dependencies are installed:

```bash
zensical build
```

Deploy the generated `site/` directory with your preferred static host.
