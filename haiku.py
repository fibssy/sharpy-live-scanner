"""
haiku.py — Claude Haiku verdict generator
"""

import os
import logging
import anthropic

log = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))


def get_verdict(match: dict, result: dict, signal: dict) -> str:
    """
    Ask Claude Haiku to interpret the signal in the context of the live match.
    Returns a 2-sentence plain-text verdict.
    """
    prompt = f"""You are a sharp football betting analyst. Given the live match data below, write exactly 2 sentences:
1. What is happening in the match right now based on the stats.
2. Whether the market signal is worth acting on and why.

Be concise, direct, no fluff.

Match: {match['home']} vs {match['away']} ({match['league']})
Score: {match['home_goals']}-{match['away_goals']} at minute {match['minute']}
xG: Home {match.get('home_xg', 0):.2f} / Away {match.get('away_xg', 0):.2f}
Big chances: Home {match.get('home_big_chances', 0)} / Away {match.get('away_big_chances', 0)}
Shots in box: Home {match.get('home_shots_in_box', 0)} / Away {match.get('away_shots_in_box', 0)}
GK saves: Home {match.get('home_gk_saves', 0)} / Away {match.get('away_gk_saves', 0)}
Model score: {result['score']}/10
Signal: {signal['market']} ({signal['strength']}) — {signal['reason']}
P(goal in next {result['effective_window']} min): {round(result['prob']*100)}%"""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=180,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        log.error("Haiku error: %s", e)
        return ""
