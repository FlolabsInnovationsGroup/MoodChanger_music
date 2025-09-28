# MoodChanger Music

This small app generates Spotify playlists based on mood/genre selections.

Developer quickstart
--------------------

1. (Optional) Enable mock mode to run without Spotify credentials:

   PowerShell:

   ```powershell
   $env:MOCK_MODE = '1'
   python -m uvicorn app:app --reload
   ```

2. Open the UI at http://127.0.0.1:8001/static/app.html

3. Run the smoke test (uses TestClient):

   ```powershell
   $env:MOCK_MODE = '1'
   python scripts\smoke_test.py
   ```

Notes
-----
- To use real Spotify integration, set SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET and optionally SPOTIFY_REDIRECT_URI in a .env file.
- The app stores tokens in `tokens.json` in the project root.
