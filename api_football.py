"""
api_football.py — API-Football client (replaces sofascore.py)

Endpoints:
  GET /fixtures?live=all                       → live matches
  GET /fixtures/statistics?fixture={id}        → match stats
  GET /fixtures/events?fixture={id}            → cards / goals
  GET /fixtures?id={id}                        → single fixture info
"""

import logging
import os
import requests

log = logging.getLogger(__name__)

BASE_URL = "https://v3.football.api-sports.io"
API_KEY  = os.environ.get("API_FOOTBALL_KEY", "")

# League IDs for our 5 leagues
ALLOWED_LEAGUE_IDS = {39, 78, 140, 61, 135}
LEAGUE_NAMES = {
    39:  "Premier League",
    78:  "Bundesliga",
    140: "La Liga",
    61:  "Ligue 1",
    135: "Serie A",
}


def _get(path: str, params: dict = None) -> dict | None:
    try:
        r = requests.get(
            f"{BASE_URL}{path}",
            headers={"x-apisports-key": API_KEY},
            params=params,
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        log.warning("API-Football %s → HTTP %s", path, r.status_code)
    except requests.RequestException as e:
        log.warning("API-Football request error: %s", e)
    return None


def _parse_stat(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(str(value).replace("%", "").strip())
    except (ValueError, TypeError):
        return 0.0


def get_live_matches() -> list[dict]:
    """Return live matches filtered to ALLOWED_LEAGUE_IDS."""
    data = _get("/fixtures", {"live": "all"})
    if not data:
        return []

    results = []
    for f in data.get("response", []):
        league_id = f.get("league", {}).get("id")
        if league_id not in ALLOWED_LEAGUE_IDS:
            continue

        status       = f.get("fixture", {}).get("status", {})
        status_short = status.get("short", "")
        elapsed      = status.get("elapsed") or 0

        if status_short not in ("1H", "2H", "ET"):
            continue

        results.append({
            "id":         f["fixture"]["id"],
            "home":       f["teams"]["home"]["name"],
            "away":       f["teams"]["away"]["name"],
            "league":     LEAGUE_NAMES.get(league_id, f["league"]["name"]),
            "minute":     elapsed,
            "home_goals": f["goals"]["home"] or 0,
            "away_goals": f["goals"]["away"] or 0,
            "status":     status_short,
        })

    log.info("Live qualifying matches: %d", len(results))
    return results


def get_fixture_info(fixture_id: int) -> dict | None:
    """Fetch basic info for a single fixture (used by test_match)."""
    data = _get("/fixtures", {"id": fixture_id})
    if not data or not data.get("response"):
        return None
    f = data["response"][0]
    status       = f.get("fixture", {}).get("status", {})
    status_short = status.get("short", "")
    elapsed      = status.get("elapsed") or 0
    return {
        "id":         fixture_id,
        "home":       f["teams"]["home"]["name"],
        "away":       f["teams"]["away"]["name"],
        "league":     f.get("league", {}).get("name", ""),
        "minute":     elapsed,
        "home_goals": f["goals"]["home"] or 0,
        "away_goals": f["goals"]["away"] or 0,
        "status":     status_short,
    }


def _parse_team_stats(team_data: dict, prefix: str) -> dict:
    result = {}
    for stat in team_data.get("statistics", []):
        name = stat.get("type", "")
        val  = _parse_stat(stat.get("value"))
        if name == "expected_goals":
            result[f"{prefix}_xg"] = val
        elif name == "Shots on Goal":
            result[f"{prefix}_shots_on_target"] = val
        elif name == "Shots insidebox":
            result[f"{prefix}_shots_in_box"] = val
        elif name == "Goalkeeper Saves":
            result[f"{prefix}_gk_saves"] = val
        elif name == "Ball Possession":
            result[f"{prefix}_possession"] = val

    # If xG missing, estimate from shots on target (rough proxy)
    if not result.get(f"{prefix}_xg"):
        result[f"{prefix}_xg"] = result.get(f"{prefix}_shots_on_target", 0) * 0.33

    return result


def get_match_stats(fixture_id: int) -> dict:
    """Fetch and parse statistics for a fixture. Home = index 0, Away = index 1."""
    data = _get("/fixtures/statistics", {"fixture": fixture_id})
    if not data or len(data.get("response", [])) < 2:
        return {}

    stats = {}
    stats.update(_parse_team_stats(data["response"][0], "home"))
    stats.update(_parse_team_stats(data["response"][1], "away"))
    return stats


def get_match_incidents(fixture_id: int) -> dict:
    """Fetch red cards from fixture events."""
    data = _get("/fixtures/events", {"fixture": fixture_id})
    if not data:
        return {"red_cards": 0}

    red_cards = sum(
        1 for e in data.get("response", [])
        if e.get("type") == "Card" and e.get("detail") in ("Red Card", "Second Yellow Card")
    )
    return {"red_cards": red_cards}
