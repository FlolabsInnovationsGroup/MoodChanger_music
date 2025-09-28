Summary

This PR adds a complete developer experience and CI onboarding:

- Tests: comprehensive pytest test suite under `tests/` (mock-mode friendly)
- CI: GitHub Actions workflow to run tests, run pre-commit/black, upload coverage, and now also run type checks and a basic security scan
- Formatting: `.pre-commit-config.yaml` with black and repo formatted
- Docs: `CONTRIBUTING.md`, `CHANGELOG.md`, README updates, and PR/Issue templates
- Scripts: PowerShell helper scripts for setting up a venv and running tests locally
- Repo hygiene: LICENSE, CODEOWNERS, dependabot, and `.gitignore` improvements

Notes

- The CI uploads `coverage.xml` when `CODECOV_TOKEN` is provided in repository Secrets.
- `mypy` is run with `--ignore-missing-imports` to avoid noise; tighten this once third-party stubs are available.
- `bandit` is run with a low severity threshold; review its output in CI logs if present.

Validation

- Local: all tests passed (15 tests), pre-commit/black ran successfully.

Checklist

- [x] Tests added
- [x] CI workflow added and extended
- [x] pre-commit configured
- [x] Docs & helper scripts added

