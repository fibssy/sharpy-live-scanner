"""
scanner.py — Main polling loop for sharpy-live-scanner

Polls API-Football every 60s for live matches in the 5 top European leagues.
Runs the Poisson hazard model and fires Discord alerts via Claude Haiku
when a strong market signal is detected.
"""

import logging
import os
import time

import api_football as sofascore
import model
import db
import notifier
import haiku

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scanner")

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))
MIN_PROB      = float(os.environ.get("MIN_PROB", "0.80"))   # 0.80 = 80% minimum signal probability
COOLDOWN      = int(os.environ.get("ALERT_COOLDOWN_MINUTES", "10"))


def should_alert(signal: dict) -> bool:
    return signal["prob"] >= MIN_PROB


def process_match(match: dict):
    stats   = sofascore.get_match_stats(match["id"])
    incidents = sofascore.get_match_incidents(match["id"])

    full = {**match, **stats, **incidents}

    result = model.calculate(full)

    if result["score"] < MIN_SCORE:
        return

    signals = result["market_signals"]
    if not signals:
        return

    top_signal = signals[0]
    if not should_alert(top_signal):
        return

    if db.was_recently_alerted(match["id"], top_signal["market"], COOLDOWN):
        log.info("Cooldown active: %s %s", match["home"], top_signal["market"])
        return

    log.info(
        "ALERT: %s vs %s | %s | %s | score=%.1f",
        match["home"], match["away"], top_signal["market"],
        top_signal["strength"], result["score"]
    )

    verdict = haiku.get_verdict(full, result, top_signal)
    notifier.post_alert(full, result, top_signal, verdict)
    db.save_alert(match["id"], full, result, top_signal, verdict)


def poll_once():
    try:
        matches = sofascore.get_live_matches()
        log.info("Scanning %d live matches", len(matches))
        for match in matches:
            try:
                process_match(match)
            except Exception as e:
                log.error("Error processing %s vs %s: %s", match["home"], match["away"], e)
    except Exception as e:
        log.error("Poll error: %s", e)


def run():
    run_once = os.environ.get("RUN_ONCE", "false").lower() == "true"

    if run_once:
        log.info("Sharpy Live Scanner — single run mode")
        poll_once()
    else:
        log.info("Sharpy Live Scanner started — poll every %ds, min score %.1f", POLL_INTERVAL, MIN_SCORE)
        while True:
            poll_once()
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
