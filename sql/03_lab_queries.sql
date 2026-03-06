-- =============================================================================
-- Summit 2026 Interactive Lab: Arcade Scores Streaming
-- Lab Query Workbook
--
-- WAREHOUSE
-- ───────────────────────────────────────────────────────────────────────────
-- All lab queries use SUMMIT_INT_WH  (Interactive Warehouse, XS)
-- Use SUMMIT_TRAD_WH (standard) only for admin/metadata queries at the end.
--
-- Interactive Warehouse rules:
--   • SELECT timeout = 5 seconds (add WHERE clauses – it's by design!)
--   • Can ONLY query Interactive Tables (ARCADE_SCORES)
--   • Does NOT auto-suspend; cache stays warm for instant responses
-- =============================================================================

USE WAREHOUSE SUMMIT_INT_WH;
USE DATABASE  ARCADE_DB;
USE SCHEMA    PUBLIC;


-- =============================================================================
-- EXERCISE 1  How fresh is the data?  (run repeatedly while the streamer runs)
-- =============================================================================

-- 1a. Total rows in the interactive table
SELECT COUNT(*) AS TOTAL_SCORES FROM ARCADE_SCORES;

-- 1b. Rows generated in the last 60 seconds
SELECT
    COUNT(*)                                AS ROWS_LAST_60_SEC,
    ROUND(COUNT(*) / 60.0, 1)              AS ROWS_PER_SECOND,
    COUNT(DISTINCT PLAYER_ID)              AS ACTIVE_PLAYERS
FROM ARCADE_SCORES
WHERE GAME_ENDED_AT >= DATEADD('second', -60, CURRENT_TIMESTAMP());

-- 1c. Ingest throughput by 10-second bucket (last 3 minutes)
SELECT
    DATEADD('second',
        FLOOR(DATEDIFF('second', '2000-01-01'::TIMESTAMP_NTZ, GAME_ENDED_AT) / 10) * 10,
        '2000-01-01'::TIMESTAMP_NTZ)        AS TIME_BUCKET,
    COUNT(*)                                AS SCORES
FROM ARCADE_SCORES
WHERE GAME_ENDED_AT >= DATEADD('minute', -3, CURRENT_TIMESTAMP())
GROUP BY TIME_BUCKET
ORDER BY TIME_BUCKET DESC
LIMIT 18;


-- =============================================================================
-- EXERCISE 2  Data freshness  (how recent is the latest row?)
--
-- GAME_ENDED_AT = when the score was generated and sent (client UTC time).
-- Freshness     = how many seconds ago was the most recent row committed.
--
-- CONVERT_TIMEZONE ensures the comparison is UTC on both sides regardless
-- of your Snowsight session timezone.
-- =============================================================================

SELECT
    MAX(GAME_ENDED_AT)                                                    AS LATEST_GAME_ENDED,
    DATEDIFF(
        'millisecond',
        MAX(GAME_ENDED_AT),
        CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP())::TIMESTAMP_NTZ
    ) / 1000.0                                                            AS FRESHNESS_SEC
FROM ARCADE_SCORES
WHERE GAME_ENDED_AT >= DATEADD('minute', -5,
          CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP())::TIMESTAMP_NTZ);


-- =============================================================================
-- EXERCISE 3  Global leaderboard  (last 24 hours)
--
-- CLUSTER BY (GAME_ENDED_AT) lets the Interactive Warehouse skip partitions
-- outside the 24-hour window – sub-second response even at large scale.
-- =============================================================================

SELECT
    RANK() OVER (ORDER BY SCORE DESC)       AS RANK,
    PLAYER_NAME,
    PLAYER_COUNTRY,
    PLAYER_CITY,
    GAME_NAME,
    TO_CHAR(SCORE, '999,999,999')           AS SCORE,
    LEVEL_REACHED,
    PLATFORM,
    COALESCE(ACHIEVEMENT, '—')              AS ACHIEVEMENT,
    GAME_ENDED_AT
FROM ARCADE_SCORES
WHERE GAME_ENDED_AT >= DATEADD('hour', -24, CURRENT_TIMESTAMP())
ORDER BY SCORE DESC
LIMIT 20;


-- =============================================================================
-- EXERCISE 4  Per-game leaderboard – top 5 per game  (last hour)
-- =============================================================================

SELECT
    GAME_NAME,
    ROW_NUMBER() OVER (
        PARTITION BY GAME_NAME ORDER BY SCORE DESC
    )                                       AS POSITION,
    PLAYER_NAME,
    PLAYER_COUNTRY,
    TO_CHAR(SCORE, '999,999,999')           AS SCORE,
    LEVEL_REACHED,
    GAME_MODE
FROM ARCADE_SCORES
WHERE GAME_ENDED_AT >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY GAME_NAME ORDER BY SCORE DESC
) <= 5
ORDER BY GAME_NAME, POSITION;


-- =============================================================================
-- EXERCISE 5  Country heat map  (last hour)
--
-- Japan and South Korea should lead – the data generator weights cities by
-- real gaming culture.  Notice how USA accumulates across many cities.
-- =============================================================================

SELECT
    PLAYER_COUNTRY,
    COUNT(*)                                AS GAMES_PLAYED,
    ROUND(AVG(SCORE))                       AS AVG_SCORE,
    MAX(SCORE)                              AS HIGH_SCORE,
    COUNT(DISTINCT PLAYER_ID)              AS UNIQUE_PLAYERS
FROM ARCADE_SCORES
WHERE GAME_ENDED_AT >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
GROUP BY PLAYER_COUNTRY
ORDER BY GAMES_PLAYED DESC
LIMIT 20;


-- =============================================================================
-- EXERCISE 6  Game popularity and performance stats  (last hour)
--
-- Pac-Man and Tetris should dominate (~5× more sessions than Joust/Tron).
-- =============================================================================

SELECT
    GAME_NAME,
    COUNT(*)                                        AS SESSIONS,
    COUNT(DISTINCT PLAYER_ID)                       AS UNIQUE_PLAYERS,
    TO_CHAR(ROUND(AVG(SCORE)), '999,999,999')       AS AVG_SCORE,
    TO_CHAR(MAX(SCORE),        '999,999,999')       AS HIGH_SCORE,
    ROUND(AVG(LEVEL_REACHED), 1)                    AS AVG_LEVEL,
    ROUND(AVG(DURATION_SECONDS) / 60.0, 1)          AS AVG_GAME_MIN
FROM ARCADE_SCORES
WHERE GAME_ENDED_AT >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
GROUP BY GAME_NAME
ORDER BY SESSIONS DESC;


-- =============================================================================
-- EXERCISE 7  Platform breakdown  (last hour)
-- =============================================================================

SELECT
    PLATFORM,
    COUNT(*)                                AS SESSIONS,
    ROUND(AVG(SCORE))                       AS AVG_SCORE,
    ROUND(AVG(ACCURACY_PCT), 1)             AS AVG_ACCURACY_PCT,
    COUNT(DISTINCT PLAYER_ID)              AS UNIQUE_PLAYERS
FROM ARCADE_SCORES
WHERE GAME_ENDED_AT >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
GROUP BY PLATFORM
ORDER BY SESSIONS DESC;


-- =============================================================================
-- EXERCISE 8  Live score feed – last 30 scores  (keep re-running!)
--
-- The CLUSTER BY clustering key makes this top-N time-range query skip
-- almost all stored data, returning in under a second.
-- =============================================================================

SELECT
    PLAYER_NAME,
    PLAYER_CITY,
    PLAYER_COUNTRY,
    GAME_NAME,
    TO_CHAR(SCORE, '999,999,999')           AS SCORE,
    LEVEL_REACHED,
    PLATFORM,
    COALESCE(ACHIEVEMENT, '—')              AS ACHIEVEMENT,
    GAME_ENDED_AT
FROM ARCADE_SCORES
WHERE GAME_ENDED_AT >= DATEADD('minute', -5, CURRENT_TIMESTAMP())
ORDER BY GAME_ENDED_AT DESC
LIMIT 30;


-- =============================================================================
-- EXERCISE 9  Achievement hunters – rarest badges  (last hour)
-- =============================================================================

SELECT
    ACHIEVEMENT,
    COUNT(*)                                AS TIMES_EARNED,
    COUNT(DISTINCT PLAYER_ID)              AS UNIQUE_EARNERS,
    ROUND(AVG(SCORE))                       AS AVG_SCORE_WHEN_EARNED,
    ROUND(AVG(LEVEL_REACHED), 1)            AS AVG_LEVEL
FROM ARCADE_SCORES
WHERE ACHIEVEMENT IS NOT NULL
  AND GAME_ENDED_AT >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
GROUP BY ACHIEVEMENT
ORDER BY TIMES_EARNED ASC;


-- =============================================================================
-- EXERCISE 10  Interactive Warehouse speed demo
--
-- Run Step A, then Step B.  Open Query History in Snowsight to compare
-- execution times – the interactive warehouse wins at high concurrency.
-- =============================================================================

-- Step A: Interactive Warehouse (sub-second – optimised index + warm cache)
USE WAREHOUSE SUMMIT_INT_WH;

SELECT
    PLAYER_COUNTRY,
    COUNT(*)    AS SESSIONS,
    MAX(SCORE)  AS HIGH_SCORE
FROM ARCADE_SCORES
WHERE GAME_ENDED_AT >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
GROUP BY PLAYER_COUNTRY
ORDER BY SESSIONS DESC;

-- Step B: Standard Warehouse (same query, no index acceleration)
USE WAREHOUSE SUMMIT_TRAD_WH;

SELECT
    PLAYER_COUNTRY,
    COUNT(*)    AS SESSIONS,
    MAX(SCORE)  AS HIGH_SCORE
FROM ARCADE_SCORES
WHERE GAME_ENDED_AT >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
GROUP BY PLAYER_COUNTRY
ORDER BY SESSIONS DESC;

-- Switch back
USE WAREHOUSE SUMMIT_INT_WH;


-- =============================================================================
-- EXERCISE 11  Concurrency demo (JMeter load test)
--
-- Use the JMeter test plan in jmeter/concurrency_test.jmx to simulate
-- 50 concurrent users. Compare results between SUMMIT_INT_WH and SUMMIT_TRAD_WH.
--
-- See README.md for JMeter installation and usage instructions.
--
-- Quick start (from the jmeter/ directory):
--   bash run_concurrency_test.sh SUMMIT_INT_WH
--
-- Then run again with SUMMIT_TRAD_WH to compare.
-- =============================================================================

-- Sample query used by the JMeter test (run manually for reference):
SELECT
    GAME_NAME,
    COUNT(*)            AS SESSIONS,
    MAX(SCORE)          AS HIGH_SCORE,
    ROUND(AVG(SCORE))   AS AVG_SCORE
FROM ARCADE_SCORES
WHERE GAME_ENDED_AT >= DATEADD('minute', -30, CURRENT_TIMESTAMP())
GROUP BY GAME_NAME
ORDER BY HIGH_SCORE DESC;


-- =============================================================================
-- BONUS A  Time Travel on an Interactive Table
-- =============================================================================

-- Row count 5 minutes ago
SELECT COUNT(*) AS ROWS_5_MIN_AGO
FROM ARCADE_SCORES AT(OFFSET => -300);

-- How many rows were generated in the last 5 minutes?
SELECT COUNT(*) AS NEW_ROWS_LAST_5_MIN
FROM ARCADE_SCORES
WHERE GAME_ENDED_AT >= DATEADD('minute', -5, CURRENT_TIMESTAMP());


-- =============================================================================
-- BONUS B  Rolling 1-minute hotspot – most active cities right now
-- =============================================================================

SELECT
    PLAYER_CITY,
    PLAYER_COUNTRY,
    COUNT(*) AS GAMES_LAST_MINUTE
FROM ARCADE_SCORES
WHERE GAME_ENDED_AT >= DATEADD('minute', -1, CURRENT_TIMESTAMP())
GROUP BY PLAYER_CITY, PLAYER_COUNTRY
ORDER BY GAMES_LAST_MINUTE DESC
LIMIT 15;


-- =============================================================================
-- BONUS C  Inspect the Interactive Table metadata
--          (run as ACCOUNTADMIN or with a standard warehouse)
-- =============================================================================
USE WAREHOUSE SUMMIT_TRAD_WH;
USE ROLE ACCOUNTADMIN;

SHOW INTERACTIVE TABLES IN SCHEMA ARCADE_DB.PUBLIC;

-- Clustering depth (lower = better-clustered for time-range queries)
SELECT SYSTEM$CLUSTERING_INFORMATION('ARCADE_DB.PUBLIC.ARCADE_SCORES', '(GAME_ENDED_AT)');
