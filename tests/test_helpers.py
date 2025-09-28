import os

# Force MOCK_MODE to keep tests isolated
os.environ.setdefault("MOCK_MODE", "1")

import pytest

from fastapi import HTTPException

import app


def test_ensure_token_missing(monkeypatch):
    # Simulate empty token store
    monkeypatch.setattr(app, "_load_tokens", lambda: {})
    with pytest.raises(HTTPException):
        app._ensure_token("no_such_user")


def test_build_recommendations_falls_back_to_top_tracks(monkeypatch):
    # Prepare a fake track as fallback
    fake_track = {"id": "fake1", "uri": "spotify:track:fake1", "name": "Fake Song", "artists": [{"name": "Artist"}]}

    # Force the primary recs to return empty and the top-tracks fallback to return our fake track
    monkeypatch.setattr(app, "_recs_with_market_fallback", lambda access_token, params: [])
    monkeypatch.setattr(app, "_fallback_from_top_tracks", lambda access_token, preset, limit=20: [fake_track])

    res = app.build_recommendations("tok", mood="happy", genre=None, limit=5)
    assert isinstance(res, dict)
    assert res.get("tracks") and res["tracks"][0]["id"] == "fake1"
