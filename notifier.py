"""
notifier.py — Discord embed notifications for sharpy-live-scanner
"""

import os
import logging
import requests

log = logging.getLogger(__name__)

DISCORD_API = "https://discord.com/api/v10"
BOT_TOKEN   = os.environ.get("DISCORD_BOT_TOKEN", "")
CHANNEL_ID  = os.environ.get("DISCORD_CHANNEL_ID_LIVE", "")

def prob_colour(prob: float, has_xg: bool) -> int:
    if not has_xg:
        return 0xef4444  # red — no xG data, low confidence
    if prob >= 0.90:
        return 0x22c55e  # green
    return 0xf97316      # orange (80–89%)

LEAGUE_FLAG = {
    "Premier League": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "Bundesliga":     "🇩🇪",
    "La Liga":        "🇪🇸",
    "Ligue 1":        "🇫🇷",
    "Serie A":        "🇮🇹",
}


def _flag(league: str) -> str:
    for k, v in LEAGUE_FLAG.items():
        if k in league:
            return v
    return "⚽"


def post_alert(match: dict, result: dict, signal: dict, verdict: str):
    """Post a Discord embed for a fired market signal."""
    if not BOT_TOKEN or not CHANNEL_ID:
        log.warning("Discord credentials not configured")
        return

    flag     = _flag(match["league"])
    has_xg   = (match.get("home_xg", 0) + match.get("away_xg", 0)) > 0
    colour   = prob_colour(signal["prob"], has_xg)
    score_str = f"{match['home_goals']}-{match['away_goals']}"
    minute   = match["minute"]

    prob_pct = round(signal["prob"] * 100)
    title    = f"{flag} {match['home']} vs {match['away']}"
    desc     = (
        f"**{match['league']}** · {minute}' · {score_str}\n"
        f"**{signal['market']}** · {prob_pct}% · odds {signal['implied_odds']} · "
        f"{result['effective_window']} mins · score {result['score']}/10"
    )

    fields = [
        {"name": "Signal",     "value": signal["reason"],  "inline": False},
        {"name": "AI Verdict", "value": verdict or "—",    "inline": False},
        {
            "name":  "Model",
            "value": (
                f"xG H/A: {match.get('home_xg',0):.2f}/{match.get('away_xg',0):.2f} · "
                f"λ H/A: {result['lambda_home']:.3f}/{result['lambda_away']:.3f}"
            ),
            "inline": False,
        },
    ]

    embed = {
        "title":       title,
        "description": desc,
        "color":       colour,
        "fields":      fields,
        "footer":      {"text": "Sharpy Live Scanner · Poisson V80"},
    }

    try:
        r = requests.post(
            f"{DISCORD_API}/channels/{CHANNEL_ID}/messages",
            headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"},
            json={"embeds": [embed]},
            timeout=10,
        )
        if r.status_code not in (200, 201):
            log.error("Discord post failed %s: %s", r.status_code, r.text)
        else:
            log.info("Discord alert sent: %s %s", match["home"], signal["market"])
    except requests.RequestException as e:
        log.error("Discord request error: %s", e)
