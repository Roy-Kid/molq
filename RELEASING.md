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

4. Build distributions:

   ```bash
   python -m build
   ```

5. Optionally verify artifacts:

   ```bash
   python -m pip install twine
   python -m twine check dist/*
   ```

6. Tag the release (tag must match the version, with a `v` prefix):

   ```bash
   git tag v0.6.0
   git push origin v0.6.0
   ```

7. Wait for the `Release` workflow to publish the artifacts to PyPI.
8. Publish a GitHub release for the tag; draft notes from `git log` since the
   previous tag (or from `docs/release-notes.md` if you keep highlights there).

## Documentation Release

If documentation dependencies are installed:

```bash
zensical build
```

Deploy the generated `site/` directory with your preferred static host.
