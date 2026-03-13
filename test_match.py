"""
test_match.py — Run the full scanner pipeline on a specific API-Football fixture ID.

Usage:
  python test_match.py <fixture_id>

Find the fixture ID on api-football.com or from the scanner logs.
Set POST_DISCORD=true to also send the Discord alert.
"""

import sys
import logging
import os

import api_football
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


def run(fixture_id: int):
    log.info("Fetching fixture %d from API-Football", fixture_id)

    match = api_football.get_fixture_info(fixture_id)
    if not match:
        log.error("Could not fetch fixture %d", fixture_id)
        sys.exit(1)

    stats     = api_football.get_match_stats(fixture_id)
    incidents = api_football.get_match_incidents(fixture_id)
    full      = {**match, **stats, **incidents}

    log.info(
        "%s vs %s | %s | %d' | %d-%d",
        match["home"], match["away"], match["league"],
        match["minute"], match["home_goals"], match["away_goals"]
    )
    log.info(
        "Stats: xG %.2f-%.2f | shots_in_box %s-%s | gk_saves %s-%s",
        full.get("home_xg", 0), full.get("away_xg", 0),
        full.get("home_shots_in_box", 0), full.get("away_shots_in_box", 0),
        full.get("home_gk_saves", 0), full.get("away_gk_saves", 0),
    )

    result = model.calculate(full)
    log.info(
        "Model score: %.2f | signals: %s",
        result["score"],
        [s["market"] + "(" + s["strength"] + ")" for s in result["market_signals"]]
    )

    if not result["market_signals"]:
        log.info("No market signals triggered")
        return

    top_signal = result["market_signals"][0]
    log.info("Top signal: %s (%s) — calling Haiku...", top_signal["market"], top_signal["strength"])

    verdict = haiku.get_verdict(full, result, top_signal)
    log.info("Haiku verdict: %s", verdict)

    if os.environ.get("POST_DISCORD", "false").lower() == "true":
        notifier.post_alert(full, result, top_signal, verdict)
        db.save_alert(match["id"], full, result, top_signal, verdict)
        log.info("Alert posted to Discord and saved to DB")
    else:
        log.info("Dry run — set POST_DISCORD=true to post to Discord")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_match.py <api_football_fixture_id>")
        sys.exit(1)
    run(int(sys.argv[1]))
