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

STRENGTH_COLOUR = {
    "STRONG":   0xef4444,  # red
    "MODERATE": 0xf97316,  # orange
    "WEAK":     0xeab308,  # yellow
}

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
    colour   = STRENGTH_COLOUR.get(signal["strength"], 0x6b7280)
    score_str = f"{match['home_goals']}-{match['away_goals']}"
    minute   = match["minute"]

    title   = f"{flag} {match['home']} vs {match['away']}"
    desc    = f"**{match['league']}** · {minute}' · {score_str}"

    fields = [
        {"name": "Market",        "value": f"**{signal['market']}**",              "inline": True},
        {"name": "Strength",      "value": signal["strength"],                     "inline": True},
        {"name": "Model Prob",    "value": f"{round(signal['prob']*100)}%",         "inline": True},
        {"name": "Implied Odds",  "value": f"{signal['implied_odds']}",             "inline": True},
        {"name": "Score Rating",  "value": f"{result['score']}/10",                "inline": True},
        {"name": "Window",        "value": f"{result['effective_window']} mins",   "inline": True},
        {"name": "Signal Reason", "value": signal["reason"],                       "inline": False},
        {"name": "AI Verdict",    "value": verdict or "—",                         "inline": False},
        {
            "name": "Model Details",
            "value": (
                f"xG H/A: {match.get('home_xg',0):.2f}/{match.get('away_xg',0):.2f} · "
                f"lambda H/A: {result['lambda_home']:.3f}/{result['lambda_away']:.3f} · "
                f"P(goal): {round(result['prob']*100)}%"
            ),
            "inline": False,
        },
    ]

    embed = {
        "title":       title,
        "description": desc,
        "color":       colour,
        "fields":      fields,
        "footer":      {"text": "Sharpy Live Scanner · Poisson V79"},
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
