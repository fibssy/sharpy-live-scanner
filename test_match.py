"""
test_match.py — Run the full scanner pipeline on a specific SofaScore match ID.

Usage:
  python test_match.py <event_id>

Example:
  python test_match.py 12345678
"""

import sys
import logging
import os

import sofascore
import model
import haiku
import notifier
import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("test_match")


def run(event_id: int):
    log.info("Fetching match data for event %d", event_id)

    # Fetch stats and incidents directly — skip the live filter
    stats    = sofascore.get_match_stats(event_id)
    incidents = sofascore.get_match_incidents(event_id)

    # Fetch basic match info
    data = sofascore._get(f"/event/{event_id}")
    if not data:
        log.error("Could not fetch event %d", event_id)
        sys.exit(1)

    e = data.get("event", {})
    status_desc = e.get("status", {}).get("description", "Unknown")
    minute = e.get("time", {}).get("played") or 0
    if status_desc == "2nd half":
        minute = e.get("time", {}).get("periodLength", 45) + minute

    match = {
        "id":         event_id,
        "home":       e.get("homeTeam", {}).get("name", "Home"),
        "away":       e.get("awayTeam", {}).get("name", "Away"),
        "league":     e.get("tournament", {}).get("name", ""),
        "minute":     minute,
        "home_goals": e.get("homeScore", {}).get("current", 0),
        "away_goals": e.get("awayScore", {}).get("current", 0),
        "status":     status_desc,
    }

    full = {**match, **stats, **incidents}

    log.info(
        "%s vs %s | %s | %d' | %d-%d",
        match["home"], match["away"], match["league"],
        match["minute"], match["home_goals"], match["away_goals"]
    )
    log.info("Stats: xG %.2f-%.2f | shots_in_box %s-%s | big_chances %s-%s",
        full.get("home_xg", 0), full.get("away_xg", 0),
        full.get("home_shots_in_box", 0), full.get("away_shots_in_box", 0),
        full.get("home_big_chances", 0), full.get("away_big_chances", 0),
    )

    result = model.calculate(full)
    log.info("Model score: %.2f | signals: %s", result["score"],
             [s["market"] + "(" + s["strength"] + ")" for s in result["market_signals"]])

    if not result["market_signals"]:
        log.info("No market signals — model below threshold")
        return

    top_signal = result["market_signals"][0]
    log.info("Top signal: %s (%s) — getting Haiku verdict...", top_signal["market"], top_signal["strength"])

    verdict = haiku.get_verdict(full, result, top_signal)
    log.info("Haiku verdict: %s", verdict)

    post = os.environ.get("POST_DISCORD", "false").lower() == "true"
    if post:
        notifier.post_alert(full, result, top_signal, verdict)
        db.save_alert(match["id"], full, result, top_signal, verdict)
        log.info("Alert posted to Discord")
    else:
        log.info("Dry run — set POST_DISCORD=true to post to Discord")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_match.py <sofascore_event_id>")
        sys.exit(1)
    run(int(sys.argv[1]))
