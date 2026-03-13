"""
sofascore.py — SofaScore unofficial API client

Endpoints used:
  GET /api/v1/sport/football/events/live          → all live matches
  GET /api/v1/event/{id}/statistics               → match stats (xG, shots, etc.)
"""

import logging
import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.sofascore.com/api/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

ALLOWED_LEAGUES = {
    "Premier League",
    "Bundesliga",
    "La Liga",
    "Ligue 1",
    "Serie A",
}

STAT_MAP = {
    "Expected goals":           ("home_xg",           "away_xg"),
    "Big chances":              ("home_big_chances",   "away_big_chances"),
    "Shots inside box":         ("home_shots_in_box",  "away_shots_in_box"),
    "Touches in penalty area":  ("home_touches_in_box","away_touches_in_box"),
    "Goalkeeper saves":         ("home_gk_saves",      "away_gk_saves"),
    "Ball possession":          ("home_possession",    "away_possession"),
    "Shots on target":          ("home_shots_on_target","away_shots_on_target"),
    "Total shots":              ("home_total_shots",   "away_total_shots"),
}


def _get(path: str, timeout: int = 10) -> dict | None:
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        log.warning("SofaScore %s → HTTP %s", path, r.status_code)
    except requests.RequestException as e:
        log.warning("SofaScore request error: %s", e)
    return None


def _parse_stat(value: str) -> float:
    """Parse '68%' → 68.0, '1.67' → 1.67, '2' → 2.0"""
    if value is None:
        return 0.0
    try:
        return float(str(value).replace("%", "").strip())
    except (ValueError, TypeError):
        return 0.0


def get_live_matches() -> list[dict]:
    """Return live matches filtered to ALLOWED_LEAGUES."""
    data = _get("/sport/football/events/live")
    if not data:
        return []

    results = []
    for e in data.get("events", []):
        league = e.get("tournament", {}).get("name", "")
        if not any(allowed in league for allowed in ALLOWED_LEAGUES):
            continue

        status = e.get("status", {})
        status_desc = status.get("description", "")

        # Only in-play matches (1st half, 2nd half, extra time)
        if status_desc not in ("1st half", "2nd half", "Extra time", "Overtime"):
            continue

        minute = e.get("time", {}).get("played") or 0

        # Adjust minute for 2nd half (SofaScore resets played time per period)
        if status_desc == "2nd half":
            period_start = e.get("time", {}).get("periodLength", 45)
            minute = period_start + minute

        results.append({
            "id":         e["id"],
            "home":       e.get("homeTeam", {}).get("name", ""),
            "away":       e.get("awayTeam", {}).get("name", ""),
            "league":     league,
            "minute":     minute,
            "home_goals": e.get("homeScore", {}).get("current", 0),
            "away_goals": e.get("awayScore", {}).get("current", 0),
            "status":     status_desc,
        })

    log.info("Live qualifying matches: %d", len(results))
    return results


def get_match_stats(event_id: int) -> dict:
    """Fetch and parse statistics for a live match."""
    data = _get(f"/event/{event_id}/statistics")
    if not data:
        return {}

    stats = {}
    for period in data.get("statistics", []):
        if period.get("period") != "ALL":
            continue
        for group in period.get("groups", []):
            for item in group.get("statisticsItems", []):
                name = item.get("name", "")
                if name in STAT_MAP:
                    home_key, away_key = STAT_MAP[name]
                    stats[home_key] = _parse_stat(item.get("home"))
                    stats[away_key] = _parse_stat(item.get("away"))

    return stats


def get_match_incidents(event_id: int) -> dict:
    """Fetch red cards from match incidents."""
    data = _get(f"/event/{event_id}/incidents")
    if not data:
        return {"red_cards": 0}

    red_cards = sum(
        1 for inc in data.get("incidents", [])
        if inc.get("incidentType") in ("card",) and inc.get("incidentClass") in ("red", "yellowRed")
    )
    return {"red_cards": red_cards}
