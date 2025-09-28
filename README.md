# MoodChanger Music

![CI](https://github.com/FlomadLabsRD/MoodChanger_music/actions/workflows/ci.yml/badge.svg)

![Codecov](https://codecov.io/gh/FlomadLabsRD/MoodChanger_music/branch/main/graph/badge.svg)

This small app generates Spotify playlists based on mood/genre selections.

Developer quickstart
--------------------

1. Start the app in mock mode (no Spotify credentials required):

   PowerShell (from repository root):

   ```powershell
   .\run_mock.ps1
   ```

   Windows CMD:

   ```bat
   .\run_mock.bat
   ```

2. Open the UI at http://127.0.0.1:8001/static/app.html

3. Run the tests (the scripts set MOCK_MODE by default):

   PowerShell:

   ```powershell
   .\run_tests.ps1
   ```

Notes
-----
- To use real Spotify integration, set SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET and optionally SPOTIFY_REDIRECT_URI in a `.env` file.
- The app stores tokens in `tokens.json` in the project root.

Pre-commit
----------
Install pre-commit and enable hooks to auto-format on commit:

```powershell
pip install pre-commit
pre-commit install
pre-commit run --all-files
```
