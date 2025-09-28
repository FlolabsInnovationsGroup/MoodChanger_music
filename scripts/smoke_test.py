"""Quick smoke test for the MoodChanger app in MOCK_MODE.

Runs a few requests using FastAPI's TestClient to validate endpoints without talking to Spotify.

Usage:
    Set MOCK_MODE=1 in your environment and run this file with Python.
"""

from fastapi.testclient import TestClient
import os
import sys

# Ensure we run the local app
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app import app

client = TestClient(app)

print("Testing /api/spotify/genre-seeds")
resp = client.get("/api/spotify/genre-seeds")
print(resp.status_code, resp.json())

print("Testing /api/spotify/mood-labels")
resp = client.get("/api/spotify/mood-labels")
print(resp.status_code, resp.json())

print("Testing POST /api/playlist")
resp = client.post("/api/playlist", data={"mood": "chill", "limit": "5"})
print(resp.status_code, resp.json())
