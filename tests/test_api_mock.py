import os

# Ensure MOCK_MODE is enabled for these tests before app imports it
os.environ.setdefault("MOCK_MODE", "1")

from fastapi.testclient import TestClient
from app import app


client = TestClient(app)


def test_moods_endpoint():
    r = client.get("/api/moods")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert "happy" in data


def test_genre_seeds_mock():
    r = client.get("/api/spotify/genre-seeds")
    assert r.status_code == 200
    j = r.json()
    assert "genres" in j and isinstance(j["genres"], list)


def test_mood_labels_mock():
    r = client.get("/api/spotify/mood-labels")
    assert r.status_code == 200
    j = r.json()
    assert "labels" in j and isinstance(j["labels"], list)


def test_playlist_mock_returns_sample_titles():
    # POST form data (no auth required in MOCK_MODE)
    r = client.post("/api/playlist", data={"mood": "happy", "limit": "5"})
    assert r.status_code == 200
    j = r.json()
    assert j.get("added") == 5
    assert "sample_titles" in j and isinstance(j["sample_titles"], list)
