Contributing
============

Quickstart for contributors
---------------------------

1. Create a virtualenv and install requirements:

   ```powershell
   .\scripts\setup_dev.ps1
   & .\.venv\Scripts\Activate.ps1
   ```

2. Run tests locally:

   ```powershell
   & .\.venv\Scripts\python.exe -m pytest
   ```

3. Run pre-commit hooks and format code:

   ```powershell
   pip install pre-commit
   pre-commit install
   pre-commit run --all-files
   ```

4. When ready, push your branch and open a pull request. CI will run tests, lint and upload coverage.

Notes
-----
- The project supports a MOCK_MODE for local development. Use `run_mock.ps1` to run the app without Spotify credentials.
- Tests are designed to run offline using monkeypatching and mock helpers.

Codecov
------

To enable automatic coverage uploads to Codecov from CI, add a repository secret named `CODECOV_TOKEN` containing your Codecov upload token. Once set, CI will upload `coverage.xml` and the README will show the Codecov badge.

