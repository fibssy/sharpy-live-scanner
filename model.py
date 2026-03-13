"""
model.py — Poisson Hazard Model V79.0
Ported from background.js (Flashscore WebScanner)

Log-linear hazard model: log(lambda) = B0 + B1*xgPerMin + B2*boxShots + B3*bigChances + B4*touchesInBox + B5*gkSaves
Team-split lambdaHome / lambdaAway unlocks BTTS, Next Goal, Asian Lines.
"""

import math


def factorial(n: int) -> int:
    if n <= 1:
        return 1
    r = 1
    for i in range(2, n + 1):
        r *= i
    return r


def compute_team_lambda(xg, xgot, shots_in_box, touches_in_box, big_chances, gk_saves, goals, minute):
    if minute < 5:
        return 0.001

    effective_xg = (xgot * 0.65 + xg * 0.35) if xgot > 0 else xg
    xg_per_min = effective_xg / minute

    log_lambda = (
        -3.5
        + 18.0 * xg_per_min
        + 0.80 * (shots_in_box / minute)
        + 0.15 * big_chances
        + 0.40 * (touches_in_box / minute)
        + 0.30 * (gk_saves / minute)
    )

    lam = math.exp(log_lambda)

    # xG efficiency adjustment (capped ±5%, only after minute 50)
    xg_deficit = effective_xg - goals
    if minute >= 50:
        if xg_deficit >= 0.8:
            lam *= 1.05
        elif xg_deficit >= 0.4:
            lam *= 1.03
        elif xg_deficit <= -0.8:
            lam *= 0.97
        elif xg_deficit <= -0.4:
            lam *= 0.98

    return max(lam, 0.001)


def compute_market_signals(minute, score_diff, total_goals, home_goals, away_goals,
                            prob_any_goal, prob_home_scores, prob_away_scores, prob_btts,
                            lambda_total, lambda_home, lambda_away,
                            effective_window, home_xg, away_xg):
    signals = []
    lt = lambda_total * effective_window

    def p_exact(k):
        return math.exp(-lt) * (lt ** k) / factorial(k)

    # 1. Over 0.5 Goals
    if minute >= 68 and prob_any_goal >= 0.65:
        signals.append({
            "market": "Over 0.5 Goals",
            "prob": round(prob_any_goal, 3),
            "implied_odds": round(1 / prob_any_goal, 2),
            "strength": "STRONG" if prob_any_goal >= 0.82 else ("MODERATE" if prob_any_goal >= 0.72 else "WEAK"),
            "reason": f"{round(prob_any_goal * 100)}% goal prob · {effective_window} mins left",
        })

    # 2. Over 1.5 Goals
    if total_goals <= 1 and 55 <= minute <= 86:
        prob_over_15 = max(0, 1 - p_exact(0) - p_exact(1))
        if prob_over_15 >= 0.38:
            signals.append({
                "market": "Over 1.5 Goals",
                "prob": round(prob_over_15, 3),
                "implied_odds": round(1 / prob_over_15, 2),
                "strength": "STRONG" if prob_over_15 >= 0.58 else ("MODERATE" if prob_over_15 >= 0.45 else "WEAK"),
                "reason": f"{total_goals} goal(s) · model projects {round(prob_over_15 * 100)}% for 2+ more",
            })

    # 3. BTTS Yes
    home_danger = (home_xg / max(minute, 1)) > 0.020
    away_danger = (away_xg / max(minute, 1)) > 0.020
    btts_still_possible = home_goals == 0 or away_goals == 0

    if home_danger and away_danger and score_diff <= 1 and minute >= 52 and prob_btts >= 0.30 and btts_still_possible:
        signals.append({
            "market": "BTTS Yes",
            "prob": round(prob_btts, 3),
            "implied_odds": round(1 / prob_btts, 2),
            "strength": "STRONG" if prob_btts >= 0.50 else ("MODERATE" if prob_btts >= 0.35 else "WEAK"),
            "reason": f"H xG {home_xg:.1f} · A xG {away_xg:.1f} · both teams active",
        })

    # 4. Lay 0-0
    if total_goals == 0 and minute >= 58:
        prob_00 = math.exp(-lt)
        prob_not_nil = 1 - prob_00
        if prob_not_nil >= 0.75:
            signals.append({
                "market": "Lay 0-0 Score",
                "prob": round(prob_not_nil, 3),
                "implied_odds": round(1 / prob_00, 2),
                "strength": "STRONG" if prob_not_nil >= 0.85 else "MODERATE",
                "reason": f"Only {round(prob_00 * 100)}% chance of goalless finish from {minute}'",
            })

    # 5. Next Goal Home / Away
    if minute >= 60 and (prob_home_scores + prob_away_scores) > 0.1:
        total_prob = prob_home_scores + prob_away_scores
        h_next = prob_home_scores / total_prob
        a_next = prob_away_scores / total_prob

        if h_next >= 0.65 and prob_any_goal >= 0.45:
            signals.append({
                "market": "Next Goal: Home",
                "prob": round(h_next, 3),
                "implied_odds": round(1 / h_next, 2),
                "strength": "STRONG" if h_next >= 0.75 else "MODERATE",
                "reason": f"H lambda {lambda_home:.3f} vs A lambda {lambda_away:.3f}",
            })
        elif a_next >= 0.65 and prob_any_goal >= 0.45:
            signals.append({
                "market": "Next Goal: Away",
                "prob": round(a_next, 3),
                "implied_odds": round(1 / a_next, 2),
                "strength": "STRONG" if a_next >= 0.75 else "MODERATE",
                "reason": f"A lambda {lambda_away:.3f} vs H lambda {lambda_home:.3f}",
            })

    order = {"STRONG": 0, "MODERATE": 1, "WEAK": 2}
    signals.sort(key=lambda s: (order[s["strength"]], -s["prob"]))
    return signals


def calculate(d: dict) -> dict:
    """
    d keys: minute, home_goals, away_goals, home_xg, away_xg, home_xgot, away_xgot,
            home_shots_in_box, away_shots_in_box, home_touches_in_box, away_touches_in_box,
            home_big_chances, away_big_chances, home_gk_saves, away_gk_saves, red_cards
    """
    minute = d.get("minute", 0)
    if not minute or minute <= 0:
        return _empty()

    home_goals = d.get("home_goals", 0)
    away_goals = d.get("away_goals", 0)
    score_diff = abs(home_goals - away_goals)
    total_goals = home_goals + away_goals

    remaining_minutes = max(95 - minute, 1)
    effective_window = min(15, remaining_minutes)

    home_xg           = d.get("home_xg", 0)
    away_xg           = d.get("away_xg", 0)
    home_xgot         = d.get("home_xgot", 0)
    away_xgot         = d.get("away_xgot", 0)
    home_shots_in_box = d.get("home_shots_in_box", 0)
    away_shots_in_box = d.get("away_shots_in_box", 0)
    home_touches      = d.get("home_touches_in_box", 0)
    away_touches      = d.get("away_touches_in_box", 0)
    home_big_chances  = d.get("home_big_chances", 0)
    away_big_chances  = d.get("away_big_chances", 0)
    home_gk_saves     = d.get("home_gk_saves", 0)
    away_gk_saves     = d.get("away_gk_saves", 0)
    red_cards         = d.get("red_cards", 0)

    lambda_home = compute_team_lambda(
        xg=home_xg, xgot=home_xgot,
        shots_in_box=home_shots_in_box, touches_in_box=home_touches,
        big_chances=home_big_chances,
        gk_saves=away_gk_saves,  # away keeper stops home attacks
        goals=home_goals, minute=minute
    )
    lambda_away = compute_team_lambda(
        xg=away_xg, xgot=away_xgot,
        shots_in_box=away_shots_in_box, touches_in_box=away_touches,
        big_chances=away_big_chances,
        gk_saves=home_gk_saves,  # home keeper stops away attacks
        goals=away_goals, minute=minute
    )

    # Time urgency multiplier
    if minute >= 90:
        time_mult = 1.45
    elif minute >= 85:
        time_mult = 1.28
    elif minute >= 80:
        time_mult = 1.14
    elif minute >= 75:
        time_mult = 1.07
    else:
        time_mult = 1.0

    # Score state multipliers
    home_trailing = home_goals < away_goals
    away_trailing = away_goals < home_goals

    if score_diff == 0:
        h_score_mult = a_score_mult = 1.08
    elif score_diff == 1:
        h_score_mult = 1.12 if home_trailing else 0.92
        a_score_mult = 1.12 if away_trailing else 0.92
    elif score_diff == 2:
        h_score_mult = 1.18 if home_trailing else 0.70
        a_score_mult = 1.18 if away_trailing else 0.70
    else:
        h_score_mult = 1.15 if home_trailing else 0.52
        a_score_mult = 1.15 if away_trailing else 0.52

    red_mult = 1.18 if red_cards > 0 else 1.0

    lambda_home *= time_mult * h_score_mult * red_mult
    lambda_away *= time_mult * a_score_mult * red_mult
    lambda_total = lambda_home + lambda_away

    prob_any_goal    = 1 - math.exp(-lambda_total * effective_window)
    prob_home_scores = 1 - math.exp(-lambda_home  * effective_window)
    prob_away_scores = 1 - math.exp(-lambda_away  * effective_window)
    prob_btts        = prob_home_scores * prob_away_scores

    score = min(max(prob_any_goal * 10, 0), 10)

    market_signals = compute_market_signals(
        minute=minute, score_diff=score_diff, total_goals=total_goals,
        home_goals=home_goals, away_goals=away_goals,
        prob_any_goal=prob_any_goal, prob_home_scores=prob_home_scores,
        prob_away_scores=prob_away_scores, prob_btts=prob_btts,
        lambda_total=lambda_total, lambda_home=lambda_home, lambda_away=lambda_away,
        effective_window=effective_window, home_xg=home_xg, away_xg=away_xg
    )

    return {
        "score":            round(score, 2),
        "prob":             round(prob_any_goal, 3),
        "lambda_total":     round(lambda_total, 4),
        "lambda_home":      round(lambda_home, 4),
        "lambda_away":      round(lambda_away, 4),
        "prob_home_scores": round(prob_home_scores, 3),
        "prob_away_scores": round(prob_away_scores, 3),
        "prob_btts":        round(prob_btts, 3),
        "effective_window": effective_window,
        "market_signals":   market_signals,
    }


def _empty():
    return {
        "score": 0, "prob": 0, "lambda_total": 0,
        "lambda_home": 0, "lambda_away": 0,
        "prob_home_scores": 0, "prob_away_scores": 0,
        "prob_btts": 0, "effective_window": 0,
        "market_signals": [],
    }
