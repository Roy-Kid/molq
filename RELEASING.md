# Releasing

0.9.0 replaces the 0.8 API without compatibility or automatic jobs.db migration. It does not delete user data or native tasks.

1. Update the version in pyproject.toml, molq.__version__, CLI version, protocol release and sdk/typescript/package.json/package-lock.json. Regenerate the contract/types/Web codec.
2. Run tools/check_generated.py, Ruff, ty, Python tests with coverage and TypeScript conformance.
3. Build sdist/wheel; install the wheel into a clean environment and run tools/check_wheel.py outside the checkout. Check package metadata and npm pack contents.
4. Confirm Linux/macOS and Windows control-plane CI. Document native Scheduler mapping limits and actual live-cluster evidence.
5. Tag only after validation. The existing v* release workflow requires reusable CI and matching package version before PyPI trusted publishing. A master push alone does not publish a package.

TypeScript publishing is a separate explicit registry release; building/testing the package does not publish it.
