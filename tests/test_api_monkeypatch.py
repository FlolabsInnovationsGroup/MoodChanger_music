import os

os.environ.setdefault("MOCK_MODE", "1")

from app import create_playlist_with_tracks, build_recommendations


def test_create_playlist_with_tracks_monkeypatch(monkeypatch):
    # Simulate _api_post to create playlist and add tracks
    calls = []

    def fake_api_post(access_token, path, json_body=None, params=None):
        calls.append((path, json_body))
        if path.startswith("/users/") and path.endswith("/playlists"):
            return {"id": "pl_mock", "external_urls": {"spotify": "https://open.spotify/mock/pl_mock"}}
        if path.startswith("/playlists/") and path.endswith("/tracks"):
            return {"snapshot_id": "s1"}
        return {}

    monkeypatch.setattr("app._api_post", fake_api_post)

    res = create_playlist_with_tracks("tok", "user1", "My Mix", [f"spotify:track:{i}" for i in range(10)])
    assert res.get("id") == "pl_mock"
    # ensure two kinds of calls were made (create playlist + add tracks)
    assert any(p for p, _ in calls if "/users/" in p and p.endswith("/playlists"))
    assert any(p for p, _ in calls if p.startswith("/playlists/") and p.endswith("/tracks"))


def test_build_recommendations_monkeypatch(monkeypatch):
    # Force recs to fail and provide a fallback via _fallback_from_top_tracks
    fake_track = {"id": "t1", "uri": "spotify:track:t1", "name": "T1", "artists": [{"name": "A"}]}
    monkeypatch.setattr("app._recs_with_market_fallback", lambda access_token, params: [])
    monkeypatch.setattr("app._fallback_from_top_tracks", lambda access_token, preset, limit=20: [fake_track])

    out = build_recommendations("tok", mood="happy", genre=None, limit=5)
    assert "tracks" in out
    assert out["tracks"][0]["id"] == "t1"
