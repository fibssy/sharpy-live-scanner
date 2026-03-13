-- 001_initial.sql — Live alerts tracking table

CREATE TABLE IF NOT EXISTS live_alerts (
    id           SERIAL PRIMARY KEY,
    event_id     BIGINT      NOT NULL,
    home_team    TEXT        NOT NULL,
    away_team    TEXT        NOT NULL,
    league       TEXT        NOT NULL,
    minute       INT         NOT NULL,
    home_goals   INT         DEFAULT 0,
    away_goals   INT         DEFAULT 0,
    score        NUMERIC(4,2),
    market       TEXT        NOT NULL,
    prob         NUMERIC(5,3),
    implied_odds NUMERIC(6,2),
    strength     TEXT,
    signal_reason TEXT,
    verdict      TEXT,
    alerted_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_live_alerts_event_market
    ON live_alerts (event_id, market, alerted_at DESC);

-- Summary view
CREATE OR REPLACE VIEW live_alerts_summary AS
SELECT
    league,
    market,
    strength,
    COUNT(*)                          AS total_alerts,
    ROUND(AVG(prob) * 100, 1)         AS avg_prob_pct,
    ROUND(AVG(score), 2)              AS avg_model_score,
    MIN(alerted_at)::DATE             AS first_alert,
    MAX(alerted_at)::DATE             AS last_alert
FROM live_alerts
GROUP BY league, market, strength
ORDER BY total_alerts DESC;
