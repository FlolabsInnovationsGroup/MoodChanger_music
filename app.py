from __future__ import annotations

import os, json, time, secrets, urllib.parse, random
from typing import Dict
from urllib.parse import urlencode

import requests
from fastapi import FastAPI, Request, Query, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeSerializer, BadSignature
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# -----------------------------
# ENV & CONSTANTS
# -----------------------------
load_dotenv(find_dotenv(usecwd=True), override=True)

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8001/callback")
SCOPES = "playlist-modify-private playlist-modify-public user-read-email"
APP_SECRET = os.getenv("APP_SECRET", "change-me")

if not CLIENT_ID:
    raise RuntimeError("SPOTIFY_CLIENT_ID is missing in .env")
if not CLIENT_SECRET:
    raise RuntimeError("SPOTIFY_CLIENT_SECRET is missing in .env")

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

# Feature flags / defaults
DISABLE_RECS = os.getenv("NO_RECS", "").lower() in ("1", "true", "yes")
DEFAULT_GENRES = [
    "pop", "rock", "dance", "edm", "house", "hip-hop", "indie", "r-n-b", "soul",
]

# -----------------------------
# APP & STATIC
# -----------------------------
app = FastAPI(title="MoodPlaylists")

# Resolve the /static folder relative to this file and don't error if it's missing.
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR), check_dir=False),
    name="static",
)

signer = URLSafeSerializer(APP_SECRET, salt="session")
def _now() -> int:
    import time
    return int(time.time())

# -----------------------------
# TOKENS STORE (simple local file)
# -----------------------------
# Save tokens.json next to this file (stable regardless of cwd)
TOKENS_PATH = str(BASE_DIR / "tokens.json")

def _load_tokens() -> Dict[str, dict]:
    if not os.path.exists(TOKENS_PATH):
        return {}
    try:
        with open(TOKENS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_tokens(store: Dict[str, dict]) -> None:
    with open(TOKENS_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
# -----------------------------
# COOKIE HELPER
# -----------------------------
def get_user_id_from_cookie(request: Request) -> str:
    user_cookie = request.cookies.get("user")
    if not user_cookie:
        raise HTTPException(status_code=401, detail="Login first.")
    try:
        return signer.loads(user_cookie)
    except Exception:
        raise HTTPException(
            status_code=401, detail="Invalid session. Please login again."
        )


# -----------------------------
# SPOTIFY HTTP HELPERS
# -----------------------------
def _api_get(access_token: str, path: str, params: dict | None = None):
    r = requests.get(
        API_BASE + path,
        headers={"Authorization": f"Bearer {access_token}"},
        params=params or {},
        timeout=20,
    )
    if not r.ok:
        try:
            body = r.json()
        except Exception:
            body = r.text
        raise HTTPException(
            status_code=r.status_code,
            detail={
                "status": r.status_code,
                "url": API_BASE + path,
                "params": params or {},
                "headers_sample": {
                    "www-authenticate": r.headers.get("www-authenticate"),
                    "retry-after": r.headers.get("retry-after"),
                    "content-type": r.headers.get("content-type"),
                },
                "spotify": body,
            },
        )
    return r.json()


def _api_post(
    access_token: str,
    path: str,
    json_body: dict | None = None,
    params: dict | None = None,
):
    r = requests.post(
        API_BASE + path,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        params=params or {},
        json=json_body or {},
        timeout=20,
    )
    if not r.ok:
        try:
            body = r.json()
        except Exception:
            body = r.text
        raise HTTPException(
            status_code=r.status_code,
            detail={
                "status": r.status_code,
                "url": API_BASE + path,
                "params": params or {},
                "json": json_body or {},
                "headers_sample": {
                    "www-authenticate": r.headers.get("www-authenticate"),
                    "retry-after": r.headers.get("retry-after"),
                    "content-type": r.headers.get("content-type"),
                },
                "spotify": body,
            },
        )
    return r.json() if r.text else {}


def create_playlist_with_tracks(access_token: str, user_id: str, name: str, uris: list[str]) -> dict:
    pl = _api_post(
        access_token,
        f"/users/{user_id}/playlists",
        json_body={
            "name": name,
            "public": True,
            "description": "Generated by MoodPlaylists",
        },
    )
    if uris:
        for i in range(0, len(uris), 100):
            _api_post(
                access_token,
                f"/playlists/{pl['id']}/tracks",
                json_body={"uris": uris[i:i+100]},
            )
    return pl


def _refresh_token(refresh_token: str) -> dict:
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def _ensure_token(user_id: str) -> str:
    store = _load_tokens()
    t = store.get(user_id)
    if not t:
        raise HTTPException(status_code=401, detail="No token for user. Login again.")
    if _now() < int(t.get("expires_at", 0)) - 15:
        return t["access_token"]

    if not t.get("refresh_token"):
        raise HTTPException(status_code=401, detail="No refresh token. Login again.")
    data = _refresh_token(t["refresh_token"])
    access_token = data["access_token"]
    expires_at = _now() + int(data.get("expires_in", 3600))
    t["access_token"] = access_token
    t["expires_at"] = expires_at
    _save_tokens(store)
    return access_token


def _recs_with_market_fallback(access_token: str, base_params: dict) -> list[dict]:
    """
    Try /recommendations with different market flavors until we get tracks.
    Order: from_token -> PT -> no market -> US
    """
    order = [base_params.get("market", "from_token"), "PT", None, "US"]
    for m in order:
        params = {**base_params}
        if m is None:
            params.pop("market", None)
        else:
            params["market"] = m
        try:
            data = _api_get(access_token, "/recommendations", params)
            tracks = data.get("tracks") or []
            if tracks:
                return tracks
        except HTTPException:
            continue
    return []


# -----------------------------
# MOOD PRESETS
# -----------------------------
MOOD_PRESETS: Dict[str, Dict[str, float]] = {
    "happy": {
        "min_valence": 0.6,
        "max_valence": 1.0,
        "min_energy": 0.5,
        "max_energy": 1.0,
        "min_danceability": 0.5,
    },
    "chill": {
        "min_valence": 0.3,
        "max_valence": 0.8,
        "max_energy": 0.6,
        "min_acousticness": 0.2,
    },
    "focus": {
        "max_valence": 0.6,
        "max_energy": 0.6,
        "min_instrumentalness": 0.4,
        "max_speechiness": 0.5,
    },
    "workout": {
        "min_energy": 0.7,
        "min_danceability": 0.6,
        "min_tempo": 110,
    },
    "melancholic": {
        "max_valence": 0.4,
        "min_acousticness": 0.3,
    },
}

# === Fallback helpers ===
def _get_audio_features(access_token: str, track_ids: list[str]) -> dict[str, dict]:
    feats: dict[str, dict] = {}
    if not track_ids:
        return feats
    for i in range(0, len(track_ids), 100):
        ids = ",".join(track_ids[i:i+100])
        r = _api_get(access_token, "/audio-features", {"ids": ids})
        for f in r.get("audio_features", []) or []:
            if f:
                feats[f["id"]] = f
    return feats


def _within_preset(features: dict, preset: dict) -> bool:
    for k, v in preset.items():
        if k.startswith("min_"):
            metric = k[4:]
            if features.get(metric) is None or features[metric] < v:
                return False
        elif k.startswith("max_"):
            metric = k[4:]
            if features.get(metric) is None or features[metric] > v:
                return False
    return True


def _fallback_from_top_tracks(access_token: str, preset: dict, limit: int = 20) -> list[dict]:
    try:
        top = _api_get(access_token, "/me/top/tracks", {"limit": 50})
        items = top.get("items") or []
        if not items:
            return []
        ids = [t.get("id") for t in items if t.get("id")]
        feats = _get_audio_features(access_token, ids)
        matched: list[dict] = []
        for t in items:
            fid = t.get("id")
            if fid and _within_preset(feats.get(fid, {}), preset):
                matched.append(t)
                if len(matched) >= limit:
                    break
        return matched or items[:limit]
    except Exception:
        return []


def _fallback_from_genre_playlist(
    access_token: str, genre: str, preset: dict, limit: int = 20
) -> list[dict]:
    try:
        q = (genre or "").strip()
        if not q:
            return []
        search = _api_get(access_token, "/search", {
            "q": q, "type": "playlist", "limit": 5, "market": "from_token"
        })
        playlists = ((search.get("playlists") or {}).get("items") or [])
        if not playlists:
            return []
        first_nonempty: list[dict] = []
        for pl in playlists:
            pid = pl["id"]
            pl_tracks = _api_get(access_token, f"/playlists/{pid}/tracks", {
                "limit": 100, "market": "from_token"
            })
            items = [it.get("track") for it in (pl_tracks.get("items") or []) if it.get("track")]
            if items and not first_nonempty:
                first_nonempty = items
            ids = [t.get("id") for t in items if t and t.get("id")]
            feats = _get_audio_features(access_token, ids)
            matched: list[dict] = []
            for t in items:
                fid = t.get("id")
                if fid and _within_preset(feats.get(fid, {}), preset):
                    matched.append(t)
                    if len(matched) >= limit:
                        break
            if matched:
                return matched[:limit]
        return first_nonempty[:limit]
    except Exception:
        return []


def _direct_search_by_genre(access_token: str, q: str, preset: dict, limit: int) -> list[dict]:
    """
    Search tracks by a keyword, filter by audio features to match the mood preset,
    and be forgiving (market fallbacks + lenient popularity threshold).
    """
    def _search_tracks(market: str | None) -> list[dict]:
        params = {"q": q, "type": "track", "limit": 50}
        if market is not None:
            params["market"] = market
        try:
            res = _api_get(access_token, "/search", params)
            return ((res.get("tracks") or {}).get("items") or [])
        except Exception:
            return []

    # try several markets
    items = (
        _search_tracks("from_token")
        or _search_tracks("PT")
        or _search_tracks(None)
        or _search_tracks("US")
    )
    if not items:
        return []

    # Deduplicate by id
    by_id = {t.get("id"): t for t in items if t and t.get("id")}
    ids = [tid for tid in by_id.keys()]

    # Pull audio features; if it fails, proceed without filtering
    try:
        feats = _get_audio_features(access_token, ids)
    except Exception:
        feats = {}

    picks: list[dict] = []
    for tid in ids:
        t = by_id.get(tid)
        if not t:
            continue
        f = feats.get(tid)
        # Very light popularity guard
        if t.get("popularity", 0) < 10:
            continue
        if not f or _within_preset(f, preset):
            picks.append(t)

    return (picks or list(by_id.values()))[:limit]


# -----------------------------
# RECOMMENDATIONS BUILDER
# -----------------------------
def build_recommendations(
    access_token: str, mood: str, genre: str | None, limit: int = 20
):
    mood = (mood or "happy").lower()
    preset = MOOD_PRESETS.get(mood, MOOD_PRESETS["happy"])
    limit = max(1, min(int(limit or 20), 100))

    # --- short-circuit: skip Spotify /recommendations entirely if disabled ---
    if DISABLE_RECS:
        tt = _fallback_from_top_tracks(access_token, preset, limit)
        if tt:
            return {
                "tracks": tt[:limit],
                "seeds": {"artists": [], "tracks": ["from_top_tracks"], "genres": []},
            }

        g = (genre or random.choice(DEFAULT_GENRES))
        gp = _fallback_from_genre_playlist(access_token, g, preset, limit)
        if gp:
            return {
                "tracks": gp[:limit],
                "seeds": {"artists": [], "tracks": ["from_playlist"], "genres": [g]},
            }

        gp = _fallback_from_genre_playlist(access_token, (genre or "pop"), {}, limit)
        if gp:
            return {
                "tracks": gp[:limit],
                "seeds": {"artists": [], "tracks": ["from_playlist"], "genres": [genre or "pop"]},
            }

        # final fallback when NO_RECS is on
        keyword = genre or random.choice(DEFAULT_GENRES)
        direct = _direct_search_by_genre(access_token, keyword, preset, limit)
        if direct:
            return {
                "tracks": direct,
                "seeds": {"artists": [], "tracks": [], "genres": [genre or "keyword_search"]},
            }

        return {"tracks": [], "seeds": {"artists": [], "tracks": [], "genres": []}}

    # --- attempt 1: use seeds from user's top artists/tracks (+ optional genre) ---
    seeds_artists: list[str] = []
    seeds_tracks: list[str] = []
    if not genre:
        try:
            top_art = _api_get(access_token, "/me/top/artists", {"limit": 10})
            top_trk = _api_get(access_token, "/me/top/tracks", {"limit": 10})
            seeds_artists = [a["id"] for a in (top_art.get("items") or [])][:3]
            seeds_tracks = [t["id"] for t in (top_trk.get("items") or [])][:2]
        except Exception:
            pass

    seed_genres: list[str] = [genre.lower()] if genre else []

    params: dict = {"limit": limit, "market": "from_token", **preset}

    # Spotify allows at most 5 total seeds across artists/tracks/genres
    while len(seeds_artists) + len(seeds_tracks) + len(seed_genres) > 5:
        if seeds_tracks:
            seeds_tracks.pop()
        elif seeds_artists:
            seeds_artists.pop()
        else:
            seed_genres = seed_genres[:1]

    if seeds_artists:
        params["seed_artists"] = ",".join(seeds_artists)
    if seeds_tracks:
        params["seed_tracks"] = ",".join(seeds_tracks)
    if seed_genres:
        params["seed_genres"] = ",".join(seed_genres)
    if not any([seeds_artists, seeds_tracks, seed_genres]):
        params["seed_genres"] = "pop"

    # Main attempt with market fallback
    tracks = _recs_with_market_fallback(access_token, params)
    if tracks:
        return {
            "tracks": tracks,
            "seeds": {
                "artists": seeds_artists,
                "tracks": seeds_tracks,
                "genres": seed_genres or params.get("seed_genres", "").split(","),
            },
        }

    # --- attempt 2: genre-only ---
    try:
        picked = [genre.lower()] if genre else random.sample(DEFAULT_GENRES, k=min(3, len(DEFAULT_GENRES)))
        fallback_params = {"limit": limit, "seed_genres": ",".join(picked)}
        tracks = _recs_with_market_fallback(access_token, fallback_params)
        if tracks:
            return {"tracks": tracks, "seeds": {"artists": [], "tracks": [], "genres": picked}}
    except Exception:
        pass

    # --- attempt 3: filter user's top tracks by audio features ---
    tt = _fallback_from_top_tracks(access_token, preset, limit)
    if tt:
        return {"tracks": tt[:limit], "seeds": {"artists": [], "tracks": ["from_top_tracks"], "genres": []}}

    # --- attempt 4: filter tracks from a genre playlist ---
    g = genre or random.choice(DEFAULT_GENRES)
    gp = _fallback_from_genre_playlist(access_token, g, preset, limit)
    if gp:
        return {"tracks": gp[:limit], "seeds": {"artists": [], "tracks": ["from_playlist"], "genres": [g]}}

    # --- attempt 5: plain 'pop' with no mood filters ---
    plain_tracks = _recs_with_market_fallback(access_token, {"limit": limit, "seed_genres": "pop"})
    if plain_tracks:
        return {"tracks": plain_tracks, "seeds": {"artists": [], "tracks": [], "genres": ["pop"]}}

    # --- attempt 6: direct keyword search with mood filtering ---
    keyword = genre or random.choice(DEFAULT_GENRES)
    direct = _direct_search_by_genre(access_token, keyword, preset, limit)
    if direct:
        return {
            "tracks": direct,
            "seeds": {"artists": [], "tracks": [], "genres": [genre or "keyword_search"]},
        }

    # --- last resort ---
    return {"tracks": [], "seeds": {"artists": [], "tracks": [], "genres": []}}


# -----------------------------
# UI + AUTH ROUTES
# -----------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html><head><title>Mood Playlists (Spotify)</title></head>
    <body>
      <h2>Mood Playlists (Spotify)</h2>
      <p><a href="/login">Login with Spotify</a></p>
      <p><a href="/static/app.html">Open UI</a></p>
      <form action="/api/playlist" method="post">
        <label>Mood:
          <select name="mood">
            <option>happy</option><option>chill</option><option>focus</option>
            <option>workout</option><option>melancholic</option>
          </select>
        </label>
        <label>Genre (optional): <input name="genre" placeholder="e.g. house"></label>
        <label>Count: <input type="number" name="limit" value="20" min="5" max="100"></label>
        <button type="submit">Generate Playlist</button>
      </form>
    </body></html>"""


@app.get("/login")
def login(request: Request,
          switch: bool = Query(False),
          show_dialog: bool = Query(False)):
    """
    If switch=1, force the Spotify chooser.
    Stores a signed 'state' cookie for CSRF protection.
    """
    if switch:
        show_dialog = True

    state = secrets.token_urlsafe(16)
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join([
            "user-read-private",
            "user-top-read",
            "playlist-modify-public",
            "playlist-modify-private",
        ]),
        "state": state,
        "show_dialog": "true" if show_dialog else "false",
    }

    url = AUTH_URL + "?" + urlencode(params)
    resp = RedirectResponse(url, status_code=307)
    resp.set_cookie("state", signer.dumps(state), httponly=True, samesite="lax")
    if switch:
        resp.delete_cookie("user")
    return resp


@app.get("/callback")
def callback(request: Request, code: str | None = None, state: str | None = None):
    # Robust state check
    cookie_state = request.cookies.get("state")
    try:
        expected = signer.loads(cookie_state) if cookie_state else None
    except BadSignature:
        return JSONResponse({"stage": "state_check", "error": "bad_state_cookie"}, status_code=400)
    if not expected or state != expected:
        return JSONResponse({"stage": "state_check", "error": "state_mismatch"}, status_code=400)

    # Exchange code for tokens
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        timeout=20,
    )
    if r.status_code != 200:
        return JSONResponse(
            {"stage": "auth_code_exchange", "status": r.status_code, "body": r.text[:300]},
            status_code=502,
        )
    try:
        tok = r.json()
    except Exception:
        return JSONResponse(
            {"stage": "auth_code_exchange", "parse_error": r.text[:300]},
            status_code=502,
        )

    access_token = tok.get("access_token")
    if not access_token:
        return JSONResponse(
            {"stage": "auth_code_exchange", "error": "missing_access_token", "raw": tok},
            status_code=502,
        )
    refresh_token_new = tok.get("refresh_token")  # may be None on re-consent
    expires_at = int(time.time()) + int(tok.get("expires_in", 3600))

    # Identify user via helper (gives structured errors)
    try:
        me = _api_get(access_token, "/me")
    except HTTPException as e:
        return JSONResponse({"stage": "whoami", "error": e.detail}, status_code=502)

    user_id = me["id"]

    # Persist tokens; preserve old refresh token if Spotify didn't send one
    store = _load_tokens()
    existing = store.get(user_id, {})
    store[user_id] = {
        "access_token": access_token,
        "refresh_token": refresh_token_new or existing.get("refresh_token"),
        "expires_at": expires_at,
    }
    _save_tokens(store)

    resp = RedirectResponse(url="/static/app.html")
    resp.set_cookie("user", signer.dumps(user_id), httponly=True, samesite="lax")
    return resp


@app.get("/logout")
def logout():
    """GET only. Clears cookies and redirects home."""
    resp = RedirectResponse(url="/", status_code=307)
    resp.delete_cookie("user")
    resp.delete_cookie("state")
    return resp


# -----------------------------
# API ROUTES USED BY THE UI
# -----------------------------
@app.get("/api/moods")
def api_moods():
    return MOOD_PRESETS


@app.get("/api/me")
def api_me(request: Request):
    user_id = get_user_id_from_cookie(request)
    tok = _ensure_token(user_id)
    return _api_get(tok, "/me")


@app.post("/api/playlist")
async def api_playlist(request: Request):
    try:
        form = await request.form()
        mood = (form.get("mood") or "").strip().lower()
        genre = (form.get("genre") or "").strip().lower() or None
        limit = int(form.get("limit") or 20)

        user_id = get_user_id_from_cookie(request)
        tok = _ensure_token(user_id)

        result = build_recommendations(tok, mood=mood, genre=genre, limit=limit)
        tracks = result.get("tracks", [])
        uris = [t["uri"] for t in tracks if t.get("uri")]

        if not tracks:
            raise HTTPException(
                status_code=502,
                detail="Spotify returned no recommendations. Try another mood/genre.",
            )

        me = _api_get(tok, "/me")
        playlist = create_playlist_with_tracks(
            tok, me["id"], f"{(mood or 'mood').title()} Mix ({genre or 'auto'})", uris
        )

        return JSONResponse(
            {
                "playlist_id": playlist.get("id"),
                "playlist_url": playlist.get("external_urls", {}).get("spotify"),
                "added": len(uris),
                "used_seeds": result.get("seeds"),
                "sample_titles": [
                    f"{t['name']} — {', '.join(a['name'] for a in t.get('artists', []))}"
                    for t in tracks[:5]
                ],
            }
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        import traceback
        return JSONResponse(
            {"error": "Internal", "detail": str(e), "trace": traceback.format_exc()},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# -----------------------------
# DEBUG / PROBE ROUTES
# -----------------------------
@app.get("/_debug_env")
def _debug_env():
    return {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "secret_set": bool(CLIENT_SECRET),
        "disable_recs": DISABLE_RECS,
    }


@app.get("/_debug_recs")
def _debug_recs(
    request: Request, mood: str = "happy", genre: str | None = None, limit: int = 20
):
    user_id = get_user_id_from_cookie(request)
    tok = _ensure_token(user_id)
    result = build_recommendations(tok, mood=mood, genre=genre, limit=limit)
    sample = [
        {
            "name": t.get("name"),
            "artists": ", ".join(a.get("name") for a in t.get("artists", [])),
            "uri": t.get("uri"),
        }
        for t in result.get("tracks", [])[:5]
    ]
    return {
        "used_seeds": result.get("seeds"),
        "sample": sample,
        "count": len(result.get("tracks", [])),
    }


@app.get("/_probe_me")
def _probe_me(request: Request):
    user_id = get_user_id_from_cookie(request)
    tok = _ensure_token(user_id)
    return _api_get(tok, "/me")


@app.get("/_probe_genres")
def _probe_genres(request: Request):
    user_id = get_user_id_from_cookie(request)
    tok = _ensure_token(user_id)
    return _api_get(tok, "/recommendations/available-genre-seeds")


@app.get("/_probe_plain")
def _probe_plain(request: Request, limit: int = 5):
    user_id = get_user_id_from_cookie(request)
    tok = _ensure_token(user_id)

    out = {}

    def attempt(label: str, params: dict):
        try:
            data = _api_get(tok, "/recommendations", params)
            tracks = data.get("tracks") or []
            out[label] = {
                "count": len(tracks),
                "sample": [t.get("name") for t in tracks[:3]],
                "params": params,
            }
        except HTTPException as e:
            out[label] = {"error": e.detail, "params": params}

    attempt("from_token", {"limit": limit, "seed_genres": "pop", "market": "from_token"})
    attempt("PT", {"limit": limit, "seed_genres": "pop", "market": "PT"})
    attempt("no_market", {"limit": limit, "seed_genres": "pop"})
    attempt("US", {"limit": limit, "seed_genres": "pop", "market": "US"})
    return out


@app.get("/_probe_sanity")
def _probe_sanity(request: Request):
    user_id = get_user_id_from_cookie(request)
    tok = _ensure_token(user_id)
    out = {}

    try:
        top = _api_get(tok, "/me/top/tracks", {"limit": 1})
        items = (top.get("items") or [])
        if items:
            tid = items[0]["id"]
            data = _api_get(tok, "/recommendations", {"limit": 5, "seed_tracks": tid})
            out["seed_tracks"] = [t.get("name") for t in data.get("tracks", [])]
        else:
            out["seed_tracks"] = []
    except HTTPException as e:
        out["seed_tracks_error"] = {"status": e.status_code, "detail": e.detail}

    for label, params in [
        ("no_market", {"limit": 5, "seed_genres": "pop"}),
        ("US", {"limit": 5, "seed_genres": "pop", "market": "US"}),
    ]:
        try:
            data = _api_get(tok, "/recommendations", params)
            out[f"genre_{label}"] = [t.get("name") for t in data.get("tracks", [])]
        except HTTPException as e:
            out[f"genre_{label}_error"] = {"status": e.status_code, "detail": e.detail}

    return out


@app.get("/_probe_search")
def _probe_search(request: Request, q: str = "pop", limit: int = 3):
    user_id = get_user_id_from_cookie(request)
    tok = _ensure_token(user_id)

    out = {"query": q, "playlists_found": 0, "samples": []}

    try:
        search = _api_get(tok, "/search", {
            "q": q,
            "type": "playlist",
            "limit": limit,
            "market": "from_token",
        })
    except HTTPException as e:
        # Surface the exact API error so we can see what's happening
        return {"search_error": e.detail}

    playlists = (((search or {}).get("playlists") or {}).get("items") or [])
    out["playlists_found"] = len(playlists)

    for pl in playlists:
        if not isinstance(pl, dict):
            continue
        pid = pl.get("id")
        name = pl.get("name") or "(unnamed)"
        if not pid:
            continue

        try:
            tr_resp = _api_get(tok, f"/playlists/{pid}/tracks", {
                "limit": 5,
                "market": "from_token",
            })
            items = tr_resp.get("items") or []
            tracks = [it.get("track") for it in items if isinstance(it, dict) and it.get("track")]
            out["samples"].append({
                "playlist": name,
                "pid": pid,
                "count": len(tracks),
                "sample": [t.get("name") for t in tracks[:3] if isinstance(t, dict)],
            })
        except HTTPException as e:
            out["samples"].append({
                "playlist": name,
                "pid": pid,
                "error": e.detail,
            })

    return out
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001, reload=True)