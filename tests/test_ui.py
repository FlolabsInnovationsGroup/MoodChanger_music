import os

# Ensure MOCK_MODE for the app where useful
os.environ.setdefault("MOCK_MODE", "1")

from fastapi.testclient import TestClient
from app import app


client = TestClient(app)


def test_home_page_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "Mood Playlists" in r.text


def test_static_app_html_served():
    r = client.get("/static/app.html")
    assert r.status_code == 200
    # basic sanity check for the HTML content
    assert "mood-multi-tags" in r.text or "Mood Playlists" in r.text


def test_genre_seeds_refresh():
    r = client.get("/api/spotify/genre-seeds?refresh=1")
    assert r.status_code == 200
    j = r.json()
    assert "fetched_at" in j and "genres" in j
