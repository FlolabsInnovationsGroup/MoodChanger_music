import os

os.environ.setdefault("MOCK_MODE", "1")

from fastapi.testclient import TestClient
from app import app


client = TestClient(app)


def test_genre_seeds_endpoint_in_mock_mode():
    # Ensure the endpoint returns a list of genres in MOCK_MODE
    r = client.get("/api/spotify/genre-seeds")
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j.get("genres"), list)

