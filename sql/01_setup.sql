-- =============================================================================
-- Summit 2026 Interactive Lab: Arcade Scores Streaming
-- Setup Script: Snowflake Objects
--
-- Pipeline:
--   Python generator
--     → Snowpipe Streaming SDK (channels)
--       → ARCADE_SCORES  (Interactive Table, directly populated)
--         → SUMMIT_LAB_WH  (Interactive Warehouse, XS, always-on)
--
-- Snowpipe Streaming uses the channel API, not SQL DML, so it writes
-- directly into an Interactive Table without any intermediate landing table.
--
-- IMPORTANT: CREATE INTERACTIVE TABLE requires a STANDARD warehouse session.
--            Run this script with SUMMIT_SETUP_WH (created in Step 2).
-- =============================================================================


-- ---------------------------------------------------------------------------
-- Step 1: Create lab role and service user for Snowpipe Streaming
--         Run as ACCOUNTADMIN or USERADMIN
-- ---------------------------------------------------------------------------
USE ROLE ACCOUNTADMIN;

CREATE ROLE IF NOT EXISTS ARCADE_STREAMING_ROLE;
CREATE USER IF NOT EXISTS ARCADE_STREAMING_USER
    DEFAULT_ROLE = ARCADE_STREAMING_ROLE
    COMMENT      = 'Service user for Summit26 Snowpipe Streaming lab';

GRANT ROLE ARCADE_STREAMING_ROLE TO USER ARCADE_STREAMING_USER;

-- RSA key-pair authentication (see README for key-generation commands).
-- Paste the output of the PUBK shell variable here before running.
-- ALTER USER ARCADE_STREAMING_USER SET RSA_PUBLIC_KEY='<YOUR_PUBLIC_KEY_HERE>';

CREATE DATABASE IF NOT EXISTS ARCADE_DB
    COMMENT = 'Summit 2026 Interactive Lab – Arcade Streaming Data';
USE DATABASE ARCADE_DB;

CREATE AUTHENTICATION POLICY IF NOT EXISTS ARCADE_KEYPAIR_POLICY
    AUTHENTICATION_METHODS = ('KEYPAIR')
    MFA_ENROLLMENT         = 'OPTIONAL'
    CLIENT_TYPES           = ('DRIVERS');

ALTER USER ARCADE_STREAMING_USER
    SET AUTHENTICATION POLICY ARCADE_KEYPAIR_POLICY;


-- ---------------------------------------------------------------------------
-- Step 2: Schema and standard setup warehouse
--
--  SUMMIT_SETUP_WH is a STANDARD warehouse used only for setup tasks.
--  Snowpipe Streaming does NOT consume warehouse credits.
--  Lab queries use the Interactive Warehouse (SUMMIT_LAB_WH) exclusively.
-- ---------------------------------------------------------------------------
USE ROLE ACCOUNTADMIN;

CREATE SCHEMA IF NOT EXISTS ARCADE_DB.PUBLIC;

CREATE WAREHOUSE IF NOT EXISTS SUMMIT_SETUP_WH
    WAREHOUSE_SIZE      = XSMALL
    AUTO_SUSPEND        = 60
    AUTO_RESUME         = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Standard warehouse for setup tasks only (not used for lab queries)';

USE WAREHOUSE SUMMIT_SETUP_WH;
USE DATABASE ARCADE_DB;
USE SCHEMA PUBLIC;


-- ---------------------------------------------------------------------------
-- Step 3: Interactive Table  (Snowpipe Streaming writes directly here)
--
--  CREATE INTERACTIVE TABLE uses CTAS syntax with WHERE FALSE to define
--  the schema of an initially empty table.  Snowpipe Streaming SDK
--  channels then append rows directly into this table – no intermediate
--  landing table is required.
--
--  CLUSTER BY (GAME_ENDED_AT)
--    Aligns with the WHERE GAME_ENDED_AT >= DATEADD(...) predicates in
--    every lab query.  The Interactive Warehouse skips irrelevant
--    micro-partitions and returns results in milliseconds.
--
--  NOTE: No TARGET_LAG or WAREHOUSE clause needed here – those are only
--        required when refreshing from another table.
-- ---------------------------------------------------------------------------
CREATE INTERACTIVE TABLE IF NOT EXISTS ARCADE_DB.PUBLIC.ARCADE_SCORES
    CLUSTER BY (GAME_ENDED_AT)
    COMMENT = 'Interactive Table – arcade scores, populated via Snowpipe Streaming'
AS
SELECT
    NULL::VARCHAR(36)    AS SCORE_ID,
    NULL::VARCHAR(36)    AS PLAYER_ID,
    NULL::VARCHAR(64)    AS PLAYER_NAME,
    NULL::VARCHAR(64)    AS PLAYER_COUNTRY,
    NULL::VARCHAR(64)    AS PLAYER_CITY,
    NULL::FLOAT          AS LATITUDE,
    NULL::FLOAT          AS LONGITUDE,
    NULL::VARCHAR(64)    AS GAME_NAME,
    NULL::VARCHAR(32)    AS GAME_MODE,
    NULL::VARCHAR(32)    AS PLATFORM,
    NULL::NUMBER(12, 0)  AS SCORE,
    NULL::NUMBER(4, 0)   AS LEVEL_REACHED,
    NULL::NUMBER(6, 0)   AS DURATION_SECONDS,
    NULL::NUMBER(2, 0)   AS LIVES_REMAINING,
    NULL::FLOAT          AS ACCURACY_PCT,
    NULL::VARCHAR(64)    AS ACHIEVEMENT,
    NULL::TIMESTAMP_NTZ  AS GAME_ENDED_AT,   -- when the game session ended (client)
    NULL::TIMESTAMP_NTZ  AS INGEST_AT        -- when the row was submitted to the SDK
FROM (SELECT 1) src
WHERE FALSE;


-- ---------------------------------------------------------------------------
-- Step 4: Interactive Warehouse  (the query engine)
--
--  Key behaviours of Interactive Warehouses:
--    • Optimised for low-latency, high-concurrency workloads
--    • Leverages ARCADE_SCORES clustering metadata and local SSD cache
--    • SELECT timeout = 5 seconds (cannot be increased – design limit)
--    • Does NOT auto-suspend; always-on for instant first-query response
--    • Can ONLY query Interactive Tables
--    • Minimum billing: 1 hour; per-second thereafter
-- ---------------------------------------------------------------------------
USE ROLE ACCOUNTADMIN;

CREATE OR REPLACE INTERACTIVE WAREHOUSE SUMMIT_LAB_WH
    TABLES = (ARCADE_DB.PUBLIC.ARCADE_SCORES)
    WAREHOUSE_SIZE = 'XSMALL'
    COMMENT = 'XS Interactive Warehouse – Summit 2026 lab queries';

-- Interactive warehouses start SUSPENDED; resume to begin cache warming.
ALTER WAREHOUSE SUMMIT_LAB_WH RESUME;


-- ---------------------------------------------------------------------------
-- Step 5: Privileges
-- ---------------------------------------------------------------------------
USE ROLE ACCOUNTADMIN;

-- Streaming role: insert into the interactive table + operate the default pipe
-- Default pipe is auto-created as "ARCADE_SCORES-STREAMING" on first SDK call
GRANT USAGE  ON DATABASE  ARCADE_DB                          TO ROLE ARCADE_STREAMING_ROLE;
GRANT USAGE  ON SCHEMA    ARCADE_DB.PUBLIC                   TO ROLE ARCADE_STREAMING_ROLE;
GRANT INSERT, SELECT
    ON TABLE ARCADE_DB.PUBLIC.ARCADE_SCORES                  TO ROLE ARCADE_STREAMING_ROLE;
GRANT OPERATE, MONITOR
    ON PIPE ARCADE_DB.PUBLIC."ARCADE_SCORES-STREAMING"       TO ROLE ARCADE_STREAMING_ROLE;

-- Lab attendee read role: query ARCADE_SCORES via the interactive warehouse
CREATE ROLE IF NOT EXISTS ARCADE_LAB_READER;

GRANT USAGE  ON DATABASE  ARCADE_DB                          TO ROLE ARCADE_LAB_READER;
GRANT USAGE  ON SCHEMA    ARCADE_DB.PUBLIC                   TO ROLE ARCADE_LAB_READER;
GRANT SELECT ON TABLE     ARCADE_DB.PUBLIC.ARCADE_SCORES     TO ROLE ARCADE_LAB_READER;
GRANT USAGE  ON WAREHOUSE SUMMIT_LAB_WH                      TO ROLE ARCADE_LAB_READER;
GRANT USAGE  ON WAREHOUSE SUMMIT_SETUP_WH                    TO ROLE ARCADE_LAB_READER;

GRANT ROLE ARCADE_LAB_READER TO ROLE SYSADMIN;


-- ---------------------------------------------------------------------------
-- Verification
-- ---------------------------------------------------------------------------
SHOW INTERACTIVE TABLES IN SCHEMA ARCADE_DB.PUBLIC;
SHOW WAREHOUSES LIKE 'SUMMIT%';
SHOW PIPES IN SCHEMA ARCADE_DB.PUBLIC;

SELECT 'Setup complete – start the Python streamer, then wait ~2 min for cache warm-up.' AS STATUS;
