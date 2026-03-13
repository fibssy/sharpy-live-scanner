"""
db.py — Database operations for sharpy-live-scanner
"""

import os
import logging
import psycopg2
import psycopg2.extras

log = logging.getLogger(__name__)


def get_conn():
    url = os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url)


def was_recently_alerted(event_id: int, market: str, cooldown_minutes: int = 10) -> bool:
    """Prevent duplicate alerts for the same match+market within cooldown window."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1 FROM live_alerts
                    WHERE event_id = %s AND market = %s
                      AND alerted_at > NOW() - INTERVAL '%s minutes'
                    LIMIT 1
                """, (event_id, market, cooldown_minutes))
                return cur.fetchone() is not None
    except Exception as e:
        log.error("DB check error: %s", e)
        return False


def save_alert(event_id: int, match: dict, result: dict, signal: dict, verdict: str):
    """Persist a fired alert to the database."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO live_alerts
                        (event_id, home_team, away_team, league, minute,
                         home_goals, away_goals, score, market, prob,
                         implied_odds, strength, signal_reason, verdict)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (event_id, market, alerted_at) DO NOTHING
                """, (
                    event_id,
                    match["home"],
                    match["away"],
                    match["league"],
                    match["minute"],
                    match["home_goals"],
                    match["away_goals"],
                    result["score"],
                    signal["market"],
                    signal["prob"],
                    signal["implied_odds"],
                    signal["strength"],
                    signal["reason"],
                    verdict,
                ))
            conn.commit()
    except Exception as e:
        log.error("DB save error: %s", e)
