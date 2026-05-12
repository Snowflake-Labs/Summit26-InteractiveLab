-- =============================================================================
-- Summit 2026 Interactive Lab: Arcade Scores Streaming
-- Cleanup / Teardown Script
--
-- WARNING: Irreversible – all data will be dropped.
-- =============================================================================

USE ROLE ACCOUNTADMIN;
USE DATABASE ARCADE_DB;
USE SCHEMA PUBLIC;

-- Streamlit dashboard
DROP STREAMLIT IF EXISTS ARCADE_DB.PUBLIC.ARCADE_SCORES_DASHBOARD;

-- Compute pool
DROP COMPUTE POOL IF EXISTS ARCADE_REPORTING_POOL;

-- Drop the interactive warehouse first (removes its ARCADE_SCORES association)
ALTER WAREHOUSE IF EXISTS SUMMIT_INT_WH SUSPEND;
DROP WAREHOUSE   IF EXISTS SUMMIT_INT_WH;

-- Standard setup warehouse
DROP WAREHOUSE IF EXISTS SUMMIT_TRAD_WH;

-- User
DROP USER IF EXISTS ARCADE_STREAMING_USER;

set uu = 'ALTER USER ' || CURRENT_USER() || ' UNSET AUTHENTICATION POLICY';
EXECUTE IMMEDIATE $uu;

DROP AUTHENTICATION POLICY pat_bypass_policy;

-- Database (cascades to schema, interactive table, and pipes)
DROP DATABASE IF EXISTS ARCADE_DB;

-- Roles
DROP ROLE IF EXISTS ARCADE_STREAMING_ROLE;
DROP ROLE IF EXISTS ARCADE_LAB_READER;

-- PAT token
BEGIN
    ALTER USER REMOVE PROGRAMMATIC ACCESS TOKEN SNOW_CLI_PAT;
EXCEPTION
    WHEN OTHER THEN NULL;
END;

SELECT 'Cleanup complete.' AS STATUS;
